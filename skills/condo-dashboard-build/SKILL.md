---
name: condo-dashboard-build
description: Build and extend the Singapore private-residential dashboard (GitHub Pages) - 28-district choropleth with CCR/RCR and MRT/LRT overlays, map search, drag/scroll pan-zoom and a home button, global Statistic / growth-method / quarter-level time controls, filters on every URA field incl. bedroom size bands and harmonised floor areas, same-project repeat-sales growth, lease-stage / floor / sale-lifecycle / unit-size / rental insight tabs, custom multi-selections (any mix of districts, projects and segments aggregated as one), and a pinned side-by-side comparison of regions, projects and selections. Final step after condo-ura-ingestion, condo-data-build and condo-district-map.
---

# Private-residential dashboard build

`assets/dashboard_template.html` is the complete current implementation (one file: inline CSS and vanilla JS, Chart.js 4.4.1 from the cdnjs pin, SVG map, MRT data embedded). **To reproduce the live dashboard exactly, use this file unchanged:** copy it to `template/dashboard_template.html` in the repo, and `pipeline/build.py` fills the `__EARLIEST_MONTH__`, `__LATEST_MONTH__`, `__TOTAL_TX__`, `__TOTAL_PROJECTS__` and `__PULLED_AT__` placeholders and writes `site/index.html` next to `site/data/tx.json` and `site/data/map.json`. Keep the skill's copy and the repo's copy byte-identical. Read and edit it rather than starting again; the sections below describe what it does so changes stay consistent. `assets/refresh.yml` is the daily GitHub Actions workflow (fetch → archive → geocode → commit store → build → validate → deploy Pages). Methods are written up in `references/dashboard-methods.md`.

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
price, $psf, area, lease left, CAGR $psf, CAGR price, total growth $psf, total growth price, velocity (tx ÷ years of data in range), rent ($psf/month, latest quarter in range, median of project medians), gross yield (rent × 12 ÷ median non-landed resale $psf over the last 4 quarters). Rent and yield are *scoped* metrics (computed from rental rows for a scope, not from the transaction rows). Use `metricFor(key, scope)` with scopes `{t:'sg'|'seg'|'d'|'p'|'m', id}` everywhere, and cache it per recompute. `t:'m'` is a custom selection (below); every function that takes a scope (`rowsForScope`, `scopeLabel`, `rentRows` via `rentMatch`, pins, charts, tabs) must handle it.

## Insight tabs (detail panel, current scope + filters)
- **Lease stage:** bands by remaining lease at the **range start** (rem + (mi − startMi)/12): FH, 999, 95+, 90–95, 85–90, 80–85, 70–80, 60–70, < 60, unknown. Show same-project CAGR for $psf and price, total growth, and the number of repeat observations. This answers "if I buy at stage X, how did it grow?".
- **Floor level:** floor groups (landed/none, basement, 01–05 … 41+). The premium vs 01–05 = median over units of (median $psf in band ÷ median $psf at 01–05) − 1, within the same project × size band, needing ≥ 5 units. Show velocity and share. There's no per-floor unit stock, so this isn't a turnover rate.
- **Sale lifecycle:** a by-sale-type table; $psf by lease age (years since lease start × sale type); and the premium of each sub sale or resale over its unit's own whole-archive new-sale median, by years since launch. Thin until the archive grows.
- **Unit size:** per band: tx, share, velocity, price, $psf, area, CAGR.
- **Rentals:** for the selection, by property type, and by segment at the SG level: rent, change vs 4 quarters earlier, number of projects, yield.

## Custom selection (multi-select)
- **State:** `SEL` = array of members `{t:'sg'|'seg'|'d'|'p', id}`; `MS` = multi-select mode. With 2+ members the page is at `V.level='multi'` and `currentScope()` returns `selScope(SEL)` = `{t:'m', id, m}`, where `m` is the members sorted by `memKey` (`t:id`) and `id` is those keys joined by commas (so the same set always has the same id, for caching and pins). With 1 member the page just shows that member; with 0 it goes back to All Singapore (`applySel()`).
- **Rows:** `rowsForScope({t:'m'})` = the **union** of the members' rows (deduplicated with a `Uint8Array` seen-mask, sorted ascending), cached per recompute in `MROWS` (cleared in `doRecompute`). A project inside a selected district therefore counts once. If any member is `sg`, the rows are `ALL`. Rentals match if any member matches (`rentMatch`).
- **Adding and removing:** `toggleSel(item)`. Triggered by Shift / Cmd / Ctrl-click on a district or project dot or project-list row (`clickItem`), by a plain click while multi-select mode is on (the two-squares button under the globe on the map), by "＋ add to selection" on project-list rows and the CCR/RCR/OCR rows, and by Shift+Enter or Shift-click on a search result. When `SEL` is empty, the first toggle seeds it with the currently open scope (unless that is All Singapore, the item itself, or a district when the item is a project inside it). "⧉ Combine" in the detail header seeds `SEL` with the open scope and turns multi-select on. Any normal navigation (`openSG/openSeg/openDistrict/openProject`) clears `SEL` unless called from `applySel` (`_keepSel`).
- **Panel at `multi`:** crumbs "All Singapore › Custom selection"; title "Custom selection · n items"; a chip tray (× per member, Clear); the usual mini-stats, chart (all breakdowns, incl. by market segment), insight tabs on the combined rows; then "In this selection", one row per member with its own $psf, price, tx, velocity and CAGR, click to open, × remove. No peer ranks.
- **Map at `multi`:** selected districts get an orange outline (`.dist.msel`, raised to the top); project dots are drawn for every selected district and for the districts of selected projects; selected projects get the orange ring. The view is not refitted when the selection changes. The compare table outlines selected districts. The key row adds "in your selection".

