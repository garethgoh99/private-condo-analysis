"""Build the 28-postal-district map (and the CCR/RCR/OCR overlay) as SVG paths.

There is no official polygon file for postal districts: URA defines them as groups of
postal sectors. So the shapes are derived:

1. Land = official URA Master Plan 2019 region boundaries (data.gov.sg), mainland + any
   island that actually has private housing (Sentosa). Projected to SVY21 metres.
2. Every located private project (URA x/y, or OneMap geocode) is a labelled point:
   (postal district, market segment). Planning areas with NO private housing at all get
   a light grid of anchor points with their conventional district (ANCHORS below), so
   Tuas, the catchments, Seletar etc. land in the right district instead of whichever
   is nearest.
3. A 100 m raster over the land is labelled by distance-weighted vote of the nearest
   points, using the joint (district, segment) label, so district and segment edges line
   up where they coincide. It is then smoothed, small fragments are folded into their
   neighbours, and the result is polygonised, simplified as one coverage (no gaps or
   overlaps between neighbours) and clipped to the real coastline.

The result is approximate at the edges but consistent with the data: each project sits
inside its own district's shape. Re-run when many new projects appear:
    python tools/build_district_map.py STORE_DIR
Writes data/district_map.json.
"""
import json
import os
import sys

import numpy as np
import pandas as pd
import rasterio.features
from affine import Affine
from pyproj import Transformer
from scipy import ndimage
from scipy.spatial import cKDTree
from shapely import coverage_simplify
from shapely.geometry import Point, mapping, shape
from shapely.ops import polylabel, transform, unary_union

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
from harmonize import load_clean  # noqa: E402

CELL = 100.0          # raster cell, metres
K = 10                # neighbours in the vote
MIN_FRAG_CELLS = 120  # fragments smaller than ~1.2 km2 get absorbed by neighbours
SIMPLIFY_M = 120.0
REGION_ID = "d_bf4d24df9129d5a8ff8cf82e20959ee0"   # MP2019 Region Boundary (No Sea)
PLANNING_ID = "d_4765db0e87b9c86336792efe8a1f7a66"  # MP2019 Planning Area Boundary (No Sea)

# Planning areas with no private housing -> conventional postal district + segment.
ANCHORS = {
    "TUAS": ("22", "OCR"), "PIONEER": ("22", "OCR"), "BOON LAY": ("22", "OCR"),
    "LIM CHU KANG": ("24", "OCR"), "WESTERN WATER CATCHMENT": ("24", "OCR"),
    "SELETAR": ("28", "OCR"), "SIMPANG": ("27", "OCR"), "CHANGI BAY": ("17", "OCR"),
    "PAYA LEBAR": ("19", "OCR"), "STRAITS VIEW": ("01", "CCR"), "MARINA EAST": ("01", "CCR"),
}
ANCHOR_SPACING = 900.0  # metres between anchor points

VB_W = 1000.0  # SVG viewBox width; height follows the land's aspect ratio
PAD = 12.0


def to_svy21():
    t = Transformer.from_crs("EPSG:4326", "EPSG:3414", always_xy=True)
    return lambda x, y, z=None: t.transform(x, y)


