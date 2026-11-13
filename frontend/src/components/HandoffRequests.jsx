import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";

export default function HandoffRequests({ onCountChange }) {
  const [handoffs, setHandoffs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setError("");
    try {
      const data = await api.getHandoffs();
      setHandoffs(data.handoffs);
      onCountChange?.(data.open_count);
    } catch (err) {
      setError(err.message || "Could not load handoff requests.");
    } finally {
      setLoading(false);
    }
  }, [onCountChange]);

  useEffect(() => {
    load();
  }, [load]);

  async function resolve(id) {
    setBusyId(id);
    try {
      await api.resolveHandoff(id);
      await load();
    } catch (err) {
      setError(err.message || "Could not mark this resolved.");
    } finally {
      setBusyId(null);
    }
  }

  if (loading) {
    return (
      <section className="settings-card" aria-busy="true">
        <p className="page-lede">Loading handoff requests…</p>
      </section>
    );
  }

  return (
    <section className="settings-card" aria-labelledby="handoffs-title">
      <div className="settings-head">
        <div>
          <h2 id="handoffs-title">Handoff requests</h2>
          <p className="upload-help">Visitors who asked for a human after the bot couldn't help.</p>
        </div>
      </div>

      {error && <p className="form-error" role="alert">{error}</p>}

      {handoffs.length === 0 ? (
        <p className="upload-help">No handoff requests yet.</p>
      ) : (
        <ul className="publish-version-list">
          {handoffs.map((h) => (
            <li key={h.id}>
              <div>
                <strong>{h.visitor_name}</strong>
                {h.status === "open" ? (
                  <span className="publish-badge" style={{ borderColor: "#f5a524", background: "#fdeccb" }}>
                    Open
                  </span>
                ) : (
                  <span className="publish-badge publish-badge-live">Resolved</span>
                )}
                <p>{h.visitor_email}</p>
                {h.reason && <p>"{h.reason}"</p>}
                <p className="upload-help">{new Date(h.created_at).toLocaleString()}</p>
              </div>
              {h.status === "open" && (
                <button
                  type="button"
                  className="button button-ghost button-small"
                  disabled={busyId === h.id}
                  onClick={() => resolve(h.id)}
                >
                  {busyId === h.id ? "Saving…" : "Mark resolved"}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}