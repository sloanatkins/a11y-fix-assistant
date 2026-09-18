import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { startScan } from "../api";

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

  return (
    <>
      <h1>Scan a public page</h1>
      <p className="lede">
        Find accessibility issues, review suggested HTML fixes, and keep track of what works.
      </p>

      <form className="panel stack" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="page-url">Page URL</label>
          <input
            id="page-url"
            name="url"
            type="url"
            placeholder="https://www.example.com"
            required
            value={url}
            onChange={(event) => setUrl(event.target.value)}
          />
        </div>
        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Starting scan..." : "Scan page"}
        </button>
        {error && (
          <p className="message error" role="alert">
            {error}
          </p>
        )}
      </form>

      <p className="note">
        A clean scan doesn&apos;t mean a page is fully accessible. Automated tools miss problems
        that need a person to judge.
      </p>
    </>
  );
}

export default NewScanPage;
