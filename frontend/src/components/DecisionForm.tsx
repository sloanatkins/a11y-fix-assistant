import { useState } from "react";
import type { FormEvent } from "react";
import { saveDecision } from "../api";
import type { Decision } from "../api";
import { DECISION_LABELS } from "../labels";

type DecisionFormProps = {
  suggestionId: number;
  fixedHtml: string;
  initialDecision: Decision | null;
};

const CHOICES: Decision[] = ["used", "edited", "rejected"];

function DecisionForm({ suggestionId, fixedHtml, initialDecision }: DecisionFormProps) {
  const [decision, setDecision] = useState<Decision | null>(initialDecision);
  const [finalHtml, setFinalHtml] = useState(fixedHtml);
  const [reason, setReason] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [savedAs, setSavedAs] = useState<Decision | null>(initialDecision);
  const [error, setError] = useState("");

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

  return (
    <form className="panel stack" onSubmit={handleSubmit}>
      <fieldset>
        <legend>What did you do with this fix?</legend>
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
      </fieldset>

      {decision === "edited" && (
        <div className="field">
          <label htmlFor="final-html">Your final HTML</label>
          <textarea
            id="final-html"
            rows={5}
            value={finalHtml}
            onChange={(event) => setFinalHtml(event.target.value)}
          />
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
    </form>
  );
}

export default DecisionForm;
