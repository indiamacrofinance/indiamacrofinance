"""The briefing checker (docs/guidebook/07-editorial-policy.md).

A draft (template text with tokens, before rendering) fails if:
  - a digit appears outside a {{token}} (numbers may only come from the ledger),
  - a token is not in the ledger.
Front matter (between the leading '---' lines) is not checked.
"""
from __future__ import annotations

import re

TOKEN = re.compile(r"\{\{\s*([a-z0-9_]+(?::[a-z0-9_]+)?(?:\.[a-z_]+)+)\s*\}\}")


def body_of(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        return text[end + 4:] if end >= 0 else text
    return text


def problems(draft: str, facts: dict[str, str]) -> list[str]:
    body = body_of(draft)
    out = []
    for tok in TOKEN.findall(body):
        if tok not in facts:
            out.append(f"token not in ledger: {{{{{tok}}}}}")
    bare = TOKEN.sub("", body)
    if "{{" in bare or "}}" in bare:
        out.append("malformed token: braces left after reading every token")
    for line_no, line in enumerate(bare.splitlines(), 1):
        if re.search(r"\d", line):
            out.append(f"line {line_no}: number typed outside a token: {line.strip()[:80]!r}")
    return out


def render(draft: str, facts: dict[str, str]) -> str:
    return TOKEN.sub(lambda m: facts[m.group(1)], draft)
