// Every call to the FastAPI backend lives here, so the screens stay about UI.

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// ── Types (these match app/models.py) ──

export type Level = "tested" | "suggested" | "report_only";
export type Decision = "used" | "edited" | "rejected";

export type AxeIssue = {
  rule_id: string;
  level: Level;
  status: string;
  impact: string | null;
  help: string;
  selector: string;
  html: string;
  parent_html: string;
};

export type IssueGroup = {
  key: string;
  rule_id: string;
  level: Level;
  status: "violation" | "needs_review";
  impact: string | null;
  help: string;
  count: number;
  example: AxeIssue;
};

export type Scan = {
  id: number;
  url: string;
  status: "running" | "complete" | "failed";
  final_url: string | null;
  error: string | null;
  groups: IssueGroup[];
};

export type Suggestion = {
  id: number;
  scan_id: number;
  group_key: string;
  model: string;
  suggestion: {
    explanation: string;
    fix_target: "element" | "parent";
    fixed_html: string;
    needs_human_input: boolean;
    human_input_reason: string;
  };
  validation: {
    verdict: "passed" | "needs_review" | "failed" | "not_applied";
    applied: boolean;
    detail: string;
    rule_before: number;
    rule_after: number;
    new_violations: Record<string, number>;
    has_placeholder: boolean;
  };
};

export type ReviewStatus = {
  group_key: string;
  suggestion_id: number;
  decision: Decision | null;
};

export type DecisionInput = {
  decision: Decision;
  final_html?: string;
  reason?: string;
  seconds_spent?: number;
};

export type RuleSummary = {
  rule_id: string;
  suggestions: number;
  verdicts: Record<string, number>;
  decisions: Record<string, number>;
  occurrences_in_groups: number;
};

export type Evaluation = {
  scans: number;
  suggestions: number;
  decisions: number;
  rules: RuleSummary[];
};

// ── Requests ──

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new Error("Could not reach the API. Is the server running?");
  }

  const data = await response.json().catch(() => null);

  // fetch doesn't throw on a 404 or 422, so we check for those ourselves
  if (!response.ok) {
    throw new Error(
      typeof data?.detail === "string" ? data.detail : "The request failed."
    );
  }
  return data as T;
}

export function startScan(url: string): Promise<Scan> {
  return request("/api/scans", { method: "POST", body: JSON.stringify({ url }) });
}

export function getScan(scanId: string | number): Promise<Scan> {
  return request(`/api/scans/${scanId}`);
}

export function getReviews(scanId: string | number): Promise<ReviewStatus[]> {
  return request(`/api/scans/${scanId}/reviews`);
}

export function getSuggestion(
  scanId: string | number,
  groupKey: string
): Promise<Suggestion> {
  return request(`/api/scans/${scanId}/groups/${groupKey}/suggestion`, {
    method: "POST",
  });
}

export function saveDecision(
  suggestionId: number,
  decision: DecisionInput
): Promise<unknown> {
  return request(`/api/suggestions/${suggestionId}/decision`, {
    method: "POST",
    body: JSON.stringify(decision),
  });
}

export function getEvaluation(): Promise<Evaluation> {
  return request("/api/evaluation");
}
