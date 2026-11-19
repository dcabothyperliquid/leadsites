"""Build a niche-specific demo site + pitch + wa.me link for every LIVE lead that has none (or an old template version)."""
import json, os, re, html, urllib.parse
import niches as N

CFG = json.load(open("config.json"))
OWNER_REPO = os.environ.get("GITHUB_REPOSITORY", "dcabothyperliquid/leadsites")
USER, REPO = OWNER_REPO.split("/")
BASE = f"https://{USER}.github.io/{REPO}/s"
VER = "6"   # bump to rebuild every page + pitch

# ── per-niche content (sample content is labelled as such on the page) ──
NICHE = {
 "salon": dict(c="#be185d", d="#831843", l="#fdf2f8", emoji="💇", tag="Look good. Feel great.", sub="Walk in, relax, walk out glowing.",
    cta="Book on WhatsApp", wa="Hi, I'd like to book an appointment at {name}", svc_title="Our services",
    items=[("✂️","Haircut & Styling"),("🎨","Hair Colour & Spa"),("✨","Facial & Clean-up"),("💄","Makeup & Bridal"),("💅","Manicure & Pedicure"),("🌿","Threading & Waxing")],
    why=[("📲","Book in one tap","Message us on WhatsApp and pick your slot."),("🕘","Timings at a glance","See when we are open before you walk in."),("📍","Easy to find","One tap opens the map to our door.")]),
 "clinic": dict(c="#0369a1", d="#0c4a6e", l="#f0f9ff", emoji="🩺", tag="Caring for your health, close to home.", sub="Clear timings, easy appointments.",
    cta="Book appointment", wa="Hi, I'd like to book an appointment at {name}", svc_title="Care we offer",
    items=[("🩺","General Consultation"),("🧪","Health Check-ups"),("💉","Vaccinations"),("📋","Follow-up Care"),("👨‍👩‍👧","Family Care"),("🕑","Walk-in Hours")],
    why=[("📲","Appointments on WhatsApp","Send a message, get a time that suits you."),("🕘","Know our timings","Opening hours always up to date."),("📍","Find us fast","Map and call button, one tap away.")]),
 "dental": dict(c="#0891b2", d="#155e75", l="#ecfeff", emoji="🦷", tag="Healthy smiles start here.", sub="Gentle care for the whole family.",
    cta="Book appointment", wa="Hi, I'd like to book a dental appointment at {name}", svc_title="Dental care",
    items=[("🦷","Check-up & Cleaning"),("🔧","Fillings & Root Canal"),("😁","Braces & Aligners"),("✨","Teeth Whitening"),("👶","Kids Dentistry"),("🦿","Implants & Crowns")],
    why=[("📲","Appointments on WhatsApp","Send a message, get a time that suits you."),("🕘","Know our timings","Opening hours always up to date."),("📍","Find us fast","Map and call button, one tap away.")]),
 "restaurant": dict(c="#c2410c", d="#7c2d12", l="#fff7ed", emoji="🍽️", tag="Fresh food, made with love.", sub="Dine in, take away, or order on WhatsApp.",
    cta="Order on WhatsApp", wa="Hi, I'd like to order / book a table at {name}", svc_title="From our kitchen",
    items=[("🥗","Starters"),("🍛","Main Course"),("🍞","Breads & Rice"),("🍰","Desserts"),("🥤","Beverages"),("⭐","Chef's Specials")],
    why=[("📲","Order or reserve on WhatsApp","No app needed, just send a message."),("🕘","Open hours at a glance","Know when to drop by."),("📍","Easy directions","One tap opens the map.")]),
 "garage": dict(c="#ea580c", d="#1f2937", l="#f3f4f6", emoji="🔧", tag="Honest repairs. Back on the road.", sub="Book your service in one message.",
    cta="Book a service", wa="Hi, I'd like to book a service at {name}", svc_title="What we fix",
    items=[("🛠️","General Service"),("🛢️","Oil Change"),("🛑","Brakes & Clutch"),("❄️","AC Service"),("🔋","Battery & Electrical"),("🛞","Wheel Alignment")],
    why=[("📲","Book on WhatsApp","Share your car model and pick a time."),("🕘","Know our hours","See when the workshop is open."),("📍","Find the workshop","Map and call button, one tap away.")]),
 "gym": dict(c="#0f766e", d="#134e4a", l="#f0fdfa", emoji="🏋️", tag="Train hard. Feel strong.", sub="Ask about a free trial session.",
    cta="Ask about a trial", wa="Hi, I'd like to know about membership at {name}", svc_title="Train with us",
    items=[("🏋️","Strength Training"),("🏃","Cardio Zone"),("🧑‍🏫","Personal Training"),("🧘","Group Classes"),("🥗","Diet Guidance"),("🎟️","Free Trial")],
    why=[("📲","Enquire on WhatsApp","Fees, timings and trial in one chat."),("🕘","Opening hours","Plan your workout around our timings."),("📍","Close to you","Map and call button, one tap away.")]),
 "bakery": dict(c="#b45309", d="#78350f", l="#fffbeb", emoji="🎂", tag="Baked fresh. Made to celebrate.", sub="Custom cakes on WhatsApp.",
    cta="Order a cake", wa="Hi, I'd like to order from {name}", svc_title="Fresh from the oven",
    items=[("🎂","Custom Cakes"),("🧁","Pastries"),("🍪","Cookies"),("🥖","Breads"),("🥐","Snacks"),("🎉","Party Orders")],
    why=[("📲","Order on WhatsApp","Share your design idea, we reply fast."),("🕘","Open hours","Know when to pick up."),("📍","Easy to find","One tap opens the map.")]),
}
DAYS = {"Mo": "Mon", "Tu": "Tue", "We": "Wed", "Th": "Thu", "Fr": "Fri", "Sa": "Sat", "Su": "Sun", "PH": "Holidays"}

