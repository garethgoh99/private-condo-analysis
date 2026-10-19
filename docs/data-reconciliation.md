# URA data: profile and reconciliation plan

These findings come from the first full pull of all four URA services, fetched on 19 Oct 2026 (UTC). The raw snapshot is on the `raw-data` branch.

## What each service gives

| Service | Grain | Window in this pull | Size | Location fields |
|---|---|---|---|---|
| `PMI_Resi_Transaction` | One row per caveat (transaction), nested under project | Oct 2021 – Oct 2026 (rolling 5 yrs) | 131,858 tx, 3,839 project+street combos | district, marketSegment, x/y (SVY21) |
| `PMI_Resi_Rental_Median` | Project × quarter, $psf **per month** (25th / median / 75th percentile) | 2023Q3 – 2026Q2 (rolling 3 yrs) | 7,111 rows, 921 projects, non-landed only | district, x/y |
| `PMI_Resi_Developer_Sales` | Project × month (one call per `refPeriod`) | Oct 2023 – Sep 2026 (Oct 2026 not out until 15 Nov) | 4,018 rows, 191 projects | district, marketSegment, x/y |
| `PMI_Resi_Pipeline` | Project, latest-quarter snapshot only | Current | 78 rows | district only (no x/y) |

Transaction mix: 52.9k Apartment, 50.5k Condominium, 16.0k EC and about 12.5k landed. By sale type: 81.7k resale, 45.1k new sale and 5.0k sub sale. By segment: 73.7k OCR, 38.1k RCR and 20.0k CCR. All 28 postal districts appear.

## Reconciliation rules

### 1. Project master table (the join spine)
- Key: normalised `(project, street)`. To normalise, convert to upper case, turn punctuation into spaces and collapse repeated spaces. Each key gets a stable `project_id`.
- Two placeholder project names cover many unrelated properties: `LANDED HOUSING DEVELOPMENT` (5,124 tx on 780 streets) and `RESIDENTIAL APARTMENTS` (267 tx). These are keyed by street + district and labelled as unnamed. They are never merged into a single "project".
- A project in more than one district: 8 cases, all large landed estates. Each transaction keeps its own district. The project gets the district where most of its transactions fall.
- A project with more than one tenure (124) or more than one property type (503): both are kept per transaction, not per project.

### 2. Linking the other three services to the master table
- **Rentals:** 97% match on name alone. The few street mismatches are spelling (`SUFFOLD WALK` vs `SUFFOLK WALK`) or an estate's other street. Matching is by name first, then within the district. The 27 unmatched projects are older blocks with no sale in 5 years; they're kept as rental-only.
- **Developer sales:** 96% match on name. Its street field often lists several streets joined by `/`, so matching is on the name, with district as a tie-break.
- **Pipeline:** 84% match. It's in Title Case, and names sometimes carry a second label ("SKYWATERS RESIDENCES / THE SKYWATERS"), so each part is tried in turn. The rest are generic mixed-use rows ("Service apartments / hotel / retail") with no sales yet. They appear only in district supply totals.

### 3. Transactions
- **Rows that look identical are kept.** There is no unit ID, and 8.2k rows are exact duplicates, mostly new-launch units sold the same month at the same size, price and floor band. They are separate sales, so they all count.
- **Multi-unit caveats** (58 rows, `noOfUnits` > 1, one of 446 units): `price` is the total for the whole lot. These are left out of price and $psf statistics, still counted in volume, and flagged.
- **Price:** `nettPrice` is used when present (117 new-sale rows with developer discounts); otherwise `price`.
- **$psf** = price ÷ (area_sqm × 10.7639). `typeOfArea` is Land for landed homes and Strata for the rest. Land $psf and strata floor $psf measure different things, so the two are never averaged together.
- **Tenure:** parsed into freehold / 999-yr / 99-yr plus a start year, which gives remaining lease at the transaction date. Three non-standard spellings exist: `99 years lease commencing…` (141 rows, parsed the same way), `99 years leasehold` with no start year (451 rows, start year borrowed from the project's other rows if any, otherwise null) and `999 years leasehold` (21 rows).
- **Dates:** `contractDate` is in mmyy format. For new sales it's the date of the option to purchase; for resale and sub sale it's the date the option was exercised.

### 4. Coordinates
- x/y are SVY21; they're converted to lat/lon with pyproj (EPSG:3414 → 4326).
- 148 named projects have **no coordinates in any service**. They account for 27.5k transactions (21%), mostly the newest launches (Parktown, Grand Dunman, Springleaf, and so on). The plan is to geocode them through OneMap's public search inside the GitHub Action, cache the results in `data/geocode_cache.json`, and fall back to the district centroid.

### 5. Developer sales
- `medianPrice`, `lowestPrice` and `highestPrice` are **$psf**, not total prices. A value of 0 means no units sold that month; it's not a real zero, so it's stored as null. This affects 2,254 of 4,018 rows, all with `soldInMonth` = 0.
- Cross-check: the developer median $psf matches the median $psf of new-sale transactions in the same project and month exactly in most cells (median difference 0.0%).
- Units sold don't fully tie: developer sales show 28.4k sold against 27.5k new-sale transactions over Oct 2023 – Sep 2026, with 85% of project-month cells matching exactly. The differences come from timing and coverage (when the option was granted vs exercised, and caveats not lodged). Developer sales are the source for supply and absorption figures; transactions are the source for prices.
- Derived figures: unsold launched units = launchedToDate − soldToDate; unlaunched = unitsAvail − launchedToDate; sell-through % = soldToDate ÷ launchedToDate.

### 6. Rentals
- Rent is $psf per month, covers only non-landed projects (about 30% of projects that have transactions), and is quarterly.
- Gross yield = (median rent psf × 12) ÷ median resale $psf for the same project and quarter. It's only shown where both exist and the quarter has at least N resales; N is still to be set.

### 7. Pipeline
- Latest quarter only, so history only builds up from our own snapshots. The expected TOP year is `na` for 60 of 78 rows, because developers didn't consent to releasing it. In 7 mixed-use rows the per-type unit counts don't add up to `totalUnits`.
- Used for district-level future supply, and as a "pipeline" badge on matched projects.

### 8. Keeping history beyond URA's rolling windows
Each fetch is committed to the `raw-data` branch as a new snapshot. The build will combine all snapshots so history grows past 5 years for transactions and 3 years for rentals and developer sales. Where months overlap, the latest snapshot wins, since URA warns that records can be revised or withdrawn.

## Open design questions
1. Scope: all private residential (landed and EC included, with a property-type filter), or condos and apartments only?
2. Map unit: postal district (28; every service has it), planning area (needs geocoding and boundary polygons) or market segment (CCR/RCR/OCR)?
3. Drill-down level below the map unit: project (the counterpart of HDB's street)?
