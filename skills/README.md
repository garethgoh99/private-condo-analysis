# Private Residential Explorer: skill set

Four skills that together rebuild the Singapore private-residential dashboard (https://garethgoh99.github.io/private-condo-analysis/), from URA's Data Service through to a GitHub Pages site. They use Claude's skill format (YAML frontmatter + Markdown in each `SKILL.md`), but each is plain instructions plus standalone Python and HTML, so any coding assistant can follow them. They're modelled on the HDB resale dashboard skill set (`reference/hdb-skills/` in the repo), and the differences are deliberate: see each skill.

## The four skills, in the order they run

1. **condo-ura-ingestion:** gets the URA token and pulls the four services (transactions, rentals, developer sales, pipeline). It merges each pull into a **permanent archive** so history outlives URA's rolling windows, geocodes projects that lack coordinates via OneMap, and harmonises the data (tenure, remaining lease, nett price, $psf, project locations).
2. **condo-data-build:** writes every transaction in compact columnar JSON (not pre-aggregated, so every combination of filters gives exact figures). It adds per-project metadata, the **harmonised floor-area flag** (`references/harmonisation.json`) and linked rentals, developer sales and pipeline. Also covers the bedroom size bands.
3. **condo-district-map:** derives the 28 postal-district shapes and the CCR/RCR/OCR overlay from URA's coastline and project locations, since postal districts have no official boundary file, and builds the MRT/LRT overlay in the same map space.
4. **condo-dashboard-build:** the page itself:
   - global statistic, growth method and quarter-level time controls
   - filters on every field
   - the same-project repeat-sales growth method
   - lease-stage, floor, sale-lifecycle, unit-size and rental tabs
   - pinned side-by-side comparison
   - map search, home button, drag / scroll pan-zoom and the MRT/LRT overlay
   - custom multi-selections (districts, projects and segments combined into one set of figures)
   - testing checklist

## Using with Claude
Upload each folder (or its zip) wherever your Claude setup accepts custom skills, or ask Claude to add them to your account. With another assistant, paste a `SKILL.md` body into its instructions; the `scripts/` and `assets/` files have no Claude-specific dependencies.

## Re-running end to end
1. Add the repo secret `URA_ACCESS_KEY` and set **Settings → Pages → Source** to GitHub Actions.
2. Put `refresh.yml` (in condo-dashboard-build's assets) in `.github/workflows/`, and the scripts in `pipeline/` and `tools/` as the repo lays them out.
3. Run the workflow. It fetches, archives to the `raw-data` branch, geocodes, builds and deploys.
4. To redraw the map: `python tools/build_district_map.py <raw-data checkout>` (needs the `geo/` boundary files and `requirements-tools.txt`).

See `CHANGES.md` for the history.
