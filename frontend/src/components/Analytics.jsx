import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";

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

  return (
    <section className="settings-card" aria-labelledby="analytics-title">
      <div className="settings-head">
        <div>
          <h2 id="analytics-title">Analytics</h2>
          <p className="upload-help">Last {data.window_days} days, across your test chat and published bot.</p>
        </div>
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
    </section>
  );
}