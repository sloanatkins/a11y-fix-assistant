"""
Issue Grouping
==============
Turns a flat list of axe issues into groups that may share one fix, so 11
pagination items show up as one thing to review instead of 11.

Dependencies:
    - app.models
"""

import hashlib

from app.models import AxeIssue, IssueGroup


# ── Grouping ──

# for these rules the parent is the usual cause, so its children go together
PARENT_RULES = {"listitem", "aria-required-parent"}


def group_key(issue: AxeIssue) -> str:
    """
    Build a stable id for an issue's group.

    Returns:
    --------
    Short hash that's the same for issues that belong together
    """
    if issue.rule_id in PARENT_RULES and issue.parent_html:
        source = issue.parent_html
    else:
        source = issue.html
    raw = f"{issue.rule_id}|{issue.status}|{source}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def group_issues(issues: list[AxeIssue]) -> list[IssueGroup]:
    """
    Group a page's issues, keeping the order axe found them in.

    Returns:
    --------
    List of IssueGroup, with the first issue saved as the group's example
    """
    groups: dict[str, IssueGroup] = {}
    for issue in issues:
        key = group_key(issue)
        if key in groups:
            groups[key].count += 1
            continue
        groups[key] = IssueGroup(
            key=key,
            rule_id=issue.rule_id,
            level=issue.level,
            status=issue.status,
            impact=issue.impact,
            help=issue.help,
            count=1,
            example=issue,
        )
    return list(groups.values())
