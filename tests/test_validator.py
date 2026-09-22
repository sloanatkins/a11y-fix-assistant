"""
Validator Tests
===============
Runs fixes against a small local page, so no network or Groq needed.

Dependencies:
    - pytest
    - playwright
"""

import pytest
from playwright.sync_api import sync_playwright

from app.models import AxeIssue, FixSuggestion
from app.scanner import scan_page
from app.validator import validate_fix

TEST_PAGE = """<!doctype html><html lang="en"><head><title>Test</title></head><body>
<main>
  <h1>Test page</h1>
  <select id="subject"><option>Finance</option><option>Marketing</option></select>
  <ul class="pagination" role="navigation" aria-label="Pagination">
    <li class="current">1</li><li><a href="#2">2</a></li>
  </ul>
  <iframe src="about:blank"></iframe>
  <div id="host"></div>
</main>
<script>
  const shadow = document.getElementById("host").attachShadow({ mode: "open" });
  shadow.innerHTML = '<iframe id="popup" src="about:blank"></iframe>';
</script>
</body></html>"""


@pytest.fixture
def scan_env(tmp_path):
    page_file = tmp_path / "test.html"
    page_file.write_text(TEST_PAGE)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser, page_file.as_uri()
        browser.close()


def fix(html: str, target: str = "element", needs_person: bool = False) -> FixSuggestion:
    return FixSuggestion(
        explanation="test",
        fix_target=target,
        fixed_html=html,
        needs_human_input=needs_person,
        human_input_reason="check it" if needs_person else "",
    )


def find_issue(browser, url: str, rule_id: str) -> AxeIssue:
    return next(i for i in scan_page(browser, url).issues if i.rule_id == rule_id)


def test_opening_tag_fix_passes_and_keeps_options(scan_env):
    browser, url = scan_env
    issue = find_issue(browser, url, "select-name")
    result = validate_fix(browser, url, issue, fix('<select id="subject" aria-label="Subject">'))
    assert result.verdict == "passed"
    assert result.rule_after == 0


def test_parent_fix_clears_every_list_item(scan_env):
    browser, url = scan_env
    issue = find_issue(browser, url, "listitem")
    fixed = '<nav aria-label="Pagination"><ul class="pagination">...</ul></nav>'
    result = validate_fix(browser, url, issue, fix(fixed, target="parent"))
    assert result.verdict == "passed"
    assert (result.rule_before, result.rule_after) == (2, 0)


def test_placeholder_goes_to_review(scan_env):
    browser, url = scan_env
    issue = find_issue(browser, url, "frame-title")
    fixed = '<iframe src="about:blank" title="[DESCRIBE THE CONTENT]"></iframe>'
    result = validate_fix(browser, url, issue, fix(fixed, needs_person=True))
    assert result.verdict == "needs_review"
    assert result.has_placeholder is True


def test_shadow_dom_iframe_can_be_fixed(scan_env):
    browser, url = scan_env
    issues = [i for i in scan_page(browser, url).issues if i.rule_id == "frame-title"]
    issue = next(i for i in issues if isinstance(i.target[0], list))
    fixed = '<iframe id="popup" src="about:blank" title="[DESCRIBE THE POPUP]"></iframe>'
    result = validate_fix(browser, url, issue, fix(fixed, needs_person=True))
    assert result.applied is True
    assert result.rule_after == result.rule_before - 1


def test_fix_that_changes_nothing_fails(scan_env):
    browser, url = scan_env
    issue = find_issue(browser, url, "select-name")
    result = validate_fix(browser, url, issue, fix('<select id="subject">'))
    assert result.verdict == "failed"


def test_stale_path_is_found_again_by_html(scan_env):
    browser, url = scan_env
    issue = find_issue(browser, url, "select-name").model_copy(
        update={"target": ["#old-spot"]}
    )
    result = validate_fix(browser, url, issue, fix('<select id="subject" aria-label="Subject">'))
    assert result.verdict == "passed"


