"""Auto proposal emails. Runs inside email.yml (GitHub Actions) -- nothing runs on Render.

One personalised email per lead (first contact only; follow-ups stay manual in the Xbot Leads tab, on WhatsApp/Messenger).
Safety rails: off by default (config.email.enabled), only chosen markets, local business hours + weekdays, daily cap, small per-run batch with
random gaps, one email per address ever, skips any lead already touched in Xbot (Turso status != new), skips Brevo-blocked/unsubscribed
addresses, every mail carries sender identity + opt-out line + List-Unsubscribe header.

Env (GitHub secrets): BREVO_API_KEY  (or SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS)  + MAIL_FROM [MAIL_FROM_NAME, MAIL_REPLY_TO]
                      TURSO_URL + TURSO_TOKEN (same DB as Xbot: reads lead status, marks 'sent')   GROQ_API_KEY (optional: AI-written body)
Inputs: DRY_RUN=true -> print drafts, send nothing | TEST_TO=addr -> send ONE draft to that address, no records."""
import json, os, re, ssl, sys, time, random, html, smtplib, datetime, urllib.request, urllib.error
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from zoneinfo import ZoneInfo
import emailutil as U

CFG = json.load(open("config.json"))
LEADS, OUTBOX = "data/leads.json", "data/outbox.json"
E = CFG.get("email", {})
TZ = {"AU": "Australia/Melbourne", "AE": "Asia/Dubai", "UK": "Europe/London", "IN": "Asia/Kolkata", "US": "America/New_York"}
PER_RUN = 5
PENDING_TTL = 48 * 3600
env = lambda k: (os.environ.get(k) or "").strip()
DRY, TEST_TO = env("DRY_RUN").lower() in ("1", "true", "yes"), env("TEST_TO")

NICHE_LINE = {
    "salon": "see your services and timings and book on WhatsApp",
    "clinic": "see your timings and request an appointment in one message",
    "restaurant": "see your hours and order or book a table on WhatsApp",
    "garage": "see your services and book a slot in one message",
    "gym": "see your timings and ask about a trial in one message",
    "bakery": "see your range and order a cake on WhatsApp",
}


