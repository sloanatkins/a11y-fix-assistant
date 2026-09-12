"""
Validate Sample Fixes
=====================
Tests the saved Groq suggestions on temporary copies of their pages.

Dependencies:
    - playwright
    - app.validator
"""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from app.models import AxeIssue, FixSuggestion
from app.validator import validate_fix


# ── Settings ──

SUGGESTIONS_PATH = Path("data/sample_suggestions.json")
OUTPUT_PATH = Path("data/validation_results.json")


# ── Main ──

def main() -> None:
    samples = json.loads(SUGGESTIONS_PATH.read_text())
    saved = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for sample in samples:
            issue = AxeIssue(**sample)
            suggestion = FixSuggestion(**sample)
            result = validate_fix(browser, sample["url"], issue, suggestion)

            print(f"\n=== {issue.rule_id}\n{sample['url']}")
            print(f"VERDICT: {result.verdict}")
            print(f"RULE COUNT: {result.rule_before} -> {result.rule_after}")
            print(f"NEW VIOLATIONS: {result.new_violations or 'none'}")
            print(f"DETAIL: {result.detail}")
            saved.append({**sample, **result.model_dump()})
        browser.close()

    OUTPUT_PATH.write_text(json.dumps(saved, indent=2))
    print(f"\nSaved {len(saved)} results to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
