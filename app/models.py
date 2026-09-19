"""
Data Models
===========
Pydantic models for what the scanner finds on a page.

Dependencies:
    - pydantic
"""

from typing import Literal

from pydantic import BaseModel, Field


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
    options: list[str] = []  # dropdown choices, the best clue to what it does
    context: dict[str, str] = {}  # extra clues, like an image URL or link destination


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


# ── API Models ──

class IssueGroup(BaseModel):
    key: str
    rule_id: str
    level: str
    status: str
    impact: str | None
    help: str
    count: int
    example: AxeIssue


class ScanRequest(BaseModel):
    url: str


class ScanResponse(BaseModel):
    id: int
    url: str
    status: Literal["running", "complete", "failed"]
    final_url: str | None = None
    error: str | None = None
    groups: list[IssueGroup] = []


class ScanSummary(BaseModel):
    id: int
    url: str
    status: Literal["running", "complete", "failed"]
    created_at: str
    flagged: int


class SuggestionResponse(BaseModel):
    id: int
    scan_id: int
    group_key: str
    model: str
    attempts: int = 1
    suggestion: FixSuggestion
    validation: ValidationResult


class DecisionRequest(BaseModel):
    decision: Literal["used", "edited", "rejected"]
    final_html: str | None = None
    reason: str | None = None
    seconds_spent: float | None = Field(default=None, ge=0)
    final_verdict: str | None = None


class RetryRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class TestEditRequest(BaseModel):
    html: str = Field(min_length=1, max_length=50_000)


class DecisionResponse(DecisionRequest):
    id: int
    suggestion_id: int


class ReviewStatus(BaseModel):
    group_key: str
    suggestion_id: int
    decision: str | None


class RuleSummary(BaseModel):
    rule_id: str
    suggestions: int
    verdicts: dict[str, int]
    decisions: dict[str, int]
    occurrences_in_groups: int


class EvaluationResponse(BaseModel):
    scans: int
    suggestions: int
    decisions: int
    rules: list[RuleSummary]
