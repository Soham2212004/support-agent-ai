import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "../api.js";

const TONES = [
  {
    id: "friendly",
    label: "Friendly",
    desc: "Warm, conversational, and polite. Great for most customer support.",
  },
  {
    id: "professional",
    label: "Professional",
    desc: "Formal, objective, and authoritative. Best for corporate or compliance.",
  },
  {
    id: "concise",
    label: "Concise",
    desc: "Direct, brief, and to the point. Minimal pleasantries, maximum speed.",
  },
];

export default function BotSettings({ onSave }) {
  const [formData, setFormData] = useState({
    name: "",
    greeting: "",
    tone: "friendly",
    custom_instructions: "",
    fallback_message: "",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [success, setSuccess] = useState("");

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.getBotSettings();
      setFormData({
        name: data.name || "",
        greeting: data.greeting || "",
        tone: data.tone || "friendly",
        custom_instructions: data.custom_instructions || "",
        fallback_message: data.fallback_message || "",
      });
    } catch (err) {
      setError(err.message || "Failed to load bot settings.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  function handleChange(field, value) {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (fieldErrors[field]) {
      setFieldErrors((prev) => {
        const copy = { ...prev };
        delete copy[field];
        return copy;
      });
    }
    setSuccess("");
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setFieldErrors({});
    setSuccess("");
    setSaving(true);

    try {
      const res = await api.saveBotSettings(formData);
      setSuccess("Bot settings saved! Your test chat is now using these updated settings.");
      if (res?.settings) {
        setFormData({
          name: res.settings.name || "",
          greeting: res.settings.greeting || "",
          tone: res.settings.tone || "friendly",
          custom_instructions: res.settings.custom_instructions || "",
          fallback_message: res.settings.fallback_message || "",
        });
      }
      onSave?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
        if (err.fieldErrors) setFieldErrors(err.fieldErrors);
      } else {
        setError("Something went wrong while saving your settings.");
      }
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <section className="settings-card" aria-busy="true">
        <p className="page-lede">Loading bot settings…</p>
      </section>
    );
  }

  return (
    <section className="settings-card" aria-labelledby="settings-title">
      <div className="settings-head">
        <div>
          <h2 id="settings-title">Bot settings</h2>
          <p className="upload-help">
            Customize how your chatbot introduces itself, speaks to visitors, and handles unanswered questions.
          </p>
        </div>
      </div>

      <form className="form settings-form" onSubmit={handleSubmit}>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        {success && (
          <div className="status-notice status-notice-success" role="status">
            {success}
          </div>
        )}

        {/* Bot Name */}
        <div className="field">
          <div className="field-label-row">
            <label htmlFor="bot-name">Bot name</label>
            <span className="field-counter">{formData.name.length} / 100</span>
          </div>
          <p className="field-desc">The name your chatbot uses when introducing itself.</p>
          <input
            id="bot-name"
            type="text"
            maxLength={100}
            placeholder="e.g. Acme Support Assistant"
            value={formData.name}
            onChange={(e) => handleChange("name", e.target.value)}
            disabled={saving}
          />
          {fieldErrors.name && <p className="field-error">{fieldErrors.name}</p>}
        </div>

        {/* Greeting */}
        <div className="field">
          <div className="field-label-row">
            <label htmlFor="bot-greeting">Greeting</label>
            <span className="field-counter">{formData.greeting.length} / 500</span>
          </div>
          <p className="field-desc">The welcome message shown to clients whenever a conversation starts.</p>
          <textarea
            id="bot-greeting"
            rows={2}
            maxLength={500}
            placeholder="e.g. Hello! How can I help you today?"
            value={formData.greeting}
            onChange={(e) => handleChange("greeting", e.target.value)}
            disabled={saving}
          />
          {fieldErrors.greeting && <p className="field-error">{fieldErrors.greeting}</p>}
        </div>

        {/* Tone Selection */}
        <div className="field">
          <label>Tone of voice</label>
          <p className="field-desc">Controls the style and vocabulary the AI uses when replying.</p>
          <div className="settings-tone-grid" role="radiogroup" aria-label="Tone selection">
            {TONES.map((t) => {
              const isSelected = formData.tone === t.id;
              return (
                <label
                  key={t.id}
                  className={`settings-tone-option ${isSelected ? "selected" : ""}`}
                >
                  <input
                    type="radio"
                    name="bot-tone"
                    value={t.id}
                    checked={isSelected}
                    onChange={() => handleChange("tone", t.id)}
                    disabled={saving}
                  />
                  <span className="settings-tone-title">{t.label}</span>
                  <span className="settings-tone-desc">{t.desc}</span>
                </label>
              );
            })}
          </div>
          {fieldErrors.tone && <p className="field-error">{fieldErrors.tone}</p>}
        </div>

        {/* Custom Instructions */}
        <div className="field">
          <div className="field-label-row">
            <label htmlFor="bot-instructions">Custom instructions</label>
            <span className="field-counter">{formData.custom_instructions.length} / 1000</span>
          </div>
          <p className="field-desc">
            Specific guidelines for your bot (for example, "Always mention our 24/7 support line", or "Recommend booking a consultation").
          </p>
          <textarea
            id="bot-instructions"
            rows={3}
            maxLength={1000}
            placeholder="e.g. Always mention our 24/7 support team and provide a friendly sign-off."
            value={formData.custom_instructions}
            onChange={(e) => handleChange("custom_instructions", e.target.value)}
            disabled={saving}
          />
          {fieldErrors.custom_instructions && (
            <p className="field-error">{fieldErrors.custom_instructions}</p>
          )}
        </div>

        {/* Fallback Message */}
        <div className="field">
          <div className="field-label-row">
            <label htmlFor="bot-fallback">Fallback message</label>
            <span className="field-counter">{formData.fallback_message.length} / 500</span>
          </div>
          <p className="field-desc">
            What your bot replies when the answer cannot be found in your uploaded document.
          </p>
          <textarea
            id="bot-fallback"
            rows={2}
            maxLength={500}
            placeholder="e.g. I couldn't find the answer to that in your document. Try rephrasing your question or contact our support team."
            value={formData.fallback_message}
            onChange={(e) => handleChange("fallback_message", e.target.value)}
            disabled={saving}
          />
          {fieldErrors.fallback_message && (
            <p className="field-error">{fieldErrors.fallback_message}</p>
          )}
        </div>

        <div className="settings-actions">
          <button className="button" type="submit" disabled={saving}>
            {saving ? "Saving settings…" : "Save settings"}
          </button>
        </div>
      </form>
    </section>
  );
}
