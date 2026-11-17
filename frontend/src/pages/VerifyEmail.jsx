import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, setToken } from "../api.js";

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const tokenFromUrl = searchParams.get("token") || "";
  const [token, setTokenValue] = useState(tokenFromUrl);
  const [status, setStatus] = useState(tokenFromUrl ? "verifying" : "idle");
  const [error, setError] = useState("");
  const [resendEmail, setResendEmail] = useState("");
  const [resendBusy, setResendBusy] = useState(false);
  const [resendNotice, setResendNotice] = useState("");

  useEffect(() => {
    if (tokenFromUrl) verify(tokenFromUrl);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tokenFromUrl]);

  async function verify(value) {
    setStatus("verifying");
    setError("");
    try {
      const data = await api.verifyEmail(value);
      setToken(data.token);
      setStatus("verified");
      setTimeout(() => navigate("/dashboard"), 1500);
    } catch (err) {
      setError(err.message || "This verification link is invalid or has expired.");
      setStatus("error");
    }
  }

  async function resend(e) {
    e.preventDefault();
    setResendBusy(true);
    setResendNotice("");
    try {
      await api.resendVerification(resendEmail);
      setResendNotice("If that email needs verifying, a new link has been sent.");
    } catch (err) {
      setResendNotice(err.message || "Something went wrong.");
    } finally {
      setResendBusy(false);
    }
  }

  return (
    <main className="page page-narrow">
      <h1>Verify your email</h1>

      {status === "idle" && (
        <form
          className="form"
          onSubmit={(e) => {
            e.preventDefault();
            verify(token);
          }}
        >
          <p className="page-lede">Paste the verification code from your email.</p>
          <div className="field">
            <label htmlFor="verify-token">Verification code</label>
            <input id="verify-token" value={token} onChange={(e) => setTokenValue(e.target.value)} required />
          </div>
          <button className="button button-block" type="submit">
            Verify
          </button>
        </form>
      )}

      {status === "verifying" && <p className="page-lede">Verifying…</p>}

      {status === "verified" && (
        <p className="notice" role="status">
          Email verified! Taking you to your dashboard…
        </p>
      )}

      {status === "error" && (
        <>
          <p className="form-error" role="alert">
            {error}
          </p>
          <form className="form" onSubmit={resend} style={{ marginTop: "1.5rem" }}>
            <p className="page-lede">Request a new verification link.</p>
            <div className="field">
              <label htmlFor="resend-email">Email</label>
              <input
                id="resend-email"
                type="email"
                value={resendEmail}
                onChange={(e) => setResendEmail(e.target.value)}
                required
              />
            </div>
            <button className="button button-block" type="submit" disabled={resendBusy}>
              {resendBusy ? "Sending…" : "Resend verification email"}
            </button>
            {resendNotice && (
              <p className="notice" role="status">
                {resendNotice}
              </p>
            )}
          </form>
        </>
      )}

      <p className="form-foot" style={{ marginTop: "1.5rem" }}>
        <Link to="/login">Back to sign in</Link>
      </p>
    </main>
  );
}