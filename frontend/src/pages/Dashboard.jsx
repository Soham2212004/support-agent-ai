import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api, clearToken, getToken } from "../api.js";
import DocumentUpload from "../components/DocumentUpload.jsx";

export default function Dashboard() {
  const navigate = useNavigate();
  const [account, setAccount] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const data = await api.me();
      setAccount(data.account);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken();
        navigate("/login", { replace: true });
        return;
      }
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    if (!getToken()) {
      navigate("/login", { replace: true });
      return;
    }
    load();
  }, [load, navigate]);

  if (loading && !account) {
    return (
      <main className="page page-narrow">
        <p className="page-lede">Loading your account…</p>
      </main>
    );
  }

  if (error && !account) {
    return (
      <main className="page page-narrow">
        <p className="form-error" role="alert">
          {error}
        </p>
        <button className="button" type="button" onClick={load}>
          Try again
        </button>
      </main>
    );
  }

  if (!account) return null;

  if (account.status === "pending") {
    return (
      <main className="page page-narrow">
        <section className="status-panel status-pending" aria-live="polite">
          <h1>Your request is pending approval</h1>
          <p>
            Thanks, {account.name.split(" ")[0]}. Once your request is approved, you’ll be able to
            access your customized dashboard. Check back soon.
          </p>
          <button className="button button-ghost" type="button" onClick={load} disabled={loading}>
            {loading ? "Checking…" : "Check status"}
          </button>
        </section>
      </main>
    );
  }

  if (account.status === "rejected") {
    return (
      <main className="page page-narrow">
        <section className="status-panel status-rejected" aria-live="polite">
          <h1>Your request was rejected by admin</h1>
          <p>Sorry, we can’t approve it right now. Please try again after a few months.</p>
        </section>
      </main>
    );
  }

  // approved
  return (
    <main className="page dash">
      <div className="dash-head">
        <h1>Welcome, {account.name.split(" ")[0]}</h1>
        <p className="page-lede">{account.company_name}</p>
      </div>
      <DocumentUpload />
    </main>
  );
}