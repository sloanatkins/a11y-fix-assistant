import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listScans } from "../api";
import type { ScanSummary } from "../api";

const DESCRIPTIONS: Record<string, string> = {
  bakery: "Unnamed image links, faint prices, an icon button with no name, and no page language.",
  library: "Unlabeled search filters, plus one pagination mistake flagged five times.",
  clinic: "An appointment form with unlabeled fields and a map frame with no title.",
};

function DemoExamples() {
  const [sites, setSites] = useState<ScanSummary[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    listScans()
      .then((data) => {
        if (!cancelled) setSites(data);
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
      <h1 className="hero-title">Find it. Fix it. Check it.</h1>
      <p className="lede">
        This tool scans a page for accessibility problems, drafts an HTML fix, and tests that fix
        before a person decides what to do with it. Choose an example to see saved results.
      </p>

      {error && (
        <p className="message error" role="alert">
          {error}
        </p>
      )}

      <ul className="examples">
        {sites.map((site) => (
          <li key={site.id}>
            <span className="example-count">{site.flagged}</span>
            <span className="example-text">
              <Link to={`/scans/${site.id}`}>{site.url}</Link>
              <span>{DESCRIPTIONS[site.id] ?? ""}</span>
            </span>
          </li>
        ))}
      </ul>

      <section aria-labelledby="how-heading" className="how">
        <h2 id="how-heading">How a review works</h2>
        <ol>
          <li>
            <strong>Scan.</strong> axe, an open-source accessibility checker, tests the page in a
            real browser.
          </li>
          <li>
            <strong>Draft.</strong> For supported issues, an LLM explains the problem and writes a
            fix.
          </li>
          <li>
            <strong>Test.</strong> The fix goes on a temporary copy of the page, then axe checks it
            again.
          </li>
          <li>
            <strong>Decide.</strong> A person uses it, edits it, or rejects it.
          </li>
        </ol>
      </section>
    </>
  );
}

export default DemoExamples;
