"""Build demo site + pitch + wa.me link for every lead that has none yet."""
import json, os, re, html, urllib.parse

CFG = json.load(open("config.json"))
OWNER_REPO = os.environ.get("GITHUB_REPOSITORY", "dcabothyperliquid/leadsites")
USER, REPO = OWNER_REPO.split("/")
BASE = f"https://{USER}.github.io/{REPO}/s"
THEMES = [("#0f766e","#ccfbf1"),("#1d4ed8","#dbeafe"),("#9333ea","#f3e8ff"),("#c2410c","#ffedd5"),("#be123c","#ffe4e6"),("#15803d","#dcfce7")]

TPL = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name} – {city}</title>
<style>
:root{{--c:{c};--l:{l}}}*{{box-sizing:border-box}}
body{{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#111;background:#fff}}
.hero{{background:var(--c);color:#fff;padding:56px 20px 44px;text-align:center}}
.hero h1{{margin:0 0 8px;font-size:30px}}.hero p{{margin:0;opacity:.9}}
.badge{{display:inline-block;background:rgba(255,255,255,.18);padding:4px 12px;border-radius:20px;font-size:13px;margin-bottom:14px}}
.cta{{display:flex;gap:10px;justify-content:center;margin-top:22px;flex-wrap:wrap}}
.btn{{padding:13px 22px;border-radius:10px;font-weight:700;text-decoration:none;font-size:16px}}
.call{{background:#fff;color:var(--c)}}.wa{{background:#25d366;color:#fff}}
.wrap{{max-width:620px;margin:0 auto;padding:28px 20px}}
.card{{background:var(--l);border-radius:14px;padding:18px;margin-bottom:14px}}
.card h2{{margin:0 0 6px;font-size:15px;color:var(--c);text-transform:uppercase;letter-spacing:.05em}}
.card p{{margin:0;font-size:17px;line-height:1.5}}
footer{{text-align:center;font-size:12px;color:#777;padding:22px}}
</style></head><body>
<div class="hero"><span class="badge">{cat} · {city}</span><h1>{name}</h1><p>Welcome! Call or message us anytime.</p>
<div class="cta"><a class="btn call" href="tel:+{phone}">📞 Call Now</a><a class="btn wa" href="https://wa.me/{phone}">💬 WhatsApp</a></div></div>
<div class="wrap">
{addr_card}{hours_card}
<div class="card"><h2>Contact</h2><p>+{phone}</p></div>
</div>
<footer>Demo preview made for {name}. Want this live on your own domain? Ask the person who sent you this link.</footer>
</body></html>"""

def card(title, text):
    return f'<div class="card"><h2>{title}</h2><p>{html.escape(text)}</p></div>\n' if text else ""

def slug(l):
    s = re.sub(r"[^a-z0-9]+", "-", l["name"].lower()).strip("-")[:30] or "biz"
    return f'{l["city"].lower()}-{s}-{l["id"][:5]}'

def pitch(l, url):
    m = CFG["markets"][l["market"]]
    seller, price, cur = CFG["seller_name"], m["price"], m["currency"]
    contact = f' {CFG["seller_contact"]}' if CFG.get("seller_contact") else ""
    if m["lang"] == "hinglish":
        return (f"Namaste! Main {seller} hoon, web developer. Maine {l['name']} ke liye ek chhota demo website bana diya hai, "
                f"dekhiye: {url}\nAgar pasand aaye toh {cur}{price} mein aapke naam se live kar dunga (domain/hosting setup ke saath). "
                f"Koi change chahiye toh bata dijiye.{contact}")
    return (f"Hi! I'm {seller}, a web developer. I noticed {l['name']} doesn't have a website, so I built a quick demo for you: {url}\n"
            f"If you like it, I can put it live under your own name for {cur}{price} (domain & hosting setup included). Happy to tweak anything.{contact}")

def main():
    leads = json.load(open("data/leads.json"))
    made = 0
    regen = os.environ.get("REGEN_PITCHES", "").lower() in ("1", "true", "yes")
    for l in leads:
        if l.get("url") and regen:   # seller name / price changed -> rebuild pitch + wa link, keep the demo page
            l["pitch"] = pitch(l, l["url"])
            l["wa"] = f'https://wa.me/{l["phone"]}?text=' + urllib.parse.quote(l["pitch"])
            made += 1
            continue
        if l.get("url"): continue
        s = slug(l)
        d = f"docs/s/{s}"; os.makedirs(d, exist_ok=True)
        c, lt = THEMES[int(l["id"], 16) % len(THEMES)]
        open(f"{d}/index.html", "w", encoding="utf-8").write(TPL.format(
            name=html.escape(l["name"]), city=html.escape(l["city"]), cat=html.escape(l["cat"]), phone=l["phone"], c=c, l=lt,
            addr_card=card("Address", l.get("addr", "")), hours_card=card("Opening hours", l.get("hours", ""))))
        l["url"] = f"{BASE}/{s}/"
        l["pitch"] = pitch(l, l["url"])
        l["wa"] = f'https://wa.me/{l["phone"]}?text=' + urllib.parse.quote(l["pitch"])
        made += 1
    json.dump(leads, open("data/leads.json", "w"), ensure_ascii=False, indent=0)
    open("docs/index.html", "w").write("<!doctype html><meta charset=utf-8><title>demo sites</title><p>Demo sites live under /s/</p>")
    print(f"GENERATED={made} TOTAL={len(leads)}")

if __name__ == "__main__":
    main()
