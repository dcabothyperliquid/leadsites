"""Proposal emails. Runs inside email.yml (GitHub Actions) -- nothing runs on Render.

config.email.mode:
  off     nothing is sent.
  manual  ONLY what you approved in the Xbot Leads > Email tab is sent (table email_queue in Turso, subject/body exactly as you saw/edited them).
  auto    the bot sends drafts (data/email_drafts.json) to eligible email leads itself: chosen markets, local business hours Mon-Fri, small batches.
Both modes: daily cap (config.email.daily_cap), one email per address ever, skips Brevo-blocked addresses, every mail has a footer (who we are +
reply STOP) and a List-Unsubscribe header. Follow-ups are never automatic.
EMAIL IS INDEPENDENT of WhatsApp/Messenger: the same customer can get both. This script never reads or writes leads_status (the WhatsApp/FB tracker);
email has its own state in email_queue (approved / sent / failed / skip / replied / interested / sold / unsub) + data/outbox.json.

Env (GitHub secrets): BREVO_API_KEY (or SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS) + MAIL_FROM [MAIL_FROM_NAME, MAIL_REPLY_TO]; TURSO_URL + TURSO_TOKEN; GROQ_API_KEY (drafts only)
Inputs: DRY_RUN=true -> print 3 drafts, send nothing | TEST_TO=addr -> send ONE draft to that address, no records."""
import json, os, ssl, time, random, smtplib, datetime, urllib.request, urllib.error
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from zoneinfo import ZoneInfo
import maildraft as MD

