"""
Harmonize one or more HDB resale-price CSVs (data.gov.sg "Resale Flat Prices" series,
uploaded directly) into a single clean dataframe.

Usage:
    python3 harmonize.py
    (edit INPUT_FILES below to point at whatever the user actually uploaded --
     you do not need all five; a single file, e.g. the 2017-onwards one, works fine)

Output:
    Writes harmonized.csv (or change OUTPUT_PATH) with columns:
    month, town, flat_type, block, street_name, storey_range, floor_area_sqm,
    flat_model, lease_commence_date, resale_price, year, remaining_lease_yrs, psf
"""
import pandas as pd
import re
import glob

# --- Edit this list to match whatever files the user uploaded ---
INPUT_FILES = sorted(glob.glob("/mnt/user-data/uploads/*Resale*.csv"))
OUTPUT_PATH = "harmonized.csv"

SQM_TO_SQFT = 10.7639


def parse_lease_string(s):
    if pd.isna(s):
        return None
    y = re.search(r"(\d+)\s*year", str(s))
    m = re.search(r"(\d+)\s*month", str(s))
    yy = int(y.group(1)) if y else 0
    mm = int(m.group(1)) if m else 0
    return round(yy + mm / 12, 2)


def harmonize_one(path):
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]

    df["town"] = df["town"].str.strip().str.upper()
    df["street_name"] = df["street_name"].str.strip().str.upper()
    df["flat_type"] = df["flat_type"].str.strip().str.upper()
    # The 1990-1999 era spells this "MULTI GENERATION" (space); every later era uses
    # "MULTI-GENERATION" (hyphen). Same flat type, just an inconsistent source spelling --
    # normalize to the hyphenated form so it isn't silently split into two categories.
    df["flat_type"] = df["flat_type"].replace({"MULTI GENERATION": "MULTI-GENERATION"})
    df["year"] = df["month"].str[:4].astype(int)
    df["resale_price"] = df["resale_price"].astype(float)
    df["floor_area_sqm"] = df["floor_area_sqm"].astype(float)

    if "remaining_lease" in df.columns:
        sample = df["remaining_lease"].dropna().iloc[0] if df["remaining_lease"].notna().any() else None
        if isinstance(sample, str):
            df["remaining_lease_yrs"] = df["remaining_lease"].apply(parse_lease_string)
        else:
            df["remaining_lease_yrs"] = df["remaining_lease"].astype(float)
    else:
        df["remaining_lease_yrs"] = 99 - (df["year"] - df["lease_commence_date"])

    df["psf"] = df["resale_price"] / (df["floor_area_sqm"] * SQM_TO_SQFT)

    keep = ["month", "town", "flat_type", "block", "street_name", "storey_range",
            "floor_area_sqm", "flat_model", "lease_commence_date", "resale_price",
            "year", "remaining_lease_yrs", "psf"]
    return df[keep]


def main():
    if not INPUT_FILES:
        raise SystemExit("No input files found -- edit INPUT_FILES to point at the uploaded CSV(s).")
    frames = []
    for p in INPUT_FILES:
        f = harmonize_one(p)
        print(f"{p.split('/')[-1]}: {len(f)} rows, years {f['year'].min()}-{f['year'].max()}")
        frames.append(f)
    combined = pd.concat(frames, ignore_index=True)
    before = len(combined)
    combined = combined.drop_duplicates(
        subset=["month", "town", "block", "street_name", "flat_type", "floor_area_sqm", "resale_price"]
    )
    after = len(combined)
    if before != after:
        print(f"Dropped {before - after} likely duplicate rows at era boundaries.")

    print(f"Combined rows: {len(combined)}")
    print(f"Towns: {combined['town'].nunique()}")
    print(sorted(combined['town'].unique()))
    print(f"Year range: {combined['year'].min()} - {combined['year'].max()}")
    print(f"Max month value: {combined['month'].max()}")
    combined.to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
