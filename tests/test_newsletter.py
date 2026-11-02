"""Newsletter digest: composed only from published briefings; never sends."""
from datetime import date

from pipelines.newsletter import digest


def test_compose_lists_week_and_footer(tmp_path, monkeypatch):
    for name, product, d in [("2026-10-26-cpi", "release-note", "2026-10-26"),
                             ("2026-10-31-weekly", "weekly-briefing", "2026-10-31"),
                             ("2026-10-30-daily", "daily-note", "2026-10-30"),
                             ("2026-10-20-iip", "release-note", "2026-10-20")]:
        (tmp_path / f"{name}.md").write_text(f"---\ntitle: T {name}\ndate: {d}\nproduct: {product}\n---\nBody of {name}.\n")
    monkeypatch.setattr(digest, "BRIEFINGS", tmp_path)
    cfg = digest.config()
    cfg["newsletter"]["products"] = ["weekly-briefing", "release-note"]
    subject, body = digest.compose(date(2026, 11, 1), cfg)
    assert subject == "T 2026-10-31-weekly"
    assert body.startswith("Body of 2026-10-31-weekly.")
    assert "2026-10-26-cpi" in body and "daily" not in body and "2026-10-20" not in body   # outside the week
    assert cfg["credit"]["inspired_by_url"] in body
    assert digest.compose(date(2026, 12, 1), cfg) is None


def test_no_key_means_no_request(monkeypatch, capsys):
    monkeypatch.delenv("BUTTONDOWN_API_KEY", raising=False)
    monkeypatch.setattr(digest, "create_draft", lambda *a: (_ for _ in ()).throw(AssertionError("called")))
    monkeypatch.setattr(digest, "compose", lambda on, cfg: ("s", "b"))
    monkeypatch.setattr("sys.argv", ["digest", "--date", "2026-11-01"])
    assert digest.main() == 0
    assert "nothing created" in capsys.readouterr().out


# --- Morning email (pipelines/newsletter/morning.py). The AI is faked: no API calls. ---
from pipelines.newsletter import morning


def fake_ai(drafts):
    """Return the given drafts in turn, as ai_draft would."""
    it = iter(drafts)
    return lambda ledger, new, model, feedback=None: (next(it), {"model": "fake", "input_tokens": 0,
                                                                  "output_tokens": 0, "stop_reason": "end_turn"})