CFG = json.load(open("config.json"))
LEADS, OUTBOX, DRAFTS = "data/leads.json", "data/outbox.json", "data/email_drafts.json"
E = CFG.get("email", {})
TZ = {"AU": "Australia/Melbourne", "AE": "Asia/Dubai", "UK": "Europe/London", "IN": "Asia/Kolkata", "US": "America/New_York"}
PER_RUN_AUTO = 5
DONE = {"sent", "skip", "replied", "interested", "sold", "unsub"}   # email_queue statuses = this lead is finished for email
env = lambda k: (os.environ.get(k) or "").strip()
DRY, TEST_TO = env("DRY_RUN").lower() in ("1", "true", "yes"), env("TEST_TO")
MODE = E.get("mode") or ("auto" if E.get("enabled") else "off")


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
        if MODE not in ("manual", "auto"):
            print("EMAIL OFF (config.email.mode=off) -- nothing sent"); return
        miss = [k for k, ok in (("MAIL_FROM", env("MAIL_FROM")), ("BREVO_API_KEY or SMTP_*", env("BREVO_API_KEY") or (env("SMTP_HOST") and env("SMTP_USER") and env("SMTP_PASS"))),
                                ("TURSO_URL/TURSO_TOKEN", env("TURSO_URL") and env("TURSO_TOKEN"))) if not ok]
        if miss:
            print("EMAIL NOT CONFIGURED, missing secrets:", ", ".join(miss)); return
    leads = json.load(open(LEADS))
    by_id = {l["id"]: l for l in leads}
    outbox = json.load(open(OUTBOX)) if os.path.exists(OUTBOX) else {}
    drafts = json.load(open(DRAFTS)) if os.path.exists(DRAFTS) else {}
    have_turso = bool(env("TURSO_URL") and env("TURSO_TOKEN"))
    qdone = set()   # leads finished for EMAIL (sent / skipped / replied ...) -- WhatsApp status is deliberately ignored
    if have_turso:
        turso("CREATE TABLE IF NOT EXISTS email_queue (id TEXT PRIMARY KEY, subject TEXT, body TEXT, status TEXT, err TEXT, updated_at TEXT)")
        qdone = {r["id"] for r in turso("SELECT id, status FROM email_queue") if (r.get("status") or "") in DONE}
    sent_addr = {(o.get("to") or "").lower() for o in outbox.values()} | brevo_blocked()
    today = now.strftime("%Y-%m-%d")
    room = max(0, int(E.get("daily_cap", 15)) - sum(1 for o in outbox.values() if (o.get("at") or "")[:10] == today))
    mks = set(E.get("markets") or [])
    print(f"EMAIL mode={'TEST' if TEST_TO else 'DRY' if DRY else MODE.upper()} markets={sorted(mks)} cap_left={room} outbox={len(outbox)}")

    def elig(l):
        em = (l.get("email") or "").lower()
        return bool(em and l.get("live") and l.get("url") and not l.get("expired") and l["market"] in mks and l["id"] not in outbox
                    and l["id"] not in qdone and em not in sent_addr)

    def draft_of(l):
        d = drafts.get(l["id"])
        if d and d.get("v") == MD.version(CFG):
            return d["subject"], d["body"], bool(d.get("ai"))
        return MD.build(l, CFG)

    # ── test / dry ──
    if testing:
        pool = [l for l in leads if elig(l)]
        print(f"  eligible leads: {len(pool)}")
        for l in pool[:3 if DRY else 1]:
            subj, body, ai = draft_of(l)
            text, htm = MD.render(l, CFG, body)
            if DRY:
                print(f"\n--- DRAFT to {l['email']} ({l['market']}, {'AI' if ai else 'template'}) ---\nSubject: {subj}\n{text}\n")
            else:
                send(TEST_TO, l["name"], "[TEST] " + subj, text, htm); print(f"TEST mail sent to {TEST_TO}")
        return

    # ── pick what to send ──
    jobs = []   # (lead, subject, body, ai)
    if MODE == "manual":
        rows = turso("SELECT id, subject, body FROM email_queue WHERE status = 'approved' ORDER BY updated_at")
        print(f"  approved in queue: {len(rows)}")
        for r in rows:
            l = by_id.get(r["id"])
            err = None
            if not l: err = "lead nahi mili"
            elif not elig(l): err = "ab eligible nahi (email/market/pehle bheja)"
            elif l["url"] not in (r.get("body") or ""): err = "body me demo link nahi"
            if err:
                turso("UPDATE email_queue SET status='failed', err=?, updated_at=? WHERE id=?", [err, time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), r["id"]])
                print(f"  SKIP {r['id']}: {err}"); continue
            jobs.append((l, r["subject"], r["body"], False))
        jobs = jobs[:room]
        gap = (8, 20)
    else:
        cand = [l for l in leads if elig(l) and in_window(l["market"], now)]
        random.shuffle(cand)
        print(f"  eligible now: {len(cand)}")
        jobs = [(l,) + draft_of(l) for l in cand[:min(PER_RUN_AUTO, room)]]
        gap = (20, 60)

    n = 0
    for l, subj, body, ai in jobs:
        text, htm = MD.render(l, CFG, body)
        try:
            mid = send(l["email"], l["name"], subj, text, htm)
        except Exception as e:
            print(f"  SEND FAILED {l['id']} {type(e).__name__}: {str(e)[:120]}")
            if MODE == "manual":
                turso("UPDATE email_queue SET status='failed', err=?, updated_at=? WHERE id=?",
                      [f"{type(e).__name__}: {str(e)[:150]}", time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), l["id"]])
            if isinstance(e, urllib.error.HTTPError) and e.code in (401, 403, 429):
                break   # bad key / quota -- stop the run
            continue
        n += 1
        sent_addr.add(l["email"].lower())
        outbox[l["id"]] = {"to": l["email"], "at": now.strftime("%Y-%m-%d %H:%M:%S"), "subject": subj, "mid": mid, "market": l["market"], "ai": ai, "mode": MODE}
        json.dump(outbox, open(OUTBOX, "w"), ensure_ascii=False, indent=0)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        try:
            turso("INSERT INTO email_queue (id, subject, body, status, err, updated_at) VALUES (?, ?, ?, 'sent', NULL, ?) "
                  "ON CONFLICT(id) DO UPDATE SET status='sent', err=NULL, updated_at=excluded.updated_at", [l["id"], subj, body, stamp])
        except Exception as e:
            print(f"  turso mark failed {l['id']}: {type(e).__name__} (outbox still has it)")
        print(f"  SENT {l['id']} -> {l['email']} [{l['market']}]")
        time.sleep(random.uniform(*gap))
    print(f"EMAIL done sent_this_run={n}")


if __name__ == "__main__":
    main()
