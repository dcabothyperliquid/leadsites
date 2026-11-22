"""Email ENRICH step: find a public business email for leads that don't have one yet.

Source: OpenStreetMap tags (`email` / `contact:email`) of the SAME place the lead came from -- looked up by its saved lat/lon + name
via Overpass. Nothing is scraped from Facebook/Google/Instagram (against their terms). Many small businesses have no email on OSM,
so expect a minority of leads to get one. Each lead is checked once (`email_checked`), re-checked after RECHECK_DAYS.
Runs inside email.yml before mailer.py. Env: MAX_CHECK (default 150)."""
import json, math, os, time, datetime, urllib.request, urllib.parse
import emailutil as U

LEADS = "data/leads.json"
MIRRORS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
           "https://overpass.private.coffee/api/interpreter"]
RECHECK_DAYS = 45
BATCH = 30
RADIUS_M = 45


def fetch(q):
    data = urllib.parse.urlencode({"data": q}).encode()
    for m in MIRRORS:
        for attempt in range(2):
            try:
                req = urllib.request.Request(m, data=data, headers={"User-Agent": "leadsites-bot/1.0 (github actions)"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    return json.load(r)["elements"]
            except Exception as e:
                print(f"  mirror {m.split('/')[2]} attempt {attempt + 1} failed: {type(e).__name__} {str(e)[:80]}")
                time.sleep(8)
    return None   # None = all mirrors failed (do NOT mark leads as checked)


def dist_m(a_lat, a_lon, b_lat, b_lon):
    k = 111320.0
    dx = (a_lon - b_lon) * k * math.cos(math.radians((a_lat + b_lat) / 2))
    dy = (a_lat - b_lat) * k
    return math.hypot(dx, dy)


def query(batch):
    parts = []
    for l in batch:
        for key in ("email", "contact:email"):
            parts.append(f'nwr(around:{RADIUS_M},{l["lat"]},{l["lon"]})["name"]["{key}"];')
    return f"[out:json][timeout:90];({''.join(parts)});out center tags;"


def match(lead, els):
    nm = U.norm_name(lead["name"])
    best = None
    for e in els:
        t = e.get("tags", {})
        en = U.norm_name(t.get("name"))
        if not en or not (en == nm or en in nm or nm in en):
            continue
        c = e.get("center") or {}
        la, lo = e.get("lat", c.get("lat")), e.get("lon", c.get("lon"))
        if la is None or lo is None:
            continue
        d = dist_m(lead["lat"], lead["lon"], la, lo)
        em = U.clean_email(t.get("email") or t.get("contact:email"))
        if em and d <= RADIUS_M * 1.5 and (best is None or d < best[0]):
            best = (d, em)
    return best[1] if best else ""


def due(l, today):
    if l.get("email") or not l.get("live") or l.get("lat") is None or l.get("lon") is None:
        return False
    ck = l.get("email_checked")
    if not ck:
        return True
    try:
        return (today - datetime.date.fromisoformat(ck)).days >= RECHECK_DAYS
    except ValueError:
        return True


def main():
    leads = json.load(open(LEADS))
    today = datetime.date.today()
    todo = [l for l in leads if due(l, today)][:int(os.environ.get("MAX_CHECK", "150") or 150)]
    have = sum(1 for l in leads if l.get("email"))
    print(f"EMAIL-ENRICH leads={len(leads)} with_email={have} to_check={len(todo)}")
    found = 0
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        els = fetch(query(batch))
        if els is None:
            print("  overpass unavailable -- stopping, will retry next run")
            break
        for l in batch:
            em = match(l, els)
            l["email_checked"] = today.isoformat()
            if em:
                l["email"], l["email_src"] = em, "osm"
                found += 1
        time.sleep(5)
    json.dump(leads, open(LEADS, "w"), ensure_ascii=False, indent=0)
    print(f"EMAIL-ENRICH found={found} total_with_email={sum(1 for l in leads if l.get('email'))}")


if __name__ == "__main__":
    main()
