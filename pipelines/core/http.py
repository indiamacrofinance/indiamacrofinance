"""HTTP helpers shared by every source.

Indian government servers have three recurring quirks handled here:
- they reject non-browser clients, so we always send browser headers;
- some (api.mospi.gov.in) need TLS legacy renegotiation, which OpenSSL 3
  disables by default;
- some (eaindustry.nic.in) send only their own certificate, without the
  intermediate. For those hosts we download the intermediate from the address in
  the certificate's Authority Information Access field and add it to the chain;
  the chain is still verified up to a trusted root. Verification is never turned off.

RBI's servers sit behind a bot shield that, at times, answers every request with a
JavaScript challenge page (HTTP 200, ~7 KB of HTML) instead of the file: every rbidocs
download for ~4 minutes of the 18:30 IST run on 16 Nov 2026, and the first 31 WSS downloads
(~70 seconds) of the 04:16 IST run on 17 Nov (issue #55). The challenge is never solved
here: get() waits (CHALLENGE_WAITS) and asks again, then raises BotChallenge, so the source
fails cleanly and keeps its last good data. Once a host has used up its waits, later
challenges from it in the same run raise at once.
"""
from __future__ import annotations

import hashlib
import ssl
import time
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import AuthorityInformationAccessOID, ExtensionOID

from pipelines.core import Raw

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}
# Hosts that only speak TLS with legacy renegotiation enabled.
LEGACY_TLS_HOSTS = {"api.mospi.gov.in"}
# Hosts that omit the intermediate certificate (see module docstring).
INCOMPLETE_CHAIN_HOSTS = {"eaindustry.nic.in"}
_intermediates: dict[str, str] = {}
# Seconds between requests to the same host; government servers are fragile.
POLITE_DELAY = 1.0
_last_hit: dict[str, float] = {}
# Seconds to wait before asking again when a host answers with its bot-challenge page.
CHALLENGE_WAITS = (60, 120)
_challenged: set[str] = set()   # hosts that challenged us after all waits, this run


class BotChallenge(RuntimeError):
    """The server answered with its bot-challenge page instead of the content."""


def is_challenge(content: bytes) -> bool:
    """True for the bot-challenge page RBI's servers (F5 "TSPD") send instead of a file.
    Both markers were absent from every real RBI page and workbook archived in Nov 2026."""
    head = content[:20000]
    return b'window["bobcmn"]' in head and b"/TSPD/" in head


def _aia_issuer(cert: x509.Certificate) -> x509.Certificate | None:
    """The issuer certificate named in `cert`'s AIA "CA Issuers" URL, if any."""
    try:
        aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS).value
    except x509.ExtensionNotFound:
        return None
    url = next((d.access_location.value for d in aia
                if d.access_method == AuthorityInformationAccessOID.CA_ISSUERS), None)
    if url is None:
        return None
    with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 - CA URL taken from the cert
        der = resp.read()
    return x509.load_der_x509_certificate(der)


def _missing_intermediates(host: str, max_depth: int = 4) -> str:
    """PEM of the certificates between `host`'s leaf and a root, found by walking AIA links.

    Self-signed certificates are never included: the chain must still end at a root
    already in the trust store. AIA downloads are plain HTTP, which is why these
    certificates are only path-building aids (see _ssl_context), never trust anchors.
    """
    if host not in _intermediates:
        cert = x509.load_pem_x509_certificate(ssl.get_server_certificate((host, 443)).encode())
        chain = []
        for _ in range(max_depth):
            cert = _aia_issuer(cert)
            if cert is None or cert.issuer == cert.subject:
                break
            chain.append(cert.public_bytes(Encoding.PEM).decode())
        _intermediates[host] = "".join(chain)
    return _intermediates[host]


def _ssl_context(host: str) -> ssl.SSLContext:
    """Default verifying context, plus the per-host fixes described in the module docstring."""
    ctx = ssl.create_default_context()
    if host in LEGACY_TLS_HOSTS:
        ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
    if host in INCOMPLETE_CHAIN_HOSTS:
        # Without partial-chain mode, the added certificates only help build the path;
        # verification must still reach a self-signed root from the trust store.
        ctx.verify_flags &= ~getattr(ssl, "VERIFY_X509_PARTIAL_CHAIN", 0)
        ctx.load_verify_locations(cadata=_missing_intermediates(host))
    return ctx


def get(url: str, params: dict | None = None, retries: int = 3, timeout: float = 60,
        challenge_waits: tuple[int, ...] = CHALLENGE_WAITS) -> httpx.Response:
    """GET with browser headers, per-host politeness delay and retries on transient errors.
    A bot-challenge page is retried after each of `challenge_waits` seconds, then raises
    BotChallenge (pass () to give up at once)."""
    host = urlparse(url).hostname or ""
    waits = () if host in _challenged else tuple(challenge_waits)
    for wait in (*waits, None):
        r = _get(url, params, retries, timeout, host)
        if not is_challenge(r.content):
            _challenged.discard(host)
            return r
        if wait is not None:
            print(f"  NOTE {host} answered with its bot-challenge page; asking again in {wait}s")
            time.sleep(wait)
    if waits:   # waited it out and still challenged: do not wait again this run
        _challenged.add(host)
    raise BotChallenge(f"{host} answered with its bot-challenge page instead of {url}"
                       + (f" (still after waiting {sum(waits)}s)" if waits else ""))


def _get(url: str, params: dict | None, retries: int, timeout: float, host: str) -> httpx.Response:
    """One GET with the politeness delay and retries on transient errors."""
    wait = POLITE_DELAY - (time.monotonic() - _last_hit.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with httpx.Client(headers=HEADERS, verify=_ssl_context(host), timeout=timeout,
                              follow_redirects=True) as client:
                r = client.get(url, params=params)
            _last_hit[host] = time.monotonic()
            if r.status_code >= 500 or r.status_code == 429:
                raise httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
            r.raise_for_status()
            return r
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            last_err = e
            # 4xx other than 429 will not fix itself; fail fast.
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code < 500 \
                    and e.response.status_code != 429:
                break
            if attempt + 1 < retries:
                time.sleep(2 ** attempt * 2)
    raise RuntimeError(f"GET {url} failed: {last_err}") from last_err


def fetch_raw(url: str, params: dict | None = None, suffix: str = ".json",
              challenge_waits: tuple[int, ...] = CHALLENGE_WAITS) -> Raw:
    """Download a URL and wrap it with its receipt."""
    r = get(url, params=params, challenge_waits=challenge_waits)
    return Raw(content=r.content, url=str(r.url), fetched_at=datetime.now(timezone.utc),
               sha256=hashlib.sha256(r.content).hexdigest(), suffix=suffix)
