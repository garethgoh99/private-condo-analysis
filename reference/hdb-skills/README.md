# HDB Resale Dashboard — skill set

Four skills that together recreate the interactive Singapore HDB resale-price dashboard
built in this conversation, from raw uploaded CSVs to a published HTML artifact. Written
for Claude's skill format (YAML frontmatter + Markdown body in each `SKILL.md`), but each
one is plain instructions plus standalone Python/HTML — readable and usable by any
LLM-based coding assistant, not just Claude.

No API calls anywhere in this set. Every skill assumes the relevant files (CSVs, or a
reference outline image) are uploaded directly into the conversation.

See `CHANGES.md` for a brief history of what's changed since the first build.

## The four skills, in the order they run

1. **hdb-data-ingestion** — read the raw data.gov.sg "Resale Flat Prices" CSVs (any one
   era, or several) and harmonize them into one clean dataframe. Handles the schema
   differences across eras (lease format, missing columns), normalizes an inconsistent
   flat_type spelling across eras (`MULTI GENERATION` vs `MULTI-GENERATION`), and computes
   derived fields ($psf, remaining lease in years).
2. **hdb-data-aggregation** — turn that harmonized dataframe into compact, multi-level
   aggregated JSON (street level, town level, nationwide, both per-flat-type and combined
   across all flat types per year), defines the "velocity"/turnover measure and the
   CAGR/total-growth measures, and documents the 18-field-per-record schema (mean, median,
   min AND max for price, lease, area, and $psf) that the dashboard's Statistic toggle
   depends on.
3. **hdb-map-outline** — town centroid coordinates, a projection technique that actually
   spreads the towns across the map instead of clustering them in the middle, and a
   method for tracing a coastline outline out of any reference image the user supplies.
4. **hdb-dashboard-build** — assembles the outputs of the previous three skills into one
   self-contained, published HTML dashboard: the map (with a global year-range slider,
   flat-type toggle, and Statistic toggle — median/mean/lowest/highest, applied to every
   figure in the dashboard), the drill-down charts, per-street ranking bars with
   town/nationwide benchmarks, rank badges throughout, and a cross-town comparison table
   that shares the map's controls.

## Installing into Claude

Each folder (`hdb-data-ingestion/`, `hdb-data-aggregation/`, `hdb-map-outline/`,
`hdb-dashboard-build/`) is a complete, independent skill. Upload each folder (or its zip)
wherever your Claude setup accepts custom skills. They're written to be used together in
sequence, but each also stands alone if you only need, say, the aggregation logic.

## Using with a different assistant

If your tool doesn't support Claude's skill format specifically, the `SKILL.md` files
still work as plain instruction documents — paste the body into a system prompt, a
project's custom instructions, or just hand it to the assistant at the start of a session
("follow these instructions when building the dashboard"). The bundled `scripts/` and
`assets/` files are plain Python/HTML with no Claude-specific dependencies, so they run
anywhere Python and a browser do.

## Re-running the whole thing end to end

1. Upload your HDB resale CSV(s) and point the ingestion skill at them.
2. Run the aggregation skill on the harmonized output — expect eight JSON files, roughly
   7 MB total for the full 1990–2026 dataset (per-record size has grown with the schema;
   see hdb-data-aggregation's sanity-check section for what's expected vs. a red flag).
3. If you want a fresh map outline, upload a reference image and run the outline skill's
   trace script; otherwise reuse `references/town_coords.json` and the existing traced
   points already embedded in `assets/dashboard_template.html`.
4. Run the build skill: substitute the aggregated JSON into the template, validate (syntax
   check plus the math unit tests described in hdb-dashboard-build), and publish.

