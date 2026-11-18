import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";

export default function Pricing() {
  const [plans, setPlans] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getPublicConfig()
      .then((data) => setPlans(data.plans))
      .catch((err) => setError(err.message || "Could not load pricing."));
  }, []);

  return (
    <main className="page">
      <p className="eyebrow">PRICING</p>
      <h1>Simple, usage-based plans</h1>
      <p className="page-lede">No credit card required. Start free, upgrade when you need more.</p>

      {error && <p className="form-error" role="alert">{error}</p>}
      {!plans && !error && <p className="page-lede">Loading…</p>}

      {plans && (
        <div className="pricing-grid">
          {plans.map((plan) => (
            <div key={plan.key} className="pricing-card">
              <h2>{plan.name}</h2>
              <ul className="doc-bullets">
                <li>{plan.monthly_messages.toLocaleString()} messages / month</li>
                <li>{plan.max_documents} document{plan.max_documents === 1 ? "" : "s"} + {plan.max_faq_entries} FAQ entries</li>
                <li>Full dashboard, analytics and handoff</li>
              </ul>
              <Link className="button button-block" to="/register">
                Get started
              </Link>
            </div>
          ))}
        </div>
      )}

      <p className="page-lede" style={{ marginTop: "2rem" }}>
        Need more? <Link to="/contact">Contact us</Link> or request an upgrade from your dashboard once approved.
      </p>
    </main>
  );
}