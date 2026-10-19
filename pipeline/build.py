"""Build the dashboard: STORE archive -> SITE/index.html + SITE/data/*.json

Unlike the HDB dashboard (pre-aggregated), the browser gets every transaction in compact
columnar form, because the filter set here (property type x sale type x tenure x remaining
lease x floor x units x price/psf/area ranges x segment x any quarter range) has far too
many combinations to precompute, and medians cannot be recombined from aggregates. At
~130k rows (growing ~30k/yr) this stays a few MB gzipped and filters in milliseconds.

Usage: python pipeline/build.py STORE_DIR SITE_DIR
"""
import datetime as dt
import json
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from harmonize import GENERIC, load_clean, norm_name  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
PTYPES = ["Apartment", "Condominium", "Executive Condominium", "Strata Terrace", "Strata Semi-detached",
          "Strata Detached", "Terrace", "Semi-detached", "Detached"]
SEGS = ["CCR", "RCR", "OCR"]
KINDS = ["FH", "999", "LH", "UNK"]
LOC_SRC = ["ura", "ura-other", "onemap-project", "onemap-street", "none"]


def floor_order(f):
    if f == "-":
        return -100
    m = re.match(r"^B(\d+)", f)
    if m:
        return -int(m.group(1))
    m = re.match(r"^(\d+)", f)
    return int(m.group(1)) if m else 999


def svg_xy(x, y, proj):
    if pd.isna(x):
        return None, None
    return round(proj["pad"] + (x - proj["x0"]) * proj["s"], 1), round(proj["pad"] + (proj["y1"] - y) * proj["s"], 1)


def extras(store, projects):
    """Link rentals / developer sales / pipeline to transaction projects (normalised name + district)."""
    a = os.path.join(store, "archive")
    key_nd = {}
    key_n = {}
    for i, r in projects.iterrows():
        nn = norm_name(r["project"])
        if r["project"] in GENERIC:
            continue
        key_nd.setdefault((nn, r["district"]), i)
        key_n.setdefault(nn, []).append(i)

    def match(name, district):
        nn = norm_name(name)
        if (nn, district) in key_nd:
            return key_nd[(nn, district)]
        c = key_n.get(nn, [])
        return c[0] if len(c) == 1 else None

    out = {}
    stats = {}
    rent_rows = []
    rp = os.path.join(a, "rentals.csv.gz")
    if os.path.exists(rp):
        r = pd.read_csv(rp, dtype=str, keep_default_na=False)
        r["district"] = r["district"].str.zfill(2)
        hit = 0
        for (proj, dist), g in r.groupby(["project", "district"]):
            i = match(proj, dist)
            if i is None:
                continue
            hit += 1
            g = g.sort_values("refPeriod")
            for q, m, p25, p75 in zip(g["refPeriod"], g["median"], g["psf25"], g["psf75"]):
                y, qq = int(q[:4]), int(q[-1])
                rent_rows.append([int(i), (y - 1990) * 4 + qq - 1, float(m), float(p25), float(p75)])
            out.setdefault(int(i), {})["rent"] = [[q, float(m), float(p25), float(p75)] for q, m, p25, p75 in
                                                  zip(g["refPeriod"], g["median"], g["psf25"], g["psf75"])]
        stats["rent_projects"] = int(r.groupby(["project", "district"]).ngroups)
        stats["rent_matched"] = hit
    dp = os.path.join(a, "dev_sales.csv.gz")
    if os.path.exists(dp):
        d = pd.read_csv(dp, dtype=str, keep_default_na=False)
        d["district"] = d["district"].str.zfill(2)
        hit = 0
        for (proj, dist), g in d.groupby(["project", "district"]):
            i = match(proj, dist)
            if i is None:
                continue
            hit += 1
            g = g.sort_values("month")
            num = lambda c: pd.to_numeric(g[c], errors="coerce").fillna(0).astype(int).tolist()  # noqa: E731
            out.setdefault(int(i), {})["dev"] = {
                "developer": g["developer"].iloc[-1],
                "m": g["month"].tolist(), "sold": num("soldInMonth"), "launched": num("launchedInMonth"),
                "med": num("medianPrice"), "lo": num("lowestPrice"), "hi": num("highestPrice"),
                "units": int(num("unitsAvail")[-1]), "launchedToDate": int(num("launchedToDate")[-1]),
                "soldToDate": int(num("soldToDate")[-1])}
        stats["dev_projects"] = int(d.groupby(["project", "district"]).ngroups)
        stats["dev_matched"] = hit
        stats["dev_latest_month"] = d["month"].max()
    pp = os.path.join(a, "pipeline.csv.gz")
    pipe_d = {}
    if os.path.exists(pp):
        p = pd.read_csv(pp, dtype=str, keep_default_na=False)
        p = p[p["release"] == p["release"].max()]
        p["district"] = p["district"].str.zfill(2)
        hit = 0
        for r in p.itertuples(index=False):
            units = int(float(r.totalUnits or 0))
            pd_ = pipe_d.setdefault(r.district, {"projects": 0, "units": 0, "list": []})
            pd_["projects"] += 1
            pd_["units"] += units
            pd_["list"].append([r.project, r.street, units, r.expectedTOPYear, r.developerName])
            for part in [r.project] + r.project.split("/"):
                i = match(part.strip(), r.district)
                if i is not None:
                    out.setdefault(int(i), {})["pipe"] = {"units": units, "top": r.expectedTOPYear,
                                                          "developer": r.developerName}
                    hit += 1
                    break
        stats["pipe_projects"] = len(p)
        stats["pipe_matched"] = hit
        stats["pipe_release"] = p["release"].max() if len(p) else None
    stats["_rent_rows"] = rent_rows
    return out, pipe_d, stats


