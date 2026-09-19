"""
Suggester Tests
===============
Uses a fake Groq client so the tests don't need a key or spend any requests.

Dependencies:
    - pytest
    - pydantic
"""

import json
from types import SimpleNamespace

import httpx
import pytest
from groq import BadRequestError
from pydantic import ValidationError

from app.models import AxeIssue
from app.models import FixSuggestion
from app.suggester import FIX_SCHEMA, apply_guards, suggest_fix

ISSUE = AxeIssue(
    rule_id="frame-title",
    status="violation",
    impact="serious",
    help="Frames must have an accessible name",
    selector="iframe",
    html='<iframe src="video.html"></iframe>',
)


class FakeClient:
    """Pretends to be Groq and remembers what it was asked."""

    def __init__(self, content: str):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.content = content

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_valid_response_becomes_a_suggestion():
    client = FakeClient(json.dumps({
        "explanation": "The frame has no name.",
        "fix_target": "element",
        "fixed_html": '<iframe src="video.html" title="[DESCRIBE THE VIDEO]"></iframe>',
        "needs_human_input": True,
        "human_input_reason": "I can't see what the video shows.",
    }))
    result = suggest_fix(ISSUE, client=client)
    assert result.needs_human_input is True
    assert result.fix_target == "element"
    assert ISSUE.html in client.calls[0]["messages"][1]["content"]


def test_missing_field_is_rejected():
    client = FakeClient(json.dumps({"explanation": "Only this."}))
    with pytest.raises(ValidationError):
        suggest_fix(ISSUE, client=client)


def test_schema_works_for_strict_mode():
    assert FIX_SCHEMA["additionalProperties"] is False
    assert set(FIX_SCHEMA["required"]) == set(FIX_SCHEMA["properties"])


def test_wrong_pagination_fix_gets_flagged():
    issue = ISSUE.model_copy(update={
        "rule_id": "listitem",
        "html": '<li class="current">1</li>',
        "parent_html": '<ul class="pagination" role="navigation"></ul>',
    })
    bad_fix = FixSuggestion(
        explanation="Not in a list.",
        fix_target="element",
        fixed_html='<span class="current">1</span>',
        needs_human_input=False,
        human_input_reason="",
    )
    assert apply_guards(issue, bad_fix).needs_human_input is True


def test_iframe_title_always_needs_a_person():
    guessed = FixSuggestion(
        explanation="No title.",
        fix_target="element",
        fixed_html='<iframe title="Popup"></iframe>',
        needs_human_input=False,
        human_input_reason="",
    )
    assert apply_guards(ISSUE, guessed).needs_human_input is True


def test_bad_generation_gets_one_retry():
    client = FakeClient(json.dumps({
        "explanation": "No name.",
        "fix_target": "element",
        "fixed_html": "<iframe></iframe>",
        "needs_human_input": True,
        "human_input_reason": "Need a title.",
    }))
    working_create = client.chat.completions.create
    response = httpx.Response(400, request=httpx.Request("POST", "https://groq.test"))
    failures = [BadRequestError("bad json", response=response, body=None)]

    def flaky_create(**kwargs):
        if failures:
            raise failures.pop()
        return working_create(**kwargs)

    client.chat.completions.create = flaky_create
    assert suggest_fix(ISSUE, client=client).explanation == "No name."


def test_generic_label_gets_flagged():
    vague = FixSuggestion(
        explanation="No name.",
        fix_target="element",
        fixed_html='<select aria-label="Select option">',
        needs_human_input=False,
        human_input_reason="",
    )
    issue = ISSUE.model_copy(update={"rule_id": "select-name"})
    assert apply_guards(issue, vague).needs_human_input is True


def test_specific_label_is_left_alone():
    clear = FixSuggestion(
        explanation="No name.",
        fix_target="element",
        fixed_html='<select aria-label="Program type">',
        needs_human_input=False,
        human_input_reason="",
    )
    issue = ISSUE.model_copy(update={"rule_id": "select-name"})
    assert apply_guards(issue, clear).needs_human_input is False


def test_options_are_sent_to_the_model():
    client = FakeClient(json.dumps({
        "explanation": "x",
        "fix_target": "element",
        "fixed_html": "<select>",
        "needs_human_input": False,
        "human_input_reason": "",
    }))
    issue = ISSUE.model_copy(update={"rule_id": "select-name", "options": ["MBA", "Masters"]})
    suggest_fix(issue, client=client)
    assert "MBA, Masters" in client.calls[0]["messages"][1]["content"]


@pytest.mark.parametrize("rule_id", ["image-alt", "link-name", "html-has-lang", "color-contrast"])
def test_judgment_rules_always_need_a_person(rule_id):
    sure = FixSuggestion(
        explanation="x",
        fix_target="element",
        fixed_html="<x>",
        needs_human_input=False,
        human_input_reason="",
    )
    issue = ISSUE.model_copy(update={"rule_id": rule_id})
    assert apply_guards(issue, sure).needs_human_input is True


def test_context_is_sent_to_the_model():
    client = FakeClient(json.dumps({
        "explanation": "x",
        "fix_target": "element",
        "fixed_html": "<a>",
        "needs_human_input": False,
        "human_input_reason": "",
    }))
    issue = ISSUE.model_copy(
        update={"rule_id": "link-name", "context": {"link_url": "https://x.test/menu"}}
    )
    suggest_fix(issue, client=client)
    assert "https://x.test/menu" in client.calls[0]["messages"][1]["content"]