def pretty_hours(h):
    if not h: return ""
    s = re.sub(r"\b(Mo|Tu|We|Th|Fr|Sa|Su|PH)\b", lambda m: DAYS[m.group(1)], h)
    return s.replace("-", "–").replace(";", " · ").strip()

def style_key(l):
    if l.get("niche") == "clinic" and l.get("sub") == "Dental Clinic": return "dental"
    return l.get("niche") if l.get("niche") in NICHE else "restaurant"

TPL = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{name} | {sub} in {city}</title>
<meta name="description" content="{name} - {tag} Call or message us.">
<meta property="og:title" content="{name}"><meta property="og:description" content="{tag}">
<meta name="theme-color" content="{c}">
<script type="application/ld+json">{ld}</script>
<style>
:root{{--c:{c};--d:{d};--l:{l}}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#1f2937;background:#fff;line-height:1.55}}
a{{color:inherit}}
.bar{{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:10px;padding:10px 16px;background:rgba(255,255,255,.92);backdrop-filter:blur(8px);border-bottom:1px solid #eee}}
.bar b{{flex:1;font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.pill{{display:inline-flex;align-items:center;gap:6px;padding:9px 16px;border-radius:999px;font-weight:700;font-size:14px;text-decoration:none}}
.p-call{{background:var(--c);color:#fff}}.p-wa{{background:#25d366;color:#fff}}.p-ghost{{background:#fff;color:var(--d);border:1px solid #e5e7eb}}
.hero{{background:radial-gradient(1200px 400px at 80% -10%,rgba(255,255,255,.22),transparent 60%),linear-gradient(135deg,var(--c),var(--d));color:#fff;padding:54px 20px 60px;text-align:center}}
.hero .em{{font-size:44px}}.hero .kick{{display:inline-block;margin:10px 0 0;padding:5px 14px;border-radius:999px;background:rgba(255,255,255,.18);font-size:12.5px;font-weight:600;letter-spacing:.04em}}
.hero h1{{margin:14px auto 8px;max-width:640px;font-size:clamp(28px,7vw,44px);line-height:1.15}}
.hero p{{margin:0 auto;max-width:520px;opacity:.92;font-size:17px}}
.cta{{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:26px}}
.cta .pill{{padding:14px 24px;font-size:16px;box-shadow:0 8px 24px rgba(0,0,0,.18)}}
.cta .p-ghost{{background:rgba(255,255,255,.14);color:#fff;border:1px solid rgba(255,255,255,.4);box-shadow:none}}
.wrap{{max-width:760px;margin:0 auto;padding:0 18px}}
section{{padding:38px 0 6px}}h2{{margin:0 0 16px;font-size:22px;color:var(--d)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}
.card{{background:var(--l);border-radius:16px;padding:18px 14px;text-align:center;font-weight:600}}
.card i{{display:block;font-style:normal;font-size:28px;margin-bottom:6px}}
.note{{font-size:12px;color:#6b7280;margin:10px 0 0}}
.why{{display:grid;gap:12px}}.why div{{display:flex;gap:14px;align-items:flex-start;padding:14px 16px;border:1px solid #eee;border-radius:14px}}
.why i{{font-style:normal;font-size:26px}}.why b{{display:block}}.why span{{font-size:14px;color:#6b7280}}
.info{{display:grid;gap:12px}}.info .row{{background:var(--l);border-radius:14px;padding:14px 16px}}.info small{{display:block;color:var(--c);font-weight:700;text-transform:uppercase;letter-spacing:.06em;font-size:11px;margin-bottom:2px}}
.map{{margin-top:14px;border-radius:16px;overflow:hidden;border:1px solid #eee}}.map iframe{{display:block;width:100%;height:240px;border:0}}
.final{{margin:42px 0 0;background:linear-gradient(135deg,var(--c),var(--d));color:#fff;text-align:center;padding:38px 20px}}
.final h2{{color:#fff}}.final .cta{{margin-top:14px}}
footer{{text-align:center;font-size:12px;color:#6b7280;padding:22px 16px 96px}}
.fab{{position:fixed;right:16px;bottom:16px;z-index:30;width:58px;height:58px;border-radius:50%;background:#25d366;color:#fff;display:flex;align-items:center;justify-content:center;font-size:28px;text-decoration:none;box-shadow:0 8px 24px rgba(0,0,0,.28)}}
</style></head><body>
<div class="bar"><b>{emoji} {name}</b>{call_bar}</div>
<div class="hero"><div class="em">{emoji}</div><span class="kick">{sublabel} · {city}</span>
<h1>{name}</h1><p>{tag} {subline}</p>
<div class="cta"><a class="pill p-wa" href="{wa_url}">💬 {cta}</a>{call_hero}</div></div>
<div class="wrap">
<section><h2>{svc_title}</h2><div class="grid">{items}</div><p class="note">Sample content for this preview. Your real services and prices go here once you approve.</p></section>
<section><h2>Why customers love it</h2><div class="why">{why}</div></section>
<section><h2>Visit us</h2><div class="info">{addr_row}{hours_row}{phone_row}</div>
{map}<p style="margin:14px 0 0"><a class="pill p-ghost" href="{maps_url}" target="_blank" rel="noopener">📍 Open in Google Maps</a></p></section>
</div>
<div class="final"><h2>Ready when you are</h2><div class="cta"><a class="pill p-wa" href="{wa_url}">💬 {cta}</a></div></div>
<footer>Demo preview made for {name}. Want this live on your own domain? Message the person who sent you this link.</footer>
<a class="fab" href="{wa_url}" aria-label="WhatsApp">💬</a>
</body></html>"""

def build_page(l):
    k = style_key(l); n = NICHE[k]
    name, city = html.escape(l["name"]), html.escape(l["city"])
    ph = l.get("phone")
    if ph: wa_url = f'https://wa.me/{ph}?text=' + urllib.parse.quote(n["wa"].format(name=l["name"]))
    else:  wa_url = f'https://m.me/{l["fb"]}'
    cta_txt = n["cta"] if ph else "Message us on Facebook"
    items = "".join(f'<div class="card"><i>{e}</i>{html.escape(t)}</div>' for e, t in n["items"])
    why = "".join(f'<div><i>{e}</i><p style="margin:0"><b>{html.escape(t)}</b><span>{html.escape(d)}</span></p></div>' for e, t, d in n["why"])
    addr = l.get("addr", "")
    addr_row = f'<div class="row"><small>Address</small>{html.escape(addr)}</div>' if addr else ""
    hrs = pretty_hours(l.get("hours", ""))
    hours_row = f'<div class="row"><small>Opening hours</small>{html.escape(hrs)}</div>' if hrs else ""
    la, lo = l.get("lat"), l.get("lon")
    if la is not None and lo is not None:
        maps_url = f"https://www.google.com/maps?q={la},{lo}"
        d = 0.004
        mp = (f'<div class="map"><iframe loading="lazy" title="Map" src="https://www.openstreetmap.org/export/embed.html?bbox='
              f'{lo-d},{la-d},{lo+d},{la+d}&layer=mapnik&marker={la},{lo}"></iframe></div>')
    else:
        maps_url = "https://www.google.com/maps/search/" + urllib.parse.quote(f'{l["name"]} {addr} {l["city"]}')
        mp = ""
    ld = {"@context": "https://schema.org", "@type": "LocalBusiness", "name": l["name"], **({"telephone": "+" + ph} if ph else {}), 
          "address": {"@type": "PostalAddress", "streetAddress": addr, "addressLocality": l["city"]}}
    return TPL.format(name=name, city=city, sub=html.escape(l.get("sub") or l.get("cat", "")), sublabel=html.escape(l.get("sub") or l.get("cat", "")),
                      tag=html.escape(n["tag"]), subline=html.escape(n["sub"]), cta=html.escape(cta_txt), emoji=n["emoji"],
                      c=n["c"], d=n["d"], l=n["l"],
                      call_bar=(f'<a class="pill p-call" href="tel:+{ph}">Call</a>' if ph else ""),
                      call_hero=(f'<a class="pill p-ghost" href="tel:+{ph}">📞 Call now</a>' if ph else ""),
                      phone_row=(f'<div class="row"><small>Phone</small><a href="tel:+{ph}">+{ph}</a></div>' if ph else ""), wa_url=html.escape(wa_url), svc_title=html.escape(n["svc_title"]),
                      items=items, why=why, addr_row=addr_row, hours_row=hours_row, map=mp, maps_url=html.escape(maps_url),
                      ld=json.dumps(ld, ensure_ascii=False).replace("</", "<\\/"))

def slug(l):
    s = re.sub(r"[^a-z0-9]+", "-", l["name"].lower()).strip("-")[:30] or "biz"
    return f'{l["city"].lower()}-{s}-{l["id"][:5]}'

# ── pitches: short, specific to the niche, Hinglish for India ──
BENEFIT_HI = {"salon": "customers seedha WhatsApp pe booking kar sakte hain",
              "clinic": "patients timings dekh ke seedha appointment book kar sakte hain",
              "restaurant": "customers menu aur timing dekh ke seedha WhatsApp pe order ya table book kar sakte hain",
              "garage": "customers seedha call ya WhatsApp karke service book kar sakte hain",
              "gym": "log fees aur timing dekh ke seedha trial ke liye WhatsApp kar sakte hain",
              "bakery": "customers seedha WhatsApp pe cake order kar sakte hain"}
BENEFIT_EN = {"salon": "clients can book straight on WhatsApp", "clinic": "patients can see your timings and book an appointment",
              "restaurant": "guests can see your timings and order or book a table on WhatsApp",
              "garage": "customers can call or WhatsApp to book a service", "gym": "people can ask about a free trial on WhatsApp",
              "bakery": "customers can order cakes on WhatsApp"}

def pitch(l, url):
    m = CFG["markets"][l["market"]]
    seller, price, cur = CFG["seller_name"], m["price"], m["currency"]
    brand = CFG.get("brand") or seller
    bits = []
    if CFG.get("seller_wa"): bits.append(f'WhatsApp: https://wa.me/{CFG["seller_wa"]}')
    if CFG.get("seller_fb"): bits.append(f'Facebook: https://m.me/{CFG["seller_fb"]}')
    if CFG.get("seller_contact"): bits.append(CFG["seller_contact"])
    contact = ("\n" + " | ".join(bits)) if bits else ""
    nk = l.get("niche") if l.get("niche") in BENEFIT_HI else "restaurant"
    if m["lang"] == "hinglish":
        return (f"Namaste! Main {seller}, {brand} se, web developer hoon. {l['name']} ke liye maine ek demo website bana di hai jisse {BENEFIT_HI[nk]}:\n{url}\n"
                f"Pasand aaye toh {cur}{price} mein aapke naam se live kar dunga (domain/hosting setup ke saath). Koi change chahiye toh bata dijiye.{contact}")
    return (f"Hi! I'm {seller} from {brand}, a web developer. I noticed {l['name']} doesn't have a website, so I built a quick demo where {BENEFIT_EN[nk]}:\n{url}\n"
            f"If you like it, I can put it live as a one-page site under your own name for {cur}{price} (domain & hosting setup included). Happy to tweak anything.{contact}\n"
            f"If you'd rather not hear from me, just say and I won't message again.")

def reach(l, text):
    """Primary outreach link + channel list. WhatsApp when a mobile exists, Facebook Messenger otherwise."""
    ch = (["wa"] if l.get("phone") else []) + (["fb"] if l.get("fb") else [])
    l["channels"] = ch
    if l.get("fb"): l["fb_link"] = f'https://m.me/{l["fb"]}'
    if l.get("phone"): return f'https://wa.me/{l["phone"]}?text=' + urllib.parse.quote(text)
    return l["fb_link"]

def main():
    leads = json.load(open("data/leads.json"))
    made = 0
    for l in leads:
        if not l.get("live"): continue
        if l.get("url") and l.get("ver") == VER: continue
        s = slug(l)
        d = f"docs/s/{s}"; os.makedirs(d, exist_ok=True)
        open(f"{d}/index.html", "w", encoding="utf-8").write(build_page(l))
        l["url"] = f"{BASE}/{s}/"
        l["ver"] = VER
        l["pitch"] = pitch(l, l["url"])
        l["wa"] = reach(l, l["pitch"])
        made += 1
    if os.environ.get("REGEN_PITCHES", "").lower() in ("1", "true", "yes"):   # seller name / price changed -> pitches only
        for l in leads:
            if l.get("url"):
                l["pitch"] = pitch(l, l["url"])
                l["wa"] = reach(l, l["pitch"])
    json.dump(leads, open("data/leads.json", "w"), ensure_ascii=False, indent=0)
    open("docs/index.html", "w").write("<!doctype html><meta charset=utf-8><meta name=robots content=noindex><title>demo sites</title><p>Demo sites live under /s/</p>")
    print(f"GENERATED={made} TOTAL={len(leads)} LIVE={sum(1 for l in leads if l.get('live'))}")

if __name__ == "__main__":
    main()
