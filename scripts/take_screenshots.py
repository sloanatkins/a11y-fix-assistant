"""
Take Screenshots
================
Opens the built demo and saves the screenshots the README uses.

Usage:
    python scripts/take_screenshots.py frontend/dist

Dependencies:
    - playwright
"""

import functools
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

from check_app_accessibility import AppHandler


# ── Main ──

def main() -> None:
    if len(sys.argv) != 2 or not Path(sys.argv[1], "index.html").exists():
        sys.exit("Usage: python scripts/take_screenshots.py <built site folder>")

    output = Path("docs")
    output.mkdir(exist_ok=True)

    handler = functools.partial(AppHandler, directory=sys.argv[1])
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800}, device_scale_factor=2)
        page.goto(f"{base}/scans/library")
        page.wait_for_selector(".rules")
        page.wait_for_timeout(300)
        page.screenshot(path=output / "results.png")

        page.locator('a[aria-label^="Review listitem"]').first.click()
        page.wait_for_selector(".verdict")
        page.wait_for_timeout(300)
        page.screenshot(path=output / "review.png", full_page=True)
        browser.close()
    server.shutdown()
    print(f"Saved screenshots to {output}/")


if __name__ == "__main__":
    main()
