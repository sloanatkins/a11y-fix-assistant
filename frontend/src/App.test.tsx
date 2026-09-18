// Tests the screens the way I'd use them, with a fake API instead of the server.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const GROUP = {
  key: "abc123",
  rule_id: "listitem",
  level: "tested",
  status: "violation",
  impact: "serious",
  help: "li elements must be contained in a ul or ol",
  count: 11,
  example: {
    rule_id: "listitem",
    level: "tested",
    status: "violation",
    impact: "serious",
    help: "li elements must be contained in a ul or ol",
    selector: "li",
    html: '<li class="current">1</li>',
    parent_html: '<ul class="pagination" role="navigation"></ul>',
  },
};

const REPORT_ONLY = {
  ...GROUP,
  key: "def456",
  rule_id: "color-contrast",
  level: "report_only",
  help: "Text must have enough contrast",
  count: 2,
};

const SCAN = {
  id: 1,
  url: "https://example.com",
  status: "complete",
  final_url: "https://example.com",
  error: null,
  groups: [REPORT_ONLY, GROUP],
};

const SUGGESTION = {
  id: 7,
  scan_id: 1,
  group_key: "abc123",
  model: "test-model",
  suggestion: {
    explanation: "The role on the list stops it being a list.",
    fix_target: "parent",
    fixed_html: '<nav aria-label="Pagination"><ul class="pagination">...</ul></nav>',
    needs_human_input: false,
    human_input_reason: "",
  },
  validation: {
    verdict: "passed",
    applied: true,
    detail: "axe checks passed",
    rule_before: 11,
    rule_after: 0,
    new_violations: {},
    has_placeholder: false,
  },
};

type Route = { status?: number; body: unknown };

