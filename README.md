# Private Residential Explorer

An interactive dashboard of Singapore private residential transactions (condos, apartments, executive condos and landed homes) by **postal district** and **project**, with the CCR / RCR / OCR market segments overlaid. It rebuilds itself every day from URA's data service and is served on GitHub Pages.

Sister project of [hdb-resale-dashboard](https://github.com/garethgoh99/hdb-resale-dashboard).

**Live dashboard:** https://garethgoh99.github.io/private-condo-analysis/ (once Pages is switched on, see *One-time setup*)

## What it shows

- **Map:** the 28 postal districts, coloured by price, $psf, area, remaining lease, CAGR or total growth (of price or $psf), velocity, median rent or gross rental yield. CCR and RCR boundaries and MRT/LRT lines and stations are drawn on top. Drag to pan, scroll or pinch to zoom, search for any project, street or station, and use the round globe button to get back to all of Singapore. Click a district to zoom in and see its projects.
- **Global controls:** a Statistic toggle (median / mean / lowest / highest), a **growth method** (same project like-for-like, or all transactions) and a time range from the full archive down to one quarter. All three apply to every figure on the page.
- **Filters on every field URA publishes:**
  - property type
  - **unit size ≈ bedrooms** (editable size bands)
  - type of sale and market segment
  - tenure and remaining lease
  - floor range
  - **floor-area basis** (pre- vs post-harmonisation, with an optional gross-up)
  - single or bulk caveats
  - price, $psf and area ranges
- **Drill-down:** All Singapore → segment → district → project. Each level has ranked mini-stats, a chart (levels, an index rebased to 100, the min–max spread, volume or rent, broken down by size, property type, sale type, segment, tenure, lease band, floor or floor-area basis) and **insight tabs**:
  - *Lease stage:* growth if you'd bought at each stage of the lease.
  - *Floor level:* within-project premium, velocity and growth by floor band.
  - *Sale lifecycle:* new → sub sale → resale, $psf by lease age, and premium over the project's own launch price.
  - *Unit size.*
  - *Rentals:* rent and yield by property type and segment.
- **Custom selections:** Shift-click (or use the multi-select button) to combine any districts, projects and segments; every figure, chart and tab shows the combined data, counting each transaction once.
- **Pinned comparison:** pin up to 8 regions, districts, projects or custom selections. You get one chart (an index for comparing growth, or price levels) and a table of merits with the best values highlighted.
- **Compare districts:** a sortable table of all 28 districts and the three segments, sharing the page's controls.

The browser gets every transaction, not pre-computed summaries, so every combination of filters gives exact figures. See `docs/dashboard-methods.md` for the methods.

## The data never shrinks: permanent archive

URA only serves the latest **5 years** of transactions, **3 years** of rentals and developer sales, and the **latest quarter** of the pipeline. To build up a longer history over time, every pull is merged into a permanent archive on the **`raw-data` branch**:

| File (on `raw-data`) | Merge rule |
|---|---|
| `archive/transactions.csv.gz` | There's no unit ID, so the merge works by contract month. Months URA still serves are replaced by the newest pull (URA revises and withdraws recent records). The boundary month keeps whichever copy has more rows. Older months are kept for good. A pull with < 80% of the archived rows for the same months is rejected. |
| `archive/rentals.csv.gz` | upsert on project + street + quarter |
| `archive/dev_sales.csv.gz` | upsert on project + street + district + month |
| `archive/pipeline.csv.gz` | each new quarterly release is appended |
| `latest/` | the raw JSON of the most recent pull; git history keeps every earlier pull too |
| `geo/` | boundary GeoJSON (data.gov.sg) and the OneMap geocode cache |
| `archive/log.json` | one line per run: rows pulled, archive size before and after |

## How it runs

`.github/workflows/refresh.yml` runs every day at 02:37 SGT, on every push to `main`, and from **Actions → Refresh data and dashboard → Run workflow**:

1. `pipeline/fetch.py` gets the day's token and pulls all four URA services (4 transaction batches, rentals, 36+ months of developer sales, pipeline).
2. `pipeline/archive.py` merges the pull into the archive (rules above).
3. `pipeline/geocode.py` looks up, via OneMap, projects that URA publishes without coordinates (mostly new launches). Results are cached, and lookups are spread over several runs because OneMap rate-limits.
4. The store is committed to `raw-data`.
5. `pipeline/build.py` (using `pipeline/harmonize.py`) builds `site/` from the archive, the page is syntax-checked, and it's deployed to Pages.

If any step fails, nothing is deployed and the previous dashboard stays live.

## The district map

Postal districts have no official boundary file; URA defines them as groups of postal sectors. `tools/build_district_map.py` builds the shapes in four steps:
1. Takes URA's official Master Plan 2019 coastline.
2. Labels a 100 m grid by the nearest projects' (district, segment), with anchor points pinning areas that have no private housing (Tuas, the catchments, Seletar and so on) to their usual district.
3. Smooths the result and folds in small fragments.
4. Simplifies the shapes so neighbours share edges exactly.

The output is `data/district_map.json`; 98.6% of projects fall inside their own district's shape. To redraw it:

```bash
pip install -r requirements-tools.txt
python tools/build_district_map.py path/to/raw-data-checkout
```

## One-time setup

1. **Settings → Secrets and variables → Actions:** add `URA_ACCESS_KEY` (done).
2. **Settings → Pages → Build and deployment → Source:** choose **GitHub Actions**.
3. **Actions → Refresh data and dashboard → Run workflow.**

## Run locally

```bash
pip install -r requirements.txt
git worktree add store origin/raw-data          # the archive
export URA_ACCESS_KEY=...                        # only needed for fetch.py
python pipeline/fetch.py && python pipeline/archive.py store   # optional: fresh pull
python pipeline/build.py store site
cd site && python -m http.server 8000            # then open http://localhost:8000
```

## Docs

- `docs/data-reconciliation.md`: profile of the four URA services and how they're joined.
- `reference/hdb-skills/`: the HDB dashboard's skill set, which this project's design builds on.