def main(store):
    geo = os.path.join(store, "geo")
    T = to_svy21()

    _, projects = load_clean(store)
    pts = projects.dropna(subset=["x"])
    # segment by project is consistent in the data; district is the project's modal district
    labels = (pts["district"] + "|" + pts["segment"]).to_numpy()
    xy = pts[["x", "y"]].to_numpy()

    # ---- land ----
    regions = json.load(open(os.path.join(geo, f"{REGION_ID}.geojson")))
    land_all = unary_union([transform(T, shape(f["geometry"])) for f in regions["features"]])
    polys = sorted(getattr(land_all, "geoms", [land_all]), key=lambda g: g.area, reverse=True)
    keep = [polys[0]] + [g for g in polys[1:] if any(g.contains(Point(p)) for p in xy) and g.area > 1e6]
    land = unary_union(keep).buffer(0)
    print(f"land: kept {len(keep)} of {len(polys)} polygons ({land.area / 1e6:.0f} km2)")

    # ---- anchors for planning areas with no private housing ----
    pa = json.load(open(os.path.join(geo, f"{PLANNING_ID}.geojson")))
    ax, al = [], []
    for f in pa["features"]:
        name = f["properties"]["PLN_AREA_N"]
        if name not in ANCHORS:
            continue
        g = transform(T, shape(f["geometry"])).intersection(land)
        if g.is_empty:
            continue
        x0, y0, x1, y1 = g.bounds
        lab = "|".join(ANCHORS[name])
        n0 = len(ax)
        for gx in np.arange(x0 + ANCHOR_SPACING / 2, x1, ANCHOR_SPACING):
            for gy in np.arange(y0 + ANCHOR_SPACING / 2, y1, ANCHOR_SPACING):
                if g.contains(Point(gx, gy)):
                    ax.append((gx, gy)); al.append(lab)
        if len(ax) == n0:  # tiny area: one point
            p = g.representative_point(); ax.append((p.x, p.y)); al.append(lab)
    print(f"anchors: {len(ax)} points in {len(ANCHORS)} empty planning areas")
    allxy = np.vstack([xy, np.array(ax)]) if ax else xy
    alllab = np.concatenate([labels, np.array(al)]) if al else labels

    # ---- raster vote ----
    x0, y0, x1, y1 = land.bounds
    W, H = int(np.ceil((x1 - x0) / CELL)), int(np.ceil((y1 - y0) / CELL))
    tf = Affine(CELL, 0, x0, 0, -CELL, y1)
    landmask = rasterio.features.rasterize([(land, 1)], out_shape=(H, W), transform=tf, fill=0,
                                           all_touched=True).astype(bool)
    classes = sorted(set(alllab))
    cid = {c: i for i, c in enumerate(classes)}
    lab_idx = np.array([cid[c] for c in alllab])
    rr, cc = np.nonzero(landmask)
    cx = x0 + (cc + 0.5) * CELL
    cy = y1 - (rr + 0.5) * CELL
    d, nn = cKDTree(allxy).query(np.c_[cx, cy], k=K)
    w = 1.0 / np.maximum(d, 50.0) ** 2
    score = np.zeros((len(rr), len(classes)))
    for j in range(K):
        np.add.at(score, (np.arange(len(rr)), lab_idx[nn[:, j]]), w[:, j])
    grid = np.full((H, W), -1, int)
    grid[rr, cc] = score.argmax(1)

    # ---- smooth: majority over a 5x5 window, a few passes ----
    for _ in range(3):
        onehot = np.stack([ndimage.uniform_filter((grid == i).astype(float), size=5) for i in range(len(classes))])
        sm = onehot.argmax(0)
        grid = np.where(landmask, sm, -1)

    # ---- fold small fragments into their dominant neighbour ----
    for _ in range(6):
        changed = 0
        for i in range(len(classes)):
            comp, n = ndimage.label(grid == i)
            if n == 0:
                continue
            sizes = ndimage.sum(np.ones_like(comp), comp, index=np.arange(1, n + 1))
            biggest = int(np.argmax(sizes)) + 1
            for k in range(1, n + 1):
                if k == biggest and sizes[k - 1] >= 1:
                    continue  # keep each class's main body, however small
                if sizes[k - 1] >= MIN_FRAG_CELLS:
                    continue
                m = comp == k
                ring = ndimage.binary_dilation(m) & ~m & (grid >= 0)
                if ring.any():
                    vals = grid[ring]
                    grid[m] = np.bincount(vals, minlength=len(classes)).argmax()
                    changed += 1
        if not changed:
            break

    # ---- polygonise per joint class, then dissolve to districts and segments ----
    by_class = {}
    for geom, val in rasterio.features.shapes(grid.astype(np.int32), mask=grid >= 0, transform=tf):
        by_class.setdefault(int(val), []).append(shape(geom))
    cls_geoms = {classes[k]: unary_union(v) for k, v in by_class.items()}
    keys = list(cls_geoms)
    simp = coverage_simplify([cls_geoms[k] for k in keys], SIMPLIFY_M)
    land_s = land.simplify(25)
    cls_geoms = {k: g.intersection(land_s).buffer(0) for k, g in zip(keys, simp)}

    districts, segments = {}, {}
    for k, g in cls_geoms.items():
        dct, seg = k.split("|")
        districts.setdefault(dct, []).append(g)
        segments.setdefault(seg, []).append(g)
    districts = {k: unary_union(v).buffer(0) for k, v in districts.items()}
    segments = {k: unary_union(v).buffer(0) for k, v in segments.items()}
    missing = sorted(set(f"{i:02d}" for i in range(1, 29)) - set(districts))
    if missing:
        print("WARNING: districts with no shape:", missing)

    # check: share of projects inside their own district polygon
    ok = sum(districts.get(r.district) is not None and districts[r.district].buffer(60).contains(Point(r.x, r.y))
             for r in pts.itertuples())
    print(f"projects inside own district shape: {ok}/{len(pts)} ({ok / len(pts):.1%})")

    # ---- project to SVG viewBox ----
    s = (VB_W - 2 * PAD) / (x1 - x0)
    vb_h = (y1 - y0) * s + 2 * PAD

    def sv(x, y):
        return PAD + (x - x0) * s, PAD + (y1 - y) * s

    def path(g):
        out = []
        for poly in getattr(g, "geoms", [g]):
            if poly.geom_type != "Polygon" or poly.area < 4e4:
                continue
            for ring in [poly.exterior] + list(poly.interiors):
                c = [sv(x, y) for x, y in ring.coords]
                out.append("M" + "L".join(f"{a:.1f},{b:.1f}" for a, b in c[:-1]) + "Z")
        return "".join(out)

    def label_pt(g):
        main = max(getattr(g, "geoms", [g]), key=lambda p: p.area)
        p = polylabel(main, tolerance=20)
        return [round(v, 1) for v in sv(p.x, p.y)]

    seg_lines = unary_union([g.boundary for g in segments.values()]).difference(land_s.boundary.buffer(80))
    seg_path = []
    for ln in getattr(seg_lines, "geoms", [seg_lines]):
        if ln.length < 300:
            continue
        c = [sv(x, y) for x, y in ln.coords]
        seg_path.append("M" + "L".join(f"{a:.1f},{b:.1f}" for a, b in c))

    out = {
        "note": "Derived shapes: postal districts have no official boundary file. See tools/build_district_map.py.",
        "viewBox": [0, 0, VB_W, round(vb_h, 1)],
        "proj": {"x0": x0, "y1": y1, "s": s, "pad": PAD},  # svgX = pad+(X-x0)*s, svgY = pad+(y1-Y)*s (SVY21)
        "land": path(land_s),
        "districts": {k: {"path": path(g), "label": label_pt(g), "area_km2": round(g.area / 1e6, 1)}
                      for k, g in sorted(districts.items())},
        "segments": {k: {"path": path(g), "label": label_pt(g)} for k, g in sorted(segments.items())},
        "segment_lines": "".join(seg_path),
    }
    dst = os.path.join(os.path.dirname(__file__), "..", "data", "district_map.json")
    json.dump(out, open(dst, "w"), separators=(",", ":"))
    print(f"wrote {dst} ({os.path.getsize(dst) / 1024:.0f} KB)")

    # optional preview PNG for visual QA
    try:
        import cairosvg  # noqa: F401
    except ImportError:
        pass
    prev = os.path.join(os.path.dirname(__file__), "..", "build", "district_map_preview.svg")
    os.makedirs(os.path.dirname(prev), exist_ok=True)
    pal = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4", "#46f0f0", "#f032e6",
           "#bcf60c", "#fabebe", "#008080", "#e6beff", "#9a6324", "#fffac8", "#800000", "#aaffc3",
           "#808000", "#ffd8b1", "#000075", "#808080", "#a9a9a9", "#ff7f50", "#2e8b57", "#daa520",
           "#7b68ee", "#20b2aa", "#cd5c5c", "#6b8e23"]
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VB_W} {vb_h:.0f}" width="{VB_W}" '
           f'height="{vb_h:.0f}" style="background:#fff">']
    for i, (k, v) in enumerate(out["districts"].items()):
        svg.append(f'<path d="{v["path"]}" fill="{pal[i % len(pal)]}" fill-opacity=".55" stroke="#333" stroke-width=".8"/>')
    svg.append(f'<path d="{out["segment_lines"]}" fill="none" stroke="#000" stroke-width="3" stroke-dasharray="8 5"/>')
    for r in pts.itertuples():
        a, b = sv(r.x, r.y)
        svg.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="1.2" fill="#000" fill-opacity=".5"/>')
    for k, v in out["districts"].items():
        svg.append(f'<text x="{v["label"][0]}" y="{v["label"][1]}" font-size="14" font-family="sans-serif" '
                   f'font-weight="bold" text-anchor="middle">{k}</text>')
    for k, v in out["segments"].items():
        svg.append(f'<text x="{v["label"][0]}" y="{v["label"][1] + 18}" font-size="16" fill="#b00" '
                   f'font-family="sans-serif" text-anchor="middle">{k}</text>')
    svg.append("</svg>")
    open(prev, "w").write("".join(svg))
    print(f"preview: {prev}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "store")
