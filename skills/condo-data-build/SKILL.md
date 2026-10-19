---
name: condo-data-build
description: Turn the harmonised URA archive into the browser data for the private-residential dashboard - every transaction in compact columnar JSON (not pre-aggregated), plus per-project location, tenure, modal property type, harmonised-floor-area flag, and linked rentals / developer sales / pipeline. Use after condo-ura-ingestion and before condo-dashboard-build, or when changing what fields the dashboard can filter on.
---

# Building the dashboard data

## Why per-transaction, not aggregates (the reverse of the HDB design)
The filters can be combined freely: property type, size band, sale type, tenure, remaining lease, floor, units, price, $psf, area, segment, floor-area basis and any quarter range. That's far too many combinations to precompute, and medians can't be recombined from aggregates. About 130k rows (growing by roughly 30k a year) come to 6–7 MB of JSON, around 0.9 MB gzipped, and filter in milliseconds. Re-evaluate around 1M rows: switch to binary typed arrays or per-year files.

## `scripts/build.py STORE SITE` → `SITE/data/tx.json`, `SITE/data/map.json`, `SITE/index.html`
`cols` holds integer arrays sorted by month:

| key | meaning |
|---|---|
| `mi` | months since 1990-01 |
| `p` | project index |
| `d` | district number |
| `g` | segment index (CCR, RCR, OCR) |
| `t` | property-type index |
| `s` | sale type (1 new, 2 sub, 3 resale) |
| `a` | area in sqm × 10 |
| `pr` | effective price |
| `f` | floor-range index, sorted `-`, B…, 01-05… |
| `k` | tenure kind (FH, 999, LH, UNK) |
| `rl` | remaining lease × 10 (−1 = none) |
| `u` | units |
| `ar` | land area flag |
| `ls` | lease start year (0 = none) |

`projects[i]` = `[name, street, district, segIdx, svgX, svgY, locSrcIdx, isGeneric, modalTenureText, modalPtypeIdx, leaseStartYear, harmFlag]`.

Also included:
- **`extras[i]`:** rent series, developer-sales series and pipeline entry for each project.
- **`rent`:** `[projIdx, quarterIdx, median, p25, p75]` rows (quarter index = (year − 1990) × 4 + q − 1).
- **`pipeline_by_district`, `meta`, `harmonisation`** (summary).

## Harmonised floor areas: `references/harmonisation.json`
URA circular URA/PB/2022/09-DCG covers development applications from 1 Jun 2023 and government land sale sites launched from 1 Sep 2022. Voids are excluded, areas are measured to the middle of the wall, and air-con ledges become common property. Listed areas shrink, so $psf rises for the same space. **URA's data has no flag.** `harmFlag` is:
- **2 = confirmed,** from sources: Lentor Mansion (first launch, Mar 2024), Emerald of Katong, Norwood Grand, Parktown Residence, ELTA.
- **1 = likely,** by rule: a leasehold project with lease start ≥ 2023 and first new sale ≥ 2024-03. This currently catches 37 more. It correctly excludes Hillhaven, The Myst, J'Den and Lentoria.
- **0 = otherwise.** `force_harmonised` and `force_not_harmonised` override the rule.

Don't use "lease start ≥ 2023" alone: private sites approved under the old rules also have 2023 leases. Keep the file editable and say in the UI which projects are confirmed and which are only likely.

## Bedrooms
URA has no bedroom field. Bands are derived **client-side** from area, so they can be edited and the gross-up can move units between bands.
- **Default cut-offs:** 580 / 850 / 1,200 / 1,600 sqft (studio/1, 2, 3, 4, 5+).
- **Where they come from:** where new-launch unit sizes cluster. 1-bed 450–549, 2-bed 600–799, 3-bed 850–1,149, 4-bed 1,200–1,450.
- **Effect of harmonisation:** about 50 sqft smaller within each band.
- **Scope:** only apartments, condos and ECs get a band; landed homes = −1.

## Templating
- Substitute `__PLACEHOLDER__` tokens.
- Then validate: no tokens left over (`__[A-Z_]+__`), and run `node --check` on the extracted `<script>`.

## Checks
- Pandas cross-check at least one figure for each of the 4 statistic modes (median $psf for Singapore, a district's median price, a district's mean $psf, the lowest $psf and highest price under a filter). They must match the page exactly.
- `tx.json` gzipped should be about 1 MB. If it reaches tens of MB, something duplicated.
