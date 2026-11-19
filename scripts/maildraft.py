"""Email draft builder (shared by drafts.py + mailer.py). stdlib only.
Draft = subject + body (plain text, editable in the Xbot UI). The legal footer (who we are + STOP line + optional address) is added at send time."""
import json, os, re, html, hashlib, urllib.request

VER = "2"   # bump when the template / prompt changes -> all drafts get rebuilt
NICHE_LINE = {
    "salon": "see your services and timings and book on WhatsApp",
    "clinic": "see your timings and request an appointment in one message",
    "restaurant": "see your hours and order or book a table on WhatsApp",
    "garage": "see your services and book a slot in one message",
    "gym": "see your timings and ask about a trial in one message",
    "bakery": "see your range and order a cake on WhatsApp",
}


def prices(cfg, mk):
    m = cfg.get("markets", {}).get(mk, {})
    cur = m.get("currency", "")
    return cur + str(m.get("price", "")), (cur + str(m["price5"])) if m.get("price5") else ""


def version(cfg):
    e = cfg.get("email", {})
    blob = json.dumps([VER, e.get("style_note", ""), e.get("address", ""), cfg.get("seller_name"), cfg.get("brand"), cfg.get("seller_wa"),
                       {k: [v.get("currency"), v.get("price"), v.get("price5")] for k, v in cfg.get("markets", {}).items()}], sort_keys=True)
    return hashlib.md5(blob.encode()).hexdigest()[:8]


def template_body(l, cfg):
    p1, p5 = prices(cfg, l["market"])
    seller, brand = cfg.get("seller_name", ""), cfg.get("brand", "")
    what = NICHE_LINE.get(l.get("niche"), "see your services and timings and get in touch in one message")
    lines = [f"Hi {l['name']} team,", "",
             f"I'm {seller} from {brand}. I couldn't find a website for {l['name']}, so I put together a quick demo of what one could look like, "
             f"where customers can {what}:", "", f"1-page demo: {l['url']}"]
    if l.get("url5"):
        lines.append(f"5-page demo: {l['url5']}")
    lines += ["", "If you like it, we can finish it with your real photos and details"
              + (f" for {p1} (1-page)" + (f" or {p5} (5-page)" if p5 else "") if p1 else "") + ". "
              "Happy to tweak anything first, and no pressure at all if it's not the right time.", "", "Kind regards,", f"{seller}, {brand}"]
    if cfg.get("seller_wa"):
        lines.append(f"WhatsApp: +{cfg['seller_wa']}")
    return "\n".join(lines)


def ai_body(l, cfg):
    key = (os.environ.get("GROQ_API_KEY") or "").strip()
    if not key:
        return None
    p1, p5 = prices(cfg, l["market"])
    style = str(cfg.get("email", {}).get("style_note", "")).strip()[:300]
    facts = {"business": l["name"], "type": l.get("sub") or l.get("niche"), "city": l["city"], "opening_hours": l.get("hours") or "",
             "demo_1page": l["url"], "demo_5page": l.get("url5") or "", "price_1page": p1, "price_5page": p5,
             "sender": cfg.get("seller_name"), "company": cfg.get("brand"), "whatsapp": ("+" + cfg["seller_wa"]) if cfg.get("seller_wa") else ""}
    prompt = ("Write a short, friendly cold proposal email (90-140 words, plain English, no hype, no emojis) from a small web studio to a local business "
              "that has no website. Mention we already built a free demo for them and include the demo link(s) exactly as given. Mention the price only "
              "if given. Offer to tweak anything first, and be relaxed about it not being the right time. Use ONLY these facts, invent nothing "
              "(no reviews, no stats, no claims about their business):\n" + json.dumps(facts, ensure_ascii=False) +
              (f"\nExtra style instructions from the sender (follow them, but keep the rules above): {style}" if style else "") +
              '\nReturn JSON: {"subject": "<max 60 chars, specific, no clickbait>", "body": "<email text incl. greeting and sign-off>"}')
    req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                                 data=json.dumps({"model": os.environ.get("GROQ_MODEL") or "llama-3.3-70b-versatile", "temperature": 0.6, "max_tokens": 450,
                                                  "response_format": {"type": "json_object"},
                                                  "messages": [{"role": "user", "content": prompt}]}).encode())
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            j = json.loads(json.load(r)["choices"][0]["message"]["content"])
        subj, body = str(j.get("subject", "")).strip(), str(j.get("body", "")).strip()
    except Exception as e:
        print(f"  groq failed: {type(e).__name__} {str(e)[:80]}")
        return None
    allowed = {l["url"], l.get("url5") or ""}
    links = set(re.findall(r"https?://[^\s)>\]]+", body))
    if not (10 <= len(subj) <= 80 and 250 <= len(body) <= 1300 and l["url"] in body and all(u.rstrip(".,") in allowed for u in links)):
        print("  groq draft rejected by validator -> template")
        return None
    return subj, body


def build(l, cfg):
    """-> (subject, body, used_ai)"""
    ai = ai_body(l, cfg)
    if ai:
        return ai[0], ai[1], True
    return f"A quick website idea for {l['name']}", template_body(l, cfg), False


def footer(l, cfg):
    foot = [f"You're receiving this one-off email because {l['name']} is listed publicly as a local business. "
            "If you'd rather not hear from us, just reply STOP and we won't email you again."]
    if cfg.get("email", {}).get("address"):
        foot.append(str(cfg["email"]["address"]))
    return foot


def render(l, cfg, body):
    """-> (text, html) with the footer attached."""
    foot = footer(l, cfg)
    text = body + "\n\n--\n" + "\n".join(foot)
    htm = "<div style=\"font-family:Arial,sans-serif;font-size:15px;line-height:1.5;color:#222\">" + "".join(
        "<p style=\"margin:0 0 12px\">" + re.sub(r"(https?://[^\s<]+)", r'<a href="\1">\1</a>', html.escape(par)).replace("\n", "<br>") + "</p>"
        for par in body.split("\n\n")) + "<hr style=\"border:0;border-top:1px solid #ddd;margin:16px 0\"><p style=\"font-size:12px;color:#777\">" + \
        "<br>".join(html.escape(x) for x in foot) + "</p></div>"
    return text, htm
