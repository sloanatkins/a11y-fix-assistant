// Plain English versions of the values the API sends back.

import type { Decision, Level, Suggestion } from "./api";

export const LEVEL_LABELS: Record<Level, string> = {
  tested: "Fix tested with axe",
  suggested: "Draft fix to review",
  report_only: "Report only",
};

export const LEVEL_ORDER: Level[] = ["tested", "suggested", "report_only"];

export const VERDICT_LABELS: Record<Suggestion["validation"]["verdict"], string> = {
  passed: "Passed axe checks",
  needs_review: "Needs your input",
  failed: "Failed axe checks",
  not_applied: "Could not be tested",
};

export const DECISION_LABELS: Record<Decision, string> = {
  used: "Used as is",
  edited: "Edited",
  rejected: "Rejected",
};

// what to check by hand for rules the tool only reports
const RULE_TIPS: Record<string, string> = {
  region:
    "Move this content into a landmark such as main, nav, header, or footer so screen reader users can jump to it.",
  "landmark-one-main": "Wrap the page's primary content in a single main element.",
  "landmark-unique":
    "When a page has several landmarks of one type, give each its own aria-label so people can tell them apart.",
  "aria-allowed-role":
    "Check whether this role belongs on this element. A native element, like nav instead of a role on a list, is usually safer.",
  "heading-order":
    "Keep heading levels in order so the outline makes sense. Don't choose a level for how it looks.",
  "page-has-heading-one": "Give the page one h1 that says what it's about.",
  "link-in-text-block":
    "Make links stand out from nearby text with more than color, such as an underline.",
};

const DEFAULT_TIP =
  "Open the flagged element on the page and check it by hand. The rule description above says what axe expects.";

export function getRuleTip(ruleId: string): string {
  return RULE_TIPS[ruleId] ?? DEFAULT_TIP;
}
