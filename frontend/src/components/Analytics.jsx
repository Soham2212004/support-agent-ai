import { useCallback, useEffect, useState } from "react";
import { api, getToken } from "../api.js";

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
          {data.top_downvoted.map((row, i) => (
            <li key={i}>
              <div className="analytics-table-row-head">
                <strong>{row.question}</strong>
                <span className="publish-badge">{row.count}×</span>
              </div>
              <p className="upload-help" style={{ marginTop: "0.4rem" }}>{row.answer}</p>
              <p className="upload-help">last rated {new Date(row.last_rated_at).toLocaleString()}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}