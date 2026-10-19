---
name: hdb-dashboard-build
description: Assemble aggregated HDB resale-price JSON (hdb-data-aggregation) and a map outline (hdb-map-outline) into one interactive, self-contained HTML dashboard — map with global year-range/flat-type/Statistic (median/mean/lowest/highest) toggles driving color+size, a quantile-binned single-hue legend, town/street drill-down with ranked bars (streets only) and town/nationwide benchmarks, a comparison table sharing the map's controls, and per-entity rank badges throughout. Final step after hdb-data-ingestion + hdb-data-aggregation.
---

# HDB resale dashboard build

`assets/dashboard_template.html` is a complete working implementation — read and edit it rather than starting fresh.

## Architecture

Single self-contained HTML, inline CSS/JS, no build step.
- Chart.js via pinned CDN `<script>` (`cdnjs.../Chart.js/4.4.1/chart.umd.min.js`) — **verify the version path actually resolves**; a 404 fails silently (page loads, `Chart` is `undefined`, looks exactly like "graph doesn't appear").
- Plain SVG for the map (not a charting lib).
- Vanilla JS — no framework needed for this much interactivity.

## Getting data into the file

Don't hand-type/paste JSON into the HTML you're authoring. Template with placeholders (`const DATA = __STREET_DATA_JSON__;`), substitute from disk via a short Python script, validate after: grep for leftover `__`, `node --check` the extracted `<script>` block (a syntax error anywhere silently breaks the whole page).

## Data model: 18-field records, two data sources per entity

```js
const F = {
  YEAR:0, N:1,
  PRICE_MEAN:2, PRICE_MEDIAN:3, PRICE_MIN:4, PRICE_MAX:5,
  LEASE_MEAN:6, LEASE_MEDIAN:7, LEASE_MIN:8, LEASE_MAX:9,
  AREA_MEAN:10, AREA_MEDIAN:11, AREA_MIN:12, AREA_MAX:13,
  PSF_MEAN:14, PSF_MEDIAN:15, PSF_MIN:16, PSF_MAX:17,
};
```

One generic render function (`selectSeries(title, breadcrumbHtml, byFt, combinedRecords, rankCtx)`) for street/town/nationwide alike — only the data passed in, title, and rank peer-set differ. Two sources:
- `byFt` (per flat_type, e.g. `STREET_DATA[town][street]`) → **chart + data table** (user wants a flat-type breakdown there).
- `combinedRecords` (all types combined, e.g. `STREET_YEAR[town][street]`) → **mini-stats + ranks** (consistent regardless of which flat-type pills are toggled; only this has a statistically valid overall median). Say so in the UI.

## The global Statistic toggle: median / mean / lowest / highest — applies everywhere

One toggle, once, near the map. Changes what every price/lease/$psf figure means: map color, comparison table, street bars, detail-view mini-stats, detail-view chart's price/$psf lines.

```js
const STAT_FIELD_SUFFIX = {median:'MEDIAN', mean:'MEAN', low:'MIN', high:'MAX'};
let globalStatMode = 'median'; // default: more outlier-robust than mean
function dimField(dim, mode){ return F[`${dim}_${STAT_FIELD_SUFFIX[mode]}`]; } // dim: PRICE|LEASE|AREA|PSF

function statValue(dim, records, yl, yh){
  const fieldIdx = dimField(dim, globalStatMode);
  const recs = filterRange(records, yl, yh);
  // low/high combine EXACTLY across a multi-year range (min of each year's min);
  // median/mean combine via a weighted-average approximation, same as elsewhere.
  if(globalStatMode==='low') return minField(recs, fieldIdx);
  if(globalStatMode==='high') return maxField(recs, fieldIdx);
  return weightedMean(recs, fieldIdx);
}
```

Remove separate "Lowest/Highest price" catalog entries once this exists — redundant with the toggle. Catalog collapses from ~8 to ~6 entries (price, lease, psf, CAGR price, CAGR psf, total growth — velocity separate, it's a count the toggle doesn't apply to).

