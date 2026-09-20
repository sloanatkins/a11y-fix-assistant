"""
Check Demo Sites
================
Serves the three demo sites locally and scans them, so we can confirm each
planted problem really gets flagged. No Groq calls here.

Dependencies:
    - playwright
    - app.scanner
"""

import functools
import threading
from collections import Counter
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

from app.models import PageScan
from app.scanner import scan_page


# ── Settings ──

SITES_DIR = Path(__file__).resolve().parent.parent / "demo_sites"

# the rules each site is built to trigger
EXPECTED_RULES = {
    "bakery": {"html-has-lang", "image-alt", "link-name", "color-contrast", "button-name"},
    "library": {"label", "select-name", "listitem", "image-alt", "link-name", "button-name"},
    "clinic": {"html-has-lang", "label", "select-name", "image-alt", "link-name", "frame-title"},
}


# ── Local Server ──

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def start_server() -> ThreadingHTTPServer:
    """Start a local server on any free port, only reachable from this computer."""
    handler = functools.partial(QuietHandler, directory=str(SITES_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def scan_sites() -> dict[str, PageScan]:
    """
    Scan every demo site.

    Returns:
    --------
    Dictionary of site name -> its scan
    """
    server = start_server()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            scans = {
                name: scan_page(browser, f"{base}/{name}/index.html")
                for name in EXPECTED_RULES
            }
            browser.close()
        return scans
    finally:
        server.shutdown()


# ── Main ──

def main() -> None:
    all_found = True
    for name, scan in scan_sites().items():
        counts = Counter(i.rule_id for i in scan.issues if i.status == "violation")
        missing = EXPECTED_RULES[name] - set(counts)
        all_found = all_found and not missing

        print(f"\n=== {name}: {sum(counts.values())} flagged")
        for rule_id, count in sorted(counts.items()):
            marker = "planted" if rule_id in EXPECTED_RULES[name] else "also found"
            print(f"{count:>4}  {rule_id:<24}{marker}")
        if missing:
            print(f"MISSING: {sorted(missing)}")

    print("\nAll planted problems found." if all_found else "\nSome planted problems were missed.")


if __name__ == "__main__":
    main()
