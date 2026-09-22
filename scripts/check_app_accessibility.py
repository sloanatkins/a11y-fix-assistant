"""
Check App Accessibility
=======================
Opens the built demo in a real browser and runs axe on every screen. jsdom
can't measure color contrast, so this catches what the frontend tests can't.
It exits with an error if axe finds anything, which fails CI.

Usage:
    python scripts/check_app_accessibility.py frontend/dist

Dependencies:
    - playwright
    - axe-playwright-python
"""

import functools
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import Page, sync_playwright


# ── Local Server ──

class AppHandler(SimpleHTTPRequestHandler):
    """Sends unknown paths to index.html, the way the hosted site will."""

    def do_GET(self):
        path = Path(self.translate_path(self.path))
        if not path.exists():
            self.path = "/index.html"
        super().do_GET()

    def log_message(self, format, *args):
        pass


# ── Checks ──

def check_screen(page: Page, name: str, viewport: str) -> list[str]:
    """
    Run axe on whatever is open.

    Returns:
    --------
    One line per violation, empty if the screen passes
    """
    violations = Axe().run(page).response["violations"]
    print(f"{viewport:<8}{name:<12}{len(violations)} violations")
    return [
        f"{viewport} {name}: {v['id']} ({len(v['nodes'])}) {v['nodes'][0]['html'][:100]}"
        for v in violations
    ]


def check_app(page: Page, base: str, viewport: str) -> list[str]:
    problems = []

    page.goto(base)
    page.wait_for_selector(".examples li")
    problems += check_screen(page, "examples", viewport)

    page.goto(f"{base}/scans/library")
    page.wait_for_selector(".rules")
    problems += check_screen(page, "results", viewport)

    page.locator('a[aria-label^="Review listitem"]').first.click()
    page.wait_for_selector(".verdict")
    problems += check_screen(page, "review", viewport)

    page.get_by_label("Edited").check()
    problems += check_screen(page, "editing", viewport)

    page.goto(f"{base}/scans/library")
    page.wait_for_selector(".rules")
    page.get_by_role("button", name="Report only").click()
    page.locator(".rule summary").first.click()
    page.locator(".review-link").first.click()
    page.wait_for_selector(".tip")
    problems += check_screen(page, "tips", viewport)

    page.goto(f"{base}/evaluation")
    page.wait_for_selector("table")
    problems += check_screen(page, "evaluation", viewport)

    return problems


# ── Main ──

def main() -> None:
    if len(sys.argv) != 2 or not Path(sys.argv[1], "index.html").exists():
        sys.exit("Usage: python scripts/check_app_accessibility.py <built site folder>")

    handler = functools.partial(AppHandler, directory=sys.argv[1])
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    problems = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for viewport, size in (("desktop", (1360, 900)), ("phone", (390, 844))):
            page = browser.new_page(viewport={"width": size[0], "height": size[1]})
            problems += check_app(page, base, viewport)
            page.close()
        browser.close()
    server.shutdown()

    if problems:
        print("\n".join(problems))
        sys.exit(1)
    print("No accessibility violations found.")


if __name__ == "__main__":
    main()
