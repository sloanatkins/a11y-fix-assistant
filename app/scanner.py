"""
Page Scanner
============
Opens a page in Chromium and runs axe on what the browser rendered.
This only reads the page, nothing on the site gets changed.

Dependencies:
    - playwright
    - axe-playwright-python
"""

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import Browser, Page

from app.models import AxeIssue, PageScan


# ── Rules We Care About ──

# axe rule -> the label we use in the logs
TARGET_RULES = {
    "select-name": "missing_label",
    "label": "missing_label",
    "listitem": "role_context",
    "aria-required-parent": "role_context",
    "frame-title": "iframe_title",
}


# ── Page Context ──

def get_parent_tag(page: Page, target: list) -> str:
    """
    Grab just the opening tag of the flagged element's parent.
    Some issues, like listitem, are really caused by the parent.

    Returns:
    --------
    Parent's opening tag, or an empty string if we can't find it
    """
    # nested targets mean iframes or shadow DOM, skip those for now
    if len(target) != 1 or not isinstance(target[0], str):
        return ""
    return page.evaluate(
        """(selector) => {
            const parent = document.querySelector(selector)?.parentElement;
            return parent ? parent.cloneNode(false).outerHTML : "";
        }""",
        target[0],
    )


# ── Scanning ──

def scan_page(browser: Browser, url: str) -> PageScan:
    """
    Scan one page and keep only the rules in TARGET_RULES.

    Returns:
    --------
    PageScan with one AxeIssue per flagged element
    """
    page = browser.new_page()
    try:
        page.goto(url, wait_until="load", timeout=60_000)
        # give any late scripts a second to finish building the page
        page.wait_for_timeout(1_000)
        results = Axe().run(page).response

        # axe puts results it isn't sure about in "incomplete", so keep those too
        groups = [("violation", results["violations"]), ("needs_review", results["incomplete"])]

        issues = []
        for status, findings in groups:
            for finding in findings:
                if finding["id"] not in TARGET_RULES:
                    continue
                for node in finding["nodes"]:
                    issues.append(
                        AxeIssue(
                            rule_id=finding["id"],
                            status=status,
                            impact=node.get("impact"),
                            help=finding["help"],
                            selector=" ".join(str(part) for part in node["target"]),
                            target=node["target"],
                            html=node["html"],
                            parent_html=get_parent_tag(page, node["target"]),
                        )
                    )
        return PageScan(url=url, final_url=page.url, issues=issues)
    finally:
        page.close()
