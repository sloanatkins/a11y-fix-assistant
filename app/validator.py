"""
Fix Validator
=============
Applies a suggested fix to a temporary copy of the page in the browser,
then runs axe again. Nothing here touches the live site, and a pass only
means axe is happy. I still have to judge the wording and how it looks.

Dependencies:
    - playwright
    - axe-playwright-python
"""

import re
from collections import Counter

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import Browser, Page

from app.models import AxeIssue, FixSuggestion, ValidationResult


# ── Applying the Fix ──

PLACEHOLDER = re.compile(r"\[[A-Z][A-Z0-9 _-]+\]")

# find the node (even inside shadow DOM), swap in the fix, keep its real children
APPLY_FIX_JS = """
({ target, fixTarget, fixedHtml }) => {
    let scope = document;
    let element = null;
    for (const step of target) {
        const path = Array.isArray(step) ? step : [step];
        for (let i = 0; i < path.length; i++) {
            element = scope.querySelector(path[i]);
            if (!element) return "Could not find the flagged element";
            if (i < path.length - 1) scope = element.shadowRoot;
            if (!scope) return "Could not get inside the shadow DOM";
        }
    }

    const node = fixTarget === "parent" ? element.parentElement : element;
    if (!node) return "Flagged element has no parent";

    // a template can't hold an html tag, so just copy its attributes across
    if (node === document.documentElement) {
        const parsed = new DOMParser().parseFromString(fixedHtml, "text/html").documentElement;
        for (const attribute of parsed.attributes) {
            node.setAttribute(attribute.name, attribute.value);
        }
        return "applied";
    }

    const template = document.createElement("template");
    template.innerHTML = fixedHtml;
    const root = template.content.firstElementChild;
    if (!root) return "Fix did not contain any HTML";

    // the children go where the model wrote ..., or in the matching tag
    const all = [root, ...root.querySelectorAll("*")];
    const hasDots = (el) => [...el.childNodes].some(
        (child) => child.nodeType === 3 && child.textContent.includes("...")
    );
    const slot = all.find(hasDots)
        || all.reverse().find((el) => el.tagName === node.tagName)
        || root;

    const emptySlot = slot.children.length === 0
        && slot.textContent.replace("...", "").trim() === "";
    if (emptySlot) {
        slot.textContent = "";
        slot.append(...node.childNodes);
    }

    node.replaceWith(...template.content.childNodes);
    return "applied";
}
"""


def apply_fix(page: Page, issue: AxeIssue, suggestion: FixSuggestion) -> str:
    """
    Swap the fix into the open page.

    Returns:
    --------
    "applied", or a short reason it couldn't be applied
    """
    return page.evaluate(
        APPLY_FIX_JS,
        {
            "target": issue.target or [issue.selector],
            "fixTarget": suggestion.fix_target,
            "fixedHtml": suggestion.fixed_html,
        },
    )


# ── Checking the Result ──

def run_axe(page: Page) -> list[dict]:
    """
    Run axe on the open page.

    Returns:
    --------
    List of axe violations
    """
    return Axe().run(page).response["violations"]


def count_violations(violations: list[dict]) -> Counter:
    """
    Count flagged elements by rule.

    Returns:
    --------
    Counter of rule id -> number of flagged elements
    """
    return Counter({v["id"]: len(v["nodes"]) for v in violations})


def find_current_target(violations: list[dict], issue: AxeIssue) -> list:
    """
    Injected elements can land in a different spot on every load, so look
    for the same HTML on this copy instead of trusting the saved path.

    Returns:
    --------
    axe's path on this copy, or the saved path if there's no HTML match
    """
    for violation in violations:
        if violation["id"] != issue.rule_id:
            continue
        for node in violation["nodes"]:
            if node["html"] == issue.html:
                return node["target"]
    return issue.target


def validate_fix(
    browser: Browser, url: str, issue: AxeIssue, suggestion: FixSuggestion
) -> ValidationResult:
    """
    Test one suggestion on a fresh copy of the page.

    Returns:
    --------
    ValidationResult with the axe counts before and after the fix
    """
    page = browser.new_page()
    try:
        page.goto(url, wait_until="load", timeout=60_000)
        page.wait_for_timeout(1_000)
        violations = run_axe(page)
        before = count_violations(violations)
        issue = issue.model_copy(update={"target": find_current_target(violations, issue)})
        rule_before = before[issue.rule_id]
        has_placeholder = bool(PLACEHOLDER.search(suggestion.fixed_html))

        status = apply_fix(page, issue, suggestion)
        if status != "applied":
            return ValidationResult(
                verdict="not_applied",
                applied=False,
                detail=status,
                rule_before=rule_before,
                rule_after=rule_before,
                new_violations={},
                has_placeholder=has_placeholder,
            )

        page.wait_for_timeout(200)
        after = count_violations(run_axe(page))
        rule_after = after[issue.rule_id]
        new_violations = {
            rule: after[rule] - before[rule]
            for rule in after
            if after[rule] > before[rule] and rule != issue.rule_id
        }

        # ── Verdict ──
        if rule_after >= rule_before or new_violations:
            verdict = "failed"
            detail = "Rule did not improve or the fix added a new violation"
        elif suggestion.needs_human_input or has_placeholder:
            verdict = "needs_review"
            detail = suggestion.human_input_reason or "Fix still has a placeholder"
        else:
            verdict = "passed"
            detail = "axe checks passed, but the wording still needs your review"

        return ValidationResult(
            verdict=verdict,
            applied=True,
            detail=detail,
            rule_before=rule_before,
            rule_after=rule_after,
            new_violations=new_violations,
            has_placeholder=has_placeholder,
        )
    finally:
        page.close()
