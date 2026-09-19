import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listScans } from "../api";
import type { ScanSummary } from "../api";

// SQLite saves times in UTC without saying so, so we add that before parsing
function formatDate(createdAt: string) {
  return new Date(`${createdAt.replace(" ", "T")}Z`).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function describeResult(scan: ScanSummary) {
  if (scan.status === "running") return "Still scanning";
  if (scan.status === "failed") return "Scan failed";
  return `${scan.flagged} flagged`;
}

function RecentScans() {
  const [scans, setScans] = useState<ScanSummary[]>([]);

  useEffect(() => {
    let cancelled = false;
    listScans()
      .then((data) => {
        if (!cancelled) setScans(data);
      })
      .catch(() => {
        // the scan form already explains if the server is down
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (scans.length === 0) return null;

  return (
    <section className="recent" aria-labelledby="recent-heading">
      <h2 id="recent-heading">Recent scans</h2>
      <ul>
        {scans.map((scan) => (
          <li key={scan.id}>
            <Link to={`/scans/${scan.id}`}>{scan.url}</Link>
            <span className="recent-result">{describeResult(scan)}</span>
            <span className="recent-date">{formatDate(scan.created_at)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default RecentScans;
