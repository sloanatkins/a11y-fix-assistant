"""
Page Scanner
============
Opens a page in Chromium and runs axe on what the browser rendered.
Keeps everything axe finds and labels how much the tool can do about it.
This only reads the page, nothing on the site gets changed.

Dependencies:
    - playwright
    - axe-playwright-python
"""

import ipaddress
import socket
from urllib.parse import urlparse

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import Browser, Page

from app.contrast import suggest_text_color
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


# rules move up to tested only after their fixes hold up in the evaluation
RULE_LEVELS = {
    "select-name": "tested",
    "listitem": "tested",
    "frame-title": "suggested",
    "html-has-lang": "suggested",
    "image-alt": "suggested",
    "link-name": "suggested",
    "button-name": "suggested",
    "label": "suggested",
    "color-contrast": "suggested",
}


def get_level(rule_id: str) -> str:
    """
    Look up how much the tool can do for a rule.

    Returns:
    --------
    "tested", "suggested", or "report_only"
    """
    return RULE_LEVELS.get(rule_id, "report_only")


# ── URL Checks ──

def validate_url(url: str) -> str:
    """
    Only allow normal public web pages, so the scanner can't be pointed at
    something like localhost or a machine on a private network.

    Returns:
    --------
    The same URL if it's okay, otherwise raises ValueError
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("URL must start with http:// or https://")

    try:
        addresses = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as e:
        raise ValueError(f"Could not find {parsed.hostname}") from e

    for address in addresses:
        if not ipaddress.ip_address(address[4][0]).is_global:
            raise ValueError("URL must point to a public website")
    return url


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


def get_select_options(page: Page, target: list, rule_id: str) -> list[str]:
    """
    axe often only gives us a dropdown's opening tag, but its options are the
    best clue about what it's for, so grab a few of them.

    Returns:
    --------
    Up to 8 option labels, or an empty list if this isn't a dropdown
    """
    if rule_id != "select-name" or len(target) != 1 or not isinstance(target[0], str):
        return []
    return page.evaluate(
        """(selector) => {
            const select = document.querySelector(selector);
            if (!select || !select.options) return [];
            return [...select.options].slice(0, 8).map((o) => o.text.trim()).filter(Boolean);
        }""",
        target[0],
    )


def get_element_context(page: Page, target: list, rule_id: str) -> dict[str, str]:
    """
    Grab clues the model and I need that aren't in the flagged HTML, like
    where a link goes or the full address of an image.

    Returns:
    --------
    Dictionary of clues, empty if there's nothing useful for this rule
    """
    if rule_id not in ("image-alt", "link-name"):
        return {}
    if len(target) != 1 or not isinstance(target[0], str):
        return {}
    return page.evaluate(
        """(selector) => {
            const el = document.querySelector(selector);
            if (!el) return {};
            const image = el.tagName === "IMG" ? el : el.querySelector("img");
            const context = {};
            if (el.href) context.link_url = el.href;
            if (image && image.src) context.image_url = image.src;
            if (image) {
                context.image_size = `${image.naturalWidth}x${image.naturalHeight}`;
            }
            // an image in a link has no text beside it, so walk up until we find some
            let ancestor = el.parentElement;
            for (let level = 0; ancestor && level < 4; level++) {
                const nearby = ancestor.textContent.replace(/\\s+/g, " ").trim();
                if (nearby) {
                    context.nearby_text = nearby.slice(0, 200);
                    break;
                }
                ancestor = ancestor.parentElement;
            }
            return context;
        }""",
        target[0],
    )


def get_contrast_context(node: dict) -> dict[str, str]:
    """
    Pull the colors out of axe's result and work out a passing text color.

    Returns:
    --------
    Colors and ratios as strings, empty if axe didn't give us the colors
    """
    for check in node.get("any", []):
        data = check.get("data")
        if not isinstance(data, dict) or not data.get("fgColor") or not data.get("bgColor"):
            continue
        target = float(str(data.get("expectedContrastRatio", "4.5")).split(":")[0])
        context = {
            "text_color": data["fgColor"],
            "background_color": data["bgColor"],
            "current_ratio": str(data.get("contrastRatio", "")),
            "required_ratio": str(target),
        }
        suggested = suggest_text_color(data["fgColor"], data["bgColor"], target)
        if suggested:
            context["suggested_color"] = suggested
        return context
    return {}


# ── Scanning ──

class PageLoadError(Exception):
    """The page answered, but with an error instead of real content."""


def scan_page(browser: Browser, url: str) -> PageScan:
    """
    Scan one page and keep everything axe finds. Call validate_url first
    for any URL that comes from a user.

    Returns:
    --------
    PageScan with one AxeIssue per flagged element
    """
    page = browser.new_page()
    try:
        response = page.goto(url, wait_until="load", timeout=60_000)
        # scanning a 404 page would only tell us about the error page
        if response is not None and response.status >= 400:
            raise PageLoadError(f"The page returned an error (status {response.status}).")
        # give any late scripts a second to finish building the page
        page.wait_for_timeout(1_000)
        results = Axe().run(page).response

        # axe puts results it isn't sure about in "incomplete", so keep those too
        groups = [("violation", results["violations"]), ("needs_review", results["incomplete"])]

        issues = []
        for status, findings in groups:
            for finding in findings:
                for node in finding["nodes"]:
                    issues.append(
                        AxeIssue(
                            rule_id=finding["id"],
                            level=get_level(finding["id"]),
                            status=status,
                            impact=node.get("impact"),
                            help=finding["help"],
                            selector=" ".join(str(part) for part in node["target"]),
                            target=node["target"],
                            html=node["html"],
                            parent_html=get_parent_tag(page, node["target"]),
                            options=get_select_options(page, node["target"], finding["id"]),
                            context=(
                                get_contrast_context(node)
                                if finding["id"] == "color-contrast"
                                else get_element_context(page, node["target"], finding["id"])
                            ),
                        )
                    )
        return PageScan(url=url, final_url=page.url, issues=issues)
    finally:
        page.close()
