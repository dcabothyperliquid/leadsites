"""Manual demo: add ONE business you found yourself (Google Maps etc). generate.py then builds its demo page + pitch.
Env: M_NAME, M_NICHE (salon|clinic|restaurant|garage|gym|bakery), M_CITY, M_MARKET (UK|AE|AU|US|IN), M_PHONE, M_FB"""
import json, os, hashlib, time
import finder as F
name = os.environ.get("M_NAME", "").strip()
if not name: raise SystemExit("no manual lead")
mk = os.environ.get("M_MARKET", "UK").strip().upper() or "UK"
niche = os.environ.get("M_NICHE", "salon").strip().lower() or "salon"
city = os.environ.get("M_CITY", "").strip() or "Your city"
ph = F.norm_phone(os.environ.get("M_PHONE", ""), F.CFG["markets"][mk]["cc"], mk) if os.environ.get("M_PHONE", "").strip() else None
fb = F.fb_handle({"facebook": os.environ.get("M_FB", "")})
SUB = {"salon": "Salon", "clinic": "Clinic", "restaurant": "Restaurant", "garage": "Auto Repair", "gym": "Gym", "bakery": "Bakery"}
if not (ph or fb): raise SystemExit("need a valid mobile number or Facebook page")
lid = hashlib.md5(f"manual{name}{city}".encode()).hexdigest()[:10]
leads = [l for l in json.load(open(F.LEADS_PATH)) if l["id"] != lid]
leads.insert(0, {"id": lid, "name": name[:80], "niche": niche, "sub": SUB.get(niche, "Business"), "cat": SUB.get(niche, "Business"), "city": city,
                 "market": mk, "phone": ph, "fb": fb, "addr": "", "hours": "", "lat": None, "lon": None, "live": True, "manual": True,
                 "found": time.strftime("%Y-%m-%d")})
json.dump(leads, open(F.LEADS_PATH, "w"), ensure_ascii=False, indent=0)
print("MANUAL LEAD ADDED:", name, mk, niche)