# ── Turso (HTTP pipeline) ────────────────────────────────────────────────
def turso(sql, args=()):
    url = env("TURSO_URL").replace("libsql://", "https://").rstrip("/")
    def arg(a):
        if a is None: return {"type": "null"}
        if isinstance(a, int): return {"type": "integer", "value": str(a)}
        return {"type": "text", "value": str(a)}
    body = {"requests": [{"type": "execute", "stmt": {"sql": sql, "args": [arg(a) for a in args]}}, {"type": "close"}]}
    req = urllib.request.Request(url + "/v2/pipeline", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + env("TURSO_TOKEN"), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.load(r)["results"][0]
    if res.get("type") == "error":
        raise RuntimeError(res.get("error", {}).get("message", "turso error"))
    rs = res["response"]["result"]
    cols = [c["name"] for c in rs.get("cols", [])]
    return [{c: (cell.get("value") if cell.get("type") != "null" else None) for c, cell in zip(cols, row)} for row in rs.get("rows", [])]


def ts(v):
    try:
        return datetime.datetime.strptime(v, "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc).timestamp() if v else 0
    except ValueError:
        return 0


# ── drafting ─────────────────────────────────────────────────────────────
def prices(mk):
    m = CFG["markets"].get(mk, {})
    cur = m.get("currency", "")
    return cur + str(m.get("price", "")), (cur + str(m["price5"])) if m.get("price5") else ""


def template_body(l):
    p1, p5 = prices(l["market"])
    seller, brand = CFG.get("seller_name", ""), CFG.get("brand", "")
    what = NICHE_LINE.get(l.get("niche"), "see your services and timings and get in touch in one message")
    lines = [f"Hi {l['name']} team,", "",
             f"I'm {seller} from {brand}. I couldn't find a website for {l['name']}, so I put together a quick demo of what one could look like, "
             f"where customers can {what}:", "",
             f"1-page demo: {l['url']}"]
    if l.get("url5"):
        lines.append(f"5-page demo: {l['url5']}")
    lines += ["", "If you like it, we can finish it with your real photos and details"
              + (f" for {p1} (1-page)" + (f" or {p5} (5-page)" if p5 else "") if p1 else "") + ". "
              "Happy to tweak anything first, and no pressure at all if it's not the right time.", "", "Kind regards,", f"{seller}, {brand}"]
    if CFG.get("seller_wa"):
        lines.append(f"WhatsApp: +{CFG['seller_wa']}")
    return "\n".join(lines)


def ai_body(l):
    key = env("GROQ_API_KEY")
    if not key:
        return None
    p1, p5 = prices(l["market"])
    facts = {"business": l["name"], "type": l.get("sub") or l.get("niche"), "city": l["city"], "opening_hours": l.get("hours") or "",
             "demo_1page": l["url"], "demo_5page": l.get("url5") or "", "price_1page": p1, "price_5page": p5,
             "sender": CFG.get("seller_name"), "company": CFG.get("brand"), "whatsapp": ("+" + CFG["seller_wa"]) if CFG.get("seller_wa") else ""}
    prompt = ("Write a short, friendly cold proposal email (90-140 words, plain English, no hype, no emojis) from a small web studio to a local business "
              "that has no website. Mention we already built a free demo for them and include the demo link(s) exactly as given. Mention the price only "
              "if given. Offer to tweak anything first, and be relaxed about it not being the right time. Use ONLY these facts, invent nothing "
              "(no reviews, no stats, no claims about their business):\n" + json.dumps(facts, ensure_ascii=False) +
              '\nReturn JSON: {"subject": "<max 60 chars, specific, no clickbait>", "body": "<email text incl. greeting and sign-off>"}')
    req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                                 data=json.dumps({"model": "llama-3.3-70b-versatile", "temperature": 0.6, "max_tokens": 450,
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


def draft(l):
    ai = ai_body(l)
    subj, body = ai if ai else (f"A quick website idea for {l['name']}", template_body(l))
    foot = [f"You're receiving this one-off email because {l['name']} is listed publicly as a local business. "
            "If you'd rather not hear from us, just reply STOP and we won't email you again."]
    if E.get("address"):
        foot.append(str(E["address"]))
    text = body + "\n\n--\n" + "\n".join(foot)
    htm = "<div style=\"font-family:Arial,sans-serif;font-size:15px;line-height:1.5;color:#222\">" + "".join(
        "<p style=\"margin:0 0 12px\">" + re.sub(r"(https?://[^\s<]+)", r'<a href="\1">\1</a>', html.escape(par)).replace("\n", "<br>") + "</p>"
        for par in body.split("\n\n")) + "<hr style=\"border:0;border-top:1px solid #ddd;margin:16px 0\"><p style=\"font-size:12px;color:#777\">" + \
        "<br>".join(html.escape(x) for x in foot) + "</p></div>"
    return subj, text, htm, bool(ai)


# ── sending ──────────────────────────────────────────────────────────────
def send(to, name, subj, text, htm):
    frm, reply = env("MAIL_FROM"), env("MAIL_REPLY_TO") or env("MAIL_FROM")
    fname = env("MAIL_FROM_NAME") or CFG.get("brand") or CFG.get("seller_name") or ""
    unsub = f"<mailto:{reply}?subject=STOP>"
    if env("BREVO_API_KEY"):
        payload = {"sender": {"name": fname, "email": frm}, "to": [{"email": to, "name": name[:60]}], "replyTo": {"email": reply},
                   "subject": subj, "textContent": text, "htmlContent": htm, "headers": {"List-Unsubscribe": unsub}}
        req = urllib.request.Request("https://api.brevo.com/v3/smtp/email", data=json.dumps(payload).encode(), method="POST",
                                     headers={"api-key": env("BREVO_API_KEY"), "Content-Type": "application/json", "accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r).get("messageId", "")
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Reply-To"], msg["Subject"] = formataddr((fname, frm)), formataddr((name[:60], to)), reply, subj
    msg["List-Unsubscribe"], msg["Message-ID"] = unsub, make_msgid(domain=frm.split("@")[-1])
    msg.set_content(text)
    msg.add_alternative(htm, subtype="html")
    host, port = env("SMTP_HOST"), int(env("SMTP_PORT") or 587)
    if port == 465:
        s = smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=30)
    else:
        s = smtplib.SMTP(host, port, timeout=30)
        s.starttls(context=ssl.create_default_context())
    with s:
        s.login(env("SMTP_USER"), env("SMTP_PASS"))
        s.send_message(msg)
    return msg["Message-ID"]


def brevo_blocked():
    """Addresses Brevo already blocks (unsubscribed / hard bounce / spam complaint). Best effort."""
    out = set()
    if not env("BREVO_API_KEY"):
        return out
    try:
        for off in range(0, 2000, 100):
            req = urllib.request.Request(f"https://api.brevo.com/v3/smtp/blockedContacts?limit=100&offset={off}",
                                         headers={"api-key": env("BREVO_API_KEY"), "accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                cs = json.load(r).get("contacts", [])
            out |= {c.get("email", "").lower() for c in cs}
            if len(cs) < 100:
                break
    except Exception as e:
        print(f"  brevo blocklist check failed: {type(e).__name__}")
    return out


def in_window(mk, now_utc):
    h0, h1 = (E.get("hours") or [9, 16])[:2]
    loc = now_utc.astimezone(ZoneInfo(TZ.get(mk, "UTC")))
    return (loc.weekday() < 5 or not E.get("weekdays_only", True)) and h0 <= loc.hour < h1


def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    testing = DRY or bool(TEST_TO)
    if not testing:
        if not E.get("enabled"):
            print("EMAIL OFF (config.email.enabled=false) -- nothing sent"); return
        miss = [k for k, ok in (("MAIL_FROM", env("MAIL_FROM")), ("BREVO_API_KEY or SMTP_*", env("BREVO_API_KEY") or (env("SMTP_HOST") and env("SMTP_USER") and env("SMTP_PASS"))),
                                ("TURSO_URL/TURSO_TOKEN", env("TURSO_URL") and env("TURSO_TOKEN"))) if not ok]
        if miss:
            print("EMAIL NOT CONFIGURED, missing secrets:", ", ".join(miss)); return
    leads = json.load(open(LEADS))
    outbox = json.load(open(OUTBOX)) if os.path.exists(OUTBOX) else {}
    st = {}
    if env("TURSO_URL") and env("TURSO_TOKEN"):
        st = {r["id"]: r for r in turso("SELECT id, status, contacts, pending_at FROM leads_status")}
    sent_addr = {(o.get("to") or "").lower() for o in outbox.values()} | brevo_blocked()
    today = now.strftime("%Y-%m-%d")
    done_today = sum(1 for o in outbox.values() if (o.get("at") or "")[:10] == today)
    room = max(0, int(E.get("daily_cap", 15)) - done_today)
    mks = set(E.get("markets") or [])
    print(f"EMAIL mode={'TEST' if TEST_TO else 'DRY' if DRY else 'LIVE'} markets={sorted(mks)} cap_left={room} outbox={len(outbox)}")
    cand = []
    for l in leads:
        em = l.get("email")
        if not (em and l.get("live") and l.get("url") and not l.get("expired") and l["market"] in mks and l["id"] not in outbox and em.lower() not in sent_addr):
            continue
        s = st.get(l["id"])
        if s and ((s.get("status") or "new") != "new" or int(s.get("contacts") or 0) > 0 or (s.get("pending_at") and now.timestamp() - ts(s["pending_at"]) < PENDING_TTL)):
            continue
        if not testing and not in_window(l["market"], now):
            continue
        cand.append(l)
    random.shuffle(cand)
    print(f"  eligible now: {len(cand)}")
    n = 0
    for l in cand:
        if not testing and (n >= PER_RUN or n >= room):
            break
        subj, text, htm, ai = draft(l)
        if DRY:
            print(f"\n--- DRAFT to {l['email']} ({l['market']}, {'AI' if ai else 'template'}) ---\nSubject: {subj}\n{text}\n"); n += 1
            if n >= 3: break
            continue
        try:
            if TEST_TO:
                send(TEST_TO, l["name"], "[TEST] " + subj, text, htm); print(f"TEST mail sent to {TEST_TO}"); return
            mid = send(l["email"], l["name"], subj, text, htm)
        except Exception as e:
            print(f"  SEND FAILED {l['id']} {type(e).__name__}: {str(e)[:120]}")
            if isinstance(e, urllib.error.HTTPError) and e.code in (401, 403, 429):
                break   # bad key / quota -- stop the run
            continue
        n += 1
        outbox[l["id"]] = {"to": l["email"], "at": now.strftime("%Y-%m-%d %H:%M:%S"), "subject": subj, "mid": mid, "market": l["market"], "ai": ai}
        json.dump(outbox, open(OUTBOX, "w"), ensure_ascii=False, indent=0)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        try:
            turso("INSERT INTO leads_status (id, status, note, updated_at, sent_at, contacts) VALUES (?, 'sent', 'email', ?, ?, 1) "
                  "ON CONFLICT(id) DO UPDATE SET status='sent', note='email', updated_at=excluded.updated_at, sent_at=excluded.sent_at, contacts=COALESCE(contacts,0)+1",
                  [l["id"], stamp, stamp])
        except Exception as e:
            print(f"  turso mark failed {l['id']}: {type(e).__name__} (outbox still has it)")
        print(f"  SENT {l['id']} -> {l['email']} [{l['market']}]")
        time.sleep(random.uniform(20, 60))
    print(f"EMAIL done sent_this_run={0 if (DRY or TEST_TO) else n}")


if __name__ == "__main__":
    main()
