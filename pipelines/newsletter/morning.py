"""The morning newsletter: the rupee, and why it moved, written with AI from our data.

Each morning: how the rupee moved on the last completed trading day (and over the week, month
and quarter), how much of that each driver accounts for (pipelines/build/rupee.py: other Asian
currencies, oil, Indian shares, the dollar, US yields, global risk), what is left unexplained,
and the background (foreign portfolio flows, RBI's reserves, carry, valuation, trade).

Default workflow (newsletter.writer: "manual", no API costs; runbook "Newsletter"):

    python -m pipelines.newsletter.morning pack            # 1. today's fact pack (local)
        -> newsletter/packs/<date>.md     instructions + facts, to give to any AI chat
        -> newsletter/drafts/<date>.facts.json   the exact facts, saved for sending
    #  2. an AI (Claude Code /morning, claude.ai, ...) writes the email from the pack, using
    #     tokens only, into newsletter/drafts/<date>.md
    python -m pipelines.newsletter.morning check           # 3. checker + preview (local)
    #  4. commit and push the draft; newsletter-send.yml runs:
    python -m pipelines.newsletter.morning send            #    check, fill in, send, archive

Optional API mode (newsletter.writer: "api"): `auto` asks Claude directly through the
Anthropic API (paid; model newsletter.llm_model), two retries, then the fixed template.

How it stays honest (07-editorial-policy.md, "Morning newsletter"):
  - The facts are tokens such as {{cpi_headline_inflation.latest}} -> "5.54%", built from the
    stored series (registry/newsletter/morning.md `views`), the release calendar and what is
    new since yesterday.
  - The writer may use only those facts and must type no digits. The briefing checker
    rejects any digit outside a token and any unknown token, so every number in the email is
    a stored value filled in afterwards, never one the writer typed.
  - `send` uses the facts saved with the pack, so the email matches what was checked.
Sending: Buttondown (POST /v1/emails, status "about_to_send") when newsletter.enabled is true
and BUTTONDOWN_API_KEY is set (a GitHub secret). data/newsletter/sent.json stops a second send
on the same date; every email is archived in data/newsletter/morning/<date>.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

import httpx
import yaml

from pipelines.briefings.check import body_of, problems, render
from pipelines.briefings.draft import TEMPLATES as BRIEFING_TEMPLATES
from pipelines.briefings.ledger import Ledger, fmt_period
from pipelines.build import rupee
from pipelines.core import registry, store

TEMPLATE = store.ROOT / "registry" / "newsletter" / "morning.md"
PACKS = store.ROOT / "newsletter" / "packs"          # git-ignored: regenerated each morning
DRAFTS = store.ROOT / "newsletter" / "drafts"        # committed: the draft and its facts
SENT = store.ROOT / "data" / "newsletter" / "sent.json"
ARCHIVE = store.ROOT / "data" / "newsletter" / "morning"
API = "https://api.buttondown.com/v1/emails"
# Models that accept the server-side refusal fallback ("default" form).
FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}

RULES = """You write a short morning email about the Indian rupee for an economist who wants to
understand, every day, why the rupee moved and be able to explain it to anyone who asks.

You are given a list of facts. Each fact is a token in double braces followed by its value,
e.g. {{rupee.day.change}} = 0.32%. The rupee's moves are measured as the rupee's own value
against the US dollar: "strengthened" means fewer rupees per dollar.

How the explanation works (say so briefly when it helps): a regression over the window in
{{rupee.model.window}} links the rupee's daily moves to its usual drivers. For each period
(day, week, month, quarter) the facts give each driver's own move (`.move`), the part of the
rupee's move the model attributes to it (`.effect`, with `.effect_word`), the rupee's usual
drift, and the part the drivers do not explain (`other`). The model explains about
{{rupee.model.share_daily}} of daily moves and {{rupee.model.share_weekly}} of weekly moves, so
the unexplained part is often large: that is normal for a currency RBI manages.

