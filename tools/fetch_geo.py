"""One-off: download Singapore boundary GeoJSON from data.gov.sg into data/geo/.
Tries each candidate dataset id, prints its title, saves the GeoJSON."""
import json, os, sys, time, requests
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "geo"); os.makedirs(OUT, exist_ok=True)
IDS = ["d_8594ae9ff96d0c708bc2af633048edfb", "d_4765db0e87b9c86336792efe8a1f7a66",
       "d_bf4d24df9129d5a8ff8cf82e20959ee0"]
H = {"User-Agent": "Mozilla/5.0"}
for i in IDS:
    try:
        meta = requests.get(f"https://api-production.data.gov.sg/v2/public/api/datasets/{i}/metadata", headers=H, timeout=60).json()
        name = meta.get("data", {}).get("name", "?"); print(i, "->", name)
        url = None
        for _ in range(10):
            p = requests.get(f"https://api-open.data.gov.sg/v1/public/api/datasets/{i}/poll-download", headers=H, timeout=60).json()
            url = (p.get("data") or {}).get("url")
            if url: break
            time.sleep(3)
        if not url: print("  no url", p); continue
        g = requests.get(url, headers=H, timeout=180).content
        json.loads(g)  # validate
        fn = os.path.join(OUT, f"{i}.geojson"); open(fn, "wb").write(g)
        json.dump({"id": i, "name": name}, open(fn + ".meta.json", "w"))
        print("  saved", len(g), "bytes")
    except Exception as e:
        print("  failed", e)
    time.sleep(5)
if not any(f.endswith(".geojson") for f in os.listdir(OUT)): sys.exit("nothing downloaded")
