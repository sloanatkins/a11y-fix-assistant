import { useState } from "react";
import type { FormEvent } from "react";
import { retrySuggestion, saveDecision, testEdit } from "../api";
import type { Decision, Suggestion, Validation } from "../api";
import { DECISION_LABELS, VERDICT_LABELS } from "../labels";

type DecisionFormProps = {
  suggestionId: number;
  fixedHtml: string;
  initialDecision: Decision | null;
  attempts: number;
  onRetried: (suggestion: Suggestion) => void;
};

const MAX_ATTEMPTS = 3;

const CHOICES: Decision[] = ["used", "edited", "rejected"];

function DecisionForm({
  suggestionId,
  fixedHtml,
  initialDecision,
  attempts,
  onRetried,
}: DecisionFormProps) {
  const [decision, setDecision] = useState<Decision | null>(initialDecision);
  const [finalHtml, setFinalHtml] = useState(fixedHtml);
  const [reason, setReason] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [savedAs, setSavedAs] = useState<Decision | null>(initialDecision);
  const [error, setError] = useState("");
  const [editResult, setEditResult] = useState<Validation | null>(null);
  const [isTesting, setIsTesting] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);

  // passing a function means this only runs once, when the form first appears
  const [startedAt] = useState(() => Date.now());

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!decision) {
      setError("Choose what you did with this fix.");
      return;
    }

    setIsSaving(true);
    setError("");
    try {
      await saveDecision(suggestionId, {
        decision,
        final_html: decision === "edited" ? finalHtml : undefined,
        final_verdict: decision === "edited" ? editResult?.verdict : undefined,
        reason: decision === "rejected" ? reason : undefined,
        seconds_spent: Math.round((Date.now() - startedAt) / 1000),
      });
      setSavedAs(decision);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save your decision.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleTestEdit() {
    setIsTesting(true);
    setError("");
    setEditResult(null);
    try {
      setEditResult(await testEdit(suggestionId, finalHtml));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not test your edit.");
    } finally {
      setIsTesting(false);
    }
  }

  async function handleRetry() {
    setIsRetrying(true);
    setError("");
    try {
      onRetried(await retrySuggestion(suggestionId, reason));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not get a new fix.");
      setIsRetrying(false);
    }
  }

  const canRetry = decision === "rejected" && savedAs === "rejected" && attempts < MAX_ATTEMPTS;

  return (
    <form className="decision-form" onSubmit={handleSubmit}>
      <fieldset>
        <legend>What did you do with this fix?</legend>
        <div className="choices">
        {CHOICES.map((choice) => (
          <label className="choice" key={choice}>
            <input
              type="radio"
              name="decision"
              value={choice}
              checked={decision === choice}
              onChange={() => {
                setDecision(choice);
                setSavedAs(null);
              }}
            />
            {DECISION_LABELS[choice]}
          </label>
        ))}
        </div>
      </fieldset>

      {decision === "edited" && (
        <div className="field">
          <label htmlFor="final-html">Your final HTML</label>
          <textarea
            id="final-html"
            rows={5}
            value={finalHtml}
            onChange={(event) => {
              setFinalHtml(event.target.value);
              // the old result doesn't apply once the HTML changes
              setEditResult(null);
            }}
          />
          <button
            type="button"
            className="secondary"
            onClick={handleTestEdit}
            disabled={isTesting || !finalHtml.trim()}
          >
            {isTesting ? "Testing your edit..." : "Test my edit"}
          </button>
          <div role="status">
            {editResult && (
              <p className={`message ${editResult.verdict === "passed" ? "success" : "error"}`}>
                {VERDICT_LABELS[editResult.verdict]}: axe count {editResult.rule_before} before,{" "}
                {editResult.rule_after} after.
                {editResult.verdict === "passed" ? "" : ` ${editResult.detail}`}
              </p>
            )}
          </div>
        </div>
      )}

      {decision === "rejected" && (
        <div className="field">
          <label htmlFor="reject-reason">Why was it wrong?</label>
          <textarea
            id="reject-reason"
            rows={3}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </div>
      )}

      <button type="submit" disabled={isSaving}>
        {isSaving ? "Saving..." : "Save decision"}
      </button>

      {error && (
        <p className="message error" role="alert">
          {error}
        </p>
      )}
      <div role="status">
        {savedAs && (
          <p className="message success">Saved: {DECISION_LABELS[savedAs]}.</p>
        )}
      </div>

      {canRetry && (
        <div className="retry">
          <button type="button" className="secondary" onClick={handleRetry} disabled={isRetrying}>
            {isRetrying ? "Drafting a new fix..." : "Try again"}
          </button>
          <span>
            Attempt {attempts} of {MAX_ATTEMPTS}. Your reason goes to Groq with the rejected fix.
          </span>
        </div>
      )}
      {decision === "rejected" && savedAs === "rejected" && attempts >= MAX_ATTEMPTS && (
        <p className="caveat">All {MAX_ATTEMPTS} attempts are used, so this one is yours to fix.</p>
      )}
    </form>
  );
}

export default DecisionForm;
