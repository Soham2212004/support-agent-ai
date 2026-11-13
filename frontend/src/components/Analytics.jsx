import { useCallback, useEffect, useState } from "react";
import { api, getToken } from "../api.js";

function DownvotedRow({ row }) {
  const [status, setStatus] = useState(row.note_status);
  const [note, setNote] = useState(row.note);
  const [draft, setDraft] = useState(row.note);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);

  async function save(newStatus, newNote) {
    setBusy(true);
    try {
      await api.saveDownvoteNote({
        key_hash: row.key_hash,
        status: newStatus,
        note: newNote,
        question: row.question,
      });
      setStatus(newStatus);
      setNote(newNote);
      setEditing(false);
    } catch {
      /* leave UI as-is; a retry is just clicking again */
    } finally {
      setBusy(false);
    }
  }

  return (
    <li>
      <div className="analytics-table-row-head">
        <strong>{row.question}</strong>
        <span className="publish-badge">{row.count}×</span>
      </div>
      <p className="upload-help" style={{ marginTop: "0.4rem" }}>{row.answer}</p>
      <p className="upload-help">last rated {new Date(row.last_rated_at).toLocaleString()}</p>

      <div className="downvote-actions">
        <span className={`publish-badge ${status === "resolved" ? "publish-badge-live" : ""}`}>
          {status === "resolved" ? "Resolved" : "Needs attention"}
        </span>
        {status === "open" ? (
          <button
            type="button"
            className="button button-small button-ghost"
            disabled={busy}
            onClick={() => save("resolved", note)}
          >
            Mark resolved
          </button>
        ) : (
          <button
            type="button"
            className="button button-small button-ghost"
            disabled={busy}
            onClick={() => save("open", note)}
          >
            Reopen
          </button>
        )}
        <button
          type="button"
          className="button button-small button-ghost"
          onClick={() => {
            setDraft(note);
            setEditing((e) => !e);
          }}
        >
          {note ? "Edit note" : "Add note"}
        </button>
      </div>

      {editing && (
        <div style={{ marginTop: "0.6rem" }}>
          <textarea
            rows={2}
            maxLength={1000}
            placeholder="e.g. Need to add a section on refund timelines to the doc."
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={() => save(status, draft)}
          />
        </div>
      )}
      {!editing && note && <p className="upload-help" style={{ marginTop: "0.4rem" }}>Note: {note}</p>}
    </li>
  );
}

export default function Analytics() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const result = await api.getAnalytics();
      setData(result);
    } catch (err) {
      setError(err.message || "Could not load analytics.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <section className="settings-card" aria-busy="true">
        <p className="page-lede">Loading analytics…</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="settings-card">
        <p className="form-error" role="alert">{error}</p>
        <button className="button" type="button" onClick={load}>Try again</button>
      </section>
    );
  }

  async function exportCsv(e) {
    e.preventDefault();
    try {
      const response = await fetch("/api/analytics/export.csv", {
        headers: { Authorization: "Bearer " + getToken() },
      });
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "conversations.csv";
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Could not export CSV.");
    }
  }

  return (
    <section className="settings-card" aria-labelledby="analytics-title">
      <div className="settings-head">
        <div>
          <h2 id="analytics-title">Analytics</h2>
          <p className="upload-help">Last {data.window_days} days, across your test chat and published bot.</p>
        </div>
        <a className="button button-small button-ghost" href={`${api.exportAnalyticsCsvUrl()}?auth=1`} onClick={exportCsv}>
          Export CSV
        </a>
      </div>

      <div className="analytics-grid">
        <div className="analytics-stat">
          <span className="analytics-stat-value">{data.total_messages}</span>
          <span className="analytics-stat-label">Visitor messages</span>
        </div>
        <div className="analytics-stat">
          <span className="analytics-stat-value">{data.fallback_rate}%</span>
          <span className="analytics-stat-label">Fallback rate</span>
        </div>
        <div className="analytics-stat">
          <span className="analytics-stat-value">{data.upvote_count}</span>
          <span className="analytics-stat-label">👍 Helpful ratings</span>
        </div>
        <div className="analytics-stat">
          <span className="analytics-stat-value">{data.downvote_count}</span>
          <span className="analytics-stat-label">👎 Unhelpful ratings</span>
        </div>
        <div className="analytics-stat">
          <span className="analytics-stat-value">{data.avg_tokens_in}</span>
          <span className="analytics-stat-label">Avg tokens in (test chat)</span>
        </div>
        <div className="analytics-stat">
          <span className="analytics-stat-value">{data.avg_tokens_out}</span>
          <span className="analytics-stat-label">Avg tokens out (test chat)</span>
        </div>
      </div>

      <h3>Top unanswered questions</h3>
      {data.top_unanswered.length === 0 ? (
        <p className="upload-help">No unanswered questions in this window. Nice.</p>
      ) : (
        <ul className="analytics-table">
          {data.top_unanswered.map((row, i) => (
            <li key={i}>
              <div className="analytics-table-row-head">
                <strong>{row.question}</strong>
                <span className="publish-badge">{row.count}×</span>
              </div>
              <p className="upload-help">
                {row.reason_label} · last asked {new Date(row.last_asked_at).toLocaleString()}
              </p>
            </li>
          ))}
        </ul>
      )}

      <h3>Answers visitors rated 👎</h3>
      <p className="upload-help">
        Unlike the list above, these are answers the bot gave confidently — visitors just didn't find them helpful.
      </p>
      {data.top_downvoted.length === 0 ? (
        <p className="upload-help">No downvoted answers in this window.</p>
      ) : (
        <ul className="analytics-table">
          {data.top_downvoted.map((row) => (
            <DownvotedRow key={row.key_hash} row={row} />
          ))}
        </ul>
      )}
    </section>
  );
}