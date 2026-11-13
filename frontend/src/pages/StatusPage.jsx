import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function StatusPage() {
  const [entries, setEntries] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getChangelog()
      .then((data) => setEntries(data.entries))
      .catch((err) => setError(err.message || "Could not load the changelog."));
  }, []);

  return (
    <main className="page">
      <p className="eyebrow">STATUS</p>
      <h1>System status &amp; changelog</h1>

      <div className="status-banner" role="status">
        <span className="status-dot" aria-hidden="true" />
        All systems operational
      </div>

      <h2 style={{ marginTop: "2.5rem", fontSize: "1.3rem" }}>What's new</h2>

      {error && <p className="form-error" role="alert">{error}</p>}

      {entries === null && !error && <p className="page-lede">Loading…</p>}

      {entries?.length === 0 && <p className="page-lede">No updates yet — check back soon.</p>}

      {entries?.length > 0 && (
        <ul className="changelog-list">
          {entries.map((entry, i) => (
            <li key={i}>
              <div className="changelog-date">{new Date(entry.published_at).toLocaleDateString()}</div>
              <h3>{entry.title}</h3>
              <p>{entry.body}</p>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}