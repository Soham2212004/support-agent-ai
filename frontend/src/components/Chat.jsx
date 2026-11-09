import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, clearToken } from "../api.js";
import { getChatState, sendChatMessage } from "../chatApi.js";

export default function Chat({ settingsRevision = 0 }) {
  const [info, setInfo] = useState(null);
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [provider, setProvider] = useState("");
  const [usage, setUsage] = useState({ used: 0, limit: 0 });
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const logRef = useRef(null);
  const abortRef = useRef(null);
  const initialised = useRef(false);

  const load = useCallback(async () => {
    try {
      const data = await getChatState();
      setInfo(data);
      setUsage(data.usage);
      if (!initialised.current) {
        initialised.current = true;
        setMessages(data.messages.map((m) => ({ ...m, key: `m${m.id}` })));
        setConversationId(data.conversation_id);
        setProvider(data.default_provider);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken();
        window.location.assign("/login");
        return;
      }
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    return () => abortRef.current?.abort();
  }, [load]);

  // Refresh settings when changed from BotSettings tab
  useEffect(() => {
    if (initialised.current && settingsRevision > 0) {
      load();
    }
  }, [settingsRevision, load]);

  // until the document is ready for search, check again every 4 seconds
  useEffect(() => {
    if (!info || info.document_ready) return undefined;
    const timer = setInterval(load, 4000);
    return () => clearInterval(timer);
  }, [info, load]);

  // keep the newest message in view
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [messages]);

  async function send(e) {
    e.preventDefault();
    const content = input.trim();
    if (!content || sending) return;

    setError("");
    setInput("");
    setSending(true);

    const stamp = Date.now();
    const userKey = `u${stamp}`;
    const botKey = `a${stamp}`;
    setMessages((list) => [
      ...list,
      { key: userKey, role: "user", content },
      { key: botKey, role: "assistant", content: "", citations: [], pending: true },
    ]);
    const patchBot = (patch) =>
      setMessages((list) => list.map((m) => (m.key === botKey ? { ...m, ...patch } : m)));
    const dropEmptyBot = () => setMessages((list) => list.filter((m) => !(m.key === botKey && !m.content)));

    const controller = new AbortController();
    abortRef.current = controller;
    let streamed = "";

    try {
      await sendChatMessage(
        { content, conversationId, provider },
        {
          meta: (d) => setConversationId(d.conversation_id),
          token: (d) => {
            streamed += d.text;
            patchBot({ content: streamed });
          },
          done: (d) => {
            patchBot({ content: d.text, citations: d.citations, is_fallback: d.is_fallback, pending: false });
            setUsage(d.usage);
          },
          error: (d) => {
            setError(d.message);
            patchBot({ pending: false });
            dropEmptyBot();
          },
        },
        controller.signal
      );
    } catch (err) {
      if (err.name !== "AbortError") {
        // the message was not accepted by the server: take it back out and restore the text
        setMessages((list) => list.filter((m) => m.key !== userKey && m.key !== botKey));
        setInput(content);
        setError(err.message);
        if (err.status === 409) load();
      }
    } finally {
      setSending(false);
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(e);
    }
  }

  function newConversation() {
    abortRef.current?.abort();
    setMessages([]);
    setConversationId(null);
    setError("");
  }

  if (loading) return <p className="page-lede">Loading chat...</p>;

  const limitReached = usage.limit > 0 && usage.used >= usage.limit;

  const botName = info?.bot_settings?.name || "Assistant";
  const greeting = info?.bot_settings?.greeting;

  return (
    <section className="chat-card" aria-labelledby="chat-title">
      <div className="chat-head">
        <div>
          <h2 id="chat-title">Chat with {botName}</h2>
          <p className="upload-help">
            Ask a question and the answer comes directly from your document, guided by your bot settings.
          </p>
        </div>
        {info?.document_ready && (
          <div className="chat-controls">
            <label htmlFor="chat-model">Model</label>
            <select id="chat-model" value={provider} onChange={(e) => setProvider(e.target.value)} disabled={sending}>
              {info.providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.id === "fake" ? p.label : `${p.label} - ${p.model}`}
                </option>
              ))}
            </select>
            <button type="button" className="button button-ghost button-small" onClick={newConversation} disabled={sending}>
              New conversation
            </button>
          </div>
        )}
      </div>

      {!info?.document_ready ? (
        <p className="index-status index-processing">
          Upload a document above and wait until it says "Ready for search". Then you can chat with it here.
        </p>
      ) : (
        <>
          <div className="chat-log" ref={logRef} role="log" aria-live="polite" aria-label="Conversation">
            {messages.length === 0 && (
              <>
                {greeting && (
                  <div className="chat-msg chat-assistant chat-greeting">
                    <div className="chat-author-label">
                      <strong>{botName}</strong>
                    </div>
                    <p>{greeting}</p>
                  </div>
                )}
                <p className="chat-empty">
                  Try saying "Hello", or ask a question about your uploaded document.
                </p>
              </>
            )}
            {messages.map((m) => (
              <div
                key={m.key}
                className={`chat-msg chat-${m.role}${m.is_fallback ? " chat-fallback" : ""}`}
              >
                {m.role === "assistant" && (
                  <div className="chat-author-label">
                    <strong>{botName}</strong>
                  </div>
                )}
                <p>{m.content || (m.pending ? "Thinking..." : "")}</p>
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

          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}

          <form className="chat-form" onSubmit={send}>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              rows={2}
              maxLength={1000}
              placeholder={limitReached ? "Daily limit reached. Try again tomorrow." : "Type your question..."}
              aria-label="Your question"
              disabled={sending || limitReached}
            />
            <button className="button" type="submit" disabled={sending || limitReached || !input.trim()}>
              {sending ? "Answering..." : "Send"}
            </button>
          </form>
          <p className="upload-help chat-usage">
            {usage.used} of {usage.limit} test messages used today
          </p>
        </>
      )}

      {!info?.document_ready && error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
