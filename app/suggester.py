"""
Fix Suggester
=============
Sends one axe issue to Groq and gets back an explanation and a draft fix.
The fix is only a draft, it still has to pass validation and my review.

Dependencies:
    - groq
    - pydantic
"""

import json
from pathlib import Path

from groq import BadRequestError, Groq

from app.config import GROQ_API_KEY, GROQ_MODEL
from app.models import AxeIssue, FixSuggestion


# ── Prompt and Schema ──

PROMPT_PATH = Path(__file__).parent / "prompts" / "fix_suggestion.md"

# strict mode wants every field required and no extras
FIX_SCHEMA = {
    **FixSuggestion.model_json_schema(),
    "additionalProperties": False,
}


# ── Rule Hints ──

# the general prompt wasn't enough, so these spell out the known problem
RULE_HINTS = {
    "listitem": (
        "If the parent tag is a ul or ol with a role attribute, that role is the cause. "
        "Set fix_target to parent, keep the li as is, remove the role from the list, "
        "and put that role's job on a wrapper. For role=navigation use "
        "<nav aria-label=...><ul ...>...</ul></nav>."
    ),
    "frame-title": (
        "You can't see inside the frame, so always use a placeholder title "
        "and set needs_human_input to true."
    ),
}


# ── Guards ──

def apply_guards(issue: AxeIssue, suggestion: FixSuggestion) -> FixSuggestion:
    """
    Catch the mistakes we already know the model makes. These only send a
    suggestion to me for review, they never rewrite the fix itself.

    Returns:
    --------
    FixSuggestion, flagged for review if a guard tripped
    """
    reason = ""
    if issue.rule_id == "frame-title":
        reason = "Only a person can check what this frame shows."
    elif (
        issue.rule_id == "listitem"
        and "role=" in issue.parent_html
        and suggestion.fix_target != "parent"
    ):
        reason = "The parent's role looks like the cause, but this fix didn't change the parent."

    if not reason:
        return suggestion
    return suggestion.model_copy(
        update={"needs_human_input": True, "human_input_reason": reason}
    )


# ── Suggestions ──

def suggest_fix(issue: AxeIssue, client: Groq | None = None) -> FixSuggestion:
    """
    Ask the model for an explanation and a fix for one issue.

    Returns:
    --------
    FixSuggestion that has been checked against the Pydantic model
    """
    client = client or Groq(api_key=GROQ_API_KEY)

    issue_text = (
        "<issue>\n"
        f"Rule: {issue.rule_id}\n"
        f"Help: {issue.help}\n"
        f"Selector: {issue.selector}\n"
        f"HTML: {issue.html}\n"
        f"Parent tag: {issue.parent_html or 'unknown'}\n"
        f"Hint: {RULE_HINTS.get(issue.rule_id, 'none')}\n"
        "</issue>"
    )

    # strict mode sometimes rejects a bad generation, so give it one more try
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                temperature=0,
                messages=[
                    {"role": "system", "content": PROMPT_PATH.read_text()},
                    {"role": "user", "content": issue_text},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "fix_suggestion",
                        "strict": True,
                        "schema": FIX_SCHEMA,
                    },
                },
            )
            break
        except BadRequestError:
            if attempt == 1:
                raise

    data = json.loads(response.choices[0].message.content)
    return apply_guards(issue, FixSuggestion.model_validate(data))
