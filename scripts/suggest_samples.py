"""
Suggest Sample Fixes
====================
Takes one saved issue per rule from the scan results and prints what
Groq suggests, so we can read the output before building anything on it.

Dependencies:
    - app.suggester
"""

import json
from pathlib import Path

from app.config import GROQ_MODEL
from app.models import AxeIssue
from app.suggester import suggest_fix


# ── Settings ──

RESULTS_PATH = Path("data/scan_results.json")
OUTPUT_PATH = Path("data/sample_suggestions.json")


# ── Main ──

def main() -> None:
    scans = json.loads(RESULTS_PATH.read_text())

    # one example per rule is enough for a first read
    samples = {}
    for scan in scans:
        for raw in scan["issues"]:
            # report only rules don't get a suggested fix yet
            if raw["status"] == "violation" and raw["level"] != "report_only":
                samples.setdefault(raw["rule_id"], (scan["url"], AxeIssue(**raw)))

    print(f"Model: {GROQ_MODEL}")
    saved = []
    for rule_id, (url, issue) in samples.items():
        print(f"\n=== {rule_id}\n{url}\nBEFORE: {issue.html}")
        try:
            suggestion = suggest_fix(issue)
        except Exception as e:
            # keep going so one bad response doesn't hide the others
            print(f"ERROR: {type(e).__name__}: {e}")
            continue
        print(f"EXPLANATION: {suggestion.explanation}")
        print(f"PARENT: {issue.parent_html}")
        print(f"FIX TARGET: {suggestion.fix_target}")
        print(f"AFTER: {suggestion.fixed_html}")
        print(f"NEEDS ME: {suggestion.needs_human_input} {suggestion.human_input_reason}")
        saved.append({"url": url, **issue.model_dump(), **suggestion.model_dump()})

    OUTPUT_PATH.write_text(json.dumps(saved, indent=2))
    print(f"\nSaved {len(saved)} of {len(samples)} suggestions to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
