"""Find local businesses (with phone, WITHOUT website) via OpenStreetMap Overpass.
Appends new ones to data/leads.json. Runs on GitHub Actions only."""
import json, re, time, hashlib, urllib.request, urllib.parse, os

CFG = json.load(open("config.json"))
LEADS_PATH = "data/leads.json"
MIRRORS = ["https://overpass-api.de/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter",
           "https://overpass.private.coffee/api/interpreter"]

def query_for(lat, lon, r):
    f = lambda sel: f'nwr(around:{r},{lat},{lon}){sel}["name"]["phone"][!"website"][!"contact:website"][!"url"];'
    parts = [
        f('["shop"~"^(hairdresser|beauty|bakery|tailor|car_repair)$"]'),
        f('["amenity"~"^(restaurant|cafe|dentist|clinic|gym|school)$"]'),
        f('["leisure"="fitness_centre"]'),
        f('["craft"="tailor"]'),
    ]
    return f"[out:json][timeout:90];({''.join(parts)});out center 400;"

def fetch(q):
    data = urllib.parse.urlencode({"data": q}).encode()
    for m in MIRRORS:
        for attempt in range(2):
            try:
                req = urllib.request.Request(m, data=data, headers={"User-Agent": "leadsites-bot/1.0 (github actions)"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    return json.load(r)["elements"]
            except Exception as e:
                print(f"  mirror {m.split('/')[2]} attempt {attempt+1} failed: {type(e).__name__} {str(e)[:80]}")
                time.sleep(8)
    return []

def norm_phone(raw, cc):
    p = re.split(r"[;,/]", raw)[0].strip()
    plus = p.startswith("+")
    d = re.sub(r"\D", "", p)
    if not d: return None
    if plus: n = d
    elif d.startswith("00"): n = d[2:]
    elif d.startswith(cc) and len(d) > 10: n = d
    else: n = cc + d.lstrip("0")
    return n if 10 <= len(n) <= 13 else None

def category(tags):
    for k in ("shop", "amenity", "craft", "leisure"):
        v = tags.get(k)
        if v == "fitness_centre": v = "gym"
        if v == "tailor": return "Tailor"
        if v in CFG["categories"]:
            return CFG["categories"][v]
    return "Local Business"

def main():
    leads = json.load(open(LEADS_PATH)) if os.path.exists(LEADS_PATH) else []
    seen = {l["id"] for l in leads}
    cap = CFG["max_new_leads_per_run"]
    new = []
    allc = [(mk, c) for mk, m in CFG["markets"].items() for c in m["cities"]]
    off = int(time.time() // 86400) % len(allc)
    for mk, c in allc[off:] + allc[:off]:
        if len(new) >= cap: break
        market = CFG["markets"][mk]
        name, lat, lon = c
        print(f"== {mk} {name}")
        els = fetch(query_for(lat, lon, CFG["radius_m"]))
        print(f"  {len(els)} raw elements")
        for e in els:
            t = e.get("tags", {})
            ph = norm_phone(t.get("phone", ""), market["cc"])
            if not ph or not t.get("name"): continue
            lid = hashlib.md5(f'{e["type"]}{e["id"]}'.encode()).hexdigest()[:10]
            if lid in seen: continue
            seen.add(lid)
            addr = ", ".join(x for x in [
                (t.get("addr:housenumber", "") + " " + t.get("addr:street", "")).strip(),
                t.get("addr:suburb", ""), t.get("addr:city", name)] if x)
            new.append({"id": lid, "name": t["name"][:80], "cat": category(t), "city": name, "market": mk,
                        "phone": ph, "addr": addr, "hours": t.get("opening_hours", ""),
                        "found": time.strftime("%Y-%m-%d")})
            if len(new) >= cap: break
        time.sleep(5)
    leads = new + leads
    json.dump(leads, open(LEADS_PATH, "w"), ensure_ascii=False, indent=0)
    print(f"NEW={len(new)} TOTAL={len(leads)}")

if __name__ == "__main__":
    main()
