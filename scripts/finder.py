"""Auto lead finder. Runs daily on GitHub Actions only (nothing runs on Render).

* Only the ACTIVE niches are searched (start: salon, clinic, restaurant; the queue adds one every rollout_days).
* Few cities per run (rotating daily, tier-2 cities included) -> polite to Overpass, steady flow of fresh leads.
* Only businesses with a name + (WhatsApp-capable mobile number and/or Facebook page) and NO website. Known chains are skipped.
* Interleaves niches so one niche can't flood the daily batch."""
import json, re, time, hashlib, urllib.request, urllib.parse, os, shutil
import niches as N

CFG = json.load(open("config.json"))
LEADS_PATH, META_PATH = "data/leads.json", "data/meta.json"
MIRRORS = ["https://overpass-api.de/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter",
           "https://overpass.private.coffee/api/interpreter"]
CHAINS = ("domino", "pizza hut", "mcdonald", "kfc", "burger king", "subway", "starbucks", "cafe coffee day", "barista", "haldiram",
          "wow! momo", "wow momo", "naturals", "lakme", "jawed habib", "green trends", "cult", "gold's gym", "golds gym", "anytime fitness",
          "apollo", "fortis", "clove dental", "sabka dentist", "theobroma", "baskin", "chaayos", "biryani by kilo", "behrouz", "faasos",
          "starbucks", "costa", "dunkin", "taco bell", "papa john", "mahindra first choice", "maruti", "hyundai", "tata motors", "greggs", "nando", "pret a manger", "wetherspoon", "pizza express", "toni & guy", "toni&guy", "supercuts",
          "specsavers", "pure gym", "the gym group", "bannatyne", "david lloyd", "nuffield", "bupa", "mydentist", "my dentist", "hair by sam mcknight",
          "tim hortons", "krispy", "five guys", "wagamama", "zizzi", "prezzo", "bella italia", "harvester", "toby carvery", "tesco", "sainsbury", "oporto", "hungry jack", "guzman", "boost juice", "michel's", "gloria jean", "muffin break", "zambrero", "mad mex", "anytime", "jetts", "snap fitness", "plus fitness", "priceline", "chemist warehouse", "terry white", "just cuts", "lincraft")

def query_for(lat, lon, r, keys):
    parts = []
    nowebsite = '[!"website"][!"contact:website"][!"url"]'
    for key, vals in N.overpass_tags(CFG, keys).items():
        base = f'nwr(around:{r},{lat},{lon})["{key}"~"^({"|".join(vals)})$"]["name"]'
        parts.append(f'{base}["phone"]{nowebsite};')
        parts.append(f'{base}["contact:phone"]{nowebsite};')
        parts.append(f'{base}["contact:mobile"]{nowebsite};')
        parts.append(f'{base}["contact:facebook"]{nowebsite};')   # Facebook-page businesses (no website)
        parts.append(f'{base}["facebook"]{nowebsite};')
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

def to_intl(p, cc):
    plus = p.startswith("+")
    d = re.sub(r"\D", "", p)
    if not d: return None
    if plus: n = d
    elif d.startswith("00"): n = d[2:]
    elif d.startswith(cc) and len(d) > 10: n = d
    else: n = cc + d.lstrip("0")
    return n if 10 <= len(n) <= 13 else None

def is_mobile(n, market):
    """WhatsApp works on mobiles only; landlines are skipped."""
    if market == "IN": return n.startswith("91") and len(n) == 12 and n[2] in "6789"
    if market == "AU": return n.startswith("614") and len(n) == 11
    if market == "UK": return re.fullmatch(r"447[1-57-9]\d{8}", n) is not None      # 07xxx mobiles (not 070 personal / 076 pagers)
    if market == "AE": return re.fullmatch(r"9715\d{8}", n) is not None             # 05x mobiles
    return True  # US numbers: cannot tell line type from the number

def norm_phone(raw, cc, market):
    """First WhatsApp-capable number among all numbers listed on the place."""
    for p in re.split(r"[;,/]", raw):
        n = to_intl(p.strip(), cc)
        if n and is_mobile(n, market): return n
    return None

def is_chain(name):
    n = name.lower()
    return any(c in n for c in CHAINS)

def fb_handle(t):
    """Facebook page username / id from OSM tags (URL or bare handle) -> usable in https://m.me/<handle>."""
    raw = (t.get("contact:facebook") or t.get("facebook") or "").strip()
    if not raw: return None
    m = re.search(r"profile\.php\?id=(\d+)", raw)
    if m: return m.group(1)
    if "facebook.com" in raw or "fb.com" in raw or "fb.me" in raw:
        u = raw if raw.startswith("http") else "https://" + raw
        seg = urllib.parse.urlparse(u).path.strip("/").split("/")[-1]
    else:
        seg = raw.lstrip("@").strip("/")
    return seg if re.fullmatch(r"[A-Za-z0-9.\-_]{3,80}", seg or "") else None

