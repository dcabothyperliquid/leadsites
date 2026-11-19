"""Build a niche-specific demo site + pitch + wa.me link for every LIVE lead that has none (or an old template version)."""
import json, os, re, html, shutil, datetime, urllib.parse
import niches as N

CFG = json.load(open("config.json"))
# Demos live in the Naem Studio site repo (checked out at SITE_DIR), served from naemstudio.github.io/d/<slug>/ (1-page) and /d/<slug>/pro/ (5-page)
SITE = os.environ.get("SITE_DIR", "site")
SITE_URL = CFG.get("site_url", "https://naemstudio.github.io")
BASE = f"{SITE_URL}/d"
PRO_TPL = {"salon": "salon-pro", "clinic": "clinic-pro", "restaurant": "restaurant-pro"}   # niches that have a 5-page template in <site>/demos/
VER = "13"   # bump to rebuild every page + pitch

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

# ── richer per-niche content: (name, description, sample price) ──
CONTENT = {
 "salon": dict(menu=[("Haircut & Styling","Wash, cut and finish",30),("Colour & Highlights","Full colour, balayage, toning",70),("Facial & Clean-up","Deep cleanse and glow",40),("Bridal & Makeup","Trial and event day",120),("Manicure & Pedicure","Shape, polish, care",35),("Threading & Waxing","Quick and gentle",15)],
   steps=[("Pick a service","Choose what you need from the menu."),("Send a message","WhatsApp or Messenger, whichever you like."),("Get your slot","We confirm a time and you walk in.")],
   faq=[("Do I need to book?","Booking is recommended so we can keep your slot. Walk-ins are welcome when we have space."),("How do I book?","Tap the button and send us a message with your preferred service and time."),("Can I reschedule?","Yes, just message us and we will move your slot.")]),
 "clinic": dict(menu=[("General Consultation","See a doctor for any concern",40),("Health Check-ups","Routine tests and advice",90),("Vaccinations","Adults and children",30),("Follow-up Care","Review and ongoing support",25),("Family Care","Care for the whole family",50),("Walk-in Hours","Ask for today's availability",None)],
   steps=[("Message us","Tell us what you need and your preferred time."),("Get confirmed","We reply with an appointment slot."),("Visit the clinic","Arrive a few minutes early and we take it from there.")],
   faq=[("How do I book an appointment?","Send us a message on WhatsApp or Messenger, or call during opening hours."),("Do you take walk-ins?","Please message first so we can tell you the best time to come."),("What should I bring?","Bring any previous reports or prescriptions that relate to your visit.")]),
 "dental": dict(menu=[("Check-up & Cleaning","Exam, scale and polish",60),("Fillings & Root Canal","Comfortable, careful treatment",80),("Braces & Aligners","Straighter smiles",None),("Teeth Whitening","Brighter in one visit",150),("Kids Dentistry","Gentle care for little ones",35),("Implants & Crowns","Long-lasting restorations",None)],
   steps=[("Message us","Share your concern and preferred time."),("Get confirmed","We reply with an appointment slot."),("Visit the clinic","Relaxed, gentle care from check-in to check-out.")],
   faq=[("How often should I get a check-up?","Most people benefit from a check-up and clean every six months, or as your dentist advises."),("Do you treat children?","Yes, we welcome patients of all ages."),("How do I book?","Send us a message on WhatsApp or Messenger, or call us.")]),
 "restaurant": dict(menu=[("Starters","Light bites to begin",6),("Main Course","Our house favourites",14),("Breads & Rice","Fresh and fragrant",4),("Desserts","A sweet finish",6),("Beverages","Hot, cold and fresh",3),("Chef's Specials","Changes with the season",18)],
   steps=[("Browse the menu","See what's cooking today."),("Message us","Order or reserve a table in one message."),("Enjoy","Dine in or take away.")],
   faq=[("Can I reserve a table?","Yes, send us a message with the date, time and number of guests."),("Do you do takeaway?","Yes, message your order and we will tell you when it is ready."),("Do you cater for dietary needs?","Tell us your needs when you message and we will guide you.")]),
}
CUR_SCALE = {"₹": 80, "AED ": 4}
GAL_EMOJI = {"salon": "💇✨💅🌿", "clinic": "🩺🏥💊🌿", "dental": "🦷😁✨🪥", "restaurant": "🍛🥗🍰🍽️", "garage": "🔧🚗🛠️🛞", "gym": "🏋️🏃🧘💪", "bakery": "🎂🥐🍪🥖"}

