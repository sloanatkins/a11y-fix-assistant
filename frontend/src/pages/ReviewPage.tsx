import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getReviews, getScan, getSuggestion } from "../api";
import type { Decision, IssueGroup, Suggestion } from "../api";
import CodeBlock from "../components/CodeBlock";
import DecisionForm from "../components/DecisionForm";
import IssueClues from "../components/IssueClues";
import LevelBadge from "../components/LevelBadge";
import { isDemoMode } from "../demo";
import { getRuleTip, VERDICT_LABELS } from "../labels";

function ReviewPage() {
  const { scanId = "", groupKey = "" } = useParams();
  const [group, setGroup] = useState<IssueGroup | null>(null);
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSuggesting, setIsSuggesting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [scan, reviews] = await Promise.all([getScan(scanId), getReviews(scanId)]);
        if (cancelled) return;

        const found = scan.groups.find((g) => g.key === groupKey);
        if (!found) {
          setError("This issue group wasn't found.");
          return;
        }
        setGroup(found);

        // if a suggestion is already saved this returns it without calling Groq again
        const review = reviews.find((r) => r.group_key === groupKey);
        if (review) {
          const saved = await getSuggestion(scanId, groupKey);
          if (cancelled) return;
          setSuggestion(saved);
          setDecision(review.decision);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load this issue.");
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [scanId, groupKey]);

  async function handleSuggest() {
    setIsSuggesting(true);
    setError("");
    try {
      setSuggestion(await getSuggestion(scanId, groupKey));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not get a suggestion.");
    } finally {
      setIsSuggesting(false);
    }
  }

  const backLink = <Link to={`/scans/${scanId}`}>Back to results</Link>;

  if (isLoading) {
    return (
      <>
        <h1>Review issue</h1>
        <p role="status">Loading this issue.</p>
      </>
    );
  }

  if (!group) {
    return (
      <>
        <h1>Review issue</h1>
        <p className="message error" role="alert">
          {error}
        </p>
        {backLink}
      </>
    );
  }

  const currentHtml =
    suggestion?.suggestion.fix_target === "parent" ? group.example.parent_html : group.example.html;
  const canSuggest = group.level !== "report_only" && group.status === "violation";

  return (
    <>
      <p className="back">{backLink}</p>
      <h1 className="code-title">{group.rule_id}</h1>
      <p className="review-meta">
        <LevelBadge level={group.level} />
        <span>
          {group.count} {group.count === 1 ? "occurrence" : "occurrences"}
        </span>
      </p>
      <p className="lede">{group.help}</p>

      {!suggestion && <CodeBlock title="Current HTML" code={group.example.html} />}
      {!suggestion && group.example.parent_html && (
        <CodeBlock title="Parent tag" code={group.example.parent_html} />
      )}

      <IssueClues context={group.example.context ?? {}} />

      {!canSuggest && (
        <section className="tip" aria-labelledby="tip-heading">
          <h2 id="tip-heading">What to check</h2>
          <p>{getRuleTip(group.rule_id)}</p>
          <p className="tip-note">
            The tool doesn&apos;t draft fixes for this rule yet, so this one is yours to decide.
          </p>
        </section>
      )}

      {canSuggest && !suggestion && (
        <div className="stack action">
          <button type="button" onClick={handleSuggest} disabled={isSuggesting}>
            {isSuggesting ? "Drafting and testing a fix..." : "Get suggested fix"}
          </button>
          <div role="status">
            {isSuggesting && !isDemoMode() && <p>This calls Groq, then tests the fix on a temporary page copy.</p>}
          </div>
        </div>
      )}

      {error && (
        <p className="message error" role="alert">
          {error}
        </p>
      )}

      {suggestion && (
        <>
          <section aria-labelledby="explanation-heading">
            <h2 id="explanation-heading">What&apos;s wrong</h2>
            <p>{suggestion.suggestion.explanation}</p>
          </section>

          <section aria-labelledby="fix-heading">
            <h2 id="fix-heading">Suggested fix</h2>
            <div className="code-compare">
              <CodeBlock
                title={
                  suggestion.suggestion.fix_target === "parent" ? "Current parent" : "Current HTML"
                }
                code={currentHtml}
                compareTo={suggestion.suggestion.fixed_html}
                changeClass="removed"
              />
              <CodeBlock
                title="Suggested HTML"
                code={suggestion.suggestion.fixed_html}
                compareTo={currentHtml}
              />
            </div>
          </section>

          <section aria-labelledby="test-heading">
            <h2 id="test-heading">Test result</h2>
            <dl className="facts">
              <div>
                <dt>Verdict</dt>
                <dd>
                  <span className={`verdict verdict-${suggestion.validation.verdict}`}>
                    {VERDICT_LABELS[suggestion.validation.verdict]}
                  </span>
                </dd>
              </div>
              <div>
                <dt>axe count for this rule</dt>
                <dd>
                  {suggestion.validation.rule_before} before, {suggestion.validation.rule_after}{" "}
                  after
                </dd>
              </div>
              <div>
                <dt>New violations</dt>
                <dd>
                  {Object.keys(suggestion.validation.new_violations).join(", ") || "None"}
                </dd>
              </div>
              <div>
                <dt>Details</dt>
                <dd>{suggestion.validation.detail}</dd>
              </div>
            </dl>
            <p className="caveat">
              A passing test only means axe found no problem. Check that the wording is accurate
              and the page still looks right.
            </p>
          </section>

          <section aria-labelledby="decision-heading">
            <h2 id="decision-heading">Your decision</h2>
            <DecisionForm
              // a new attempt gets a fresh form and timer
              key={`${suggestion.id}-${suggestion.attempts}`}
              suggestionId={suggestion.id}
              fixedHtml={suggestion.suggestion.fixed_html}
              initialDecision={decision}
              attempts={suggestion.attempts}
              onRetried={(next) => {
                setSuggestion(next);
                setDecision(null);
              }}
            />
          </section>
        </>
      )}
    </>
  );
}

export default ReviewPage;
