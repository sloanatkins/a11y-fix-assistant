"""
Data Models
===========
Pydantic models for what the scanner finds on a page.

Dependencies:
    - pydantic
"""

from typing import Literal

from pydantic import BaseModel


# ── Scan Results ──

class AxeIssue(BaseModel):
    rule_id: str
    level: str = "report_only"  # tested, suggested, or report_only
    status: str  # "violation" or "needs_review"
    impact: str | None
    help: str
    selector: str
    target: list = []  # axe's raw path, needed for shadow DOM
    html: str
    parent_html: str = ""


class PageScan(BaseModel):
    url: str
    final_url: str
    issues: list[AxeIssue]


# ── Fix Suggestions ──

class FixSuggestion(BaseModel):
    explanation: str
    fix_target: Literal["element", "parent"]
    fixed_html: str
    needs_human_input: bool
    human_input_reason: str


# ── Validation Results ──

class ValidationResult(BaseModel):
    verdict: Literal["passed", "needs_review", "failed", "not_applied"]
    applied: bool
    detail: str
    rule_before: int
    rule_after: int
    new_violations: dict[str, int]
    has_placeholder: bool