def test_ai_draft_with_tokens_is_rendered(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(morning, "ai_draft", fake_ai(["**Prices.** CPI inflation was {{cpi_headline_inflation.latest}}."]))
    email = morning.compose(date(2026, 10, 29), morning.config())
    assert email["drafted_by"].startswith("AI")
    assert "{{" not in email["body"] and "%" in email["body"].split("\n")[0]      # the value, filled in
    assert "not typed by the writer" in email["body"]


def test_typed_number_is_rejected_then_retry_then_template(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    # All three drafts type a number: the checker rejects them and the template is used.
    monkeypatch.setattr(morning, "ai_draft", fake_ai(["Inflation was 5.5%.", "Still 5.5%.", "Again 5.5%."]))
    email = morning.compose(date(2026, 10, 29), morning.config())
    assert email["drafted_by"] == "template (no AI)"
    assert email["body"].startswith("**In one line.**") and "{{" not in email["body"]


def test_retry_can_fix_the_draft(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(morning, "ai_draft", fake_ai(["Repo at 5.50%.", "The repo rate is {{repo_rate.latest}}."]))
    assert morning.compose(date(2026, 10, 29), morning.config())["drafted_by"].startswith("AI")


def test_no_keys_means_nothing_sent(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("BUTTONDOWN_API_KEY", raising=False)
    monkeypatch.setattr(morning, "SENT", tmp_path / "sent.json")
    monkeypatch.setattr(morning, "send", lambda *a: (_ for _ in ()).throw(AssertionError("sent")))
    cfg = morning.config()
    cfg["newsletter"].update(writer="api", enabled=True)
    monkeypatch.setattr(morning, "config", lambda: cfg)
    monkeypatch.setattr("sys.argv", ["morning", "auto", "--date", "2026-10-29"])
    assert morning.main() == 0
    assert "nothing sent" in capsys.readouterr().out


def test_auto_does_nothing_in_manual_mode(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(morning, "SENT", tmp_path / "sent.json")      # not the real record
    monkeypatch.setattr(morning, "compose", lambda *a, **k: (_ for _ in ()).throw(AssertionError("composed")))
    cfg = morning.config()
    cfg["newsletter"].update(writer="manual", enabled=True)
    monkeypatch.setattr(morning, "config", lambda: cfg)
    monkeypatch.setattr("sys.argv", ["morning", "auto", "--date", "2026-10-29"])
    assert morning.main() == 0 and "written by hand" in capsys.readouterr().out


def test_on_hold_drafts_and_sends_nothing(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(morning, "SENT", tmp_path / "sent.json")
    monkeypatch.setattr(morning, "compose", lambda *a, **k: (_ for _ in ()).throw(AssertionError("composed")))
    cfg = morning.config()
    cfg["newsletter"].update(writer="api", enabled=False)
    monkeypatch.setattr(morning, "config", lambda: cfg)
    monkeypatch.setattr("sys.argv", ["morning", "auto", "--date", "2026-10-29"])
    assert morning.main() == 0 and "on hold" in capsys.readouterr().out


def manual_dirs(monkeypatch, tmp_path):
    cfg = morning.config()
    cfg["newsletter"]["enabled"] = True            # these tests exercise sending, on hold or not
    monkeypatch.setattr(morning, "config", lambda: cfg)
    monkeypatch.setattr(morning, "PACKS", tmp_path / "packs")
    monkeypatch.setattr(morning, "DRAFTS", tmp_path / "drafts")
    monkeypatch.setattr(morning, "SENT", tmp_path / "sent.json")
    monkeypatch.setattr(morning, "ARCHIVE", tmp_path / "archive")


def test_pack_check_send(monkeypatch, tmp_path, capsys):
    """Manual mode end to end: pack -> draft with tokens -> check -> send (faked)."""
    manual_dirs(monkeypatch, tmp_path)
    on = date(2026, 10, 29)
    pack_path, draft_path = morning.pack(on)
    text = open(pack_path).read()
    assert "{{cpi_headline_inflation.latest}} = " in text and "Never type a digit" in text
    open(draft_path, "w").write("**Prices.** CPI inflation was {{cpi_headline_inflation.latest}}.")
    assert morning.check_draft(on) == []
    cfg = morning.config()
    cfg["newsletter"]["enabled"] = True
    monkeypatch.setattr(morning, "config", lambda: cfg)
    monkeypatch.setenv("BUTTONDOWN_API_KEY", "test")
    sent = []
    monkeypatch.setattr(morning, "send", lambda subject, body, key: sent.append((subject, body)) or "email-1")
    monkeypatch.setattr("sys.argv", ["morning", "send", "--date", on.isoformat()])
    assert morning.main() == 0
    subject, body = sent[0]
    assert "{{" not in subject + body and "%" in body and "Written each morning with AI" in body
    assert (tmp_path / "archive" / f"{on}.md").exists()
    assert morning.main() == 0 and len(sent) == 1                    # second run: already sent


def test_send_refuses_typed_number(monkeypatch, tmp_path):
    manual_dirs(monkeypatch, tmp_path)
    on = date(2026, 10, 29)
    _, draft_path = morning.pack(on)
    open(draft_path, "w").write("Inflation was 5.5%.")
    monkeypatch.setattr(morning, "send", lambda *a: (_ for _ in ()).throw(AssertionError("sent")))
    monkeypatch.setattr("sys.argv", ["morning", "send", "--date", on.isoformat()])
    assert morning.main() == 1


def test_send_without_draft_sends_nothing(monkeypatch, tmp_path, capsys):
    manual_dirs(monkeypatch, tmp_path)
    monkeypatch.setattr("sys.argv", ["morning", "send", "--date", "2026-10-29"])
    assert morning.main() == 0 and "nothing to send" in capsys.readouterr().out


def test_fallback_template_passes_checker():
    from pipelines.briefings.check import body_of, problems
    front, text = morning.template()
    ledger, _ = morning.build_ledger(front, date(2026, 10, 29))
    assert problems(body_of(text), ledger.facts) == []
    assert problems("---\n---\n" + front["subject"], ledger.facts) == []


def test_rupee_tokens_render_and_malformed_braces_are_rejected():
    from pipelines.briefings.check import TOKEN, problems, render
    front, _ = morning.template()
    ledger, _ = morning.build_ledger(front, date(2026, 10, 29))
    assert ledger.facts["rupee.fresh"] in ("yes", "no")
    assert all(TOKEN.fullmatch("{{" + k + "}}") for k in ledger.facts)      # every fact is writable
    text = "The rupee {{rupee.day.direction}} {{rupee.day.change}}."
    assert problems(text, ledger.facts) == [] and "{{" not in render(text, ledger.facts)
    assert problems("The gap is {{rupee.spread.bad name}}.", ledger.facts)       # braces left over


def test_fresh_is_no_when_the_last_email_covered_the_same_day(monkeypatch, tmp_path):
    import json
    front, _ = morning.template()
    monkeypatch.setattr(morning, "SENT", tmp_path / "sent.json")
    ledger, _ = morning.build_ledger(front, date(2026, 10, 29))
    (tmp_path / "sent.json").write_text(json.dumps({"2026-10-28": {"id": "x", "rupee_as_of": ledger.facts["rupee.as_of"]}}))
    assert morning.build_ledger(front, date(2026, 10, 29))[0].facts["rupee.fresh"] == "no"
