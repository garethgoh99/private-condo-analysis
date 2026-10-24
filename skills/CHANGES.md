# Changelog

Newest first. The SKILL.md files describe the current design directly.

- **v3 (24 Oct 2026):**
  - Map search for projects, landed streets and MRT/LRT stations.
  - Round "whole of Singapore" button on the map to get back to the island-wide figures.
  - Draggable, zoomable map (drag, scroll wheel / trackpad, pinch, + / − / fit buttons).
  - MRT/LRT overlay: lines and stations coloured by line, names shown as you zoom in (toggle under Overlay).
  - Custom multi-selections: Shift-click, the map's multi-select button, "⧉ Combine" or "＋ add to selection" combine any districts, projects and segments; every figure, chart and tab shows the union (each transaction once), with a per-member list. Selections can be pinned and compared.
  - The skill's template is byte-identical to the repo's `template/dashboard_template.html` (the live dashboard).
- **v2 (20 Oct 2026):**
  - Bedroom size-band filter (editable cut-offs).
  - Harmonised floor-area flags (5 confirmed from sources + a rule for the rest) with an optional gross-up.
  - Same-project repeat-sales growth method as the default.
  - Growth never anchors on a partial period. The current quarter's one month of data had inflated the raw all-Singapore CAGR (9.3% → 4.8%).
  - Lease-stage, floor-level, sale-lifecycle, unit-size and rentals tabs.
  - Rent and gross yield as map and compare metrics.
  - Pinned comparison panel (up to 8 regions, districts or projects).
  - Caches that cut a full recompute from 2.2 s to about 0.6 s.
- **v1 (20 Oct 2026):**
  - Daily pull of the four URA services.
  - Permanent archive on the `raw-data` branch (month-wise replacement, older months kept).
  - OneMap geocoding.
  - Derived 28-district map with CCR/RCR overlay.
  - Per-transaction columnar data.
  - Global statistic and quarter-level time range.
  - Filters on every URA field.
  - District → project drill-down and compare table.
