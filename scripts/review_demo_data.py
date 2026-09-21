"""
Review Demo Data
================
Walks through each saved suggestion so I can record what I'd really do with
it. My decisions are the evaluation results, so judge these honestly.

It saves after every answer. Quit any time and run it again to pick up where
you left off. Use --summary to only print the results.

Usage:
    PYTHONPATH=. python scripts/review_demo_data.py

Dependencies:
    - none
"""

import json
import sys
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path


# ── Settings ──

DATA_DIR = Path("demo_data")
DECISIONS_FILE = "decisions.json"
CHOICES = {"u": "used", "e": "edited", "r": "rejected"}


# ── Loading ──

def load_items(data_dir: Path) -> list[dict]:
    """
    Pull every suggestion out of the site files.

    Returns:
    --------
    List of items with an id, the issue group, and the suggestion
    """
    items = []
    for path in sorted(data_dir.glob("*.json")):
        if path.name == DECISIONS_FILE:
            continue
        site = json.loads(path.read_text())
        groups = {group["key"]: group for group in site["groups"]}
        for key, saved in site["suggestions"].items():
            items.append(
                {
                    "id": f"{site['site']}/{key}",
                    "site": site["site"],
                    "group": groups[key],
                    **saved,
                }
            )
    return items


def load_decisions(data_dir: Path) -> dict:
    path = data_dir / DECISIONS_FILE
    return json.loads(path.read_text()) if path.exists() else {}


def save_decisions(data_dir: Path, decisions: dict) -> None:
    (data_dir / DECISIONS_FILE).write_text(json.dumps(decisions, indent=2))


# ── Reviewing ──

def show_item(item: dict, position: int, total: int) -> None:
    group = item["group"]
    suggestion = item["suggestion"]
    validation = item["validation"]
    print(f"\n[{position}/{total}] {item['site']}: {group['rule_id']} ({group['count']} flagged)")
    print(f"Problem:    {suggestion['explanation']}")
    target = group["example"]["parent_html"] if suggestion["fix_target"] == "parent" else group["example"]["html"]
    print(f"Current:    {target}")
    print(f"Suggested:  {suggestion['fixed_html']}")
    print(
        f"Test:       {validation['verdict']}, "
        f"{validation['rule_before']} before, {validation['rule_after']} after, "
        f"new violations: {validation['new_violations'] or 'none'}"
    )
    print(f"Details:    {validation['detail']}")
    context = group["example"].get("context") or {}
    options = group["example"].get("options") or []
    if context:
        print(f"Clues:      {context}")
    if options:
        print(f"Options:    {options}")


def review(
    items: list[dict],
    decisions: dict,
    save: Callable[[dict], None],
    ask: Callable[[str], str] = input,
) -> None:
    """Ask about every item without a decision yet, saving after each answer."""
    remaining = [item for item in items if item["id"] not in decisions]
    for position, item in enumerate(remaining, start=1):
        show_item(item, position, len(remaining))

        answer = ""
        while answer not in CHOICES and answer != "q":
            answer = ask("[u]sed as is, [e]dited, [r]ejected, [q]uit: ").strip().lower()
        if answer == "q":
            return

        decision = {"decision": CHOICES[answer]}
        if answer == "e":
            decision["final_html"] = ask("Your final HTML: ").strip()
        if answer == "r":
            decision["reason"] = ask("Why was it wrong? ").strip()
        decisions[item["id"]] = decision
        save(decisions)


# ── Summary ──

def build_summary(items: list[dict], decisions: dict) -> dict[str, dict]:
    """
    Total up the results by rule.

    Returns:
    --------
    Dictionary of rule id -> counts
    """
    rules: dict[str, dict] = defaultdict(
        lambda: {"suggestions": 0, "verdicts": Counter(), "decisions": Counter()}
    )
    for item in items:
        rule = rules[item["group"]["rule_id"]]
        rule["suggestions"] += 1
        rule["verdicts"][item["validation"]["verdict"]] += 1
        if item["id"] in decisions:
            rule["decisions"][decisions[item["id"]]["decision"]] += 1
    return dict(sorted(rules.items()))


def print_summary(items: list[dict], decisions: dict) -> None:
    print(f"\nReviewed {len([i for i in items if i['id'] in decisions])} of {len(items)}\n")
    print(f"{'rule':<18}{'fixes':>6}{'passed':>8}{'input':>7}{'failed':>8}{'used':>6}{'edited':>8}{'rejected':>10}")
    for rule_id, rule in build_summary(items, decisions).items():
        verdicts, chosen = rule["verdicts"], rule["decisions"]
        failed = verdicts["failed"] + verdicts["not_applied"]
        print(
            f"{rule_id:<18}{rule['suggestions']:>6}{verdicts['passed']:>8}{verdicts['needs_review']:>7}"
            f"{failed:>8}{chosen['used']:>6}{chosen['edited']:>8}{chosen['rejected']:>10}"
        )


# ── Main ──

def main() -> None:
    items = load_items(DATA_DIR)
    if not items:
        sys.exit("Nothing to review yet. Run scripts/generate_demo_data.py first.")

    decisions = load_decisions(DATA_DIR)
    if "--summary" not in sys.argv:
        review(items, decisions, lambda d: save_decisions(DATA_DIR, d))
    print_summary(items, decisions)


if __name__ == "__main__":
    main()
