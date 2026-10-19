# Changelog

All four skills are current as of this version — the SKILL.md files describe the final
design directly rather than narrating how it got there. Brief history, newest first:

- **Lightweight pass**: all docs rewritten for density — same technical content (every
  formula, field name, gotcha), ~50% less prose.
- **Ingestion**: normalized a flat_type spelling split (`MULTI GENERATION` vs
  `MULTI-GENERATION`, 1990s era vs. later).
- **Schema**: expanded 9→18 fields — mean/median/min/max for all of price/lease/area/psf,
  not just price.
- **Dashboard**: added the global Statistic toggle (median/mean/lowest/highest, applies
  everywhere); fixed a bar-scale bug where nationwide/town benchmark values (on a
  different scale than any single street) were collapsing street-to-street bar
  comparisons — benchmarks now show numbers only, bars are street-only; fixed tooltip
  transaction-count labeling to be mode-aware; added the global year-range + flat-type
  toggle (shared by map, comparison table, street bars); switched the map's color scale
  from 2-hue to a single-hue 5-class quantile-binned scale with corrected legend labels;
  corrected a CAGR/"growth" metric that was accidentally double-annualized (now "total %
  growth," not annualized, alongside CAGR which is).

`assets/dashboard_template.html` is the current reference implementation.
