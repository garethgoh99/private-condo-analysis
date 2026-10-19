---
name: condo-ura-ingestion
description: Pull Singapore private residential data from URA's Data Service (transactions, median rentals, developer sales, pipeline), merge each pull into a permanent archive so history outlives URA's rolling 5-year / 3-year windows, geocode projects URA publishes without coordinates, and harmonise everything into clean typed tables (tenure, remaining lease, nett price, $psf). Use whenever fetching, archiving, cleaning or reconciling URA private-property data, or when debugging the daily refresh.
---

# URA private-residential ingestion

Everything runs in GitHub Actions (URA and OneMap are unreachable from Claude's cloud workspace and from the Mac's sandboxed shell). The access key is the repo secret `URA_ACCESS_KEY`. Never paste it into chat or commit it.

## 1. Token: `scripts/ura_token.py`
`GET https://eservice.ura.gov.sg/uraDataService/insertNewToken/v1` with header `AccessKey`. The response is `{Result: token, Status: "Success"}`. The token is valid for the day; get a fresh one each run and never store it. Send a browser-like `User-Agent`. Treat a non-JSON reply as a block page and fail loudly. Never print the token.

## 2. Fetch: `scripts/fetch.py` → `data/raw/*.json`
`GET .../invokeUraDS/v1?service=…` with headers `AccessKey` and `Token`:

| Service | Params | Window | Notes |
|---|---|---|---|
| `PMI_Resi_Transaction` | `batch=1..4` (postal districts 01–07 / 08–14 / 15–21 / 22–28) | 5 yrs rolling | ~130k tx, nested `project → transaction[]` |
| `PMI_Resi_Rental_Median` | none | 3 yrs | non-landed, project × quarter, $psf **per month**, no contract counts |
| `PMI_Resi_Developer_Sales` | `refPeriod=mmyy`, one call per month | 3 yrs | med/low/high are **$psf**; 0 = no sales that month (store as null) |
| `PMI_Resi_Pipeline` | none | latest quarter only | `expectedTOPYear` is mostly `na` |

Retry with backoff. Refuse the pull if fewer than 1,000 transactions come back.

## 3. Permanent archive: `scripts/archive.py STORE` (the `raw-data` branch)
There's no unit ID, so transactions are merged **by contract month**:
- Months after the new pull's earliest month are replaced wholesale, because URA revises and withdraws recent records.
- The boundary month keeps whichever copy has more rows.
- Older months are kept forever. This is the point of the archive: they're what lets history grow.
- **Safety:** if the new pull has fewer than 80% of the archived rows for the same months, abort without writing.

For the other services:
- **Rentals:** upsert on (project, street, refPeriod).
- **Developer sales:** upsert on (project, street, district, month).
- **Pipeline:** append a new `release` only when its content changes.

The source contains exact duplicate project blocks (e.g. GRANGE HEIGHTS, PARC CLEMATIS), so the upsert collapsing them is correct. `log.json` records counts for every run. Re-running the same pull must be a no-op; test this.

## 4. Geocode: `scripts/geocode.py STORE`
About 21% of transactions belong to projects (mostly new launches) that have no x/y in **any** URA service.
- **Lookup:** OneMap public search, querying `project` → `project street` → `street`.
- **Acceptance:** a hit counts only if its postal sector (first 2 digits) maps to the project's own district (table in the script). Use the centroid of the in-district hits.
- **Caching:** results go in `geo/geocode_cache.json`. Cache misses (retry after 30 days), but **never** cache request errors as misses.
- **Rate limits:** OneMap returns HTTP 429 quickly, so sleep 1 s per call, cap the run at 150 lookups, and stop after 12 errors.
- **Diagnostics:** emit a `::notice::` summary, because job logs can't be read through the proxy but annotations can.

## 5. Harmonise: `scripts/harmonize.py` → `load_clean(store)`
- **`month`:** `'20'+contractDate[2:4]+'-'+contractDate[0:2]` (contractDate is mmyy). It's the option date for new sales and the exercise date for resale and sub sale.
- **Price:** `price = nettPrice if > 0 else price` (nettPrice is set on about 117 discounted new sales). Sanity-check the result: `psf = price / (area_sqm × 10.7639)`, roughly 100–6,600.
- **Tenure:** `Freehold` → FH. `N yrs/years …` with N ≥ 900 → `999`; otherwise LH. Take the start year from `from YYYY`. `99 years leasehold` has no start year, so borrow the project's modal start year.
  - `rem_lease = start + years − (year + (month − 0.5)/12)`.
- **Projects:**
  - **Key:** `pkey = PROJECT|STREET`.
  - **Generic names:** `LANDED HOUSING DEVELOPMENT` (780 streets) and `RESIDENTIAL APARTMENTS` are placeholders, so key them by street and never merge them.
  - **Location priority:** URA tx x/y → x/y from the other URA services (matched by normalised name) → OneMap cache → none.
  - **Conversion:** SVY21 (EPSG:3414) → WGS84 via pyproj.
- **Bulk caveats:** `noOfUnits > 1` (up to 446 units) are en-bloc lots, with price and area as lot totals. Keep them, but default the filters to single units.
- **Identical rows:** about 8k rows look like exact duplicates. Keep them: they're separate units sold in the same month.

## 6. Matching the other services to projects
Normalise names (upper case, punctuation → space, collapse spaces) and match on (name, district), falling back to name alone if it's unique. Expect about 97% of rental projects, about 96% of developer-sales projects and about 84% of pipeline rows to match. Pipeline names come in Title Case with `/` aliases, so try each part. The unmatched pipeline rows are generic mixed-use developments.

## Gotchas
- **Shallow push:** in Actions, push the store with `git push origin HEAD:raw-data` from a worktree. A plain `git push origin raw-data` failed.
- **Unreadable logs:** surface failures with `echo "::error title=…::msg"` and read them via the check-runs annotations API.
