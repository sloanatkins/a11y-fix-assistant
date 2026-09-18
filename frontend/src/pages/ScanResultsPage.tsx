import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getReviews, getScan } from "../api";
import type { IssueGroup, Level, ReviewStatus, Scan } from "../api";
import LevelBadge from "../components/LevelBadge";
import { DECISION_LABELS, LEVEL_LABELS, LEVEL_ORDER } from "../labels";

const POLL_MS = 1500;

type LevelFilter = Level | "all";

type RuleGroup = {
  ruleId: string;
  level: Level;
  help: string;
  total: number;
  groups: IssueGroup[];
};

// collapses separate rows into one section per rule
function groupByRule(groups: IssueGroup[]): RuleGroup[] {
  const rules = new Map<string, RuleGroup>();
  for (const group of groups) {
    const rule = rules.get(group.rule_id) ?? {
      ruleId: group.rule_id,
      level: group.level,
      help: group.help,
      total: 0,
      groups: [],
    };
    rule.total += group.count;
    rule.groups.push(group);
    rules.set(group.rule_id, rule);
  }
  return [...rules.values()].sort(
    (a, b) =>
      LEVEL_ORDER.indexOf(a.level) - LEVEL_ORDER.indexOf(b.level) || b.total - a.total
  );
}

function ScanResultsPage() {
  const { scanId = "" } = useParams();
  const [scan, setScan] = useState<Scan | null>(null);
  const [reviews, setReviews] = useState<ReviewStatus[]>([]);
  const [filter, setFilter] = useState<LevelFilter>("all");
  const [error, setError] = useState("");

  // keeps checking until the scan finishes, and cleans up if we leave the page
  useEffect(() => {
    let cancelled = false;
    const polling: { timer?: number } = {};

    async function poll() {
      try {
        const latest = await getScan(scanId);
        if (cancelled) return;
        setScan(latest);
        if (latest.status === "running") {
          polling.timer = window.setTimeout(poll, POLL_MS);
          return;
        }
        const latestReviews = await getReviews(scanId);
        if (!cancelled) setReviews(latestReviews);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load this scan.");
        }
      }
    }

    poll();
    return () => {
      cancelled = true;
      window.clearTimeout(polling.timer);
    };
  }, [scanId]);

  const decisions = useMemo(
    () => new Map(reviews.map((review) => [review.group_key, review.decision])),
    [reviews]
  );

  const rules = useMemo(() => {
    const groups = scan?.groups ?? [];
    return groupByRule(
      filter === "all" ? groups : groups.filter((group) => group.level === filter)
    );
  }, [scan, filter]);

  if (error) {
    return (
      <>
        <h1>Scan results</h1>
        <p className="message error" role="alert">
          {error}
        </p>
        <Link to="/">Start a new scan</Link>
      </>
    );
  }

  if (!scan || scan.status === "running") {
    return (
      <>
        <h1>Scanning page</h1>
        <p role="status">Opening the page and running axe. This can take a little while.</p>
        {scan && <p className="url">{scan.url}</p>}
      </>
    );
  }

  if (scan.status === "failed") {
    return (
      <>
        <h1>The scan failed</h1>
        <p className="message error" role="alert">
          {scan.error}
        </p>
        <Link to="/">Try another page</Link>
      </>
    );
  }

  const total = scan.groups.reduce((sum, group) => sum + group.count, 0);

  return (
    <>
      <h1>Scan results</h1>
      <p className="url">{scan.final_url}</p>
      <p className="lede">
        axe flagged {total} {total === 1 ? "item" : "items"} across {scan.groups.length}{" "}
        {scan.groups.length === 1 ? "group" : "groups"}.
      </p>

      {scan.groups.length === 0 && (
        <p className="note">
          axe found nothing, but that doesn&apos;t mean the page is fully accessible. Manual
          testing is still needed.
        </p>
      )}

      {scan.groups.length > 0 && (
        <div className="field filter">
          <label htmlFor="level-filter">Show</label>
          <select
            id="level-filter"
            value={filter}
            onChange={(event) => setFilter(event.target.value as LevelFilter)}
          >
            <option value="all">All issues</option>
            {LEVEL_ORDER.map((level) => (
              <option key={level} value={level}>
                {LEVEL_LABELS[level]}
              </option>
            ))}
          </select>
        </div>
      )}

      {rules.length === 0 && scan.groups.length > 0 && (
        <p className="note">No issues match this filter.</p>
      )}

      <div className="stack">
        {rules.map((rule) => (
          <details className="panel rule" key={rule.ruleId} open={rule.level !== "report_only"}>
            <summary>
              <span className="rule-name">{rule.ruleId}</span>
              <LevelBadge level={rule.level} />
              <span className="rule-count">{rule.total} flagged</span>
            </summary>
            <p>{rule.help}</p>
            <ul className="group-list">
              {rule.groups.map((group) => {
                const decision = decisions.get(group.key);
                return (
                  <li key={group.key}>
                    <code className="snippet">{group.example.html}</code>
                    <div className="group-meta">
                      <span>
                        {group.count} {group.count === 1 ? "occurrence" : "occurrences"}
                        {group.status === "needs_review" && ", axe was unsure"}
                        {decision && `, ${DECISION_LABELS[decision]}`}
                      </span>
                      <Link
                        to={`/scans/${scanId}/groups/${group.key}`}
                        aria-label={`Review ${rule.ruleId}: ${group.example.html.slice(0, 60)}`}
                      >
                        Review
                      </Link>
                    </div>
                  </li>
                );
              })}
            </ul>
          </details>
        ))}
      </div>
    </>
  );
}

export default ScanResultsPage;
