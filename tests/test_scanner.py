"""
Scanner Tests
=============
Runs the scanner on a small local page with problems we planted.

Dependencies:
    - pytest
    - playwright
"""

import pytest
from playwright.sync_api import sync_playwright

from app.scanner import get_level, scan_page, validate_url

BROKEN_PAGE = """<!doctype html><html lang="en"><head><title>Test</title></head><body>
<main>
  <h1>Test page</h1>
  <img src="missing.png">
  <input type="text">
  <iframe src="about:blank"></iframe>
  <div role="listitem">Not inside a list</div>
  <ul class="pagination" role="navigation" aria-label="Pagination"><li>1</li></ul>
</main></body></html>"""


def test_scanner_finds_planted_issues(tmp_path):
    page_file = tmp_path / "broken.html"
    page_file.write_text(BROKEN_PAGE)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        scan = scan_page(browser, page_file.as_uri())
        browser.close()

    found = {issue.rule_id for issue in scan.issues}
    assert {"label", "frame-title", "aria-required-parent", "listitem"} <= found

    # the parent tag is what makes the pagination fix possible
    listitem = next(i for i in scan.issues if i.rule_id == "listitem")
    assert 'role="navigation"' in listitem.parent_html

    # rules outside our fix list should still be reported
    image = next(i for i in scan.issues if i.rule_id == "image-alt")
    assert image.level == "report_only"


def test_levels():
    assert get_level("listitem") == "tested"
    assert get_level("frame-title") == "suggested"
    assert get_level("color-contrast") == "report_only"


@pytest.mark.parametrize(
    "bad_url",
    [
        "ftp://example.com",
        "file:///etc/passwd",
        "not a url",
        "http://localhost:8000",
        "http://127.0.0.1",
        "http://192.168.1.1",
        "http://169.254.169.254/latest/meta-data",
    ],
)
def test_bad_urls_are_rejected(bad_url):
    with pytest.raises(ValueError):
        validate_url(bad_url)


def test_public_ip_is_allowed():
    assert validate_url("https://93.184.216.34/") == "https://93.184.216.34/"
