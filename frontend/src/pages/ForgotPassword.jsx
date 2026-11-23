import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setNotice("");
    try {
      const res = await api.requestPasswordReset(email);
      setNotice(res.message);
    } catch (err) {
      setNotice(err.message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page page-narrow">
      <h1>Forgot your password?</h1>
      <p className="page-lede">Enter your email and we'll send you a link to reset it.</p>

      <form className="form" onSubmit={submit}>
        <div className="field">
          <label htmlFor="forgot-email">Email</label>
          <input
            id="forgot-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </div>
        <button className="button button-block" type="submit" disabled={busy}>
          {busy ? "Sending…" : "Send reset link"}
        </button>
        {notice && (
          <p className="notice" role="status">
            {notice}
          </p>
        )}
      </form>

      <p className="form-foot">
        <Link to="/login">Back to sign in</Link>
      </p>
    </main>
  );
}