import { useEffect, useState } from "react";
import { api } from "../api.js";

const DISMISS_KEY = "onboarding_dismissed";

export default function OnboardingChecklist() {
  const [steps, setSteps] = useState(null);
  const [dismissed, setDismissed] = useState(() => {
    try {
      return localStorage.getItem(DISMISS_KEY) === "1";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    if (dismissed) return;
    Promise.all([api.getDocument(), api.getBotSettings(), api.getPublication()])
      .then(([doc, settings, pub]) => {
        setSteps({
          uploaded: Boolean(doc.document),
          indexed: doc.document?.index_status === "ready",
          customized: Boolean(settings.name && settings.name !== "Support Assistant"),
          published: Boolean(pub.published),
        });
      })
      .catch(() => {});
  }, [dismissed]);

  function dismiss() {
    setDismissed(true);
    try {
      localStorage.setItem(DISMISS_KEY, "1");
    } catch {
      /* ignore */
    }
  }

  if (dismissed || !steps) return null;
  if (steps.uploaded && steps.indexed && steps.customized && steps.published) return null;

  const items = [
    { done: steps.uploaded, label: "Upload a document" },
    { done: steps.indexed, label: "Wait for it to finish indexing" },
    { done: steps.customized, label: "Give your bot a name in Bot Settings" },
    { done: steps.published, label: "Publish your chatbot" },
  ];

  return (
    <section className="onboarding-card" aria-labelledby="onboarding-title">
      <div className="settings-head">
        <h2 id="onboarding-title" style={{ fontSize: "1.1rem" }}>
          Get your chatbot live
        </h2>
        <button type="button" className="link-button" onClick={dismiss}>
          Dismiss
        </button>
      </div>
      <ul className="onboarding-list">
        {items.map((item, i) => (
          <li key={i} className={item.done ? "onboarding-done" : ""}>
            <span className="onboarding-check">{item.done ? "✓" : i + 1}</span>
            {item.label}
          </li>
        ))}
      </ul>
    </section>
  );
}