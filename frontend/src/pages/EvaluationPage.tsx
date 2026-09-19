import { useEffect, useState } from "react";
import { getEvaluation } from "../api";
import type { Evaluation } from "../api";

function EvaluationPage() {
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    getEvaluation()
      .then((data) => {
        if (!cancelled) setEvaluation(data);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <h1>Evaluation</h1>
      <p className="lede">How the suggested fixes hold up, by rule.</p>

      {error && (
        <p className="message error" role="alert">
          {error}
        </p>
      )}
      {!evaluation && !error && <p role="status">Loading results.</p>}

      {evaluation && (
        <>
          <dl className="stats">
            <div>
              <dt>Scans</dt>
              <dd>{evaluation.scans}</dd>
            </div>
            <div>
              <dt>Suggestions</dt>
              <dd>{evaluation.suggestions}</dd>
            </div>
            <div>
              <dt>Decisions</dt>
              <dd>{evaluation.decisions}</dd>
            </div>
          </dl>

          {evaluation.rules.length === 0 ? (
            <p className="empty">No suggestions yet. Scan a page and get a fix to start filling this in.</p>
          ) : (
            <div className="table-wrap" tabIndex={0} role="region" aria-label="Results by rule">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Rule</th>
                    <th scope="col">Suggestions</th>
                    <th scope="col">Passed axe</th>
                    <th scope="col">Needs input</th>
                    <th scope="col">Failed or not tested</th>
                    <th scope="col">Used</th>
                    <th scope="col">Edited</th>
                    <th scope="col">Rejected</th>
                    <th scope="col">Occurrences</th>
                  </tr>
                </thead>
                <tbody>
                  {evaluation.rules.map((rule) => (
                    <tr key={rule.rule_id}>
                      <th scope="row">{rule.rule_id}</th>
                      <td>{rule.suggestions}</td>
                      <td>{rule.verdicts.passed ?? 0}</td>
                      <td>{rule.verdicts.needs_review ?? 0}</td>
                      <td>{(rule.verdicts.failed ?? 0) + (rule.verdicts.not_applied ?? 0)}</td>
                      <td>{rule.decisions.used ?? 0}</td>
                      <td>{rule.decisions.edited ?? 0}</td>
                      <td>{rule.decisions.rejected ?? 0}</td>
                      <td>{rule.occurrences_in_groups}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="caveat">
            Occurrences count every flagged item in the reviewed groups. They don&apos;t mean those
            items were fixed on a live site.
          </p>
        </>
      )}
    </>
  );
}

export default EvaluationPage;