def main(store, site):
    os.makedirs(os.path.join(site, "data"), exist_ok=True)
    tx, projects = load_clean(store)
    dmap = json.load(open(os.path.join(ROOT, "data", "district_map.json")))
    names = json.load(open(os.path.join(ROOT, "data", "district_names.json")))
    proj = dmap["proj"]

    unknown_pt = sorted(set(tx["ptype"]) - set(PTYPES))
    ptypes = PTYPES + unknown_pt
    floors = sorted(tx["floor"].unique(), key=floor_order)

    projects = projects.sort_values(["district", "project", "street"]).reset_index(drop=True)
    pidx = {k: i for i, k in enumerate(projects["pkey"])}
    plist = []
    for r in projects.itertuples(index=False):
        sx, sy = svg_xy(r.x, r.y, proj)
        plist.append([r.project, r.street, int(r.district), SEGS.index(r.segment) if r.segment in SEGS else -1,
                      sx, sy, LOC_SRC.index(r.loc_src) if r.loc_src in LOC_SRC else 4,
                      1 if r.project in GENERIC else 0])

    # tenure text per project (most common) for the project panel
    ten = tx.groupby("pkey")["tenure_raw"].agg(lambda s: s.value_counts().index[0])
    for i, k in enumerate(projects["pkey"]):
        plist[i].append(ten.get(k, ""))
    # ---- harmonised floor-area flag per project (0 no, 1 likely by rule, 2 confirmed) ----
    hcfg = json.load(open(os.path.join(ROOT, "data", "harmonisation.json")))
    conf = {norm_name(c["project"]) for c in hcfg.get("confirmed", [])}
    force_y = {norm_name(x) for x in hcfg.get("force_harmonised", [])}
    force_n = {norm_name(x) for x in hcfg.get("force_not_harmonised", [])}
    rule = hcfg.get("rule", {})
    ns = tx[tx["sale"] == 1].groupby("pkey").agg(first_new=("month", "min"))
    pl = tx.groupby("pkey").agg(ls=("lease_start", "max"), kind=("tenure_kind", lambda s: s.mode().iat[0]),
                                pt=("ptype", lambda s: s.mode().iat[0]))
    pl = pl.join(ns)
    harm = {}
    for k, r in pl.iterrows():
        nn = norm_name(k.split("|")[0])
        f = 0
        if (r["kind"] == "LH" and pd.notna(r["ls"]) and r["ls"] >= rule.get("min_lease_start", 2023)
                and isinstance(r["first_new"], str) and r["first_new"] >= rule.get("min_first_new_sale", "2024-03")):
            f = 1
        if nn in conf:
            f = 2
        if nn in force_y:
            f = 2
        if nn in force_n:
            f = 0
        harm[k] = f
    for i, k in enumerate(projects["pkey"]):
        r = pl.loc[k]
        plist[i] += [ptypes.index(r["pt"]) if r["pt"] in ptypes else -1,
                     int(r["ls"]) if pd.notna(r["ls"]) else 0, harm.get(k, 0)]

    tx = tx.sort_values(["mi", "district"], kind="stable").reset_index(drop=True)
    cols = {
        "mi": tx["mi"].astype(int).tolist(),
        "p": tx["pkey"].map(pidx).astype(int).tolist(),
        "d": tx["district"].astype(int).tolist(),
        "g": tx["segment"].map({s: i for i, s in enumerate(SEGS)}).fillna(-1).astype(int).tolist(),
        "t": tx["ptype"].map({s: i for i, s in enumerate(ptypes)}).astype(int).tolist(),
        "s": tx["sale"].fillna(0).astype(int).tolist(),
        "a": (tx["area_sqm"] * 10).round().astype(int).tolist(),
        "pr": tx["price"].round().astype(np.int64).tolist(),
        "f": tx["floor"].map({s: i for i, s in enumerate(floors)}).astype(int).tolist(),
        "k": tx["tenure_kind"].map({s: i for i, s in enumerate(KINDS)}).fillna(3).astype(int).tolist(),
        "rl": (tx["rem_lease"] * 10).round().fillna(-1).astype(int).tolist(),
        "u": tx["units"].astype(int).tolist(),
        "ar": (tx["area_type"] == "Land").astype(int).tolist(),
        "ls": tx["lease_start"].fillna(0).astype(int).tolist(),
    }

    ex, pipe_d, xstats = extras(store, projects)
    rent_rows = xstats.pop("_rent_rows", [])

    manifest = {}
    mp = os.path.join(store, "latest", "manifest.json")
    if os.path.exists(mp):
        manifest = json.load(open(mp))
    log = []
    lp = os.path.join(store, "archive", "log.json")
    if os.path.exists(lp):
        log = json.load(open(lp))

    meta = {
        "built_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
        "pulled_at": manifest.get("fetched_at", "")[:16].replace("T", " ") + " UTC" if manifest else "",
        "earliest": tx["month"].min(), "latest": tx["month"].max(), "n": int(len(tx)),
        "n_projects": int(sum(1 for p in plist if not p[7])), "n_streets_landed": int(sum(p[7] for p in plist)),
        "archive_runs": len(log),
        "located_tx_share": round(float(projects.loc[projects["loc_src"] != "none", "n"].sum() / len(tx)), 3),
        **xstats,
    }
    data = {
        "meta": meta, "base_year": 1990,
        "dict": {"ptype": ptypes, "floor": floors, "seg": SEGS, "kind": KINDS, "loc": LOC_SRC},
        "projects": plist, "cols": cols, "extras": {str(k): v for k, v in ex.items()},
        "pipeline_by_district": pipe_d, "rent": rent_rows,
        "harmonisation": {"rule": hcfg.get("rule", {}).get("description", ""),
                          "confirmed": [c["project"] for c in hcfg.get("confirmed", [])],
                          "n_likely": sum(1 for v in harm.values() if v == 1),
                          "n_confirmed": sum(1 for v in harm.values() if v == 2)},
    }
    with open(os.path.join(site, "data", "tx.json"), "w") as f:
        json.dump(data, f, separators=(",", ":"))
    mapdata = {**dmap, "names": names}
    with open(os.path.join(site, "data", "map.json"), "w") as f:
        json.dump(mapdata, f, separators=(",", ":"))

    tpl = open(os.path.join(ROOT, "template", "dashboard_template.html")).read()
    fmt_m = lambda m: dt.date(int(m[:4]), int(m[5:7]), 1).strftime("%b %Y")  # noqa: E731
    subs = {
        "__EARLIEST_MONTH__": fmt_m(meta["earliest"]), "__LATEST_MONTH__": fmt_m(meta["latest"]),
        "__TOTAL_TX__": f"{meta['n']:,}", "__TOTAL_PROJECTS__": f"{meta['n_projects']:,}",
        "__PULLED_AT__": meta["pulled_at"] or "n/a", "__BUILD_ID__": meta["built_at"],
    }
    for k, v in subs.items():
        tpl = tpl.replace(k, v)
    open(os.path.join(site, "index.html"), "w").write(tpl)
    json.dump(meta, open(os.path.join(site, "meta.json"), "w"), indent=1)
    sz = os.path.getsize(os.path.join(site, "data", "tx.json")) / 1e6
    print(f"built {site}: {meta['n']:,} tx, {len(plist)} projects, tx.json {sz:.1f} MB; extras {xstats}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "store", sys.argv[2] if len(sys.argv) > 2 else "site")
