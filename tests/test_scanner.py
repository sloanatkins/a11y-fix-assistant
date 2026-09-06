"""
Scanner Tests
=============
Runs the scanner on a small local page with problems we planted.

Dependencies:
    - pytest
    - playwright
"""

from playwright.sync_api import sync_playwright

from app.scanner import scan_page

BROKEN_PAGE = """<!doctype html><html lang="en"><head><title>Test</title></head><body>
<main>
  <h1>Test page</h1>
  <input type="text">
  <iframe src="about:blank"></iframe>
  <div role="listitem">Not inside a list</div>
  <table>
    <thead><tr><th>Name</th><th>Unused</th></tr></thead>
    <tbody><tr><td>Sloan</td></tr></tbody>
  </table>
</main></body></html>"""


def test_scanner_finds_planted_issues(tmp_path):
    page_file = tmp_path / "broken.html"
    page_file.write_text(BROKEN_PAGE)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        scan = scan_page(browser, page_file.as_uri())
        browser.close()

    found = {issue.rule_id for issue in scan.issues}
    assert {"label", "frame-title", "aria-required-parent"} <= found
