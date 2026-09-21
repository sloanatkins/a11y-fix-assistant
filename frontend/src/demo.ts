// Demo mode: the public site runs from saved results, with no server or API key.
// Nothing here gets saved. A visitor's clicks last until they refresh the page.

import type {
  Decision,
  DecisionInput,
  Evaluation,
  IssueGroup,
  ReviewStatus,
  Scan,
  ScanSummary,
  Suggestion,
} from "./api";

export function isDemoMode(): boolean {
  return import.meta.env.VITE_DEMO_MODE === "true";
}

// ── Saved Data ──

type SavedSuggestion = Pick<Suggestion, "model" | "suggestion" | "validation">;

type SavedSite = {
  site: string;
  title: string;
  url: string;
  groups: IssueGroup[];
  suggestions: Record<string, SavedSuggestion>;
};

type SavedDecision = { decision: Decision };

const SITE_NAMES = ["bakery", "library", "clinic"];

// each file only gets fetched once
const cache = new Map<string, Promise<unknown>>();

function loadJson<T>(path: string): Promise<T> {
  if (!cache.has(path)) {
    cache.set(
      path,
      fetch(path).then((response) => {
        if (!response.ok) throw new Error("This example couldn't be loaded.");
        return response.json();
      })
    );
  }
  return cache.get(path) as Promise<T>;
}

const loadSite = (name: string) => {
  if (!SITE_NAMES.includes(name)) throw new Error("This example doesn't exist.");
  return loadJson<SavedSite>(`/demo/${name}.json`);
};

const loadSavedDecisions = () => loadJson<Record<string, SavedDecision>>("/demo/decisions.json");

// Suggestions need number ids to match the real API, so this hands them out as needed.
const suggestionIds: string[] = [];

function idFor(itemId: string): number {
  if (!suggestionIds.includes(itemId)) suggestionIds.push(itemId);
  return suggestionIds.indexOf(itemId) + 1;
}

// decisions made during this visit, which go away on refresh
const visitDecisions = new Map<string, Decision>();

async function decisionFor(itemId: string): Promise<Decision | null> {
  return visitDecisions.get(itemId) ?? (await loadSavedDecisions())[itemId]?.decision ?? null;
}

function countFlagged(site: SavedSite): number {
  return site.groups.reduce((sum, group) => sum + group.count, 0);
}

// ── Same Shapes as the Real API ──

export async function demoListScans(): Promise<ScanSummary[]> {
  const sites = await Promise.all(SITE_NAMES.map(loadSite));
  return sites.map((site) => ({
    id: site.site,
    url: site.title,
    status: "complete",
    created_at: "",
    flagged: countFlagged(site),
  }));
}

export async function demoGetScan(scanId: string | number): Promise<Scan> {
  const site = await loadSite(String(scanId));
  return {
    id: site.site,
    url: site.url,
    status: "complete",
    final_url: site.url,
    error: null,
    groups: site.groups,
    title: site.title,
  };
}

export async function demoGetReviews(scanId: string | number): Promise<ReviewStatus[]> {
  const site = await loadSite(String(scanId));
  return Promise.all(
    Object.keys(site.suggestions).map(async (key) => {
      const itemId = `${site.site}/${key}`;
      return {
        group_key: key,
        suggestion_id: idFor(itemId),
        decision: await decisionFor(itemId),
      };
    })
  );
}

export async function demoGetSuggestion(
  scanId: string | number,
  groupKey: string
): Promise<Suggestion> {
  const site = await loadSite(String(scanId));
  const saved = site.suggestions[groupKey];
  if (!saved) throw new Error("There's no saved fix for this issue.");
  return {
    ...saved,
    id: idFor(`${site.site}/${groupKey}`),
    scan_id: 0,
    group_key: groupKey,
    attempts: 1,
  };
}

export async function demoSaveDecision(suggestionId: number, input: DecisionInput): Promise<void> {
  const itemId = suggestionIds[suggestionId - 1];
  if (itemId) visitDecisions.set(itemId, input.decision);
}

// shows the saved review results, so a visitor's clicks can't change the numbers
export async function demoGetEvaluation(): Promise<Evaluation> {
  const [sites, saved] = await Promise.all([
    Promise.all(SITE_NAMES.map(loadSite)),
    loadSavedDecisions(),
  ]);
  const rules = new Map<string, Evaluation["rules"][number]>();
  let total = 0;

  for (const site of sites) {
    for (const group of site.groups) {
      const fix = site.suggestions[group.key];
      if (!fix) continue;
      total += 1;
      const rule = rules.get(group.rule_id) ?? {
        rule_id: group.rule_id,
        suggestions: 0,
        verdicts: {},
        decisions: {},
        occurrences_in_groups: 0,
      };
      rule.suggestions += 1;
      rule.occurrences_in_groups += group.count;
      const verdict = fix.validation.verdict;
      rule.verdicts[verdict] = (rule.verdicts[verdict] ?? 0) + 1;
      const decision = saved[`${site.site}/${group.key}`]?.decision;
      if (decision) rule.decisions[decision] = (rule.decisions[decision] ?? 0) + 1;
      rules.set(group.rule_id, rule);
    }
  }

  return {
    scans: sites.length,
    suggestions: total,
    decisions: Object.keys(saved).length,
    rules: [...rules.values()].sort((a, b) => a.rule_id.localeCompare(b.rule_id)),
  };
}