def migrate(leads):
    """Old leads (before niches) get niche/sub/live fields; landlines are dropped with their demo pages."""
    keep, dropped = [], 0
    for l in leads:
        ph = l.get("phone")
        if not ((ph and is_mobile(ph, l["market"])) or l.get("fb")):
            dropped += 1
            if l.get("url"): shutil.rmtree("docs/s/" + l["url"].rstrip("/").split("/")[-1], ignore_errors=True)
            continue
        if "niche" not in l:
            l["sub"] = l.get("cat", "")
            l["niche"] = N.LEGACY.get(l["sub"])
        keep.append(l)
    if dropped: print(f"CLEAN dropped={dropped}")
    return keep

def main():
    leads = json.load(open(LEADS_PATH)) if os.path.exists(LEADS_PATH) else []
    leads = migrate(leads)
    act = N.active_niches(CFG)
    mkts = N.active_markets(CFG)
    for l in leads: l["live"] = l.get("niche") in act and l.get("market") in mkts
    print("ACTIVE NICHES:", act)
    seen = {l["id"] for l in leads}
    cap = CFG["max_new_leads_per_run"]
    print("ACTIVE MARKETS:", mkts)
    per_mk = [[(mk, c) for c in CFG["markets"][mk]["cities"]] for mk in mkts]
    allc = [x for grp in zip(*per_mk) for x in grp] + [x for grp in per_mk for x in grp[min(map(len, per_mk)):]] if per_mk else []   # UK, AE, UK, AE ... (interleaved)
    only = os.environ.get("ONLY_CITY", "").strip().lower()
    enabled = [x.lower() for x in CFG.get("enabled_cities", [])]
    if only: allc = [x for x in allc if x[1][0].lower() == only]
    elif enabled: allc = [x for x in allc if x[1][0].lower() in enabled]
    cities_today = []
    by_niche = {k: [] for k in act}
    if not allc:
        print("NO CITY MATCHED (check ONLY_CITY / enabled_cities)")
    else:
        per = max(1, CFG.get("cities_per_run", 4))
        day = int(time.time() // 86400)
        order = [allc[(day * per + i) % len(allc)] for i in range(min(per, len(allc)))]
        if only: order = allc[:1]
        for mk, c in order:
            if sum(len(v) for v in by_niche.values()) >= cap * 2: break
            market = CFG["markets"][mk]
            name, lat, lon = c
            cities_today.append(name)
            print(f"== {mk} {name}")
            els = fetch(query_for(lat, lon, CFG["radius_m"], act))
            print(f"  {len(els)} raw elements")
            for e in els:
                t = e.get("tags", {})
                nm = (t.get("name") or "").strip()
                if len(nm) < 3 or is_chain(nm): continue
                ph = norm_phone(";".join(t.get(k, "") for k in ("phone", "contact:phone", "contact:mobile")), market["cc"], mk)
                fb = fb_handle(t)
                nk, sub = N.classify(t, CFG)
                if not (ph or fb) or nk not in by_niche: continue
                lid = hashlib.md5(f'{e["type"]}{e["id"]}'.encode()).hexdigest()[:10]
                if lid in seen: continue
                seen.add(lid)
                ctr = e.get("center") or {}
                la, lo = e.get("lat", ctr.get("lat")), e.get("lon", ctr.get("lon"))
                addr = ", ".join(x for x in [
                    (t.get("addr:housenumber", "") + " " + t.get("addr:street", "")).strip(),
                    t.get("addr:suburb", ""), t.get("addr:city", name)] if x)
                by_niche[nk].append({"id": lid, "name": nm[:80], "niche": nk, "sub": sub, "cat": sub, "city": name, "market": mk,
                                     "phone": ph, "fb": fb, "addr": addr, "hours": t.get("opening_hours", ""), "lat": la, "lon": lo,
                                     "live": True, "found": time.strftime("%Y-%m-%d")})
            time.sleep(5)
    # round-robin over niches so the daily batch stays balanced
    new, i = [], 0
    while len(new) < cap and any(by_niche.values()):
        k = act[i % len(act)]; i += 1
        if by_niche[k]: new.append(by_niche[k].pop(0))
    leads = new + leads
    json.dump(leads, open(LEADS_PATH, "w"), ensure_ascii=False, indent=0)
    nxt, nd = N.next_niche(CFG)
    json.dump({"last_run": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "active": act,
               "labels": {k: CFG["niches"][k]["label"] for k in CFG["niches"]}, "markets": mkts,
               "next_niche": nxt, "next_date": nd.isoformat() if nd else None,
               "cities_today": cities_today, "new_today": len(new)},
              open(META_PATH, "w"), ensure_ascii=False, indent=1)
    print(f"NEW={len(new)} TOTAL={len(leads)} LIVE={sum(1 for l in leads if l.get('live'))}")

if __name__ == "__main__":
    main()
