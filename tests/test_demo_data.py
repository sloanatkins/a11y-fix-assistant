"""
Demo Data Tests
===============
Runs the real scanner and validator on the demo sites with a fake Groq step,
then checks the review script saves and totals decisions correctly.

Dependencies:
    - pytest
    - playwright
"""

import json

import pytest
from playwright.sync_api import sync_playwright

from app.models import FixSuggestion, ValidationResult
from app.validator import validate_fix
from scripts.check_demo_sites import start_server
from scripts.generate_demo_data import generate_site
from scripts.review_demo_data import build_summary, load_items, review


def fake_suggest(issue):
    return FixSuggestion(
        explanation="test",
        fix_target="element",
        fixed_html=issue.html.replace(">", ' aria-label="Test">', 1),
        needs_human_input=False,
        human_input_reason="",
    )


@pytest.fixture
def browser_and_base():
    server = start_server()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser, f"http://127.0.0.1:{server.server_address[1]}"
        browser.close()
    server.shutdown()


def test_generate_saves_tested_fixes_without_local_addresses(browser_and_base, tmp_path):
    browser, base = browser_and_base
    calls = []

    def suggest(issue):
        calls.append(issue)
        return fake_suggest(issue)

    counts = generate_site(browser, "library", base, tmp_path, suggest, validate_fix)
    assert counts["new"] > 0
    assert counts["failed"] == 0

    text = (tmp_path / "library.json").read_text()
    assert "127.0.0.1" not in text
    assert "/demo-sites/library/" in text

    # report only rules shouldn't use up Groq requests
    assert all(issue.level != "report_only" for issue in calls)


def test_second_run_doesnt_call_groq_again(browser_and_base, tmp_path):
    browser, base = browser_and_base
    generate_site(browser, "clinic", base, tmp_path, fake_suggest, validate_fix)

    def should_not_run(issue):
        raise AssertionError("called Groq for a saved suggestion")

    counts = generate_site(browser, "clinic", base, tmp_path, should_not_run, validate_fix)
    assert counts["new"] == 0
    assert counts["failed"] == 0
    assert counts["skipped"] > 0


def test_failure_is_counted_and_retried_next_run(browser_and_base, tmp_path):
    browser, base = browser_and_base

    def broken(issue):
        raise RuntimeError("rate limited")

    counts = generate_site(browser, "bakery", base, tmp_path, broken, validate_fix)
    assert counts["failed"] > 0
    assert json.loads((tmp_path / "bakery.json").read_text())["suggestions"] == {}

    counts = generate_site(browser, "bakery", base, tmp_path, fake_suggest, validate_fix)
    assert counts["new"] > 0


def make_items(tmp_path):
    validation = ValidationResult(
        verdict="passed",
        applied=True,
        detail="ok",
        rule_before=1,
        rule_after=0,
        new_violations={},
        has_placeholder=False,
    ).model_dump()
    suggestion = fake_suggest(type("I", (), {"html": "<a>"})()).model_dump()
    example = {"html": "<a>", "parent_html": "", "context": {}, "options": []}
    site = {
        "site": "bakery",
        "groups": [
            {"key": k, "rule_id": rule, "count": 1, "example": example}
            for k, rule in [("k1", "link-name"), ("k2", "link-name"), ("k3", "image-alt")]
        ],
        "suggestions": {
            k: {"model": "m", "suggestion": suggestion, "validation": validation}
            for k in ("k1", "k2", "k3")
        },
    }
    (tmp_path / "bakery.json").write_text(json.dumps(site))
    return load_items(tmp_path)


def test_review_saves_answers_and_can_quit_and_resume(tmp_path):
    items = make_items(tmp_path)
    decisions = {}
    saves = []
    answers = iter(["x", "u", "r", "too vague", "q"])
    review(items, decisions, lambda d: saves.append(dict(d)), ask=lambda _: next(answers))

    assert len(saves) == 2
    assert decisions["bakery/k1"] == {"decision": "used"}
    assert decisions["bakery/k2"] == {"decision": "rejected", "reason": "too vague"}

    answers = iter(["e", "<a>mine</a>"])
    review(items, decisions, lambda d: None, ask=lambda _: next(answers))
    assert decisions["bakery/k3"] == {"decision": "edited", "final_html": "<a>mine</a>"}


def test_summary_totals_by_rule(tmp_path):
    items = make_items(tmp_path)
    decisions = {"bakery/k1": {"decision": "used"}, "bakery/k2": {"decision": "rejected"}}
    summary = build_summary(items, decisions)
    assert summary["link-name"]["suggestions"] == 2
    assert summary["link-name"]["decisions"]["rejected"] == 1
    assert summary["image-alt"]["verdicts"]["passed"] == 1