Use getters for mode-dependent labels (cheap since render functions already re-run on mode change):
```js
price: {get label(){return `${STAT_MODE_LABELS[globalStatMode]} price`;}, compute:(r,yl,yh)=>statValue('PRICE',r,yl,yh), fmt:...}
```

Refresh every view on mode change WITHOUT resetting that view's own independent filters:
```js
let currentSeriesUpdate = null; // set when a detail view builds its own update()
function refreshEverything(){
  renderMap();
  if(compareBuilt) renderCompareTable();
  if(viewMode==='list' && activeTown) selectTown(activeTown, currentBarMetric);
  if(viewMode==='series' && currentSeriesUpdate) currentSeriesUpdate();
}
```

**What "n" means depends on mode** — for median/mean it's a confidence signal (n=200 means more than n=2); for low/high the figure IS one real transaction, and n means "floor/ceiling among n transactions." Label accordingly or `n=23` next to a single extreme reads as "23 transactions at this price":
```js
function nContext(n){ return globalStatMode==='low' ? `lowest of ${n} tx` : globalStatMode==='high' ? `highest of ${n} tx` : `n=${n}`; }
```
Any secondary figure shown alongside a main stat (e.g. a tooltip's psf/area/lease next to a price line) must read off the SAME `dimField(dim, globalStatMode)`, not a hardcoded mean/median — a real bug this dashboard shipped with briefly.

## The "range metrics" catalog — one definition, reused everywhere

`{label, compute(records,yl,yh), fmt(v)}` entries for price/lease/psf/area/CAGR-price/CAGR-psf/total-growth/velocity, used identically by map color toggle, comparison table columns, street-bar metric toggle, and detail-view rank badges. Write "price" once, not four times (they'll drift otherwise).

```js
function filterRange(r,yl,yh){ return r.filter(x=>x[F.YEAR]>=yl && x[F.YEAR]<=yh); }
function weightedMean(r,i){ const n=r.reduce((a,x)=>a+x[F.N],0); return n?r.reduce((a,x)=>a+x[i]*x[F.N],0)/n:null; }
function minField(r,i){ return r.length?Math.min(...r.map(x=>x[i])):null; }
function maxField(r,i){ return r.length?Math.max(...r.map(x=>x[i])):null; }
function cagrField(r,i){ /* (last/first)^(1/years)-1, first/last year present */ }
function totalGrowthField(r,i){ /* (last/first-1), NOT annualized */ }
```

CAGR and total growth: don't annualize both (one earlier version computed "growth" as mean-of-YoY-%-changes — also annualized, redundant with CAGR). Sanity check: `(1+CAGR/100)^years == 1+total_growth/100`.

## Ranking against peers

```js
function computeRank(metricKey, yl, yh, rankCtx, activeTypes){
  if(!rankCtx || rankCtx.level==='sg') return '';
  const [peersObj, perTypeMap, ownKey] = rankCtx.level==='street'
    ? [STREET_YEAR[rankCtx.town], STREET_DATA[rankCtx.town], rankCtx.street]
    : [TOWN_YEAR, TOWN_AGG, rankCtx.town];
  const entries = Object.keys(peersObj).map(k=>{
    const combined = combinedForSelection(peersObj[k], perTypeMap[k], activeTypes);
    return {k, v: RM[metricKey].compute(combined,yl,yh)};
  }).filter(e=>e.v!=null);
  entries.sort((a,b)=>b.v-a.v);
  const idx = entries.findIndex(e=>e.k===ownKey);
  return idx<0 ? '' : `#${idx+1} of ${entries.length}`;
}
```
Attach to every mini-stat with a meaningful peer group ("$450k" → "$450k — #6 of 26 towns"). Skip for nationwide (no peer) and chart-metric-specific stats.

## Flat-type subset combination (client-side; no precomputed data for arbitrary subsets)

- `n` and every **mean** field: recombine exactly (n-weighted sum).
- Every **min/max** field: recombine exactly (`Math.min`/`Math.max`).
- Every **median** field: approximate only (n-weighted average of selected types' medians) — don't hide this.
- If selection covers everything the entity has, skip approximation, use the exact precomputed record (check via `every type present is in selection`, not a fixed master list).

```js
const COMBINE_DIMS = ['PRICE','LEASE','AREA','PSF'];
function combineByYearApprox(perTypeObj, selectedTypes){
  const acc = {};
  selectedTypes.forEach(ft=>(perTypeObj[ft]||[]).forEach(r=>{
    const y=r[F.YEAR];
    if(!acc[y]){ acc[y]={n:0}; COMBINE_DIMS.forEach(d=>acc[y][d]={meanN:0,medN:0,min:Infinity,max:-Infinity}); }
    const a=acc[y], n=r[F.N]; a.n+=n;
    COMBINE_DIMS.forEach(d=>{ const ad=a[d];
      ad.meanN+=r[F[`${d}_MEAN`]]*n; ad.medN+=r[F[`${d}_MEDIAN`]]*n;
      ad.min=Math.min(ad.min,r[F[`${d}_MIN`]]); ad.max=Math.max(ad.max,r[F[`${d}_MAX`]]);
    });
  }));
  return Object.entries(acc).map(([y,a])=>{
    const rec=[+y,a.n]; COMBINE_DIMS.forEach(d=>{ const ad=a[d]; rec.push(ad.meanN/a.n, ad.medN/a.n, ad.min, ad.max); });
    return rec;
  }).sort((x,y2)=>x[0]-y2[0]);
}
function isFullSelection(perTypeObj, sel){ return Object.keys(perTypeObj).every(ft=>sel.includes(ft)); }
function combinedForSelection(exact, perTypeObj, sel){ return isFullSelection(perTypeObj,sel) ? exact : combineByYearApprox(perTypeObj,sel); }
```

Toggle lives once, near the map (drives comparison table + street bars too). A detail view's existing flat-type chart-pills double as driving its own mini-stats/ranks (one control, not two to keep in sync) — default them to the global selection, intersected with what the entity has, when the view opens.

## Filters: global vs. per-detail-view

**Global** (map, comparison table, street bars — one shared state): Statistic, year range, flat type.
**Per detail-view**: own flat-type pills (chart + mini-stats via `combinedForSelection`), own year range (chart + table + mini-stats/ranks), remaining-lease range and price range (chart/table only — deliberately always mean-based regardless of Statistic mode, to avoid re-deriving bounds/labels on every mode change; say so in the filter's own label).

State plainly that lease/price filters act on the yearly aggregate (can drop a whole year's point for a flat type, not individual transactions) and don't affect mini-stats.

## Chart view switcher

Price and $psf (Statistic-mode-aware: `field` is a FUNCTION, `()=>dimField('PRICE',globalStatMode)`, not a static index), a min–max range band (two lines, `fill:'+1'`, always literal min/max regardless of mode — the point of this view is the full spread), transaction volume (bar). Surface transaction count in every tooltip, labeled per "What n means" above.

## The map

One year-range slider + flat-type toggle + Statistic toggle, all near the map, all driving map + comparison table + street bars identically. Size = **always** velocity (don't double its meaning). Color toggles among price/lease/psf/CAGR-price/CAGR-psf/total-growth (6 — not low/high price separately, see Statistic toggle above). Pronounced sizing: `r = 7 + 24*normalized_velocity`, not subtle.

**Color scale**: single hue, 5 classes, light→dark (not a 2-hue gradient — muddy middle; not a 5-hue rainbow — needs legend-reading). Quantile-binned, not fixed thirds:
```js
const PALETTE_5 = ['#DCEEEA','#9FD3C7','#4FA895','#0E7C6B','#054A3F'];
function quantileBreaks(values, k){
  const v = values.filter(x=>x!=null).sort((a,b)=>a-b);
  if(!v.length) return null;
  return Array.from({length:k+1},(_,i)=>v[Math.min(v.length-1, Math.round(i/k*(v.length-1)))]);
}
```
**Legend**: 4 bold labels at internal seams + 2 smaller/lighter labels at the overall min/max endpoints (omitting the endpoints was tried and reverted — no way to read the overall range without them). Compact format here only (`$388k` not `$388,000`).

`null` (no data for metric+range+flat-type) → distinct gray/dashed circle, never defaults to one end of the scale. `LIM CHU KANG` (defunct town, data stops 1998) renders this way for any post-1998 range — expected, confirm during testing.

## Multi-level navigation: streets, town/SG benchmarks

- Two benchmark rows above streets: "All Singapore (average)" and "Whole town (average)," visually distinct, click → nationwide/town combined data.
- Metric toggle (same catalog + velocity) above the list.
- **Bars for streets only.** Benchmark rows show the number, no bar. (A shared min/max scale across streets+benchmarks was tried: nationwide velocity is a sum across 27 towns — 50-100x any single street — which collapsed every street bar toward zero; nationwide "lowest price" similarly compressed from the other end. A capped/clipped benchmark bar was also rejected — still implies a comparability that usually isn't there.)
```js
const streetVals = rows.map(r=>r.val).filter(v=>v!=null);
const vMin=Math.min(...streetVals), vMax=Math.max(...streetVals);
function barPct(v){ return v==null?0:Math.min(100,Math.max(2,Math.round(100*(v-vMin)/((vMax-vMin)||1)))); }
```
- "Whole market" also gets a distinct separate map control (dashed marker outside the landmass) — a double-click-means-something-else interaction is easy to miss.

## Velocity display

Always the currently-active range (map's or a detail view's own). Nationwide: show both total and average-per-township (different questions). Street/town: value + rank vs. peer set.

## Comparison table

Collapsible, shares the map's year range + flat-type + Statistic controls (re-render on any change, caption says so). Columns: streets active in range, total tx, velocity, every RM entry. Click-to-sort, `null` values pinned to the bottom regardless of direction.

## Units

`sqft = sqm * 10.7639`, show both everywhere area appears. One helper, used consistently.

## Styling

CSS custom properties, light/dark pair (`:root` + `prefers-color-scheme` + `[data-theme]` override). Non-default palette (this build: teal/amber `#0E7C6B`/`#C97A2B`). Geometric display face for headings/numbers (Space Grotesk), plain sans for body (Inter), Google Fonts.

## Testing

`node --check` only catches syntax. Pull pure-JS helpers (`filterRange, weightedMean, minField, maxField, cagrField, totalGrowthField, statValue, quantileBreaks, combineByYearApprox`, the `RM` catalog) into a standalone script, unit-test in Node:
- Weighted average (median/mean mode).
- `statValue` all 4 modes against the same fake records — catches a mode silently not propagating somewhere.
- CAGR + total-growth pair, check the `(1+CAGR/100)^years` identity.
- Flat-type-subset combine vs. hand-computed weighted n/mean/min/max, for >1 dimension (not just price).
- A quantile-bucket assignment.

Then cross-check ≥1 real figure (e.g. one town's price + CAGR, in ≥2 Statistic modes) against manual pandas — unit tests catch formula bugs, pandas cross-check catches data-plumbing bugs (wrong field index/file), neither alone catches both.

## Publishing checklist

1. No leftover `__` placeholders.
2. `node --check` on extracted script.
3. Chart.js CDN version actually resolves.
4. Math unit tests (all 4 Statistic modes) + ≥1 pandas cross-check.
5. File size: ~7MB total for full 1990–2026/27-town/~600-street dataset at the 18-field schema; tens of MB = too-fine aggregation upstream.
6. Click through all 4 Statistic modes live — confirm map/table/bars/open-detail-view all update without resetting unrelated filters.
