---
name: hdb-map-outline
description: Build a simple geographic base map of Singapore for a resale-price dashboard — town centroid coordinates, a lat/lon-to-SVG projection that actually fills the available space, and a technique for tracing a coastline outline from any reference image. Use whenever building/fixing a map-based visualization of Singapore towns, or when a user uploads an outline/shape image for a map backdrop.
---

# HDB dashboard map & outline

Two independent things: town **positions** and a **coastline outline**. Use real sources — don't hand-draw either from memory.

## Town centroids

`references/town_coords.json` has all 26 standard HDB towns as `{TOWN_NAME: [lat, lon]}` — general geographic facts, safe to hardcode. Use directly.

## Projection: derive the bounding box from the TOWNS, not the landmass

Singapore's landmass spans roughly lat 1.15–1.47, lon 103.60–104.05 — but the 26 town centroids occupy a narrower band inside that (roughly lat 1.28–1.45, lon 103.71–103.96; towns are heartlands, not at the water's edge). Projecting onto the full landmass box crowds every bubble into the middle third. Fix: compute the box from the town coordinates themselves, padded 10–20%:

```js
const lats = Object.values(TOWN_COORDS).map(c=>c[0]), lons = Object.values(TOWN_COORDS).map(c=>c[1]);
const pad = 0.12;
const latSpan = Math.max(...lats)-Math.min(...lats), lonSpan = Math.max(...lons)-Math.min(...lons);
const LAT_MIN = Math.min(...lats)-latSpan*pad, LAT_MAX = Math.max(...lats)+latSpan*pad;
const LON_MIN = Math.min(...lons)-lonSpan*pad, LON_MAX = Math.max(...lons)+lonSpan*pad;
function project(lat, lon){
  const x = MAP_LEFT + (lon-LON_MIN)/(LON_MAX-LON_MIN)*(MAP_RIGHT-MAP_LEFT);
  const y = MAP_TOP + (LAT_MAX-lat)/(LAT_MAX-LAT_MIN)*(MAP_BOTTOM-MAP_TOP); // y inverted
  return [x, y];
}
```

Never derive the box from the coastline outline's own extent — related but not the same thing, and coupling them is the bug this fixes.

## Safety net: point-in-polygon + pull-to-centroid

A traced outline never exactly matches real geography — a coastal town (Marine Parade, in practice) can project just outside it. Don't hand-tune padding per case; apply a general safeguard to every projected point unconditionally (no-op if already inside):

```js
function pointInPolygon(x,y,poly){
  let inside=false;
  for(let i=0,j=poly.length-1;i<poly.length;j=i++){
    const xi=poly[i][0], yi=poly[i][1], xj=poly[j][0], yj=poly[j][1];
    if(((yi>y)!==(yj>y)) && (x < (xj-xi)*(y-yi)/(yj-yi)+xi)) inside=!inside;
  }
  return inside;
}
function clampToOutline(x,y){
  if(pointInPolygon(x,y,OUTLINE_PTS)) return [x,y];
  const c = OUTLINE_PTS.reduce((a,p)=>[a[0]+p[0]/OUTLINE_PTS.length, a[1]+p[1]/OUTLINE_PTS.length],[0,0]);
  let cx=x, cy=y;
  for(let i=0;i<25;i++){ cx+=(c[0]-cx)*0.08; cy+=(c[1]-cy)*0.08; if(pointInPolygon(cx,cy,OUTLINE_PTS)) break; }
  return [cx,cy];
}
```

Pull toward centroid in steps, don't clamp to nearest edge (bunches multiple towns onto one point).

## Tracing an outline from a reference image

If the shape is a **single solid color** on plain/transparent background, extract programmatically:

1. Build a binary mask (threshold alpha if present; else color, e.g. green: `(g>r+15)&(g>b+15)`).
2. `cv2.findContours` (`opencv-python-headless`), take largest by area.
3. `cv2.approxPolyDP(contour, epsilon, True)`, `epsilon = 0.003–0.005 * arcLength` → clean 20–40pt polygon.
4. **Verify visually** — overlay the simplified polygon on the original (`cv2.polylines`), adjust epsilon if it doesn't hug the shape.
5. Rescale from image pixel space to the SVG viewBox region (same region used for town projection, so they align):

```python
minx,maxx,miny,maxy = min(xs),max(xs),min(ys),max(ys)
def scale(pt):
    x,y = pt
    return (MAP_LEFT+(x-minx)/(maxx-minx)*(MAP_RIGHT-MAP_LEFT), MAP_TOP+(y-miny)/(maxy-miny)*(MAP_BOTTOM-MAP_TOP))
```

If it's a **line drawing** (no fill to mask), eyeball vertices instead — say so plainly, trace conservatively, and label the coastline as approximate/orientation-only in the dashboard UI.

`scripts/trace_outline.py` implements the full pipeline for the filled-shape case.

## Rendering

Single closed `<path>` (`M x,y L x,y ... Z`) beneath town markers — light fill, low-opacity stroke, reads as backdrop not data. Markers as `<circle>`, sized/colored by metrics. Outline + markers in the same `<svg>` (one coordinate space).
