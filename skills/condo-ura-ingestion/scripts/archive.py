"""Merge the latest raw URA pull (data/raw/) into the long-term archive (STORE/archive/).

URA only serves rolling windows (5 yrs of transactions, 3 yrs of rentals / developer sales,
latest quarter of pipeline). This archive keeps everything ever pulled, so history keeps
growing past those windows.

Merge rules
-----------
transactions  No unit ID exists, so rows can't be matched one-to-one. Instead, by month:
              * months AFTER the earliest month in the new pull -> replaced wholesale by
                the new pull (URA revises/aborts recent records; latest wins);
              * the earliest month of the new pull (likely only partly inside the 5-yr
                window) -> whichever version has more rows is kept;
              * older months -> kept from the archive untouched.
              Safety: if the new pull has < 80% of the rows the archive holds for the
              same months, the merge aborts (protects against a partial/broken pull).
rentals       upsert on (project, street, refPeriod)
dev_sales     upsert on (project, street, district, refPeriod)
pipeline      appended as a new release when its content differs from the last release

Usage: python pipeline/archive.py STORE_DIR
"""
import datetime as dt
import glob
import gzip
import json
import os
import sys

import pandas as pd

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

TX_COLS = ["month", "project", "street", "marketSegment", "x", "y", "district", "propertyType",
           "typeOfSale", "typeOfArea", "tenure", "floorRange", "area", "price", "nettPrice",
           "noOfUnits", "contractDate", "pulled_on"]


def load_raw(name):
    with open(os.path.join(RAW, f"{name}.json")) as f:
        return json.load(f)


def read_archive(path, cols=None):
    if os.path.exists(path):
        return pd.read_csv(path, dtype=str, keep_default_na=False)
    return pd.DataFrame(columns=cols or [])


def write_archive(df, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wt") as f:
        df.to_csv(f, index=False)


def flatten(projects, child, extra=None):
    rows = []
    for p in projects:
        base = {k: v for k, v in p.items() if k != child}
        for c in p.get(child, []) or []:
            rows.append({**base, **c, **(extra or {})})
    return pd.DataFrame(rows)


def merge_transactions(store, today, log):
    path = os.path.join(store, "archive", "transactions.csv.gz")
    new = pd.concat([flatten(load_raw(f"transactions_batch{b}"), "transaction") for b in (1, 2, 3, 4)],
                    ignore_index=True)
    new["month"] = "20" + new["contractDate"].str[2:4] + "-" + new["contractDate"].str[0:2]
    new["pulled_on"] = today
    for c in TX_COLS:
        if c not in new.columns:
            new[c] = ""
    new = new[TX_COLS].fillna("").astype(str)

    old = read_archive(path, TX_COLS)
    for c in TX_COLS:
        if c not in old.columns:
            old[c] = ""
    old = old[TX_COLS]

    m0 = new["month"].min()
    new_after = new[new["month"] > m0]
    old_after = old[old["month"] > m0]
    if len(old_after) and len(new_after) < 0.8 * len(old_after):
        raise SystemExit(f"New pull has {len(new_after)} rows after {m0} vs {len(old_after)} archived - "
                         "looks partial; archive NOT updated.")
    new_m0, old_m0 = new[new["month"] == m0], old[old["month"] == m0]
    keep_m0 = old_m0 if len(old_m0) > len(new_m0) else new_m0
    merged = pd.concat([old[old["month"] < m0], keep_m0, new_after], ignore_index=True)
    merged = merged.sort_values(["month", "district", "project"], kind="stable")
    write_archive(merged, path)
    log["transactions"] = {"pulled": len(new), "archive_before": len(old), "archive_after": len(merged),
                           "window_start": m0, "kept_older_than_window": int((merged["month"] < m0).sum()),
                           "earliest": merged["month"].min(), "latest": merged["month"].max()}


def upsert(store, fname, new, key, log_key, log):
    path = os.path.join(store, "archive", fname)
    new = new.fillna("").astype(str)
    old = read_archive(path, list(new.columns))
    cols = list(dict.fromkeys(list(old.columns) + list(new.columns)))
    old, new = old.reindex(columns=cols, fill_value=""), new.reindex(columns=cols, fill_value="")
    merged = pd.concat([old, new], ignore_index=True).drop_duplicates(subset=key, keep="last")
    merged = merged.sort_values(key, kind="stable")
    write_archive(merged, path)
    log[log_key] = {"pulled": len(new), "archive_before": len(old), "archive_after": len(merged)}


def merge_pipeline(store, today, log):
    path = os.path.join(store, "archive", "pipeline.csv.gz")
    new = pd.DataFrame(load_raw("pipeline")).fillna("").astype(str)
    old = read_archive(path)
    content_cols = [c for c in new.columns]
    if len(old):
        last = old[old["release"] == old["release"].max()].drop(columns=["release"])
        a = last.reindex(columns=content_cols, fill_value="").sort_values(content_cols).reset_index(drop=True)
        b = new.sort_values(content_cols).reset_index(drop=True)
        if a.equals(b):
            log["pipeline"] = {"pulled": len(new), "new_release": False, "releases": int(old["release"].nunique())}
            return
    new["release"] = today
    merged = pd.concat([old, new], ignore_index=True)
    write_archive(merged, path)
    log["pipeline"] = {"pulled": len(new), "new_release": True, "releases": int(merged["release"].nunique())}


def main(store):
    today = dt.date.today().isoformat()
    log = {"run": dt.datetime.now(dt.timezone.utc).isoformat()}
    merge_transactions(store, today, log)

    rent = flatten(load_raw("rental_median"), "rentalMedian")
    upsert(store, "rentals.csv.gz", rent, ["project", "street", "refPeriod"], "rentals", log)

    dev_frames = []
    for f in sorted(glob.glob(os.path.join(RAW, "dev_sales_*.json"))):
        d = flatten(json.load(open(f)), "developerSales")
        if len(d):
            dev_frames.append(d)
    dev = pd.concat(dev_frames, ignore_index=True)
    dev["month"] = "20" + dev["refPeriod"].str[2:4] + "-" + dev["refPeriod"].str[0:2]
    upsert(store, "dev_sales.csv.gz", dev, ["project", "street", "district", "month"], "dev_sales", log)

    merge_pipeline(store, today, log)

    lp = os.path.join(store, "archive", "log.json")
    hist = json.load(open(lp)) if os.path.exists(lp) else []
    hist.append(log)
    json.dump(hist[-500:], open(lp, "w"), indent=1)
    print(json.dumps(log, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "store")
