import { useState } from "react";
import { Link } from "react-router-dom";

async function responseData(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.message || "The request failed.");
  return data;
}

export default function PublicChatDemo() {
  const [apiKey, setApiKey] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [visitorToken, setVisitorToken] = useState("");
  const [bot, setBot] = useState(null);
  const [messages, setMessages] = useState([]);
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [usage, setUsage] = useState(null);

  async function connect(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = await responseData(
        await fetch("/api/public/token/", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-API-Key": apiKey.trim() },
          body: JSON.stringify({ origin: window.location.origin, name: name.trim(), email: email.trim() }),
        }),
      );
      setVisitorToken(data.visitor_token);
      setBot(data.bot);
      setMessages([{ role: "assistant", content: data.bot.greeting, citations: [] }]);
    } catch (err) {
      setError(err.message || "Could not start the sample chat.");
    } finally {
      setBusy(false);
    }
  }

  async function send(event) {
    event.preventDefault();
    const question = content.trim();
    if (!question || !visitorToken || busy) return;
    setBusy(true);
    setError("");
    setContent("");

    try {
      const response = await fetch("/api/public/chat/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + visitorToken,
        },
        body: JSON.stringify({ content: question }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.message || "The message could not be sent.");
      }

      setMessages((current) => [...current, { role: "user", content: question }, { role: "assistant", content: "", citations: [] }]);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      function consume(block) {
        let event = "message";
        let payloadText = "";
        for (const line of block.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) payloadText += line.slice(5).trim();
        }
        if (!payloadText) return;
        const payload = JSON.parse(payloadText);
        if (event === "token") {
          setMessages((current) => {
            const next = [...current];
            const last = next[next.length - 1];
            next[next.length - 1] = { ...last, content: last.content + payload.text };
            return next;
          });
        } else if (event === "done") {
          setUsage(payload.usage);
          setMessages((current) => {
            const next = [...current];
            next[next.length - 1] = {
              ...next[next.length - 1],
              content: payload.text,
              citations: payload.citations,
            };
            return next;
          });
        } else if (event === "error") {
          setError(payload.message);
        }
      }

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let boundary;
        while ((boundary = buffer.indexOf("\n\n")) !== -1) {
          consume(buffer.slice(0, boundary));
          buffer = buffer.slice(boundary + 2);
        }
      }
    } catch (err) {
      setError(err.message || "The chat request failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page public-demo">
      <p className="eyebrow">PUBLIC CHAT</p>
      <h1>Test your published bot</h1>
      <p className="page-lede">
        This playground calls the same token and streaming endpoints that your website uses. Add{" "}
        <code>{typeof window === "undefined" ? "" : window.location.origin}</code> to Allowed websites first.
      </p>

      {!visitorToken ? (
        <form className="form settings-card" onSubmit={connect}>
          <div className="demo-warning">
            Test only: the API key is sent from this browser. Never expose a production API key in a public
            website; exchange it for visitor tokens on your server instead.
          </div>
          <div className="field">
            <label htmlFor="demo-api-key">Client API key</label>
            <input id="demo-api-key" type="password" autoComplete="off" value={apiKey} onChange={(event) => setApiKey(event.target.value)} required />
          </div>
          <div className="field-row">
            <div className="field">
              <label htmlFor="visitor-name">Your name</label>
              <input id="visitor-name" value={name} onChange={(event) => setName(event.target.value)} maxLength={150} required />
            </div>
            <div className="field">
              <label htmlFor="visitor-email">Your email</label>
              <input id="visitor-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
            </div>
          </div>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button type="submit" className="button" disabled={busy}>
            {busy ? "Connecting…" : "Start chat"}
          </button>
        </form>
      ) : (
        <section className="settings-card demo-chat" aria-label="Public chat playground">
          <div className="publish-section-heading">
            <div>
              <h2>{bot?.name}</h2>
              <p>Published version {bot?.version} · visitor token expires in 15 minutes</p>
            </div>
            <button type="button" className="button button-ghost button-small" disabled={busy} onClick={() => setVisitorToken("")}>
              Reconnect
            </button>
          </div>
          <ol className="demo-messages" aria-live="polite">
            {messages.map((message, index) => (
              <li key={`${index}-${message.role}`} className={`demo-message demo-message-${message.role}`}>
                <strong>{message.role === "user" ? name || "You" : bot?.name}</strong>
                <p>{message.content || (busy && message.role === "assistant" ? "…" : "")}</p>
                {message.citations?.length > 0 && (
                  <ul className="demo-citations">
                    {message.citations.map((citation) => (
                      <li key={citation.n}>
                        <strong>[{citation.n}] {citation.label}</strong>
                        <span>{citation.text}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ol>
          {error && <p className="form-error" role="alert">{error}</p>}
          <form className="search-form" onSubmit={send}>
            <input value={content} maxLength={1000} onChange={(event) => setContent(event.target.value)} placeholder="Ask a question about the published bot…" aria-label="Message" disabled={busy} />
            <button type="submit" className="button" disabled={busy || !content.trim()}>{busy ? "Replying…" : "Send"}</button>
          </form>
          {usage && <p className="field-hint">Monthly public messages: {usage.used} / {usage.limit}</p>}
        </section>
      )}
      <p className="doc-back"><Link to="/dashboard">Back to dashboard</Link> · <Link to="/api-docs">API docs</Link></p>
    </main>
  );
}
