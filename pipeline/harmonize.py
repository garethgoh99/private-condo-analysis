"""Turn the raw archive (STORE/archive/*.csv.gz) into clean, typed tables.

load_clean(store) -> (tx, projects)

tx: one row per URA caveat, with
    month 'YYYY-MM', year, q (1-4), mi (months since 1990-01)
    pkey 'PROJECT|STREET', project, street, district 'NN', segment CCR/RCR/OCR
    ptype (URA propertyType), sale 1 new / 2 sub / 3 resale
    area_sqm, area_type Land/Strata, floor (URA floorRange, '-' for landed)
    price      effective price: nettPrice where URA gives one (developer discounts), else price
    units      noOfUnits (>1 = bulk/en-bloc caveat; price and area are then lot totals)
    tenure_kind FH (freehold) / 999 (leases of 900+ yrs) / LH (other leasehold)
    lease_years, lease_start (start may be borrowed from the project's other rows; NaN if unknown)
    rem_lease  remaining lease in years at the transaction month (LH and 999 only)
    psf        price / (area_sqm * 10.7639)

projects: one row per pkey with location (lat/lon + SVY21 x/y) and where it came from.

Run directly to write build/tx_clean.csv.gz + build/projects.csv for inspection.
"""
import json
import os
import re
import sys

import numpy as np
import pandas as pd

SQM_TO_SQFT = 10.7639
GENERIC = {"LANDED HOUSING DEVELOPMENT", "RESIDENTIAL APARTMENTS", "N.A.", "NA", "-"}


def norm_name(s):
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9@& ]", " ", str(s).upper())).strip()


def parse_tenure(t):
    t = str(t).strip()
    if t.lower() == "freehold":
        return "FH", np.nan, np.nan
    m = re.match(r"^(\d+)\s*(?:yrs|years?)", t, re.I)
    if not m:
        return "UNK", np.nan, np.nan
    yrs = int(m.group(1))
    s = re.search(r"(?:from|commencing from)\s+(\d{4})", t, re.I) or re.search(r"(\d{2})/(\d{2})/(\d{4})", t)
    start = float(s.group(s.lastindex)) if s else np.nan
    return ("999" if yrs >= 900 else "LH"), float(yrs), start


def load_clean(store):
    a = os.path.join(store, "archive")
    raw = pd.read_csv(os.path.join(a, "transactions.csv.gz"), dtype=str, keep_default_na=False)
    tx = pd.DataFrame({
        "month": raw["month"],
        "project": raw["project"].str.strip().str.upper(),
        "street": raw["street"].str.strip().str.upper(),
        "district": raw["district"].str.strip().str.zfill(2),
        "segment": raw["marketSegment"].str.strip().str.upper(),
        "ptype": raw["propertyType"].str.strip(),
        "sale": pd.to_numeric(raw["typeOfSale"], errors="coerce").astype("Int64"),
        "area_type": raw["typeOfArea"].str.strip(),
        "floor": raw["floorRange"].str.strip().replace({"": "-"}),
        "area_sqm": pd.to_numeric(raw["area"], errors="coerce"),
        "price_gross": pd.to_numeric(raw["price"], errors="coerce"),
        "nett": pd.to_numeric(raw["nettPrice"], errors="coerce"),
        "units": pd.to_numeric(raw["noOfUnits"], errors="coerce").fillna(1).astype(int),
        "tenure_raw": raw["tenure"].str.strip(),
        "x": pd.to_numeric(raw["x"], errors="coerce"),
        "y": pd.to_numeric(raw["y"], errors="coerce"),
    })
    tx["price"] = tx["nett"].where(tx["nett"] > 0, tx["price_gross"])
    tx["year"] = tx["month"].str[:4].astype(int)
    mo = tx["month"].str[5:7].astype(int)
    tx["q"] = (mo - 1) // 3 + 1
    tx["mi"] = (tx["year"] - 1990) * 12 + (mo - 1)
    tx["pkey"] = tx["project"] + "|" + tx["street"]

    ten = tx["tenure_raw"].map(parse_tenure)
    tx["tenure_kind"] = ten.str[0]
    tx["lease_years"] = ten.str[1].astype(float)
    tx["lease_start"] = ten.str[2].astype(float)
    # "99 years leasehold" has no start year: borrow the project's most common start year if it has one
    named = ~tx["project"].isin(GENERIC)
    fill = (tx[named & tx["lease_start"].notna()].groupby(["pkey", "lease_years"])["lease_start"]
            .agg(lambda s: s.mode().iat[0]))
    need = named & tx["lease_start"].isna() & tx["lease_years"].notna()
    idx = pd.MultiIndex.from_arrays([tx.loc[need, "pkey"], tx.loc[need, "lease_years"]])
    tx.loc[need, "lease_start"] = fill.reindex(idx).to_numpy()
    tx["rem_lease"] = (tx["lease_start"] + tx["lease_years"] - (tx["year"] + (mo - 0.5) / 12)).round(1)
    tx.loc[tx["tenure_kind"] == "FH", "rem_lease"] = np.nan

    tx["psf"] = tx["price"] / (tx["area_sqm"] * SQM_TO_SQFT)
    bad = tx["price"].isna() | tx["area_sqm"].isna() | (tx["area_sqm"] <= 0)
    if bad.any():
        print(f"harmonize: dropping {int(bad.sum())} rows with missing price/area")
        tx = tx[~bad]
    tx = tx.drop(columns=["nett"])

    projects = build_projects(store, tx)
    return tx.reset_index(drop=True), projects


