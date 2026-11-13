import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api, clearToken, getToken } from "../api.js";
import DocumentUpload from "../components/DocumentUpload.jsx";
import Chat from "../components/Chat.jsx";
import BotSettings from "../components/BotSettings.jsx";
import Publishing from "../components/Publishing.jsx";
import Analytics from "../components/Analytics.jsx";
import HandoffRequests from "../components/HandoffRequests.jsx";
import OnboardingChecklist from "../components/OnboardingChecklist.jsx";

export default function Dashboard() {
  const navigate = useNavigate();
  const [account, setAccount] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("chat");
  const [settingsRevision, setSettingsRevision] = useState(0);
  const [handoffCount, setHandoffCount] = useState(0);

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
    api.getHandoffs().then((data) => setHandoffCount(data.open_count)).catch(() => {});
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

      <nav className="dash-tabs" aria-label="Dashboard sections">
        <button
          type="button"
          className={`dash-tab ${activeTab === "chat" ? "dash-tab-active" : ""}`}
          onClick={() => setActiveTab("chat")}
          aria-current={activeTab === "chat" ? "page" : undefined}
        >
          Documents &amp; Test Chat
        </button>
        <button
          type="button"
          className={`dash-tab ${activeTab === "settings" ? "dash-tab-active" : ""}`}
          onClick={() => setActiveTab("settings")}
          aria-current={activeTab === "settings" ? "page" : undefined}
        >
          Bot Settings
        </button>
        <button
          type="button"
          className={`dash-tab ${activeTab === "publish" ? "dash-tab-active" : ""}`}
          onClick={() => setActiveTab("publish")}
          aria-current={activeTab === "publish" ? "page" : undefined}
        >
          Publish &amp; API
        </button>
        <button
          type="button"
          className={`dash-tab ${activeTab === "analytics" ? "dash-tab-active" : ""}`}
          onClick={() => setActiveTab("analytics")}
          aria-current={activeTab === "analytics" ? "page" : undefined}
        >
          Analytics
        </button>
        <button
          type="button"
          className={`dash-tab ${activeTab === "handoffs" ? "dash-tab-active" : ""}`}
          onClick={() => setActiveTab("handoffs")}
          aria-current={activeTab === "handoffs" ? "page" : undefined}
        >
          Handoffs{handoffCount > 0 && <span className="tab-badge">{handoffCount}</span>}
        </button>
      </nav>

      {activeTab === "chat" && (
        <>
          <OnboardingChecklist />
          <DocumentUpload />
          <Chat settingsRevision={settingsRevision} />
        </>
      )}
      {activeTab === "settings" && <BotSettings onSave={() => setSettingsRevision((r) => r + 1)} />}
      {activeTab === "publish" && <Publishing />}
      {activeTab === "analytics" && <Analytics />}
      {activeTab === "handoffs" && <HandoffRequests onCountChange={setHandoffCount} />}
    </main>
  );
}
