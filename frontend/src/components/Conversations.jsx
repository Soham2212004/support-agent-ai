import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";

const STATUS_LABEL = {
  active: "Active",
  waiting_human: "Waiting for human",
  human_replied: "Human replied",
  closed: "Closed",
};

function ConversationDetail({ id, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getConversationDetail(id)
      .then(setData)
      .catch((err) => setError(err.message || "Could not load this conversation."));
  }, [id]);

  return (
    <div className="conversation-detail-overlay" role="dialog" aria-label="Conversation transcript">
      <div className="conversation-detail-panel">
        <div className="settings-head">
          <h3>{data ? data.conversation.visitor_name : "Loading…"}</h3>
          <button type="button" className="link-button" onClick={onClose}>
            Close
          </button>
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
        {data && (
          <>
            <p className="upload-help">
              {data.conversation.visitor_email} · {STATUS_LABEL[data.conversation.status] || data.conversation.status}
            </p>
            <div className="chat-log" style={{ height: "22rem", marginTop: "1rem" }}>
              {data.messages.map((m) => (
                <div
                  key={m.seq}
                  className={`chat-msg ${m.role === "user" ? "chat-user" : "chat-assistant"}${
                    m.is_fallback ? " chat-fallback" : ""
                  }`}
                >
                  {m.role !== "user" && (
                    <div className="chat-author-label">
                      <strong>{m.role === "human" ? "Human (you)" : m.role === "system" ? "System" : "Bot"}</strong>
                    </div>
                  )}
                  <p>{m.content}</p>
                  {m.feedback !== "none" && (
                    <span style={{ fontSize: "0.8rem" }}>{m.feedback === "up" ? "👍" : "👎"}</span>
                  )}
                  {m.citations?.length > 0 && (
                    <ul className="chat-sources" aria-label="Sources">
                      {m.citations.map((c) => (
                        <li key={c.n}>
                          <details>
                            <summary>
                              [{c.n}] {c.label}
                            </summary>
                            <p>{c.text}</p>
                          </details>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function Conversations() {
  const [conversations, setConversations] = useState([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState(null);

  const load = useCallback(async (pageNum, searchTerm) => {
    setLoading(true);
    setError("");
    try {
      const data = await api.getConversations(pageNum, searchTerm);
      setConversations(data.conversations);
      setHasMore(data.has_more);
      setTotal(data.total);
    } catch (err) {
      setError(err.message || "Could not load conversations.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(page, search);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  function submitSearch(e) {
    e.preventDefault();
    setPage(1);
    load(1, search);
  }

  return (
    <section className="settings-card" aria-labelledby="conversations-title">
      <div className="settings-head">
        <div>
          <h2 id="conversations-title">Conversations</h2>
          <p className="upload-help">Every chat your published bot has had with a real visitor. {total} total.</p>
        </div>
      </div>

      <form className="search-form" onSubmit={submitSearch}>
        <input
          type="text"
          placeholder="Search by visitor name or email…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button className="button" type="submit">
          Search
        </button>
      </form>

      {error && <p className="form-error" role="alert">{error}</p>}

      {loading ? (
        <p className="upload-help" style={{ marginTop: "1rem" }}>
          Loading…
        </p>
      ) : conversations.length === 0 ? (
        <p className="upload-help" style={{ marginTop: "1rem" }}>
          No conversations yet — they'll appear here once visitors start chatting with your published bot.
        </p>
      ) : (
        <ul className="publish-version-list" style={{ marginTop: "1rem" }}>
          {conversations.map((c) => (
            <li key={c.id} style={{ cursor: "pointer" }} onClick={() => setOpenId(c.id)}>
              <div>
                <strong>{c.visitor_name}</strong>
                <span className="publish-badge">{STATUS_LABEL[c.status] || c.status}</span>
                <p>{c.visitor_email}</p>
                <p className="upload-help">{c.last_message_preview}</p>
                <p className="upload-help">
                  {c.message_count} message{c.message_count === 1 ? "" : "s"} · last activity{" "}
                  {new Date(c.last_message_at).toLocaleString()}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}

      {(page > 1 || hasMore) && (
        <div className="doc-actions">
          <button
            type="button"
            className="button button-ghost button-small"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Previous
          </button>
          <span className="upload-help">Page {page}</span>
          <button
            type="button"
            className="button button-ghost button-small"
            disabled={!hasMore}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </button>
        </div>
      )}

      {openId && <ConversationDetail id={openId} onClose={() => setOpenId(null)} />}
    </section>
  );
}