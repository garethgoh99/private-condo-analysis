# Changelog

Newest first. The SKILL.md files describe the current design directly.

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
