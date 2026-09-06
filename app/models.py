"""
Data Models
===========
Pydantic models for what the scanner finds on a page.

Dependencies:
    - pydantic
"""

from pydantic import BaseModel


# ── Scan Results ──

class AxeIssue(BaseModel):
    rule_id: str
    status: str  # "violation" or "needs_review"
    impact: str | None
    help: str
    selector: str
    html: str


class PageScan(BaseModel):
    url: str
    final_url: str
    issues: list[AxeIssue]
