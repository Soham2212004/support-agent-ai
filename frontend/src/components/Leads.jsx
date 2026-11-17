import { useCallback, useEffect, useState } from "react";
import { api, getToken } from "../api.js";

export default function Leads() {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const data = await api.getLeads();
      setLeads(data.leads);
    } catch (err) {
      setError(err.message || "Could not load leads.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function exportCsv(e) {
    e.preventDefault();
    try {
      const response = await fetch("/api/leads/export.csv", {
        headers: { Authorization: "Bearer " + getToken() },
      });
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "leads.csv";
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Could not export CSV.");
    }
  }

  if (loading) {
    return (
      <section className="settings-card" aria-busy="true">
        <p className="page-lede">Loading leads…</p>
      </section>
    );
  }

  return (
    <section className="settings-card" aria-labelledby="leads-title">
      <div className="settings-head">
        <div>
          <h2 id="leads-title">Leads</h2>
          <p className="upload-help">Every visitor who has started a chat with your published bot.</p>
        </div>
        <a className="button button-small button-ghost" href="/api/leads/export.csv" onClick={exportCsv}>
          Export CSV
        </a>
      </div>

      {error && <p className="form-error" role="alert">{error}</p>}

      {leads.length === 0 ? (
        <p className="upload-help">No leads yet — they'll appear here once visitors start chatting with your published bot.</p>
      ) : (
        <ul className="publish-version-list">
          {leads.map((lead, i) => (
            <li key={i}>
              <div>
                <strong>{lead.name}</strong>
                <span className="publish-badge">{lead.conversation_count} conversation{lead.conversation_count === 1 ? "" : "s"}</span>
                <p>{lead.email}</p>
                <p className="upload-help">
                  First seen {new Date(lead.first_seen_at).toLocaleDateString()} · last seen{" "}
                  {new Date(lead.last_seen_at).toLocaleDateString()}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}