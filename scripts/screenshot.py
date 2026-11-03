"""Screenshot built pages at 1280 and 375 px and report console errors and sideways overflow
(playbooks/qa-site.md, step 3).

    make build
    uv run --with playwright==1.55.0 python scripts/screenshot.py /analysis/bop-stress/ /external/

Serves site/dist on a local port, writes PNGs to site/screenshots/ (git-ignored), and prints, per
page and width, console errors and elements wider than the screen (outside scrolling tables).
Needs Playwright's Chromium (`playwright install chromium` once if it is missing).
"""
from __future__ import annotations

import functools
import http.server
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DIST, OUT = ROOT / "site" / "dist", ROOT / "site" / "screenshots"
OVERFLOW = """() => { const W = document.documentElement.clientWidth; const out = [];
  for (const el of document.querySelectorAll('main *')) { const r = el.getBoundingClientRect();
    if (r.right > W + 2 && !el.closest('.scroll')) out.push(`${el.tagName.toLowerCase()}.${el.className}`); }
  return [...new Set(out)].slice(0, 6); }"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:   # no request log
        pass


def main(paths: list[str]) -> int:
    handler = functools.partial(Quiet, directory=str(DIST))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    OUT.mkdir(exist_ok=True)
    problems = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width in (1280, 375):
            page = browser.new_page(viewport={"width": width, "height": 900})
            errors: list[str] = []
            page.on("console", lambda m, errors=errors: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
            for path in paths:
                page.goto(base + path, wait_until="networkidle")
                page.wait_for_timeout(600)
                name = path.strip("/").replace("/", "_") or "home"
                page.screenshot(path=str(OUT / f"{name}_{width}.png"), full_page=True)
                wide = page.evaluate(OVERFLOW)
                print(f"{width:>4} {path}: errors={errors or 'none'} overflow={wide or 'none'}")
                problems += bool(errors)
                errors.clear()
        browser.close()
    server.shutdown()
    print(f"screenshots in {OUT}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["/"]))
