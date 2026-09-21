import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { startScan } from "../api";
import DemoExamples from "../components/DemoExamples";
import RecentScans from "../components/RecentScans";
import { isDemoMode } from "../demo";

function NewScanPage() {
  const [url, setUrl] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    // stops the browser from reloading the page
    event.preventDefault();
    setIsSubmitting(true);
    setError("");

    try {
      const scan = await startScan(url);
      navigate(`/scans/${scan.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setIsSubmitting(false);
    }
  }

  if (isDemoMode()) return <DemoExamples />;

  return (
    <>
      <h1 className="hero-title">Scan a public page</h1>
      <p className="lede">
        Find accessibility issues, review suggested HTML fixes, and keep track of what works.
      </p>

      <form className="scan-form" onSubmit={handleSubmit}>
        <label htmlFor="page-url">Page URL</label>
        <div className="scan-input">
          <input
            id="page-url"
            name="url"
            type="url"
            placeholder="https://www.example.com"
            required
            value={url}
            onChange={(event) => setUrl(event.target.value)}
          />
          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Starting scan..." : "Scan page"}
          </button>
        </div>
        {error && (
          <p className="message error" role="alert">
            {error}
          </p>
        )}
      </form>

      <RecentScans />

      <section aria-labelledby="how-heading" className="how">
        <h2 id="how-heading">How a review works</h2>
        <ol>
          <li>
            <strong>Scan.</strong> axe, an open-source accessibility checker, tests the page in a real browser.
          </li>
          <li>
            <strong>Draft.</strong> For supported issues, Groq explains the problem and writes a
            fix.
          </li>
          <li>
            <strong>Test.</strong> The fix goes on a temporary copy of the page, then axe checks it
            again.
          </li>
          <li>
            <strong>Decide.</strong> You use it, edit it, or reject it. Nothing on the site changes.
          </li>
        </ol>
      </section>
    </>
  );
}

export default NewScanPage;
