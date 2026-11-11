import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";

export default function Publishing() {
  const [publication, setPublication] = useState(null);
  const [key, setKey] = useState(null);
  const [websites, setWebsites] = useState([]);
  const [origin, setOrigin] = useState("");
  const [oneTimeSecret, setOneTimeSecret] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [publicationData, keyData, websitesData] = await Promise.all([
        api.getPublication(),
        api.getApiKey(),
        api.getAllowedWebsites(),
      ]);
      setPublication(publicationData);
      setKey(keyData.key);
      setWebsites(websitesData.websites);
    } catch (err) {
      setError(err.message || "Could not load publishing settings.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function run(action, successMessage) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      setNotice(successMessage);
      await load();
    } catch (err) {
      setError(err.message || "The request could not be completed.");
    } finally {
      setBusy(false);
    }
  }

  async function rotateKey() {
    if (key?.configured && !window.confirm("Replace the current API key? The old key will work for 24 hours.")) {
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api.rotateApiKey();
      setOneTimeSecret(result.secret);
      setNotice("New key created. Copy it now; it will not be displayed again.");
      await load();
    } catch (err) {
      setError(err.message || "Could not create an API key.");
    } finally {
      setBusy(false);
    }
  }

  async function revokeKeys() {
    if (!window.confirm("Revoke every API key now? Connected websites will stop working immediately.")) return;
    setOneTimeSecret("");
    await run(api.revokeApiKeys, "All API keys were revoked.");
  }

  async function addWebsite(event) {
    event.preventDefault();
    const value = origin.trim();
    if (!value) return;
    await run(() => api.addAllowedWebsite(value), "Website origin added.");
    setOrigin("");
  }

  async function removeWebsite(value) {
    await run(() => api.removeAllowedWebsite(value), "Website origin removed.");
  }

  async function restore(version) {
    if (
      !window.confirm(
        `Restore version ${version.version} as your draft? This replaces the current document and settings. It will not go live until you publish.`,
      )
    ) {
      return;
    }
    await run(() => api.restoreVersion(version.id), `Version ${version.version} restored as a draft.`);
  }

  async function copySecret() {
    try {
      await navigator.clipboard.writeText(oneTimeSecret);
      setNotice("API key copied to clipboard.");
    } catch {
      setError("Clipboard access failed. Select and copy the key manually.");
    }
  }

  if (loading) {
    return (
      <section className="settings-card" aria-busy="true">
        <p className="page-lede">Loading publishing settings…</p>
      </section>
    );
  }

  return (
    <section className="settings-card publishing-card" aria-labelledby="publishing-title">
      <div className="settings-head">
        <div>
          <h2 id="publishing-title">Publish and connect your chatbot</h2>
          <p className="upload-help">
            Publishing freezes the current settings and indexed document. Draft edits do not affect your live bot
            until you publish another version.
          </p>
        </div>
      </div>

      {error && <p className="form-error" role="alert">{error}</p>}
      {notice && <p className="status-notice status-notice-success" role="status">{notice}</p>}

      <div className="publish-section">
        <div className="publish-section-heading">
          <div>
            <h3>Live version</h3>
            {publication?.published ? (
              <p>
                Version {publication.published.version} · {publication.published.document_name} ·{" "}
                {new Date(publication.published.published_at).toLocaleString()}
              </p>
            ) : (
              <p>No chatbot is currently published.</p>
            )}
          </div>
          <span className={`publish-badge ${publication?.published ? "publish-badge-live" : ""}`}>
            {publication?.published ? "Live" : "Unpublished"}
          </span>
        </div>
        <p className="upload-help">
          Monthly public messages: {publication?.usage.used ?? 0} / {publication?.usage.limit ?? 1000}
        </p>
        <div className="doc-actions">
          <button
            className="button"
            type="button"
            disabled={busy || !publication?.document_ready}
            onClick={() => run(api.publishBot, "A new chatbot version is live.")}
          >
            {busy ? "Working…" : publication?.published ? "Publish new version" : "Publish chatbot"}
          </button>
          {publication?.published && (
            <button
              className="button button-ghost"
              type="button"
              disabled={busy}
              onClick={() => run(api.unpublishBot, "The chatbot is now unpublished.")}
            >
              Unpublish
            </button>
          )}
        </div>
        {!publication?.document_ready && (
          <p className="field-hint">Upload a document and wait for indexing to finish before publishing.</p>
        )}
      </div>

      <div className="publish-section">
        <h3>Version history</h3>
        {publication?.versions.length ? (
          <ul className="publish-version-list">
            {publication.versions.map((version) => (
              <li key={version.id}>
                <div>
                  <strong>Version {version.version}</strong>
                  {version.is_published && <span className="publish-badge publish-badge-live">Live</span>}
                  <p>{version.document_name} · {new Date(version.published_at).toLocaleString()}</p>
                </div>
                <button
                  type="button"
                  className="button button-ghost button-small"
                  disabled={busy}
                  onClick={() => restore(version)}
                >
                  Restore as draft
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="upload-help">Your published versions will appear here.</p>
        )}
      </div>

      <div className="publish-section">
        <h3>Secret API key</h3>
        <p className="upload-help">
          Keep this key on your server only. A replacement keeps the old key working for 24 hours; revoking disables
          all keys immediately.
        </p>
        {key?.configured ? (
          <p className="key-status">
            Active key: <code>{key.prefix}…</code>
            {key.previous_expires_at && (
              <span> · Previous key expires {new Date(key.previous_expires_at).toLocaleString()}</span>
            )}
          </p>
        ) : (
          <p className="key-status">No active API key.</p>
        )}
        {oneTimeSecret && (
          <div className="one-time-key" role="alert">
            <strong>Copy this key now. It cannot be shown again.</strong>
            <code>{oneTimeSecret}</code>
            <button type="button" className="button button-small" onClick={copySecret}>Copy key</button>
          </div>
        )}
        <div className="doc-actions">
          <button type="button" className="button" disabled={busy} onClick={rotateKey}>
            {key?.configured ? "Replace API key" : "Create API key"}
          </button>
          {key?.configured && (
            <button type="button" className="button button-ghost" disabled={busy} onClick={revokeKeys}>
              Revoke all keys
            </button>
          )}
        </div>
      </div>

      <div className="publish-section">
        <h3>Allowed websites</h3>
        <p className="upload-help">
          Add exact website origins (scheme, hostname, and optional port; no paths or wildcards).
        </p>
        <form className="search-form" onSubmit={addWebsite}>
          <input
            type="url"
            value={origin}
            onChange={(event) => setOrigin(event.target.value)}
            placeholder="https://www.example.com"
            aria-label="Website origin"
            required
          />
          <button type="submit" className="button" disabled={busy}>Allow website</button>
        </form>
        {websites.length > 0 ? (
          <ul className="publish-site-list">
            {websites.map((site) => (
              <li key={site.id}>
                <code>{site.origin}</code>
                <button
                  type="button"
                  className="link-button"
                  disabled={busy}
                  onClick={() => removeWebsite(site.origin)}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="field-hint">No website origins have been added.</p>
        )}
      </div>

      <div className="publish-links">
        <Link to="/api-docs">API documentation</Link>
        <Link to="/demo">Try the sample chat</Link>
      </div>
    </section>
  );
}
