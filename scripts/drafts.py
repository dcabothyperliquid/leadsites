"""Draft step (email.yml): builds subject + body for every email lead that has none (or an outdated one) -> data/email_drafts.json.
The Xbot UI shows these as full previews (editable); in MANUAL mode only what you approve is sent, in AUTO mode the bot sends them.
Env: REGEN_DRAFTS=true rebuilds all | GROQ_API_KEY optional (AI-written; template otherwise) | MAX_DRAFTS (default 60)."""
import json, os, time
import maildraft as MD

CFG = json.load(open("config.json"))
E = CFG.get("email", {})
DRAFTS, OUTBOX = "data/email_drafts.json", "data/outbox.json"


def main():
    leads = json.load(open("data/leads.json"))
    old = json.load(open(DRAFTS)) if os.path.exists(DRAFTS) else {}
    outbox = json.load(open(OUTBOX)) if os.path.exists(OUTBOX) else {}
    ver = MD.version(CFG)
    regen = (os.environ.get("REGEN_DRAFTS") or "").lower() in ("1", "true", "yes")
    mks = set(E.get("markets") or [])
    pool = [l for l in leads if l.get("email") and l.get("live") and l.get("url") and not l.get("expired") and l["market"] in mks and l["id"] not in outbox]
    keep = {l["id"] for l in pool}
    drafts = {k: v for k, v in old.items() if k in keep}
    todo = [l for l in pool if regen or drafts.get(l["id"], {}).get("v") != ver][:int(os.environ.get("MAX_DRAFTS") or 60)]
    ai_on = bool((os.environ.get("GROQ_API_KEY") or "").strip())
    print(f"DRAFTS pool={len(pool)} have={len(drafts)} to_build={len(todo)} ai={'on' if ai_on else 'off (template)'} ver={ver}")
    for l in todo:
        subj, body, ai = MD.build(l, CFG)
        drafts[l["id"]] = {"subject": subj, "body": body, "footer": "\n".join(MD.footer(l, CFG)), "ai": ai, "v": ver,
                           "at": time.strftime("%Y-%m-%d %H:%M", time.gmtime())}
        if ai_on:
            time.sleep(2.2)   # stay under Groq's per-minute limit
    json.dump(drafts, open(DRAFTS, "w"), ensure_ascii=False, indent=0)
    print(f"DRAFTS saved={len(drafts)}")


if __name__ == "__main__":
    main()
