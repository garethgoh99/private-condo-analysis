---
name: condo-district-map
description: Build the 28 Singapore postal-district shapes (and the CCR/RCR/OCR overlay) for an SVG choropleth when no official boundary file exists - derived from URA's official Master Plan coastline plus where each district's projects sit, with anchors for areas without private housing. Use when (re)drawing the district map or adding districts/segments to a map-based property visualisation.
---

# Postal-district map

Postal districts have no official polygon file; URA defines them as groups of postal sectors. Don't hand-draw them or trust a random GeoJSON. Derive them with `scripts/build_district_map.py STORE` → `references/district_map.json`:

1. **Land:** the union of the URA MP2019 *Region Boundary (No Sea)* from data.gov.sg (`d_bf4d24df9129d5a8ff8cf82e20959ee0`), projected to SVY21. Keep the mainland plus any island containing a project (Sentosa); drop Jurong Island, Ubin, Tekong and the other islets. Fetch it in Actions with `tools/fetch_geo.py` (data.gov.sg poll-download, no key needed).
2. **Points:** every located project, labelled by the joint **(district, segment)**. Using the joint label makes district and segment edges coincide where they should.
3. **Anchors:** planning areas (MP2019 Planning Area, `d_4765db0e87b9c86336792efe8a1f7a66`) with no private housing get a 900 m grid of anchor points with their usual district:
   - Tuas, Pioneer, Boon Lay → 22
   - Lim Chu Kang, Western Water Catchment → 24
   - Seletar → 28
   - Simpang → 27
   - Changi Bay → 17
   - Paya Lebar (airbase) → 19
   - Straits View and Marina East → 01 / CCR

   Without these, D24 (Tengah, Lim Chu Kang) had no shape at all. Leave the Central Catchment unanchored, so its neighbours divide it naturally.
4. **Raster vote:** a 100 m grid over the land. Each cell takes the distance-weighted (1/d², d ≥ 50 m) vote of its 10 nearest points.
5. **Smoothing:** 3 passes of a 5×5 majority filter. Then fold fragments under 120 cells into their dominant neighbour, keeping each class's main body.
6. **Polygonise:** use `rasterio.features.shapes`, then **`shapely.coverage_simplify`** (120 m). Simplifying each polygon separately opens gaps and overlaps between neighbours. Clip to the real coastline, simplified at 25 m.
7. **Output:** SVG paths in a 1000-wide viewBox, with `proj` = {x0, y1, s, pad}. The page projects project dots with `svgX = pad + (X − x0)·s`, `svgY = pad + (y1 − Y)·s` (SVY21). Each district gets a label point from `polylabel` and its area in km² (only districts of 7 km² or more show a value on the map).

**QA:** check that at least 98% of projects fall inside their own district's shape (buffered by 60 m); it was 98.6% at build. Render the preview SVG and look at it. The CCR (D09/10/11 + downtown + Sentosa) and RCR ring should match URA's published segment map.

**Rendering:**
- **Districts:** filled `<path>` elements with `vector-effect:non-scaling-stroke`.
- **Segment overlay:** stroke only. CCR solid, RCR dashed, OCR not drawn (it's everything outside RCR).
- **Zoom:** on selecting a district, zoom the viewBox to its bounding box padded by 35%, keeping the aspect ratio fixed. Scale labels and dots by the zoom factor.
- **Labels:** colour each label by the luminance of its fill. Draw no text labels for segments, because they collide with the district numbers.

`references/district_names.json` holds the conventional district names (D01 Raffles Place, Cecil, Marina, People's Park … D28 Seletar).

Requirements: `shapely>=2.1 rasterio scipy affine pyproj`.
