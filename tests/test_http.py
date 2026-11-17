"""Retry policy without network requests or real sleeps."""
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from pipelines.core import http


@pytest.mark.parametrize("status,attempts,delays", [
    (503, 3, [2, 4]), (429, 3, [2, 4]), (404, 1, []), (200, 1, []),
])
def test_retry_policy(monkeypatch, status, attempts, delays):
    response = httpx.Response(status, request=httpx.Request("GET", "https://example.test"))
    client = MagicMock()
    client.__enter__.return_value.get.return_value = response
    monkeypatch.setattr(http.httpx, "Client", lambda **kwargs: client)
    monkeypatch.setattr(http, "_ssl_context", lambda host: True)
    monkeypatch.setattr(http, "_last_hit", {})
    monkeypatch.setattr(http, "POLITE_DELAY", 0)
    sleeps = []
    monkeypatch.setattr(http.time, "sleep", sleeps.append)

    if status == 200:
        assert http.get("https://example.test") is response
    else:
        with pytest.raises(RuntimeError, match=str(status)):
            http.get("https://example.test")

    assert client.__enter__.return_value.get.call_count == attempts
    assert sleeps == delays


CHALLENGE = (Path(__file__).parent / "fixtures" / "rbi" / "bot_challenge.html").read_bytes()


def fake_server(monkeypatch, bodies):
    """http.get against responses with these bodies, in order; returns the recorded sleeps."""
    req = httpx.Request("GET", "https://rbidocs.example.test/x.xlsx")
    client = MagicMock()
    client.__enter__.return_value.get.side_effect = [httpx.Response(200, content=b, request=req) for b in bodies]
    monkeypatch.setattr(http.httpx, "Client", lambda **kwargs: client)
    monkeypatch.setattr(http, "_ssl_context", lambda host: True)
    monkeypatch.setattr(http, "_last_hit", {})
    monkeypatch.setattr(http, "_challenged", set())
    monkeypatch.setattr(http, "POLITE_DELAY", 0)
    sleeps = []
    monkeypatch.setattr(http.time, "sleep", sleeps.append)
    return sleeps


def test_bot_challenge_page_is_recognised():
    # The page RBI's file server sent instead of a WSS workbook on 17 Nov 2026 (issue #55).
    assert http.is_challenge(CHALLENGE)
    assert not http.is_challenge(b"PK\x03\x04 a workbook")
    assert not http.is_challenge(b"<html><body>Weekly Statistical Supplement</body></html>")


def test_bot_challenge_waited_out(monkeypatch):
    sleeps = fake_server(monkeypatch, [CHALLENGE, CHALLENGE, b"PK\x03\x04"])
    assert http.get("https://rbidocs.example.test/x.xlsx").content == b"PK\x03\x04"
    assert sleeps == list(http.CHALLENGE_WAITS)
    assert http._challenged == set()


def test_bot_challenge_that_persists_raises_and_stops_waiting(monkeypatch):
    sleeps = fake_server(monkeypatch, [CHALLENGE] * 4 + [b"PK\x03\x04"])
    with pytest.raises(http.BotChallenge, match="still after waiting 180s"):
        http.get("https://rbidocs.example.test/x.xlsx")
    assert sleeps == [60, 120]
    # The host used up its waits: the next challenge raises at once, without waiting again.
    with pytest.raises(http.BotChallenge):
        http.get("https://rbidocs.example.test/y.xlsx")
    assert sleeps == [60, 120]
    # Once the host answers properly again, it is trusted again.
    assert http.get("https://rbidocs.example.test/z.xlsx").content == b"PK\x03\x04"
    assert http._challenged == set()


def test_bot_challenge_no_waits(monkeypatch):
    sleeps = fake_server(monkeypatch, [CHALLENGE])
    with pytest.raises(http.BotChallenge):
        http.get("https://rbidocs.example.test/x.xlsx", challenge_waits=())
    assert sleeps == []
    assert http._challenged == set()    # giving up at once leaves other sources their waits
