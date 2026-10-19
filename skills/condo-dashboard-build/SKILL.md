---
name: condo-dashboard-build
description: Build and extend the Singapore private-residential dashboard (GitHub Pages) - 28-district choropleth with CCR/RCR overlay, global Statistic / growth-method / quarter-level time controls, filters on every URA field incl. bedroom size bands and harmonised floor areas, same-project repeat-sales growth, lease-stage / floor / sale-lifecycle / unit-size / rental insight tabs, and a pinned side-by-side comparison of regions and projects. Final step after condo-ura-ingestion, condo-data-build and condo-district-map.
---

# Private-residential dashboard build

`assets/dashboard_template.html` is the complete current implementation (one file: inline CSS and vanilla JS, Chart.js 4.4.1 from the cdnjs pin, SVG map). Read and edit it rather than starting again. `assets/refresh.yml` is the daily GitHub Actions workflow (fetch → archive → geocode → commit store → build → validate → deploy Pages). Methods are written up in `references/dashboard-methods.md`.

## Global state (applies to every figure: map, detail, tabs, pins, compare table)
- **Statistic:** median / mean / lowest / highest. Lowest and highest are single real transactions, so label n as "lowest of n tx".
- **Growth method:** same project (default) or all transactions.
- **Time range:** a dual slider over quarters (archive start → latest), with presets for All, 10Y, 5Y, 3Y, 2Y, 1Y and the latest quarter.
- **Period granularity:** Auto gives quarterly when the range is ≤ 24 quarters. Charts for groups with fewer than 150 transactions fall back to yearly.
- **Filters:**
  - property type, with quick sets: non-landed / + EC / landed
  - size band ≈ bedrooms: editable cut-offs, saved in localStorage; picking a subset excludes landed homes
  - sale type and segment
  - tenure kind, plus a remaining-lease slider that applies to leasehold only
  - floor band slider, plus "include no-floor rows"
  - floor-area basis (pre / harmonised), plus a gross-up % (default 0)
  - units: single by default / bulk / both
  - price, $psf and area min/max boxes
- **Warnings:** show inline warnings when the selection mixes land-area and strata $psf, or harmonised and pre-harmonisation areas.

## Growth: two methods; never show a figure without saying which
- **All transactions:** the chosen statistic in the first vs last period with ≥ 3 tx.
- **Same project:** a repeat-sales index (Bailey–Muth–Nourse) on **unit = project × size band** (landed: project × property type) medians.
  - For each pair of consecutive traded periods: `r = ln(med_b / med_a)`, clipped to ±0.7, weighted `w = √min(n_a, n_b)`.
  - Solve weighted least squares for β per period, with β₀ = 0 and a tiny smoothness penalty λ = 10⁻³·Σw/P so that unconnected periods stay identified. Gaussian elimination is fine (P ≤ ~120).
  - It always uses medians.
- **Both methods:**
  - CAGR = (last/first)^(1/yrs) − 1, with anchors **≥ 1 year apart**.
  - Total growth = last/first − 1, not annualised. Check that `(1 + CAGR)^yrs == 1 + total`.
  - **Never anchor on a partial period** (e.g. the current quarter with one month of data) unless nothing else exists. Doing so once inflated the all-Singapore raw CAGR from 4.8% to 9.3%.
- **$psf vs price:** $psf is the cleaner like-for-like measure. Price growth within a band also picks up unit-size shifts, e.g. Lentor Mansion: −0.5% psf vs +7.2% price.

## Metric catalogue (`RM`): one definition reused by the map, compare table, project list, ranks and pins
price, $psf, area, lease left, CAGR $psf, CAGR price, total growth $psf, total growth price, velocity (tx ÷ years of data in range), rent ($psf/month, latest quarter in range, median of project medians), gross yield (rent × 12 ÷ median non-landed resale $psf over the last 4 quarters). Rent and yield are *scoped* metrics (computed from rental rows for a scope, not from the transaction rows). Use `metricFor(key, scope)` with scopes `{t:'sg'|'seg'|'d'|'p', id}` everywhere, and cache it per recompute.

## Insight tabs (detail panel, current scope + filters)
- **Lease stage:** bands by remaining lease at the **range start** (rem + (mi − startMi)/12): FH, 999, 95+, 90–95, 85–90, 80–85, 70–80, 60–70, < 60, unknown. Show same-project CAGR for $psf and price, total growth, and the number of repeat observations. This answers "if I buy at stage X, how did it grow?".
- **Floor level:** floor groups (landed/none, basement, 01–05 … 41+). The premium vs 01–05 = median over units of (median $psf in band ÷ median $psf at 01–05) − 1, within the same project × size band, needing ≥ 5 units. Show velocity and share. There's no per-floor unit stock, so this isn't a turnover rate.
- **Sale lifecycle:** a by-sale-type table; $psf by lease age (years since lease start × sale type); and the premium of each sub sale or resale over its unit's own whole-archive new-sale median, by years since launch. Thin until the archive grows.
- **Unit size:** per band: tx, share, velocity, price, $psf, area, CAGR.
- **Rentals:** for the selection, by property type, and by segment at the SG level: rent, change vs 4 quarters earlier, number of projects, yield.

## Pinned comparison
- **Pinning:** up to 8 pins of any scope, from the detail header, the project list, the segment rows or the compare table.
- **Colours:** a stable colour slot per pin (colour follows the entity, never its rank). Slots use the 8-hue categorical order `--s1..--s8`.
- **Persistence:** localStorage `pins`.
- **Chart:** index (rebased to 100 at each pin's first covered period) of $psf or price; or $psf, price, transactions or rent levels.
- **Merits table:** tx, velocity, price, $psf, area, lease, CAGRs, total growths, rent, yield, % harmonised. The best value among pins is highlighted for growth, yield and velocity.

## Map
- **Choropleth:** 28 districts. Magnitude metrics use a single-hue 5-class quantile scale; growth metrics use a diverging amber–teal scale centred on 0, split into thirds on each side. Districts with no data get a hatched pattern.
- **Interaction:** hover shows a tooltip; click zooms to the district and shows its project dots (sized by transactions).
- **Overlay:** CCR and RCR outlines.

## Performance (≈130k rows)
- **Caching:** cache `summarize()` and `growth()` per row-array identity (WeakMap), rebuilt each recompute. Cache rent stats and `metricFor` per scope.
- **Render order:** render the map and detail first; render pins and the compare table on a 30 ms timeout.
- **Target:** a full recompute under ~0.7 s (it was 2.2 s before the caches).

## Testing before publishing
1. `node --check` on the extracted script, and no leftover `__X__` placeholders.
2. Playwright (`playwright-core`, pointing at `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`; route cdnjs to a local `chart.js@4.4.1` file) with no page errors across every method × statistic × map metric.
3. Pandas cross-checks (see condo-data-build), the CAGR identity, and a gross-up check (psf ÷ 1.05 at 5%).
4. Screenshots: overview, a district (zoom + list), a project, every tab, pins, dark mode, and 390 px mobile.
5. Never publish illustrative numbers in docs. Compute them.
