// Runs the app the way the public demo does, with no API server.

import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const VALIDATION = {
  verdict: "passed",
  applied: true,
  detail: "ok",
  rule_before: 5,
  rule_after: 0,
  new_violations: {},
  has_placeholder: false,
};

function group(key: string, ruleId: string, level: string, count: number) {
  return {
    key,
    rule_id: ruleId,
    level,
    status: "violation",
    impact: "serious",
    help: `Help for ${ruleId}`,
    count,
    example: {
      rule_id: ruleId,
      level,
      status: "violation",
      impact: "serious",
      help: "h",
      selector: "x",
      html: "<li>1</li>",
      parent_html: "<ul></ul>",
      options: [],
      context: {},
    },
  };
}

const site = (name: string, title: string) => ({
  site: name,
  title,
  url: `/demo-sites/${name}/index.html`,
  groups: [group("g1", "listitem", "tested", 5), group("g2", "region", "report_only", 2)],
  suggestions: {
    g1: {
      model: "m",
      suggestion: {
        explanation: "Saved explanation.",
        fix_target: "element",
        fixed_html: "<li>fixed</li>",
        needs_human_input: false,
        human_input_reason: "",
      },
      validation: VALIDATION,
    },
  },
});

const FILES: Record<string, unknown> = {
  "/demo/bakery.json": site("bakery", "Crumb and Copper Bakery"),
  "/demo/library.json": site("library", "Alder Street Library"),
  "/demo/clinic.json": site("clinic", "Harbor Family Clinic"),
  "/demo/decisions.json": { "bakery/g1": { decision: "used" } },
};

function openAt(path: string) {
  window.history.pushState({}, "", path);
  return render(<App />);
}

beforeEach(() => {
  vi.stubEnv("VITE_DEMO_MODE", "true");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (!(url in FILES)) throw new Error(`Tried to reach ${url}`);
      return new Response(JSON.stringify(FILES[url]), { status: 200 });
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("public demo", () => {
  it("lists the three examples and offers no scan form", async () => {
    openAt("/");
    expect(await screen.findByRole("link", { name: "Alder Street Library" })).toHaveAttribute(
      "href",
      "/scans/library"
    );
    expect(screen.getByRole("link", { name: "Harbor Family Clinic" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Page URL")).not.toBeInTheDocument();
    expect(screen.getByText(/Demo with saved results/)).toBeInTheDocument();
  });

  it("shows saved results and only reads saved files", async () => {
    openAt("/scans/bakery");
    expect(await screen.findByRole("heading", { name: "Crumb and Copper Bakery" })).toBeInTheDocument();
    const urls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]));
    expect(urls.every((url) => url.startsWith("/demo/"))).toBe(true);
  });

  it("opens a saved fix with its decision, and has no Groq or test buttons", async () => {
    openAt("/scans/bakery/groups/g1");
    expect(await screen.findByText("Saved explanation.")).toBeInTheDocument();
    expect(screen.getByLabelText("Used as is")).toBeChecked();
    expect(screen.queryByRole("button", { name: "Get suggested fix" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByLabelText("Edited"));
    expect(screen.queryByRole("button", { name: "Test my edit" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Rejected"));
    await userEvent.click(screen.getByRole("button", { name: "Mark decision" }));
    expect(await screen.findByText("Marked: Rejected.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });

  it("gives a clear error for an unknown example", async () => {
    openAt("/scans/nope");
    expect(await screen.findByRole("alert")).toHaveTextContent("doesn't exist");
  });

  it("shows evaluation from the saved review", async () => {
    openAt("/evaluation");
    const row = (await screen.findByRole("rowheader", { name: "listitem" })).closest("tr");
    expect(within(row as HTMLElement).getAllByRole("cell")[0]).toHaveTextContent("3");
  });

  it("has no axe violations on the examples page", async () => {
    const { container } = openAt("/");
    await screen.findByRole("link", { name: "Alder Street Library" });
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });
});