Rules, all strict:
- Use only these facts. Do not add news, events, quotes, forecasts or anything you know from
  elsewhere. Causes may be stated only as the model's attribution (for example: oil's rise
  accounted for about the oil effect token's amount of the fall) or as the facts' own
  readings (e.g. the reserves reading).
  For the unexplained part, you may name candidates only from the facts: RBI's dealing (the
  reserves facts, with the caveat that reserves also move with valuation), foreign portfolio
  flows (the fpi facts), and otherwise importers' and exporters' dollar demand, in general
  terms. Never present a candidate as certain.
- Drivers listed in {{rupee.model.drivers_dropped}} had no reliable link with the rupee over
  the window: you may report their moves but must not attribute any of the rupee's move to them.
- Write every number, date, percentage or period by copying its token exactly, braces
  included. Never type a digit (0-9) anywhere in your text, not even in a year or a heading.
  Words such as "ten-year", "one" or "four weeks" are fine.
- Mind which tokens carry their own direction. `.move` already reads "up 0.45%" or "down 5
  basis points": never put rose, fell, up or down next to it. To write your own verb, use
  `.move_direction` ("rose"/"fell") with `.move_abs` ("0.45%"). `.effect` and `.change` are
  sizes without direction: pair them with `.effect_word` or `.direction`. Read each sentence
  with the values filled in and make sure it is grammatical and not repetitive.
- If {{rupee.fresh}} is "no", there has been no new trading day since the last email: do not
  repeat the daily story; lead with the week and month instead, and say so in one clause.
- Structure, in Markdown, about four hundred to five hundred and fifty words of prose (bullets
  only where a list is clearer, never more than one list), each section starting with a bold
  lead-in:
  **In one line.** One or two sentences the reader could say if asked why the rupee moved.
  **What happened.** The move, the level, today's live quote if any, FBIL's reference rate,
  and where it stands against its weakest close and the past year's range.
  **Why.** The day's decomposition, largest effects first, with each driver's own move; then
  the unexplained part and its candidates.
  **The bigger picture.** Week, month and quarter: direction and the main drivers, and the drift.
  **Background.** Flows, reserves, the India-US bond yield gap, valuation (REER) and trade,
  only where they help explain the trend.
  **What to watch.** The calendar tokens and the drivers that have mattered most lately.
