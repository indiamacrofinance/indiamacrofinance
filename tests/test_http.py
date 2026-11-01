"""Retry policy without network requests or real sleeps."""
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
