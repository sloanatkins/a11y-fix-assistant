"""
Scan Any URL
============
Scans one public page and prints everything axe found, grouped by how much
the tool can do about it.

Usage:
    python scripts/scan_url.py https://example.com

Dependencies:
    - playwright
    - app.scanner
"""

import json
import sys
from collections import Counter
from pathlib import Path

from playwright.sync_api import sync_playwright

from app.scanner import scan_page, validate_url


# ── Settings ──

OUTPUT_PATH = Path("data/latest_scan.json")


# ── Main ──

def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/scan_url.py <url>")

    try:
        url = validate_url(sys.argv[1])
    except ValueError as e:
        sys.exit(f"Can't scan that URL: {e}")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        scan = scan_page(browser, url)
        browser.close()

    counts = Counter((i.level, i.status, i.rule_id) for i in scan.issues)
    print(f"Scanned: {scan.final_url}")
    print(f"{'level':<14}{'status':<15}{'count':>5}  rule")
    for (level, status, rule_id), count in sorted(counts.items()):
        print(f"{level:<14}{status:<15}{count:>5}  {rule_id}")

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(scan.model_dump(), indent=2))
    print(f"\nFound {len(scan.issues)} items. A clean scan doesn't mean a page is fully accessible.")
    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
