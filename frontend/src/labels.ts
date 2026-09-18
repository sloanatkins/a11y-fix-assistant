// Plain English versions of the values the API sends back.

import type { Decision, Level, Suggestion } from "./api";

export const LEVEL_LABELS: Record<Level, string> = {
  tested: "Tested fix",
  suggested: "Suggested fix",
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
