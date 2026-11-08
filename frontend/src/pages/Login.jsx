import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api, setToken } from "../api.js";

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const registered = Boolean(location.state?.registered);

  const [email, setEmail] = useState(location.state?.email || "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const data = await api.login(email, password);
      setToken(data.token);
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page page-narrow">
      <h1>Sign in</h1>

      {registered && (
        <p className="notice" role="status">
          Request received. Sign in with your email and password to check its status.
        </p>
      )}

      <form className="form" onSubmit={submit}>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>

        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        <button className="button button-block" type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>

        <p className="form-foot">
          New here? <Link to="/register">Try our services</Link>
        </p>
      </form>
    </main>
  );
}