"""
Generate Demo Data
==================
Runs the real pipeline on the three demo sites: scan, Groq suggestion, then a
fix test. The results get saved so the public demo never needs an API key.

Run it again to fill in anything that failed. Saved suggestions aren't redone,
so it won't spend Groq requests twice. Use --fresh to start over.

Usage:
    PYTHONPATH=. python scripts/generate_demo_data.py

Dependencies:
    - playwright
    - groq
"""

import json
import sys
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Browser, sync_playwright

from app.config import GROQ_MODEL
from app.grouping import group_issues
from app.models import AxeIssue, FixSuggestion, ValidationResult
from app.scanner import scan_page
from app.suggester import suggest_fix
from app.validator import validate_fix
from scripts.check_demo_sites import EXPECTED_RULES, start_server


# ── Settings ──

OUTPUT_DIR = Path("demo_data")
PUBLIC_PREFIX = "/demo-sites"

SITE_TITLES = {
    "bakery": "Crumb and Copper Bakery",
    "library": "Alder Street Library",
    "clinic": "Harbor Family Clinic",
}

Suggest = Callable[[AxeIssue], FixSuggestion]
Validate = Callable[[Browser, str, AxeIssue, FixSuggestion], ValidationResult]


# ── Helpers ──

def replace_base(value, base: str):
    """Swap the temporary local address for the path the public demo will use."""
    if isinstance(value, str):
        return value.replace(base, PUBLIC_PREFIX)
    if isinstance(value, list):
        return [replace_base(item, base) for item in value]
    if isinstance(value, dict):
        return {key: replace_base(item, base) for key, item in value.items()}
    return value


def load_existing(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def generate_site(
    browser: Browser,
    name: str,
    base: str,
    output_dir: Path,
    suggest: Suggest,
    validate: Validate,
) -> dict[str, int]:
    """
    Scan one site and get a tested suggestion for each supported group.
    Saves after every suggestion, so a crash doesn't lose finished work.

    Returns:
    --------
    Counts of new suggestions, saved ones skipped, and failures
    """
    url = f"{base}/{name}/index.html"
    scan = scan_page(browser, url)
    groups = group_issues(scan.issues)

    path = output_dir / f"{name}.json"
    saved = load_existing(path).get("suggestions", {})
    counts = {"new": 0, "skipped": 0, "failed": 0}

    data = {
        "site": name,
        "title": SITE_TITLES[name],
        "url": f"{PUBLIC_PREFIX}/{name}/index.html",
        "groups": replace_base([g.model_dump() for g in groups], base),
        "suggestions": saved,
    }

    for group in groups:
        if group.level == "report_only" or group.status != "violation":
            continue
        if group.key in saved:
            counts["skipped"] += 1
            continue

        print(f"  {group.rule_id}: {group.example.html[:60]}")
        try:
            suggestion = suggest(group.example)
            validation = validate(browser, url, group.example, suggestion)
        except Exception as e:
            # keep going, running the script again retries whatever failed
            print(f"    FAILED: {type(e).__name__}: {str(e)[:120]}")
            counts["failed"] += 1
            continue

        saved[group.key] = {
            "model": GROQ_MODEL,
            "suggestion": suggestion.model_dump(),
            "validation": validation.model_dump(),
        }
        counts["new"] += 1
        print(f"    {validation.verdict}")

        output_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))

    output_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    return counts


# ── Main ──

def main() -> None:
    if "--fresh" in sys.argv:
        for path in OUTPUT_DIR.glob("*.json"):
            path.unlink()

    server = start_server()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    totals = {"new": 0, "skipped": 0, "failed": 0}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for name in EXPECTED_RULES:
                print(f"\n=== {name}")
                counts = generate_site(browser, name, base, OUTPUT_DIR, suggest_fix, validate_fix)
                for key, value in counts.items():
                    totals[key] += value
            browser.close()
    finally:
        server.shutdown()

    print(f"\nNew: {totals['new']}  Already saved: {totals['skipped']}  Failed: {totals['failed']}")
    if totals["failed"]:
        print("Run this again to retry the failures.")
    print(f"Saved to {OUTPUT_DIR}/. Next: PYTHONPATH=. python scripts/review_demo_data.py")


if __name__ == "__main__":
    main()