DAYS = {"Mo": "Mon", "Tu": "Tue", "We": "Wed", "Th": "Thu", "Fr": "Fri", "Sa": "Sat", "Su": "Sun", "PH": "Holidays"}

def pretty_hours(h):
    if not h: return ""
    s = re.sub(r"\b(Mo|Tu|We|Th|Fr|Sa|Su|PH)\b", lambda m: DAYS[m.group(1)], h)
    return s.replace("-", "–").replace(";", " · ").strip()

def style_key(l):
    if l.get("niche") == "clinic" and l.get("sub") == "Dental Clinic": return "dental"
    return l.get("niche") if l.get("niche") in NICHE else "restaurant"

# ── per-niche look: layout family, font, corner radius, hero background ──
THEME = {
 "salon":      dict(cls="split", font="Georgia,'Times New Roman',serif", r=24, bg="#fdf2f8"),
 "bakery":     dict(cls="split", font="Georgia,'Times New Roman',serif", r=28, bg="#fffbeb"),
 "clinic":     dict(cls="clean", font="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif", r=14, bg="#f0f9ff"),
 "dental":     dict(cls="clean", font="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif", r=20, bg="#ecfeff"),
 "restaurant": dict(cls="dark", font="Georgia,'Times New Roman',serif", r=10, bg="#1a0f0a"),
 "garage":     dict(cls="dark bold", font="'Segoe UI',Roboto,Arial,sans-serif", r=6, bg="#111827"),
 "gym":        dict(cls="dark bold", font="'Segoe UI',Roboto,Arial,sans-serif", r=6, bg="#0b1f1e"),
}

