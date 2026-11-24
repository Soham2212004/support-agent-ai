import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, clearToken, getToken, setToken } from "../api.js";

export default function AccountSettings() {
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [passwordNotice, setPasswordNotice] = useState("");
  const [passwordBusy, setPasswordBusy] = useState(false);
  const [logoutBusy, setLogoutBusy] = useState(false);
  const [logoutNotice, setLogoutNotice] = useState("");

  async function changePassword(e) {
    e.preventDefault();
    setPasswordNotice("");
    if (newPassword !== confirmNewPassword) {
      setPasswordNotice("New passwords do not match.");
      return;
    }
    setPasswordBusy(true);
    try {
      const res = await api.changePassword(currentPassword, newPassword);
      setToken(res.token);
      setPasswordNotice("Password changed. You've been logged out of all other devices.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmNewPassword("");
    } catch (err) {
      setPasswordNotice(err.message || "Could not change your password.");
    } finally {
      setPasswordBusy(false);
    }
  }

  async function logoutEverywhere() {
    if (!window.confirm("Log out of all devices, including this one? You'll need to sign in again.")) return;
    setLogoutBusy(true);
    try {
      await api.logoutEverywhere();
      clearToken();
      navigate("/login");
    } catch (err) {
      setLogoutNotice(err.message || "Could not log out of all devices.");
    } finally {
      setLogoutBusy(false);
    }
  }
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

      <div className="publish-section">
        <h3>Change password</h3>
        <form className="form" onSubmit={changePassword}>
          <div className="field">
            <label htmlFor="current-password">Current password</label>
            <input
              id="current-password"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              disabled={passwordBusy}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="new-password-account">New password</label>
            <input
              id="new-password-account"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              disabled={passwordBusy}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="confirm-new-password-account">Confirm new password</label>
            <input
              id="confirm-new-password-account"
              type="password"
              value={confirmNewPassword}
              onChange={(e) => setConfirmNewPassword(e.target.value)}
              disabled={passwordBusy}
              required
            />
          </div>
          <button className="button button-small" type="submit" disabled={passwordBusy}>
            Change password
          </button>
          {passwordNotice && (
            <p className="notice" role="status">
              {passwordNotice}
            </p>
          )}
        </form>
      </div>

      <div className="publish-section">
        <h3>Sessions</h3>
        <p className="upload-help">
          Signed in on a device you don't recognize? Log out everywhere, including this device, and sign back in.
        </p>
        <button type="button" className="button button-ghost" onClick={logoutEverywhere} disabled={logoutBusy}>
          {logoutBusy ? "Logging out…" : "Log out of all devices"}
        </button>
        {logoutNotice && <p className="form-error">{logoutNotice}</p>}
      </div>

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