- No title, greeting or sign-off. You may start with front matter holding a subject line
  (`---` / `subject: ...` / `---`), using tokens only for numbers; otherwise output only the
  email body."""
SYSTEM = RULES                      # the API mode's system prompt


def rel(path) -> str:
    """Path relative to the repo for messages (absolute if it lies elsewhere)."""
    try:
        return str(path.relative_to(store.ROOT))
    except ValueError:
        return str(path)


def config() -> dict:
    return yaml.safe_load((store.ROOT / "site.config.yaml").read_text())


def today_ist() -> date:
    return (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).date()


def template() -> tuple[dict, str]:
    text = TEMPLATE.read_text()
    return yaml.safe_load(text.split("---")[1]), text


def recent_releases(on: date, series_ids: list[str], days: int = 1, cap: int = 10) -> list[str]:
    """Headline series (the template's views) whose newest observation first appeared in the
    `days` days to `on`; daily and weekly series are left out (they update every day)."""
    since = (on - timedelta(days=days)).isoformat()
    out = []
    for sid in dict.fromkeys(series_ids):
        spec = registry.series(sid)
        df = store.load_series(sid)
        if df.empty or spec["frequency"] in ("D", "W"):
            continue
        last = df.sort_values("period").iloc[-1]
        if since <= str(last["vintage"]) <= on.isoformat():
            out.append(f"{spec['short_title']} ({fmt_period(str(last['period']), spec['frequency'])})")
    return out[:cap] + ([f"and {len(out) - cap} more"] if len(out) > cap else [])


def build_ledger(front: dict, on: date) -> tuple[Ledger, list[str]]:
    ledger = Ledger()
    ledger.add_calendar(on.isoformat())
    for view in front["views"]:
        sid, _, how = view.partition(":")
        ledger.add_view(sid, how or "level")
    ledger.add_constants(BRIEFING_TEMPLATES / "constants.yaml")
    new = recent_releases(on, [v.partition(":")[0] for v in front["views"]])
    ledger.facts["new.recent"] = "; ".join(new) if new else "no new monthly or quarterly data"
    ledger.facts["today.date"] = fmt_period(on.isoformat(), "D")
    analysis = rupee.analyse()
    facts, receipts = rupee.rupee_facts(analysis)
    ledger.facts.update(facts)
    ledger.receipts.update(receipts)
    sent = json.loads(SENT.read_text()) if SENT.exists() else {}
    covered = [v.get("rupee_as_of", "") for d, v in sent.items() if d < on.isoformat()]
    ledger.facts["rupee.fresh"] = "no" if covered and max(covered) >= analysis["as_of"] else "yes"
    ledger.facts["rupee.as_of"] = analysis["as_of"]          # not for the text: recorded when sent
    return ledger, new


def facts_text(facts: dict[str, str]) -> str:
    return "\n".join(f"{{{{{tok}}}}} = {val}" for tok, val in sorted(facts.items()))


# --- Manual mode: pack -> (AI writes) -> check -> send ----------------------------------------

def pack(on: date) -> tuple[str, str]:
    """Write today's fact pack and the facts file. Returns (pack path, draft path)."""
    front, _ = template()
    ledger, new = build_ledger(front, on)
    PACKS.mkdir(parents=True, exist_ok=True)
    DRAFTS.mkdir(parents=True, exist_ok=True)
    draft_path = DRAFTS / f"{on}.md"
    (DRAFTS / f"{on}.facts.json").write_text(json.dumps(
        {"date": on.isoformat(), "facts": ledger.facts, "receipts": ledger.receipts}, indent=1, ensure_ascii=False))
    body = (f"# Morning newsletter fact pack, {on}\n\n"
            f"Give everything below the line to an AI (Claude Code: `/morning`; or paste it into\n"
            f"claude.ai or any chat). Save its reply as `{rel(draft_path)}`, run\n"
            f"`make morning-check`, then commit and push the draft: it is sent automatically.\n\n"
            f"---\n\n{RULES}\n\nNew since yesterday: {'; '.join(new) if new else 'nothing new'}.\n\n"
            f"Facts:\n{facts_text(ledger.facts)}\n\nWrite today's email.\n")
    path = PACKS / f"{on}.md"
    path.write_text(body)
    return str(path), str(draft_path)


def load_draft(on: date) -> tuple[str, dict[str, str]]:
    """(draft text, the facts saved by `pack`) for date `on`."""
    draft_path, facts_path = DRAFTS / f"{on}.md", DRAFTS / f"{on}.facts.json"
    if not draft_path.exists():
        raise FileNotFoundError(f"no draft at {rel(draft_path)}")
    if not facts_path.exists():
        raise FileNotFoundError(f"no facts at {rel(facts_path)}: run `pack` first")
    return draft_path.read_text().strip(), json.loads(facts_path.read_text())["facts"]


def finish(draft: str, facts: dict[str, str], drafted_by: str, cfg: dict) -> dict:
    """Render subject and body with the footer. `draft` may start with front matter
    holding `subject:` (tokens allowed); otherwise the template's subject is used."""
    front, _ = template()
    subject = front["subject"]
    if draft.startswith("---"):
        meta = yaml.safe_load(draft.split("---")[1]) or {}
        subject = meta.get("subject", subject)
        draft = body_of(draft).strip()
    site = cfg["site"]
    how = ("Generated each morning" if drafted_by.startswith("template")
           else "Written each morning with AI")
    typed = "" if drafted_by.startswith("template") else ", not typed by the writer"
    footer = (f"\n\n---\n\n*{site['name']}: {site['tagline']}.* {how} from the data on "
              f"[{site['url'].split('//')[-1]}]({site['url']}) and checked automatically: every number above is "
              f"filled in from the stored series{typed}. Sources: [{site['url']}/data/]({site['url']}/data/). "
              f"Feedback: {cfg['contact'].get('feedback_email', '')}. "
              f"{' '.join(cfg['credit']['inspired_by_text'].split())}")
    return {"subject": render(subject, facts), "body": render(draft, facts) + footer, "drafted_by": drafted_by}


def check_draft(on: date) -> list[str]:
    draft, facts = load_draft(on)
    issues = problems(draft, facts)
    if draft.startswith("---"):
        meta = yaml.safe_load(draft.split("---")[1]) or {}
        if "subject" in meta:
            issues += [f"subject: {p}" for p in problems("---\n---\n" + str(meta["subject"]), facts)]
    return issues


# --- API mode (optional, paid) -------------------------------------------------------------------

def ai_draft(ledger: Ledger, new: list[str], model: str, feedback: list[str] | None = None) -> tuple[str | None, dict]:
    """Ask Claude for a token-only draft through the API. Returns (draft or None, usage)."""
    import anthropic

    prompt = (f"New since yesterday: {'; '.join(new) if new else 'nothing new'}.\n\n"
              f"Facts:\n{facts_text(ledger.facts)}\n\nWrite today's email.")
    if feedback:
        prompt += ("\n\nYour previous draft was rejected by the checker for these reasons; fix "
                   "every one (copy tokens exactly, no digits outside tokens):\n- " + "\n- ".join(feedback))
    kwargs = dict(model=model, max_tokens=16000, system=SYSTEM,
                  messages=[{"role": "user", "content": prompt}])
    client = anthropic.Anthropic()
    if model in FALLBACK_MODELS:
        resp = client.beta.messages.create(**kwargs, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    else:
        resp = client.messages.create(**kwargs)
    usage = {"model": resp.model, "input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens,
             "stop_reason": resp.stop_reason}
    if resp.stop_reason in ("refusal", "max_tokens"):
        return None, usage
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return (text or None), usage


def compose(on: date, cfg: dict, use_ai: bool = True) -> dict:
    """API mode: {subject, body, drafted_by, usage, ledger}; template when the AI fails."""
    front, text = template()
    ledger, new = build_ledger(front, on)
    model = cfg["newsletter"].get("llm_model") or "claude-opus-5-5"
    draft, drafted_by, usage, issues = None, "template (no AI)", [], []
    if use_ai and os.environ.get("ANTHROPIC_API_KEY"):
        for attempt in range(3):
            try:
                candidate, info = ai_draft(ledger, new, model, issues or None)
            except Exception as e:                       # API trouble: fall back, never skip the email
                print(f"  AI draft failed: {type(e).__name__}: {e}")
                break
            usage.append(info)
            issues = problems(candidate, ledger.facts) if candidate else [f"no usable text ({info['stop_reason']})"]
            if not issues:
                draft, drafted_by = candidate, f"AI ({info['model']}), checked"
                break
            print(f"  attempt {attempt + 1} rejected: {issues[:3]}")
    if draft is None:
        draft = body_of(text).strip()
        tpl_issues = problems(draft, ledger.facts)
        if tpl_issues:
            raise ValueError(f"fallback template fails the checker: {tpl_issues}")
    return {**finish(draft, ledger.facts, drafted_by, cfg), "usage": usage, "ledger": ledger}


# --- Sending ------------------------------------------------------------------------------------

def send(subject: str, body: str, key: str) -> str:
    # Buttondown asks for explicit confirmation the first time a key sends immediately.
    r = httpx.post(API, timeout=60, json={"subject": subject, "body": body, "status": "about_to_send"},
                   headers={"Authorization": f"Token {key}", "X-Buttondown-Live-Dangerously": "true"})
    r.raise_for_status()
    return r.json().get("id", "")


def deliver(on: date, email: dict, facts: dict, cfg: dict, sent: dict) -> int:
    key = os.environ.get("BUTTONDOWN_API_KEY")
    if not (cfg["newsletter"].get("enabled") and key):
        print("newsletter disabled or BUTTONDOWN_API_KEY not set; nothing sent")
        return 0
    email_id = send(email["subject"], email["body"], key)
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    meta = {"subject": email["subject"], "date": on.isoformat(), "drafted_by": email["drafted_by"],
            "buttondown_id": email_id, "usage": email.get("usage", [])}
    (ARCHIVE / f"{on}.md").write_text("---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True)
                                      + "---\n" + email["body"] + "\n")
    (ARCHIVE / f"{on}.facts.json").write_text(json.dumps(facts, indent=1, ensure_ascii=False))
    sent[on.isoformat()] = {"id": email_id, "subject": email["subject"], "drafted_by": email["drafted_by"],
                            "rupee_as_of": facts.get("facts", facts).get("rupee.as_of", "")}
    SENT.parent.mkdir(parents=True, exist_ok=True)
    SENT.write_text(json.dumps(sent, indent=2))
    print(f"sent: {email['subject']} ({email_id})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("command", nargs="?", default="send", choices=["pack", "check", "send", "auto"])
    ap.add_argument("--date", default=today_ist().isoformat())
    ap.add_argument("--preview", help="write the email to this file; send nothing")
    ap.add_argument("--no-ai", action="store_true", help="auto: use the fallback template only")
    args = ap.parse_args()
    on, cfg = date.fromisoformat(args.date), config()

    if args.command == "pack":
        pack_path, draft_path = pack(on)
        print(f"fact pack: {pack_path}\nsave the AI's email as: {draft_path}")
        return 0

    if args.command == "check":
        issues = check_draft(on)
        if issues:
            print("the draft fails the checker:\n- " + "\n- ".join(issues))
            return 1
        draft, facts = load_draft(on)
        email = finish(draft, facts, "AI-assisted (maintainer)", cfg)
        out = args.preview or str(PACKS / f"{on}.preview.md")
        open(out, "w").write(f"Subject: {email['subject']}\n\n{email['body']}\n")
        print(f"draft passes the checker. Preview: {out}")
        return 0

    if not cfg["newsletter"].get("enabled") and not args.preview:
        print("newsletter.enabled is false (on hold): nothing drafted or sent")
        return 0
    sent = json.loads(SENT.read_text()) if SENT.exists() else {}
    if not args.preview and on.isoformat() in sent:
        print(f"morning email for {on} already sent ({sent[on.isoformat()]['id']}); skipping")
        return 0

    if args.command == "auto":
        if cfg["newsletter"].get("writer", "manual") != "api" and not args.preview:
            print("newsletter.writer is not 'api': the morning email is written by hand from the fact pack; nothing to do")
            return 0
        email = compose(on, cfg, use_ai=not args.no_ai)
        for u in email["usage"]:
            print(f"  {u['model']}: {u['input_tokens']} input + {u['output_tokens']} output tokens ({u['stop_reason']})")
        facts = {"facts": email["ledger"].facts, "receipts": email["ledger"].receipts}
    else:                                                    # send: a maintainer's checked draft
        try:
            draft, saved = load_draft(on)
        except FileNotFoundError as e:
            print(f"{e}; nothing to send for {on}")
            return 0
        issues = check_draft(on)
        if issues:
            print("the draft fails the checker; not sent:\n- " + "\n- ".join(issues))
            return 1
        email = finish(draft, saved, "AI-assisted (maintainer)", cfg)
        facts = {"facts": saved}
    print(f"  drafted by: {email['drafted_by']}")
    if args.preview:
        open(args.preview, "w").write(f"Subject: {email['subject']}\n\n{email['body']}\n")
        print(f"preview written to {args.preview}")
        return 0
    return deliver(on, email, facts, cfg, sent)


if __name__ == "__main__":
    sys.exit(main())
