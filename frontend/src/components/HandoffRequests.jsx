import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";

const STATUS_LABEL = { waiting: "Waiting", replied: "Replied", resolved: "Resolved", expired: "Expired" };
const STATUS_STYLE = {
  waiting: { borderColor: "#f5a524", background: "#fdeccb", color: "#78350f" },
  replied: { borderColor: "#2b45f5", background: "#e9edff", color: "#1f33c4" },
};

function HandoffThread({ handoffId, onChanged }) {
  const [detail, setDetail] = useState(null);
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const data = await api.getHandoffDetail(handoffId);
      setDetail(data);
    } catch (err) {
      setError(err.message || "Could not load this conversation.");
    }
  }, [handoffId]);

  useEffect(() => {
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [load]);

  async function send(e) {
    e.preventDefault();
    const content = reply.trim();
    if (!content) return;
    setBusy(true);
    setError("");
    try {
      await api.replyHandoff(handoffId, content);
      setReply("");
      await load();
      onChanged?.();
    } catch (err) {
      setError(err.message || "Could not send your reply.");
    } finally {
      setBusy(false);
    }
  }

  async function resolve() {
    setBusy(true);
    try {
      await api.resolveHandoff(handoffId);
      await load();
      onChanged?.();
    } catch (err) {
      setError(err.message || "Could not mark this resolved.");
    } finally {
      setBusy(false);
    }
  }

  if (!detail) return <p className="upload-help">Loading conversation…</p>;

  const open = detail.handoff.status === "waiting" || detail.handoff.status === "replied";

  return (
    <div className="handoff-thread">
      <div className="chat-log" style={{ height: "16rem" }}>
        {detail.messages.map((m) => (
          <div key={m.seq} className={`chat-msg chat-${m.role === "user" ? "user" : "assistant"}`}>
            <div className="chat-author-label">
              <strong>
                {m.role === "user" ? detail.handoff.visitor_name : m.role === "human" ? "You" : "System"}
              </strong>
            </div>
            <p>{m.content}</p>
          </div>
        ))}
      </div>

      {error && <p className="form-error" role="alert">{error}</p>}

      {open && (
        <form className="chat-form" onSubmit={send} style={{ marginTop: "0.75rem" }}>
          <textarea
            rows={2}
            maxLength={1000}
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            placeholder="Reply to the visitor…"
            disabled={busy}
          />
          <button className="button" type="submit" disabled={busy || !reply.trim()}>
            Send
          </button>
        </form>
      )}

      {open && (
        <button type="button" className="button button-ghost button-small" style={{ marginTop: "0.6rem" }} onClick={resolve} disabled={busy}>
          Mark resolved
        </button>
      )}
    </div>
  );
}

export default function HandoffRequests({ onCountChange }) {
  const [handoffs, setHandoffs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState(null);

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
          <p className="upload-help">
            Visitors who asked for a human. Reply within 10 minutes to avoid a reminder; after 30 minutes unreplied
            the bot resumes automatically.
          </p>
        </div>
      </div>

      {error && <p className="form-error" role="alert">{error}</p>}

      {handoffs.length === 0 ? (
        <p className="upload-help">No handoff requests yet.</p>
      ) : (
        <ul className="publish-version-list">
          {handoffs.map((h) => (
            <li key={h.id} style={{ display: "block" }}>
              <div
                style={{ display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer" }}
                onClick={() => setOpenId(openId === h.id ? null : h.id)}
              >
                <div>
                  <strong>{h.visitor_name}</strong>
                  <span className="publish-badge" style={STATUS_STYLE[h.status]}>
                    {STATUS_LABEL[h.status] || h.status}
                  </span>
                  <p>{h.visitor_email}</p>
                  {h.reason && <p>"{h.reason}"</p>}
                  <p className="upload-help">{new Date(h.created_at).toLocaleString()}</p>
                </div>
                <span className="link-button">{openId === h.id ? "Hide" : "Open"}</span>
              </div>
              {openId === h.id && <HandoffThread handoffId={h.id} onChanged={load} />}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}