def build_projects(store, tx):
    from pyproj import Transformer
    a = os.path.join(store, "archive")
    p = (tx.groupby("pkey").agg(project=("project", "first"), street=("street", "first"),
                                 district=("district", lambda s: s.mode().iat[0]),
                                 segment=("segment", lambda s: s.mode().iat[0]),
                                 x=("x", "median"), y=("y", "median"), n=("price", "size"))
         .reset_index())
    p["loc_src"] = np.where(p["x"].notna(), "ura", "")

    # other URA services sometimes carry coordinates the transactions lack (match on normalised name)
    other = []
    for f in ("rentals.csv.gz", "dev_sales.csv.gz"):
        fp = os.path.join(a, f)
        if os.path.exists(fp):
            d = pd.read_csv(fp, dtype=str, keep_default_na=False)
            d = d[d["x"] != ""]
            other.append(pd.DataFrame({"nn": d["project"].map(norm_name), "x": d["x"].astype(float),
                                       "y": d["y"].astype(float)}))
    if other:
        o = pd.concat(other).groupby("nn")[["x", "y"]].median()
        need = p["x"].isna() & ~p["project"].isin(GENERIC)
        nn = p.loc[need, "project"].map(norm_name)
        hit = nn.isin(o.index)
        ids = nn[hit].index
        p.loc[ids, "x"] = o.loc[nn[hit], "x"].to_numpy()
        p.loc[ids, "y"] = o.loc[nn[hit], "y"].to_numpy()
        p.loc[ids, "loc_src"] = "ura-other"

    cpath = os.path.join(store, "geo", "geocode_cache.json")
    if os.path.exists(cpath):
        cache = json.load(open(cpath))
        need = p["x"].isna()
        for i in p.index[need]:
            c = cache.get(p.at[i, "pkey"])
            if c and c.get("x") is not None:
                p.at[i, "x"], p.at[i, "y"] = c["x"], c["y"]
                p.at[i, "loc_src"] = "onemap-" + c.get("level", "project")

    t = Transformer.from_crs("EPSG:3414", "EPSG:4326", always_xy=True)
    lon, lat = t.transform(p["x"].to_numpy(), p["y"].to_numpy())
    p["lat"], p["lon"] = np.round(lat, 6), np.round(lon, 6)
    p.loc[p["x"].isna(), "loc_src"] = "none"
    return p


if __name__ == "__main__":
    store = sys.argv[1] if len(sys.argv) > 1 else "store"
    tx, projects = load_clean(store)
    os.makedirs("build", exist_ok=True)
    tx.to_csv("build/tx_clean.csv.gz", index=False)
    projects.to_csv("build/projects.csv", index=False)
    print(f"tx {len(tx)} rows, {tx['month'].min()}..{tx['month'].max()}; projects {len(projects)}")
    print("tenure kinds:", tx["tenure_kind"].value_counts().to_dict())
    print("location sources:", projects["loc_src"].value_counts().to_dict())
    w = projects.groupby("loc_src")["n"].sum()
    print("transactions by location source:", w.to_dict())