def test_missing_element_is_not_applied(scan_env):
    browser, url = scan_env
    issue = find_issue(browser, url, "select-name").model_copy(
        update={"target": ["#does-not-exist"], "html": "<select id=\"gone\">"}
    )
    result = validate_fix(browser, url, issue, fix("<select>"))
    assert result.verdict == "not_applied"


COLOR_PAGE = """<!doctype html><html><head><title>Test</title></head><body><main><h1>Test</h1>
<p id="faint" style="color: #bbbbbb; background: #ffffff">Hard to read</p>
<a href="/menu"><img src="menu.png"></a>
<img id="pic" src="photo.png">
</main></body></html>"""


@pytest.fixture
def color_env(tmp_path):
    page_file = tmp_path / "color.html"
    page_file.write_text(COLOR_PAGE)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser, page_file.as_uri()
        browser.close()


def test_html_lang_fix_works_on_the_root_element(color_env):
    browser, url = color_env
    issue = find_issue(browser, url, "html-has-lang")
    result = validate_fix(browser, url, issue, fix('<html lang="en">', needs_person=True))
    assert result.applied is True
    assert (result.rule_before, result.rule_after) == (1, 0)


def test_suggested_color_passes_axe(color_env):
    browser, url = color_env
    issue = find_issue(browser, url, "color-contrast")
    color = issue.context["suggested_color"]
    fixed = f'<p id="faint" style="color: {color}; background: #ffffff">Hard to read</p>'
    result = validate_fix(browser, url, issue, fix(fixed, needs_person=True))
    assert (result.rule_before, result.rule_after) == (1, 0)


def test_image_and_link_context_is_saved(color_env):
    browser, url = color_env
    link = find_issue(browser, url, "link-name")
    assert link.context["link_url"].endswith("/menu")
    assert link.context["image_url"].endswith("menu.png")
    image = next(
        i for i in scan_page(browser, url).issues
        if i.rule_id == "image-alt" and "photo" in i.html
    )
    assert image.context["image_url"].endswith("photo.png")


def test_decorative_alt_passes_axe(color_env):
    browser, url = color_env
    image = next(
        i for i in scan_page(browser, url).issues
        if i.rule_id == "image-alt" and "photo" in i.html
    )
    result = validate_fix(browser, url, image, fix('<img id="pic" src="photo.png" alt="">', needs_person=True))
    assert result.rule_after == result.rule_before - 1


def test_fix_cant_pass_by_removing_the_link(color_env):
    browser, url = color_env
    link = find_issue(browser, url, "link-name")
    result = validate_fix(browser, url, link, fix('<img src="menu.png" alt="Menu">'))
    assert result.verdict == "not_applied"
    assert "removes the <a>" in result.detail


def test_link_fix_that_keeps_the_link_passes(color_env):
    browser, url = color_env
    link = find_issue(browser, url, "link-name")
    fixed = '<a href="/menu"><img src="menu.png" alt="Menu"></a>'
    result = validate_fix(browser, url, link, fix(fixed))
    assert result.applied is True
    assert result.rule_after == result.rule_before - 1


def test_image_inside_a_link_finds_nearby_text(tmp_path):
    page_file = tmp_path / "card.html"
    page_file.write_text(
        '<!doctype html><html lang="en"><head><title>T</title></head><body><main><h1>x</h1>'
        '<article><a href="#a"><img src="a.png"></a><h3>Country sourdough</h3></article>'
        "</main></body></html>"
    )
    with sync_playwright() as p:
        browser = p.chromium.launch()
        scan = scan_page(browser, page_file.as_uri())
        browser.close()
    image = next(i for i in scan.issues if i.rule_id == "image-alt")
    assert "Country sourdough" in image.context["nearby_text"]


def test_error_page_stops_the_scan():
    import threading
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    from app.scanner import PageLoadError

    server = ThreadingHTTPServer(("127.0.0.1", 0), SimpleHTTPRequestHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            with pytest.raises(PageLoadError, match="404"):
                scan_page(browser, f"http://127.0.0.1:{server.server_address[1]}/missing.html")
            browser.close()
    finally:
        server.shutdown()
