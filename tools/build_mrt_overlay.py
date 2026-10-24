"""Build the MRT/LRT overlay embedded in the dashboard template as `const MRT = {...}`.

Usage: python build_mrt_overlay.py sg-rail.geojson mrt.json
  sg-rail.geojson: https://raw.githubusercontent.com/cheeaun/sgraildata/master/data/v1/sg-rail.geojson
  (OpenStreetMap contributors, ODbL). Re-run when new stations open, then paste mrt.json over the
  `const MRT = ...;` line in dashboard_template.html.
Projection matches site/data/map.json "proj" (WGS84 -> SVY21 -> SVG viewBox); update P if the district map is rebuilt.
Needs pyproj and shapely.
"""
import json, sys
from pyproj import Transformer
from shapely.geometry import shape, LineString, MultiLineString
src, out = sys.argv[1], sys.argv[2]
P = {'x0': 2667.5380000340847, 'y1': 50256.33430014718, 's': 0.02002602398231247, 'pad': 12.0}
t = Transformer.from_crs("EPSG:4326", "EPSG:3414", always_xy=True)
def sv(lon, lat):
    X, Y = t.transform(lon, lat)
    return round(P['pad'] + (X - P['x0']) * P['s'], 1), round(P['pad'] + (P['y1'] - Y) * P['s'], 1)
COL = {'red':'NS','green':'EW','yellow':'CC','orange':'CC','purple':'NE','blue':'DT','darkslateblue':'DT','brown':'TE','gray':'LRT'}
g = json.load(open(src))
stations = []
for f in g['features']:
    p = f['properties']
    if p.get('stop_type') != 'station': continue
    x, y = sv(*f['geometry']['coordinates'][:2])
    lines = []
    for c in p['station_colors'].split('-'):
        l = COL[c]
        if l not in lines: lines.append(l)
    stations.append([p['name'], p['station_codes'].replace('-', ' · '), lines, x, y])
stations.sort(key=lambda s: s[0])
lines = []
for f in g['features']:
    p = f['properties']
    if 'Line' not in f['geometry']['type']: continue
    geom = shape(f['geometry'])
    parts = list(geom.geoms) if isinstance(geom, MultiLineString) else [geom]
    d = []
    for ln in parts:
        pts = [sv(*c[:2]) for c in ln.coords]
        simp = LineString(pts).simplify(0.4)
        d.append('M' + 'L'.join(f'{a:.1f},{b:.1f}' for a, b in simp.coords))
    NM={'North South Line':'NS','East West Line':'EW','Circle Line':'CC','North East Line':'NE','Downtown Line':'DT','Thomson-East Coast Line':'TE'}
    lines.append([NM.get(p['name'],'LRT'), p['name'], ''.join(d)])
json.dump({'src': 'cheeaun/sgraildata (OpenStreetMap contributors, ODbL)', 'stations': stations, 'lines': lines}, open(out, 'w'), separators=(',', ':'))
print(len(stations), len(lines))
