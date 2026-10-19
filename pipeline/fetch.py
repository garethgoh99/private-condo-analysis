"""Fetch the four URA private-residential data services as raw JSON.

Writes to data/raw/:
  transactions_batch{1..4}.json   PMI_Resi_Transaction   (past 5 yrs, by postal-district batch)
  rental_median.json              PMI_Resi_Rental_Median (past 3 yrs, non-landed, by project)
  dev_sales_YYYYMM.json           PMI_Resi_Developer_Sales (one per refPeriod month, past ~3 yrs)
  pipeline.json                   PMI_Resi_Pipeline      (latest quarter only)
  manifest.json                   what was fetched, row counts, timestamp

Needs URA_ACCESS_KEY. Never prints the token.
"""
import datetime as dt
import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(__file__))
from ura_token import HEADERS_BASE, get_token  # noqa: E402

BASE = "https://eservice.ura.gov.sg/uraDataService/invokeUraDS/v1"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
DEV_SALES_MONTHS_BACK = 40  # a little over the documented 3 yrs, to see where coverage actually ends


def call(session, params, retries=4):
    last = None
    for attempt in range(retries):
        try:
            r = session.get(BASE, params=params, timeout=180)
            if "json" not in r.headers.get("content-type", "").lower():
                raise RuntimeError(f"HTTP {r.status_code}, non-JSON: {r.text[:200]!r}")
            body = r.json()
            if body.get("Status") != "Success":
                raise RuntimeError(f"Status={body.get('Status')!r} Message={body.get('Message')!r}")
            return body.get("Result") or []
        except Exception as e:  # noqa: BLE001
            last = e
            wait = 5 * (attempt + 1)
            print(f"  {params} attempt {attempt + 1} failed: {e}; retrying in {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"Giving up on {params}: {last}")


def save(name, obj):
    with open(os.path.join(OUT, name), "w") as f:
        json.dump(obj, f, separators=(",", ":"))


def main():
    os.makedirs(OUT, exist_ok=True)
    key = os.environ["URA_ACCESS_KEY"].strip()
    s = requests.Session()
    s.headers.update({**HEADERS_BASE, "AccessKey": key, "Token": get_token(key)})
    manifest = {"fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(), "files": {}}

    for b in (1, 2, 3, 4):
        res = call(s, {"service": "PMI_Resi_Transaction", "batch": b})
        n_tx = sum(len(p.get("transaction", [])) for p in res)
        save(f"transactions_batch{b}.json", res)
        manifest["files"][f"transactions_batch{b}.json"] = {"projects": len(res), "transactions": n_tx}
        print(f"transactions batch {b}: {len(res)} projects, {n_tx} transactions")

    res = call(s, {"service": "PMI_Resi_Rental_Median"})
    save("rental_median.json", res)
    manifest["files"]["rental_median.json"] = {
        "projects": len(res), "rows": sum(len(p.get("rentalMedian", [])) for p in res)}
    print(f"rental median: {len(res)} projects")

    today = dt.date.today()
    y, m = today.year, today.month
    for _ in range(DEV_SALES_MONTHS_BACK):
        ref = f"{m:02d}{y % 100:02d}"
        try:
            res = call(s, {"service": "PMI_Resi_Developer_Sales", "refPeriod": ref}, retries=2)
        except RuntimeError as e:
            res = None
            manifest["files"][f"dev_sales_{y}{m:02d}.json"] = {"error": str(e)[:300]}
            print(f"dev sales {ref}: ERROR {e}")
        if res is not None:
            save(f"dev_sales_{y}{m:02d}.json", res)
            manifest["files"][f"dev_sales_{y}{m:02d}.json"] = {"refPeriod": ref, "projects": len(res)}
            print(f"dev sales {ref}: {len(res)} projects")
        m -= 1
        if m == 0:
            y, m = y - 1, 12

    res = call(s, {"service": "PMI_Resi_Pipeline"})
    save("pipeline.json", res)
    manifest["files"]["pipeline.json"] = {"projects": len(res)}
    print(f"pipeline: {len(res)} projects")

    save("manifest.json", manifest)
    tx_total = sum(v.get("transactions", 0) for k, v in manifest["files"].items() if k.startswith("transactions"))
    if tx_total < 1000:
        raise SystemExit(f"Only {tx_total} transactions fetched - refusing to treat this as a good pull.")


if __name__ == "__main__":
    main()
