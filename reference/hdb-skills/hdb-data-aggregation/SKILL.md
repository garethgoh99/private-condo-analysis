---
name: hdb-data-aggregation
description: Turn a harmonized HDB resale-price dataframe into compact, multi-level aggregated JSON for an interactive dashboard — street/town/nationwide, both per-flat-type (chart breakdowns) and combined-across-flat-type per year (range stats, CAGR/growth, ranking). Every record carries mean/median/min/max for price, lease, area AND $psf — the symmetric schema a dashboard needs to offer a single median/mean/lowest/highest toggle that applies everywhere, not just to price. Run after hdb-data-ingestion, before hdb-dashboard-build.
---

# HDB resale data aggregation

Raw transactions (200k–1M+ rows) are too heavy for smooth client-side filtering. Pick grain **street × flat_type × year** — fine enough to be useful, coarse enough to stay small (low-single-digit MB as JSON); anything finer just re-derives raw data.

## Three levels, one schema

1. **Street**: group `(town, street_name, flat_type, year)`.
2. **Town**: group `(town, flat_type, year)` — recompute from raw rows, NOT by averaging street-level medians (mean-of-medians is invalid).
3. **Nationwide**: group `(flat_type, year)`.

## Record schema: 18 fields — mean/median/min/max × (price, lease, area, psf)

```
[year, n,
 price_mean, price_median, price_min, price_max,
 lease_mean, lease_median, lease_min, lease_max,
 area_mean,  area_median,  area_min,  area_max,
 psf_mean,   psf_median,   psf_min,   psf_max]
```

Plain array (not object) to keep JSON small; document field order once as a named-index lookup in the frontend. `psf` is computed per-transaction first (`price/(area_sqm*10.7639)`), then its mean/median/min/max taken of that column — not derived from price's and area's stats separately.

**Why all four stats for all four dimensions, not just price:** this is what lets a dashboard offer one global toggle (median/mean/lowest/highest) that means the same thing for every figure — a person asking "what's the floor on this street" wants the *lowest* transaction, not an average, and wants it for lease/psf too, not just price. Decide this up front; retrofitting later means re-aggregating and migrating every downstream JSON.

## Also: combined-across-flat-type, per year

The three levels above are flat_type-split — wrong shape for "this street's price for whatever range is picked," since flat-type medians/mins/maxes can't be validly re-combined by further averaging (though min-of-mins and max-of-maxes ARE valid — only median isn't). Build 3 more structures, same 18-field schema, grouped WITHOUT flat_type, direct from raw rows:

- **`town_year`**: `(town, year)`
- **`street_year`**: `(town, street_name, year)`
- **`sg_year`**: `(year)` only

These enable a year-range slider anywhere (map, comparison table, detail view) instead of only "latest year," and let the frontend compute CAGR/growth/ranking for whatever range is selected — see hdb-dashboard-build's "range metrics" catalog, which runs one generic set of functions over any of the six structures.

## Flat-type SUBSETS: not this skill's job, but design for it

A dashboard may let someone deselect some flat types — too many possible subsets to precompute, so that combination happens client-side (hdb-dashboard-build). It depends on every dimension here having all four stats: `mean` recombines exactly via n-weighted sum, `min`/`max` recombine exactly via `Math.min`/`Math.max`, only `median` needs an approximate n-weighted-average fallback. None of that works if a dimension is missing its mean or min/max — another reason for the symmetric schema.

## Velocity (not stored)

```
velocity (tx/yr) = n in selected range / years in that range
```

Always recompute against whatever range is currently active — never a hardcoded window.

## CAGR and total % growth — different things, compute both

- **CAGR**: `(last/first)^(1/years) − 1` between first/last year present. Always annualized.
- **Total % growth**: `(last/first) − 1`. Never annualized — a 10-yr span shows a much bigger number than its CAGR, correctly.

Don't accidentally make both annualized (e.g. by computing "growth" as the mean of year-over-year % changes) — that's just a noisier CAGR and the two stop being worth showing together. Sanity check: `(1+CAGR/100)^years == 1+total_growth/100`, exactly. Compute both for price and $psf, reading off whichever field the dashboard's Statistic toggle currently selects (not hardcoded to mean/median) — don't precompute/store, derive on the frontend per range+mode.

## Ranking

Same schema across levels → ranking "this entity among peers" is one function regardless of metric/level: compute for every peer over the same range+flat-type+mode, sort, find position. Keep generic, not per-metric bespoke.

## Reference implementation

`scripts/aggregate.py` → 8 JSON files: `street_data/town_agg/sg_agg.json` (per-flat-type), `town_summary/town_compare.json` (lightweight, backward-compat), `town_year/street_year/sg_year.json` (combined, 18-field).

## Sanity checks

- File sizes: low-single-digit MB total, not tens of MB (too fine a grain if so). `street_year.json` should be smaller than `street_data.json` (same grouping, minus flat_type split).
- Manual cross-check: `df[df.town==X].resale_price.median()` for one year, against BOTH a per-flat-type record and a combined (`town_year`, no flat_type filter) record — differ from each other, each should exactly match its own manual computation. Repeat for ≥1 non-price dimension (e.g. `lease_min`) — easy to get price right and transpose a later-added field.
- `psf_median` plausibility: ~60–120 in the 1990s rising to 400–1400 recently — a common bug is forgetting the sqft conversion (10x too high).
- Hand-check one CAGR calculation against the frontend's display.
- `df['flat_type'].unique()` — confirm no near-duplicate spelling slipped through (see hdb-data-ingestion).
