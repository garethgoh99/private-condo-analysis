"""Fill in coordinates for projects that URA publishes without x/y (mostly new launches).

Looks each one up via OneMap's public search API and caches the result in
STORE/geo/geocode_cache.json so each project is only looked up once. A result is
accepted only if its postal code falls in the project's own postal district
(postal sector -> district table below), which guards against same-name matches
elsewhere on the island.

Query order: "<project>" -> "<project> <street>" -> "<street>" (street centroid).
Failures are cached too and retried after 30 days.

Usage: python pipeline/geocode.py STORE_DIR
"""
import datetime as dt
import json
import os
import sys
import time

import pandas as pd
import requests

SEARCH = "https://www.onemap.gov.sg/api/common/elastic/search"
GENERIC = {"LANDED HOUSING DEVELOPMENT", "RESIDENTIAL APARTMENTS", "N.A.", "NA", "-"}
RETRY_DAYS = 30

# Postal sector (first 2 digits of a 6-digit postal code) -> postal district.
SECTOR_TO_DISTRICT = {}
for d, sectors in {
    1: "01 02 03 04 05 06", 2: "07 08", 3: "14 15 16", 4: "09 10", 5: "11 12 13", 6: "17",
    7: "18 19", 8: "20 21", 9: "22 23", 10: "24 25 26 27", 11: "28 29 30", 12: "31 32 33",
    13: "34 35 36 37", 14: "38 39 40 41", 15: "42 43 44 45", 16: "46 47 48", 17: "49 50 81",
    18: "51 52", 19: "53 54 55 82", 20: "56 57", 21: "58 59", 22: "60 61 62 63 64",
    23: "65 66 67 68", 24: "69 70 71", 25: "72 73", 26: "77 78", 27: "75 76", 28: "79 80",
}.items():
    for s in sectors.split():
        SECTOR_TO_DISTRICT[s] = f"{d:02d}"


def postal_district(postal):
    postal = str(postal or "").strip()
    return SECTOR_TO_DISTRICT.get(postal[:2]) if len(postal) == 6 and postal.isdigit() else None


def search(session, q):
    r = session.get(SEARCH, params={"searchVal": q, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1},
                    timeout=30)
    r.raise_for_status()
    return r.json().get("results", []) or []


def pick(results, district):
    ok = [x for x in results if postal_district(x.get("POSTAL")) == district]
    if not ok:
        return None
    # centroid of all in-district hits (a big estate has many blocks/postcodes)
    xs = [float(x["X"]) for x in ok]; ys = [float(x["Y"]) for x in ok]
    la = [float(x["LATITUDE"]) for x in ok]; lo = [float(x["LONGITUDE"]) for x in ok]
    return {"x": sum(xs) / len(xs), "y": sum(ys) / len(ys), "lat": sum(la) / len(la), "lon": sum(lo) / len(lo),
            "hits": len(ok), "example": ok[0].get("ADDRESS", "")[:120]}


def needed(store):
    a = os.path.join(store, "archive")
    tx = pd.read_csv(os.path.join(a, "transactions.csv.gz"), dtype=str, keep_default_na=False)
    have = set()
    for f in ("transactions.csv.gz", "rentals.csv.gz", "dev_sales.csv.gz"):
        p = os.path.join(a, f)
        if os.path.exists(p):
            d = pd.read_csv(p, dtype=str, keep_default_na=False)
            have |= set(d.loc[d["x"] != "", "project"].str.upper().str.strip())
    miss = tx[tx["x"] == ""].groupby(["project", "street"])["district"].agg(lambda s: s.mode().iat[0]).reset_index()
    miss = miss[~(miss["project"].str.upper().str.strip().isin(have) & ~miss["project"].isin(GENERIC))]
    return miss


def main(store):
    cpath = os.path.join(store, "geo", "geocode_cache.json")
    os.makedirs(os.path.dirname(cpath), exist_ok=True)
    cache = json.load(open(cpath)) if os.path.exists(cpath) else {}
    today = dt.date.today()
    s = requests.Session(); s.headers["User-Agent"] = "Mozilla/5.0"
    todo = needed(store)
    looked = found = 0
    for r in todo.itertuples(index=False):
        key = f"{r.project}|{r.street}"
        c = cache.get(key)
        if c and (c.get("x") is not None or
                  (today - dt.date.fromisoformat(c["checked"])).days < RETRY_DAYS):
            continue
        generic = r.project in GENERIC
        queries = ([] if generic else [r.project, f"{r.project} {r.street}"]) + [r.street]
        res = None
        for q in queries:
            try:
                hit = pick(search(s, q), r.district)
            except Exception as e:  # noqa: BLE001
                print(f"  search failed for {q!r}: {e}")
                hit = None
            time.sleep(0.25)
            if hit:
                res = {**hit, "query": q, "level": "street" if q == r.street else "project"}
                break
        looked += 1
        cache[key] = {**(res or {"x": None}), "district": r.district, "checked": today.isoformat()}
        if res:
            found += 1
    json.dump(cache, open(cpath, "w"), indent=0, sort_keys=True)
    ok = sum(1 for v in cache.values() if v.get("x") is not None)
    print(f"geocode: {len(todo)} projects lack URA coordinates; looked up {looked} now, found {found}; "
          f"cache has {ok}/{len(cache)} located")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "store")