function mockApi(routes: Record<string, Route | Route[]>) {
  const calls: { key: string; body: unknown }[] = [];
  const fetchMock = vi.fn(async (url: string, options?: RequestInit) => {
    const key = `${options?.method ?? "GET"} ${new URL(url).pathname}`;
    calls.push({ key, body: options?.body ? JSON.parse(options.body as string) : null });
    const route = routes[key];
    if (!route) throw new Error(`No fake route for ${key}`);
    const current = Array.isArray(route) ? (route.length > 1 ? route.shift()! : route[0]) : route;
    return new Response(JSON.stringify(current.body), { status: current.status ?? 200 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return calls;
}

function openAt(path: string) {
  window.history.pushState({}, "", path);
  return render(<App />);
}

beforeEach(() => {
  window.history.pushState({}, "", "/");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("new scan", () => {
  it("shows the API's error for a blocked URL", async () => {
    mockApi({
      "POST /api/scans": { status: 422, body: { detail: "URL must point to a public website" } },
    });
    openAt("/");
    await userEvent.type(screen.getByLabelText("Page URL"), "http://localhost:8000");
    await userEvent.click(screen.getByRole("button", { name: "Scan page" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("public website");
  });

  it("explains when the server is down", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    openAt("/");
    await userEvent.type(screen.getByLabelText("Page URL"), "https://example.com");
    await userEvent.click(screen.getByRole("button", { name: "Scan page" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Is the server running?");
  });

  it("goes to the results and waits for a running scan", async () => {
    mockApi({
      "POST /api/scans": { status: 202, body: { ...SCAN, status: "running", groups: [] } },
      "GET /api/scans/1": [{ body: { ...SCAN, status: "running", groups: [] } }, { body: SCAN }],
      "GET /api/scans/1/reviews": { body: [] },
    });
    openAt("/");
    await userEvent.type(screen.getByLabelText("Page URL"), "https://example.com");
    await userEvent.click(screen.getByRole("button", { name: "Scan page" }));
    expect(await screen.findByRole("heading", { name: "Scanning page" })).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Scan results" }, { timeout: 3000 })
    ).toBeInTheDocument();
  });
});

describe("results", () => {
  it("sorts tested fixes first and filters by level", async () => {
    mockApi({
      "GET /api/scans/1": { body: SCAN },
      "GET /api/scans/1/reviews": { body: [] },
    });
    openAt("/scans/1");
    expect(await screen.findByText("axe flagged 13 items across 2 groups.")).toBeInTheDocument();
    const names = screen.getAllByText(/^(listitem|color-contrast)$/).map((n) => n.textContent);
    expect(names).toEqual(["listitem", "color-contrast"]);

    await userEvent.selectOptions(screen.getByLabelText("Show"), "report_only");
    expect(screen.queryByText("listitem")).not.toBeInTheDocument();
  });

  it("shows why a scan failed", async () => {
    mockApi({
      "GET /api/scans/1": { body: { ...SCAN, status: "failed", error: "Page timed out" } },
      "GET /api/scans/1/reviews": { body: [] },
    });
    openAt("/scans/1");
    expect(await screen.findByRole("alert")).toHaveTextContent("Page timed out");
  });
});

describe("review", () => {
  it("only calls Groq after I ask, then saves an edited decision", async () => {
    const calls = mockApi({
      "GET /api/scans/1": { body: SCAN },
      "GET /api/scans/1/reviews": { body: [] },
      "POST /api/scans/1/groups/abc123/suggestion": { body: SUGGESTION },
      "POST /api/suggestions/7/decision": { body: { id: 1 } },
    });
    openAt("/scans/1/groups/abc123");

    const button = await screen.findByRole("button", { name: "Get suggested fix" });
    expect(calls.some((c) => c.key.includes("suggestion"))).toBe(false);
    await userEvent.click(button);

    expect(await screen.findByText("Passed axe checks")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Edited"));
    const textarea = screen.getByLabelText("Your final HTML");
    await userEvent.clear(textarea);
    await userEvent.type(textarea, "<nav>mine</nav>");
    await userEvent.click(screen.getByRole("button", { name: "Save decision" }));

    expect(await screen.findByText("Saved: Edited.")).toBeInTheDocument();
    const saved = calls.find((c) => c.key.endsWith("/decision"))?.body as Record<string, unknown>;
    expect(saved.decision).toBe("edited");
    expect(saved.final_html).toBe("<nav>mine</nav>");
    expect(saved.seconds_spent).toEqual(expect.any(Number));
  });

  it("doesn't offer a fix for report only issues", async () => {
    mockApi({
      "GET /api/scans/1": { body: SCAN },
      "GET /api/scans/1/reviews": { body: [] },
    });
    openAt("/scans/1/groups/def456");
    expect(await screen.findByText(/reports this issue/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Get suggested fix" })).not.toBeInTheDocument();
  });

  it("reopens a saved suggestion with its decision", async () => {
    mockApi({
      "GET /api/scans/1": { body: SCAN },
      "GET /api/scans/1/reviews": {
        body: [{ group_key: "abc123", suggestion_id: 7, decision: "rejected" }],
      },
      "POST /api/scans/1/groups/abc123/suggestion": { body: SUGGESTION },
    });
    openAt("/scans/1/groups/abc123");
    expect(await screen.findByText("Saved: Rejected.")).toBeInTheDocument();
    expect(screen.getByLabelText("Rejected")).toBeChecked();
  });
});

describe("accessibility", () => {
  it.each([
    ["/", "Scan a public page"],
    ["/scans/1", "Scan results"],
    ["/evaluation", "Evaluation"],
  ])("%s has no axe violations", async (path, heading) => {
    mockApi({
      "GET /api/scans/1": { body: SCAN },
      "GET /api/scans/1/reviews": { body: [] },
      "GET /api/evaluation": {
        body: {
          scans: 1,
          suggestions: 1,
          decisions: 1,
          rules: [
            {
              rule_id: "listitem",
              suggestions: 1,
              verdicts: { passed: 1 },
              decisions: { used: 1 },
              occurrences_in_groups: 11,
            },
          ],
        },
      },
    });
    const { container } = openAt(path);
    await screen.findByRole("heading", { name: heading });
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
    // jsdom can't measure colors, so the browser check covers contrast
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });
});