## Pinned comparison
- **Pinning:** up to 8 pins of any scope, including custom selections, from the detail header, the project list, the segment rows or the compare table. A selection pin is stored as `{t:'m', id, m, slot}`, labelled by its members (up to 3 names, else the first two + "n more"), and reopening it restores the whole selection. Invalid stored pins (missing projects) are dropped on load.
- **Colours:** a stable colour slot per pin (colour follows the entity, never its rank). Slots use the 8-hue categorical order `--s1..--s8`.
- **Persistence:** localStorage `pins`.
- **Chart:** index (rebased to 100 at each pin's first covered period) of $psf or price; or $psf, price, transactions or rent levels.
- **Merits table:** tx, velocity, price, $psf, area, lease, CAGRs, total growths, rent, yield, % harmonised. The best value among pins is highlighted for growth, yield and velocity.

## Map
- **Choropleth:** 28 districts. Magnitude metrics use a single-hue 5-class quantile scale; growth metrics use a diverging amber–teal scale centred on 0, split into thirds on each side. Districts with no data get a hatched pattern.
- **Interaction:** hover shows a tooltip; click zooms to the district and shows its project dots (sized by transactions).
- **View state:** `VIEW` = current viewBox; `applyZoom(force)` refits (`fitBox()`: the open district's bbox padded by 35% + 20, aspect locked; else the full island) only when the fit key changes (`'d'+V.d` / `'sg'`; at `multi` the key is kept) or when forced. `setView()` clamps width to [viewBox/60, viewBox × 1.05] and the centre to the island, then rescales: district labels and project dots grow on screen by min(√zoom, 2.2 / 2.5); district value labels show when area × zoom² ≥ 7 km²; MRT markers scale by min(zoom^0.6, 3.2), interchanges 1.3× and pie-split by line.
- **Pan and zoom:** drag to pan, wheel / trackpad / pinch to zoom (viewBox-based, clamped to 1×–60×), plus + / − / fit buttons (hidden under 600 px, where pinch is used). Wheel zoom factor exp(deltaY × 0.0022), or × 0.012 when ctrlKey (trackpad pinch); `touch-action:none` on the SVG; pointer events handle one-finger pan and two-finger pinch. The view is refitted only when the open district changes, or on Fit / Home, so filter changes never undo the user's panning. A drag suppresses the click that follows it. Labels, dots and station markers are rescaled on every view change.
- **Controls (top right, stacked):** a round globe Home button (returns to All Singapore, clears the selection and search, refits the island; filled teal while at All Singapore), the multi-select toggle (filled orange when on; the bottom-left hint pill turns orange and changes text), + / −, and fit (⤢).
- **Search (top left, `#mapQ`):** a box on the map finds projects, landed streets and MRT/LRT stations (all words must match; exact and prefix matches first, then by transactions). A project opens its panel and centres the map on it with a highlight ring; a station centres the map on the station and highlights it. Results show district and transaction count; stations show their line-colour dots and codes. Arrow keys, Enter, Escape; up to 30 results. Shift+Enter / Shift-click adds the project to the custom selection instead.
- **Overlays (independent toggles):** CCR and RCR outlines; MRT/LRT lines and stations, coloured by line (interchanges split by line). Station names appear from about 2.6× zoom for interchanges and 4.5× for all. The MRT toggle is remembered in localStorage `mrt` (default on). Hover a station for its name, codes and lines; click to centre on it. Line colours are tokens `--mrt-NS/EW/NE/CC/DT/TE/LRT` (LTA colours in light mode, lifted variants in dark mode). The station data is embedded in the template as `MRT` and is rebuilt with `condo-district-map/scripts/build_mrt_overlay.py` when new stations open.

## Performance (≈130k rows)
- **Caching:** cache `summarize()` and `growth()` per row-array identity (WeakMap), rebuilt each recompute. Cache rent stats and `metricFor` per scope.
- **Render order:** render the map and detail first; render pins and the compare table on a 30 ms timeout.
- **Target:** a full recompute under ~0.7 s (it was 2.2 s before the caches).

## Testing before publishing
1. `node --check` on the extracted script, and no leftover `__X__` placeholders.
2. Playwright (`playwright-core`, pointing at `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`; route cdnjs to a local `chart.js@4.4.1` file) with no page errors across every method × statistic × map metric.
3. Pandas cross-checks (see condo-data-build), the CAGR identity, and a gross-up check (psf ÷ 1.05 at 5%).
4. Interaction checks: search (project → panel + ring; station → centred), drag doesn't trigger a district click, wheel zoom, Home returns to All Singapore from a district, Shift-click D10 then D11 gives a 2-item selection, Shift+Enter in search adds a project, pin two selections, reload and reopen a selection pin, remove a chip.
5. Screenshots: overview, a district (zoom + list), a project, a custom selection, every tab, pins, dark mode, and 390 px mobile (no horizontal scroll).
6. Never publish illustrative numbers in docs. Compute them.
