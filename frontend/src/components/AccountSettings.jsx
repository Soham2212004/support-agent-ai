import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, clearToken, getToken } from "../api.js";

export default function AccountSettings() {
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [upgradeMessage, setUpgradeMessage] = useState("");
  const [upgradeNotice, setUpgradeNotice] = useState("");
  const [upgradeBusy, setUpgradeBusy] = useState(false);

  async function requestUpgrade(e) {
    e.preventDefault();
    setUpgradeBusy(true);
    setUpgradeNotice("");
    try {
      const res = await api.requestUpgrade("pro", upgradeMessage);
      setUpgradeNotice(res.message);
      setUpgradeMessage("");
    } catch (err) {
      setUpgradeNotice(err.message || "Could not send the request.");
    } finally {
      setUpgradeBusy(false);
    }
  }

  async function exportZip(e) {
    e.preventDefault();
    try {
      const response = await fetch("/api/account/export.zip", {
        headers: { Authorization: "Bearer " + getToken() },
      });
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "account_export.zip";
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Could not export your data.");
    }
  }

  async function deleteAccount(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.deleteAccount(password);
      clearToken();
      navigate("/");
    } catch (err) {
      setError(err.message || "Could not delete your account.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="settings-card" aria-labelledby="account-title">
      <div className="settings-head">
        <div>
          <h2 id="account-title">Your data</h2>
          <p className="upload-help">Export everything, or permanently delete your account and all associated data.</p>
        </div>
      </div>

      {error && <p className="form-error" role="alert">{error}</p>}

      <div className="doc-actions">
        <a className="button button-ghost" href="/api/account/export.zip" onClick={exportZip}>
          Export all my data (.zip)
        </a>
      </div>

      <div className="publish-section">
        <h3>Request an upgrade</h3>
        <p className="upload-help">Need a higher message limit? Send a request — we'll follow up by email.</p>
        <form className="form" onSubmit={requestUpgrade} style={{ marginTop: "1rem" }}>
          <div className="field">
            <label htmlFor="upgrade-message">Message (optional)</label>
            <textarea
              id="upgrade-message"
              rows={2}
              maxLength={1000}
              value={upgradeMessage}
              onChange={(e) => setUpgradeMessage(e.target.value)}
              disabled={upgradeBusy}
            />
          </div>
          <button className="button button-small" type="submit" disabled={upgradeBusy}>
            Request Pro plan
          </button>
          {upgradeNotice && (
            <p className="notice" role="status">
              {upgradeNotice}
            </p>
          )}
        </form>
      </div>

      <div className="publish-section">
        <h3>Delete account</h3>
        <p className="upload-help">
          This deletes your document, FAQ entries, conversations, leads, API keys, and published bot — everything.
          This cannot be undone.
        </p>
        {!confirming ? (
          <button type="button" className="button button-ghost" onClick={() => setConfirming(true)}>
            Delete my account
          </button>
        ) : (
          <form className="form" onSubmit={deleteAccount} style={{ marginTop: "1rem" }}>
            <div className="field">
              <label htmlFor="delete-password">Confirm your password</label>
              <input
                id="delete-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={busy}
                required
              />
            </div>
            <div className="doc-actions">
              <button className="button" type="submit" disabled={busy || !password}>
                {busy ? "Deleting…" : "Permanently delete my account"}
              </button>
              <button type="button" className="button button-ghost" onClick={() => setConfirming(false)} disabled={busy}>
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>
    </section>
  );
}