CSS = """
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;font-family:var(--f);color:#1f2937;background:#fff;line-height:1.55;-webkit-font-smoothing:antialiased}
a{color:inherit}h1,h2,.mi b,summary{font-family:var(--f)}
.exp{background:#111827;color:#fde68a;text-align:center;font-size:12.5px;padding:7px 12px}
.bar{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:10px;padding:10px 16px;background:rgba(255,255,255,.92);backdrop-filter:blur(8px);border-bottom:1px solid #eee}
.bar b{flex:1;font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pill{display:inline-flex;align-items:center;gap:6px;padding:9px 16px;border-radius:999px;font-weight:700;font-size:14px;text-decoration:none;transition:transform .18s ease,box-shadow .18s ease,filter .18s ease}
.pill:hover{transform:translateY(-2px);filter:brightness(1.05)}.pill:active{transform:translateY(0)}
.p-call{background:var(--c);color:#fff}.p-wa{background:#25d366;color:#fff}.p-ghost{background:#fff;color:var(--d);border:1px solid #e5e7eb}
.wrap{max-width:760px;margin:0 auto;padding:0 18px}
/* hero */
.hero{position:relative;overflow:hidden;background:var(--bg);background-size:cover;background-position:center}
.hero-in{max-width:960px;margin:0 auto;padding:34px 18px 38px;display:grid;gap:26px;align-items:center}
.kick{display:inline-block;padding:5px 14px;border-radius:999px;font-size:12.5px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;background:var(--l);color:var(--d);border:1px solid rgba(0,0,0,.06)}
.hero h1{margin:14px 0 8px;font-size:clamp(32px,8vw,54px);line-height:1.08;color:var(--d)}
.hero p{margin:0;max-width:480px;font-size:17px;color:#4b5563}
.cta{display:flex;gap:10px;flex-wrap:wrap;margin-top:20px}.cta .pill{padding:13px 22px;font-size:16px;box-shadow:0 10px 26px rgba(0,0,0,.16)}
.chips{list-style:none;margin:22px 0 0;padding:0;display:flex;gap:8px;flex-wrap:wrap}
.chips li{font-size:13px;font-weight:600;padding:6px 12px;border-radius:999px;background:#fff;border:1px solid rgba(0,0,0,.08);color:var(--d)}
.chips li:before{content:"✓ ";color:var(--c)}
.art{justify-self:center;width:min(70vw,300px);aspect-ratio:1;display:flex;align-items:center;justify-content:center;background-size:cover;background-position:center;position:relative}
.art b{font-size:clamp(70px,22vw,110px);line-height:1;position:relative;z-index:1;animation:fl 5s ease-in-out infinite}
@keyframes fl{50%{transform:translateY(-8px)}}
@media(min-width:760px){.hero-in{grid-template-columns:1.25fr .75fr;padding:56px 18px 60px}.art{width:300px}}
/* split: soft arch with rings (salon, bakery) */
.h-split .art{border-radius:999px 999px 28px 28px;background-color:var(--l);box-shadow:0 0 0 12px rgba(255,255,255,.7),0 0 0 13px var(--c),0 24px 50px rgba(0,0,0,.12)}
.h-split{background:linear-gradient(180deg,var(--bg),#fff)}
.h-split h1{font-style:italic;font-weight:400}
/* clean: bright, trust chips, round art (clinic, dental) */
.h-clean .art{border-radius:50%;background-color:#fff;box-shadow:0 0 0 14px rgba(255,255,255,.8),0 24px 50px rgba(3,105,161,.15)}
.h-clean{background:radial-gradient(900px 300px at 85% 0,#fff,transparent 70%),var(--bg)}
.h-clean h1{font-weight:800}
/* dark: restaurant, garage, gym */
.h-dark{color:#fff}.h-dark h1{color:#fff}.h-dark p{color:rgba(255,255,255,.82)}
.h-dark .kick{background:rgba(255,255,255,.12);color:#fff;border-color:rgba(255,255,255,.25)}
.h-dark .chips li{background:rgba(255,255,255,.1);color:#fff;border-color:rgba(255,255,255,.2)}
.h-dark .art{border-radius:20px;background-color:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.18)}
.h-dark:before{content:"";position:absolute;inset:0;background:radial-gradient(700px 320px at 90% 0,var(--c),transparent 65%);opacity:.55}
.h-dark .hero-in{position:relative}
.h-bold h1{text-transform:uppercase;letter-spacing:.01em;font-weight:900}.h-bold .kick{border-radius:4px}.h-bold .pill{border-radius:6px}
.hp{background-blend-mode:normal}
/* sections */
section{padding:26px 0 2px}h2{margin:0 0 14px;font-size:24px;color:var(--d)}
.sec-bold h2{text-transform:uppercase;letter-spacing:.03em}
.note{font-size:12px;color:#6b7280;margin:10px 0 0}
.mn{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}
.mi{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 16px;background:var(--l);border-radius:var(--r);transition:transform .18s ease,box-shadow .18s ease}
.mi:hover{transform:translateY(-3px);box-shadow:0 10px 24px rgba(0,0,0,.08)}
.mi b{display:block;font-size:15.5px}.mi span{font-size:13px;color:#6b7280}.mi em{font-style:normal;font-weight:700;color:var(--d);white-space:nowrap;font-size:15px}
.t-restaurant .mn{grid-template-columns:1fr;gap:0}
.t-restaurant .mi{background:none;border-radius:0;border-bottom:1px dashed #d6c3b3;padding:14px 2px}.t-restaurant .mi:hover{transform:none;box-shadow:none;background:var(--l)}
.t-garage .mi,.t-gym .mi{border-left:5px solid var(--c);background:#f3f4f6}
.stp{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}
.stp div{display:flex;gap:12px;align-items:flex-start;padding:15px;border:1px solid #eee;border-radius:var(--r);transition:transform .18s ease,box-shadow .18s ease}
.stp div:hover{transform:translateY(-3px);box-shadow:0 10px 24px rgba(0,0,0,.07)}
.stp i{flex:none;width:30px;height:30px;border-radius:50%;background:var(--c);color:#fff;font-style:normal;font-weight:700;display:flex;align-items:center;justify-content:center;font-size:14px}
.stp b{display:block;font-size:15px}.stp span{font-size:13.5px;color:#6b7280}
.gl{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}.gl img{width:100%;aspect-ratio:1;object-fit:cover;border-radius:var(--r);display:block;transition:transform .25s ease}.gl img:hover{transform:scale(1.03)}
details{border-top:1px solid #eee;padding:13px 0}details:last-of-type{border-bottom:1px solid #eee}
summary{cursor:pointer;font-weight:600;list-style:none;display:flex;justify-content:space-between;font-size:15.5px}summary::-webkit-details-marker{display:none}
summary:after{content:"+";color:var(--c);font-weight:700;transition:transform .2s}details[open] summary:after{content:"–"}
details p{margin:8px 0 0;color:#6b7280;font-size:14.5px}
.info{display:grid;gap:12px}.info .row{background:var(--l);border-radius:var(--r);padding:14px 16px}
.info small{display:block;color:var(--c);font-weight:700;text-transform:uppercase;letter-spacing:.06em;font-size:11px;margin-bottom:2px}
.map{margin-top:14px;border-radius:var(--r);overflow:hidden;border:1px solid #eee}.map iframe{display:block;width:100%;height:240px;border:0}
.final{margin:26px 0 0;background:linear-gradient(135deg,var(--c),var(--d));color:#fff;text-align:center;padding:30px 18px}
.final h2{color:#fff;margin-bottom:4px}.final .cta{justify-content:center}.final .p-wa{box-shadow:0 10px 26px rgba(0,0,0,.25)}
footer{text-align:center;font-size:12px;color:#6b7280;padding:16px 16px 92px}
/* sticky booking bar (mobile) */
.sb{position:fixed;left:0;right:0;bottom:0;z-index:30;display:flex;gap:8px;padding:10px 12px calc(10px + env(safe-area-inset-bottom,0px));background:rgba(255,255,255,.96);backdrop-filter:blur(10px);border-top:1px solid #e5e7eb;box-shadow:0 -8px 24px rgba(0,0,0,.08)}
.sb .pill{flex:1;justify-content:center;padding:13px 10px;font-size:15px}
@media(min-width:760px){.sb{left:auto;right:18px;bottom:18px;border:0;background:none;box-shadow:none;padding:0;backdrop-filter:none}.sb .pill{flex:none;padding:14px 22px;box-shadow:0 10px 28px rgba(0,0,0,.25)}.sb .p-ghost{display:none}}
/* scroll reveal (only when JS runs) */
.js .rv{opacity:0;transform:translateY(16px);transition:opacity .55s ease,transform .55s ease}.js .rv.in{opacity:1;transform:none}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}.js .rv{opacity:1;transform:none}}
"""

