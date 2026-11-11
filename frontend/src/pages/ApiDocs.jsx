import { Link } from "react-router-dom";

function CopyButton({ value }) {
  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      window.prompt("Copy this example:", value);
    }
  }

  return <button className="button button-small button-ghost" type="button" onClick={copy}>Copy</button>;
}

function CodeExample({ children }) {
  const value = String(children).trim();
  return (
    <div className="code-example">
      <CopyButton value={value} />
      <pre><code>{value}</code></pre>
    </div>
  );
}

export default function ApiDocs() {
  return (
    <main className="page api-docs">
      <p className="eyebrow">PUBLISHING</p>
      <h1>Public Chat API</h1>
      <p className="page-lede">
        Publish a bot, allow your website origin, and keep your API key on your own server. Your server exchanges
        that key for a short-lived visitor token; the browser uses the token to stream answers.
      </p>

      <section className="doc-section">
        <h2>1. Create a visitor token on your server</h2>
        <p>Collect the visitor’s name and email before their first message. Do not send your client API key to the browser.</p>
        <CodeExample>{`curl -X POST https://YOUR_API_HOST/api/public/token/ \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: YOUR_SECRET_API_KEY" \\
  -d '{
    "origin": "https://www.example.com",
    "name": "Alex Visitor",
    "email": "alex@example.com"
  }'`}</CodeExample>
        <p>The response contains a visitor token that expires in 15 minutes. Return it to the browser over your own authenticated HTTPS endpoint.</p>
        <CodeExample>{`{
  "visitor_token": "SIGNED_SHORT_LIVED_TOKEN",
  "expires_at": "2026-11-11T09:00:00+00:00",
  "bot": { "name": "Example Assistant", "greeting": "Hello!", "version": 1 }
}`}</CodeExample>
      </section>

      <section className="doc-section">
        <h2>2. Stream a visitor message</h2>
        <p>The public chat endpoint streams Server-Sent Events. Text arrives as <code>token</code> events; the final <code>done</code> event includes source citations.</p>
        <CodeExample>{`const response = await fetch("https://YOUR_API_HOST/api/public/chat/", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": \`Bearer \${visitorToken}\`
  },
  body: JSON.stringify({ content: "What are your opening hours?" })
});

if (!response.ok) throw new Error(await response.text());
const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = "";

while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  let boundary;
  while ((boundary = buffer.indexOf("\\n\\n")) !== -1) {
    const block = buffer.slice(0, boundary);
    buffer = buffer.slice(boundary + 2);
    const event = block.match(/^event: (.+)$/m)?.[1];
    const payload = JSON.parse(block.match(/^data: (.+)$/m)?.[1] || "{}");
    if (event === "token") renderText(payload.text);
    if (event === "done") renderSources(payload.citations);
    if (event === "error") showError(payload.message);
  }
}`}</CodeExample>
      </section>

      <section className="doc-section">
        <h2>Limits and security</h2>
        <ul className="doc-bullets">
          <li>1,000 visitor messages per client per calendar month.</li>
          <li>10 visitor-token requests per API key per minute; 10 chat messages per visitor token per minute.</li>
          <li>Visitor tokens expire after 15 minutes and are restricted to the website origin used to create them.</li>
          <li>Allowed origins are exact scheme/host/port matches. Browser chat requests must come from an allowlisted origin.</li>
          <li>Replacing an API key gives the previous key a 24-hour grace period. Revoking keys disables them immediately.</li>
          <li>Visitor transcripts, including name and email, are retained for 90 days.</li>
          <li>Published versions are immutable. Restoring a version changes the draft; publish again to make it live.</li>
        </ul>
      </section>
      <p className="doc-back"><Link to="/dashboard">Back to dashboard</Link> · <Link to="/demo">Try the sample chat</Link></p>
    </main>
  );
}
