---
name: hdb-data-ingestion
description: Read and harmonize Singapore HDB resale flat price CSV files (the data.gov.sg "Resale Flat Prices" series, uploaded directly) into one clean, consistent dataframe. Handles inconsistent per-era schemas, a flat_type spelling split across eras, and remaining-lease formats. Use whenever the user uploads one or more HDB resale price CSVs and wants them read, cleaned, combined, or prepared for aggregation/dashboarding. Trigger even for a single file (e.g. 2017-onwards) — its lease-string column still needs parsing.
---

# HDB resale data ingestion

Never call the data.gov.sg API — work from uploaded files only.

## Why harmonize: the 5 era files disagree on schema

| File (era) | `remaining_lease`? | `resale_price` type | Rows |
|---|---|---|---|
| Approval Date 1990–1999 | No | int | ~287k |
| Approval Date 2000–Feb 2012 | No | float | ~370k |
| Registration Date Mar 2012–Dec 2014 | No | float | ~52k |
| Registration Date Jan 2015–Dec 2016 | Yes, int years | float | ~37k |
| Registration Date Jan 2017 onwards | Yes, string `"61 years 04 months"` | float | ~240k+, growing |

## Target schema

```
month str 'YYYY-MM' | town str UPPER | flat_type str UPPER, normalized (see below)
block str | street_name str UPPER (finest granularity — don't go finer)
storey_range str | floor_area_sqm float | flat_model str
lease_commence_date int | resale_price float | year int (month[:4])
remaining_lease_yrs float (see below) | psf float = resale_price/(floor_area_sqm*10.7639)
```

## Remaining lease

1. **2017+**: parse `"X years Y months"` with separate regexes for `(\d+)\s*year` / `(\d+)\s*month` (default 0 each — singular "1 year" and missing-months both occur) → `years + months/12`.
2. **2015–2016**: already an int year count — use directly.
3. **No column at all** (1990–2012, 2012–2014): `99 - (year - lease_commence_date)` (standard 99-yr HDB lease; approximate, ignores transaction month within the year).

## flat_type normalization — a real bug, not hypothetical

1990–1999 spells one category `"MULTI GENERATION"` (space); every later era spells it `"MULTI-GENERATION"` (hyphen) — same type, splits into two throughout every downstream structure if left unmerged. Fix in `harmonize_one()`, right after `.str.strip().str.upper()`:

```python
df["flat_type"] = df["flat_type"].replace({"MULTI GENERATION": "MULTI-GENERATION"})
```

Print `df['flat_type'].unique()` after combining and eyeball for other near-duplicates (different punctuation/spacing, same meaning) — cheap insurance against a future data.gov.sg revision introducing a similar split.

## Combining multiple files

- Harmonize each to target schema first, concatenate after (raw column sets differ).
- `drop_duplicates(subset=['month','town','block','street_name','flat_type','floor_area_sqm','resale_price'])` — catches accidental overlap at era boundaries.
- `town`/`street_name` spellings are consistent across eras in practice (no fuzzy matching needed) — but print `df['town'].unique()` as a sanity check.

## Reference implementation

`scripts/harmonize.py` does all of the above end-to-end. Adapt `INPUT_FILES` to whatever's actually uploaded (not all 5 need be present).

## Practical notes

- Files are large (20–30MB each) — `pandas.read_csv` directly, don't go row-by-row.
- The 2017+ file is a live, growing extract — read the actual max `month` rather than assuming a date, and say so when reporting totals.
- Hand off the harmonized dataframe to **hdb-data-aggregation** next — don't feed 240k+ raw rows into a browser visualization.