TPL = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{name} | {sub} in {city}</title>
<meta name="description" content="{name} - {tag} Call or message us.">
<meta property="og:title" content="{name}"><meta property="og:description" content="{tag}">
<meta name="theme-color" content="{c}">
<script type="application/ld+json">{ld}</script>
<style>:root{{--c:{c};--d:{d};--l:{l};--bg:{bg};--r:{r}px;--f:{font}}}{css}</style></head><body class="t-{k}">
{exp}<div class="bar"><b>{emoji} {name}</b>{call_bar}</div>
<header class="hero h-{hcls}"{hero_style}><div class="hero-in"><div class="ht"><span class="kick">{sublabel} · {city}</span>
<h1>{name}</h1><p>{tag} {subline}</p>
<div class="cta"><a class="pill p-wa" href="{wa_url}">💬 {cta}</a>{call_hero}</div>
<ul class="chips">{chips}</ul></div>
<div class="art" aria-hidden="true"{art_style}>{art_emoji}</div></div></header>
<div class="wrap {secb}">
<section class="rv"><h2>{svc_title}</h2><div class="mn">{menu}</div><p class="note">Sample services and prices. Your real ones go here once you approve.</p></section>
<section class="rv"><h2>How it works</h2><div class="stp">{steps}</div></section>
{gallery}
<section class="rv"><h2>Good to know</h2>{faq}</section>
<section class="rv"><h2>Visit us</h2><div class="info">{addr_row}{hours_row}{phone_row}</div>
{map}<p style="margin:14px 0 0"><a class="pill p-ghost" href="{maps_url}" target="_blank" rel="noopener">📍 Open in Google Maps</a></p></section>
</div>
<div class="final rv"><h2>Ready when you are</h2><div class="cta"><a class="pill p-wa" href="{wa_url}">💬 {cta}</a></div></div>
<footer>Demo preview made for {name}. Want this live on your own domain? Message the person who sent you this link.</footer>
<div class="sb"><a class="pill p-wa" href="{wa_url}">💬 {cta}</a>{call_sb}</div>
<script>document.documentElement.classList.add("js");(function(){{var e=document.querySelectorAll(".rv");if(!("IntersectionObserver" in window)){{e.forEach(function(x){{x.classList.add("in")}});return}}var o=new IntersectionObserver(function(a){{a.forEach(function(i){{if(i.isIntersecting){{i.target.classList.add("in");o.unobserve(i.target)}}}})}},{{threshold:.12}});e.forEach(function(x){{o.observe(x)}})}})();</script>
</body></html>"""

def exp_banner(l):
    if not l.get("found") or l.get("keep"): return ""
    d = datetime.date.fromisoformat(l["found"]) + datetime.timedelta(days=CFG.get("demo_days", 14))
    return f'<div class="exp">Free preview made for {html.escape(l["name"])} · available until {d.strftime("%d %b %Y")}</div>'

def build_page(l):
    k = style_key(l); n = NICHE[k]
    name, city = html.escape(l["name"]), html.escape(l["city"])
    ph = l.get("phone")
    if ph: wa_url = f'https://wa.me/{ph}?text=' + urllib.parse.quote(n["wa"].format(name=l["name"]))
    else:  wa_url = f'https://m.me/{l["fb"]}'
    cta_txt = n["cta"] if ph else "Message us on Facebook"
    cur = CFG["markets"].get(l.get("market"), {}).get("currency", "")
    sc = CUR_SCALE.get(cur, 1)
    ct = CONTENT.get(k) or dict(menu=[(t, "", None) for e, t in n["items"]],
        steps=[("Message us","Tell us what you need."),("Get confirmed","We reply with a time."),("Visit us","We look forward to seeing you.")],
        faq=[("How do I get in touch?","Tap the button and send us a message, or call us."),("Where are you?","See the map and address below.")])
    menu = "".join(f'<div class="mi"><p style="margin:0"><b>{html.escape(a)}</b><span>{html.escape(d)}</span></p>' + (f'<em>from {html.escape(cur)}{p*sc}</em>' if p else '<em>On request</em>') + '</div>' for a, d, p in ct["menu"])
    steps = "".join(f'<div><i>{i}</i><p style="margin:0"><b>{html.escape(a)}</b><span>{html.escape(d)}</span></p></div>' for i, (a, d) in enumerate(ct["steps"], 1))
    faq = "".join(f'<details><summary>{html.escape(q)}</summary><p>{html.escape(a)}</p></details>' for q, a in ct["faq"])
    th = THEME[k]
    photos = [u for u in (CFG.get("photos", {}).get(k) or []) if isinstance(u, str) and u.startswith("https://")][:4]
    ge = lambda u: html.escape(u, quote=True)
    gallery = ("<section class=\"rv\"><h2>Gallery</h2><div class=\"gl\">" + "".join(f'<img src="{ge(u)}" alt="{name} - {html.escape(l.get("sub") or k)}" loading="lazy">' for u in photos[1:] or photos) + "</div></section>") if photos else ""
    hero_style = art_style = ""
    if photos:
        if "dark" in th["cls"]: hero_style = f' style="background-image:linear-gradient(rgba(0,0,0,.62),rgba(0,0,0,.62)),url({ge(photos[0])})"'
        else: art_style = f' style="background-image:url({ge(photos[0])})"'
    art_emoji = "" if (photos and "dark" not in th["cls"]) else f"<b>{n['emoji']}</b>"
    chips = "".join(f"<li>{html.escape(t if ph else t.replace('WhatsApp', 'Messenger'))}</li>" for e, t, d in n["why"])
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
    return TPL.format(exp=exp_banner(l), name=name, city=city, sub=html.escape(l.get("sub") or l.get("cat", "")), sublabel=html.escape(l.get("sub") or l.get("cat", "")),
                      tag=html.escape(n["tag"]), subline=html.escape(n["sub"]), cta=html.escape(cta_txt), emoji=n["emoji"],
                      c=n["c"], d=n["d"], l=n["l"],
                      call_bar=(f'<a class="pill p-call" href="tel:+{ph}">Call</a>' if ph else ""),
                      call_hero=(f'<a class="pill p-ghost" href="tel:+{ph}">📞 Call now</a>' if ph else ""),
                      phone_row=(f'<div class="row"><small>Phone</small><a href="tel:+{ph}">+{ph}</a></div>' if ph else ""), wa_url=html.escape(wa_url), svc_title=html.escape(n["svc_title"]),
                      k=k, bg=th["bg"], r=th["r"], font=th["font"], css=CSS, hcls=th["cls"].replace(" ", " h-"), secb=("sec-bold" if "bold" in th["cls"] else ""),
                      hero_style=hero_style, art_style=art_style, art_emoji=art_emoji, chips=chips, gallery=gallery,
                      call_sb=(f'<a class="pill p-ghost" href="tel:+{ph}">📞 Call</a>' if ph else ""),
                      menu=menu, steps=steps, faq=faq, addr_row=addr_row, hours_row=hours_row, map=mp, maps_url=html.escape(maps_url),
                      ld=json.dumps(ld, ensure_ascii=False).replace("</", "<\\/"))

def _cur(l):
    cur = CFG["markets"].get(l.get("market"), {}).get("currency", "£")
    return cur, CUR_SCALE.get(cur, 1)

def build_pro(l):
    """5-page Pro demo for one lead, made from the sample Pro pages in <site>/demos/<niche>-pro. -> {filename: html} or {}"""
    t = PRO_TPL.get(style_key(l)); src = os.path.join(SITE, "demos", t or "")
    if not t or not os.path.isdir(src): return {}
    esc, q = html.escape, lambda v: urllib.parse.quote(v, safe="")
    name, city, ph = l["name"], l["city"], l.get("phone")
    home = open(os.path.join(src, "index.html"), encoding="utf-8").read()
    m = re.search(r"<title>(.*?)\s*\|\s*[^<]*? in ([^<]*)</title>", home); sname, scity = html.unescape(m.group(1)), m.group(2).strip()
    sub = l.get("sub") or l.get("cat") or "Business"
    la, lo, addr = l.get("lat"), l.get("lon"), l.get("addr", "")
    maps_url = f"https://www.google.com/maps?q={la},{lo}" if la is not None and lo is not None else "https://www.google.com/maps/search/" + q(f"{name} {addr} {city}")
    cur, sc = _cur(l)
    hrs = pretty_hours(l.get("hours", ""))
    visit = (f'<p class="sub">{esc(addr)}</p>' if addr else "") + (f'<div class="hrs"><div><span>Opening hours</span><span>{esc(hrs)}</span></div></div>' if hrs else "")
    story = f"{esc(name)} is a local {esc(sub.lower())} in {esc(city)}. This is where your story goes: how you started, what you care about and who looks after your customers. We write it with you once you approve the demo."
    if l.get("found") and not l.get("keep"):
        d = datetime.date.fromisoformat(l["found"]) + datetime.timedelta(days=CFG.get("demo_days", 14))
        rib = f'<div class="rib">Free preview made for {esc(name)} · available until {d.strftime("%d %b %Y")}</div>'
    else: rib = f'<div class="rib">Preview made for {esc(name)}</div>'
    foot = f'<footer>Demo preview made for {esc(name)} by <a href="{SITE_URL}">Naem Studio</a>. Text, prices and services are samples until you approve. Want it live on your own domain? <a href="{SITE_URL}/#contact">Message us</a>.</footer>'
    out = {}
    for f in sorted(os.listdir(src)):
        if not f.endswith(".html"): continue
        s = open(os.path.join(src, f), encoding="utf-8").read()
        s = re.sub(r'https://www\.google\.com/maps/search/[^"\']+', html.escape(maps_url), s)
        s = re.sub(r"<title>.*?</title>", f"<title>{esc(name)} | {esc(sub)} in {esc(city)}</title>", s, count=1)
        for old, new in ((q(sname), q(name)), (esc(sname), esc(name)), (sname, esc(name))):
            s = s.replace(old, new)
        s = s.replace(f'"addressLocality":"{scity}"', '"addressLocality":' + json.dumps(city, ensure_ascii=False).replace("</", "<\\/")).replace(scity, esc(city))
        if ph: s = s.replace("447700900123", ph)
        else:
            s = re.sub(r'<a[^>]*href="tel:\+447700900123"[^>]*>.*?</a>', "", s, flags=re.S).replace(',"telephone":"+447700900123"', "")
            s = s.replace("</style>", ".dock{grid-template-columns:1.4fr 1fr!important}.qa{grid-template-columns:repeat(2,1fr)!important}</style>", 1)
        if CFG.get("seller_wa"): s = s.replace("917522805545", CFG["seller_wa"])
        s = re.sub(r"£(\d+)", lambda x: f"{cur}{int(x.group(1)) * sc}", s)
        for h2 in ("What people say", "Meet the team", "Guest favourites"):   # invented reviews / staff / dishes never go on a real business's page
            s = re.sub(r'<section class="rv"[^>]*><h2>' + h2 + r'</h2>.*?</section>\s*', "", s, flags=re.S)
        s = re.sub(r'<div class="chips">.*?</div>', "", s, count=1, flags=re.S)
        s = re.sub(r'<div class="rib">.*?</div>', rib, s, count=1)
        s = re.sub(r"<footer>.*?</footer>", foot, s, count=1, flags=re.S)
        s = re.sub(r'(<h2>Our story</h2><p class="sub">).*?(</p>)', lambda x: x.group(1) + story + x.group(2), s, count=1, flags=re.S)
        s = re.sub(r'<div class="hrs" id="hrs">(?:<div data-d="\d"><span>[^<]*</span><span>[^<]*</span></div>)+</div>', visit, s)
        s = s.replace('fetch("../photos.json")', 'fetch("/demos/photos.json")')
        out[f] = s
    return out

def slug(l):
    s = re.sub(r"[^a-z0-9]+", "-", l["name"].lower()).strip("-")[:30] or "biz"
    return re.sub(r"[^a-z0-9]+", "-", f'{l["city"].lower()}-{s}-{l["id"][:5]}').strip("-")

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

def pitch(l, url, url5=""):
    m = CFG["markets"][l["market"]]
    seller, price, cur = CFG["seller_name"], m["price"], m["currency"]
    p5 = m.get("price5")
    brand = CFG.get("brand") or seller
    bits = []
    if CFG.get("seller_wa"): bits.append(f'WhatsApp: https://wa.me/{CFG["seller_wa"]}')
    if CFG.get("seller_fb"): bits.append(f'Facebook: https://m.me/{CFG["seller_fb"]}')
    if CFG.get("seller_contact"): bits.append(CFG["seller_contact"])
    contact = ("\n" + " | ".join(bits)) if bits else ""
    nk = l.get("niche") if l.get("niche") in BENEFIT_HI else "restaurant"
    two = bool(url5)
    if m["lang"] == "hinglish":
        links = (f"1 page: {url}\n5 page (Pro): {url5}" if two else url)
        cost = (f"Pasand aaye toh aapki real photos aur details ke saath final kar dunga: 1 page {cur}{price}" + (f", 5 page Pro {cur}{p5}" if p5 else "") + ".") if two else f"Pasand aaye toh {cur}{price} mein aapki real photos aur details ke saath final kar dunga."
        return (f"Namaste! Main {seller}, {brand} se, web developer hoon. {l['name']} ke liye maine demo website bana di hai jisse {BENEFIT_HI[nk]}:\n{links}\n"
                f"{cost} Koi change chahiye toh bata dijiye.{contact}")
    # English: human-style DM (varied hook per lead, price in USD, no seller WA link -- they are already chatting on WhatsApp)
    NOUN = {"salon": "salons", "clinic": "clinics", "restaurant": "restaurants", "garage": "garages", "gym": "gyms", "bakery": "bakeries"}
    h = int(str(l.get("id", "0"))[:8], 16) % 3 if re.fullmatch(r"[0-9a-f]{8,}", str(l.get("id", ""))[:8] or "x") else 0
    hook = [f"Hi, is this {l['name']}?",
            f"Hey, quick question, does {l['name']} have its own website?",
            f"Hi, I came across {l['name']} while looking at local {NOUN[nk]} in {l['city']}."][h]
    intro = f"We're {brand}, we build websites for local businesses. We couldn't find one for you, so we made a quick demo where {BENEFIT_EN[nk]}:"
    links = (f"1-page: {url}\n5-page: {url5}" if two else url)
    if two:
        cost = f"If you like one, we can finish it with your real photos and details: ${price} for the 1-page or ${p5} for the 5-page (USD). Happy to change anything first, and no worries at all if it's not the right time."
    else:
        cost = f"If you like it, we can finish it with your real photos and details for ${price} (USD). Happy to change anything first, and no worries at all if it's not the right time."
    return f"{hook} {intro}\n{links}\n{cost}\nA proper website builds trust and brings you new customers who search before they visit."

def reach(l, text):
    """Primary outreach link + channel list. WhatsApp when a mobile exists, Facebook Messenger otherwise."""
    ch = (["wa"] if l.get("phone") else []) + (["fb"] if l.get("fb") else [])
    l["channels"] = ch
    if l.get("fb"): l["fb_link"] = f'https://m.me/{l["fb"]}'
    if l.get("phone"): return f'https://wa.me/{l["phone"]}?text=' + urllib.parse.quote(text)
    return l["fb_link"]

def expire(leads):
    """Demo pages auto-delete after demo_days (unless lead is marked keep=true, e.g. a paying client)."""
    days, today, gone = CFG.get("demo_days", 14), datetime.date.today(), 0
    for l in leads:
        if not l.get("url") or l.get("keep") or l.get("expired") or not l.get("found"): continue
        if (today - datetime.date.fromisoformat(l["found"])).days >= days:
            shutil.rmtree(f"{SITE}/d/" + l["url"].rstrip("/").split("/")[-1], ignore_errors=True)
            l.update(expired=True, live=False, url="", url5="", pitch="", wa="")
            gone += 1
    if gone: print(f"EXPIRED demos deleted: {gone}")

def main():
    leads = json.load(open("data/leads.json"))
    expire(leads)
    made = 0
    for l in leads:
        if not l.get("live") or l.get("expired"): continue
        if l.get("url") and l.get("ver") == VER: continue
        s = slug(l)
        d = f"{SITE}/d/{s}"; os.makedirs(d, exist_ok=True)
        open(f"{d}/index.html", "w", encoding="utf-8").write(build_page(l))
        shutil.rmtree(f"{d}/pro", ignore_errors=True)
        pro = build_pro(l)
        if pro:
            os.makedirs(f"{d}/pro", exist_ok=True)
            for fn, h in pro.items(): open(f"{d}/pro/{fn}", "w", encoding="utf-8").write(h)
        l["url"] = f"{BASE}/{s}/"
        l["url5"] = f"{BASE}/{s}/pro/" if pro else ""
        l["ver"] = VER
        l["pitch"] = pitch(l, l["url"], l["url5"])
        l["wa"] = reach(l, l["pitch"])
        made += 1
        if l.get("manual"): print("MANUAL DEMO:", l["url"]); print(l["pitch"])
    if os.environ.get("REGEN_PITCHES", "").lower() in ("1", "true", "yes"):   # seller name / price changed -> pitches only
        for l in leads:
            if l.get("url"):
                l["pitch"] = pitch(l, l["url"], l.get("url5", ""))
                l["wa"] = reach(l, l["pitch"])
    json.dump(leads, open("data/leads.json", "w"), ensure_ascii=False, indent=0)
    print(f"GENERATED={made} TOTAL={len(leads)} LIVE={sum(1 for l in leads if l.get('live'))}")

if __name__ == "__main__":
    main()
