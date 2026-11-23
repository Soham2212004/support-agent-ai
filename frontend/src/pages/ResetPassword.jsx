import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api.js";

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      await api.confirmPasswordReset(token, password);
      setDone(true);
      setTimeout(() => navigate("/login"), 1500);
    } catch (err) {
      setError(err.message || "This reset link is invalid or has expired.");
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <main className="page page-narrow">
        <h1>Reset password</h1>
        <p className="form-error" role="alert">
          No reset code found. Use the link from your email, or{" "}
          <Link to="/forgot-password">request a new one</Link>.
        </p>
      </main>
    );
  }

  return (
    <main className="page page-narrow">
      <h1>Set a new password</h1>

      {done ? (
        <p className="notice" role="status">
          Password reset! Taking you to sign in…
        </p>
      ) : (
        <form className="form" onSubmit={submit}>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <div className="field">
            <label htmlFor="new-password">New password</label>
            <input
              id="new-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="confirm-new-password">Confirm new password</label>
            <input
              id="confirm-new-password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              required
            />
          </div>
          <button className="button button-block" type="submit" disabled={busy}>
            {busy ? "Saving…" : "Reset password"}
          </button>
        </form>
      )}
    </main>
  );
}