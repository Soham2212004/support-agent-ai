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
    similarity_threshold: 0.75,
    show_citations: true,
    max_answer_length: "standard",
    starter_questions: ["", "", "", ""],
    escalation_email: "",
    avatar_url: "",
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
        similarity_threshold: data.similarity_threshold ?? 0.75,
        show_citations: data.show_citations ?? true,
        max_answer_length: data.max_answer_length || "standard",
        starter_questions: [...(data.starter_questions || []), "", "", "", ""].slice(0, 4),
        escalation_email: data.escalation_email || "",
        avatar_url: data.avatar_url || "",
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
      const payload = {
        ...formData,
        starter_questions: formData.starter_questions.map((q) => q.trim()).filter(Boolean),
      };
      const res = await api.saveBotSettings(payload);
      setSuccess("Bot settings saved! Your test chat is now using these updated settings.");
      if (res?.settings) {
        setFormData({
          name: res.settings.name || "",
          greeting: res.settings.greeting || "",
          tone: res.settings.tone || "friendly",
          custom_instructions: res.settings.custom_instructions || "",
          fallback_message: res.settings.fallback_message || "",
          similarity_threshold: res.settings.similarity_threshold ?? 0.75,
          show_citations: res.settings.show_citations ?? true,
          max_answer_length: res.settings.max_answer_length || "standard",
          starter_questions: [...(res.settings.starter_questions || []), "", "", "", ""].slice(0, 4),
          escalation_email: res.settings.escalation_email || "",
          avatar_url: res.settings.avatar_url || "",
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

        {/* Answer behavior */}
        <div className="field">
          <div className="field-label-row">
            <label htmlFor="bot-similarity">Match strictness</label>
            <span className="field-counter">{formData.similarity_threshold.toFixed(2)}</span>
          </div>
          <p className="field-desc">
            Higher = stricter matches, fewer but more confident answers. Lower = more answers, more risk of a weak match.
          </p>
          <input
            id="bot-similarity"
            type="range"
            min="0.3"
            max="0.95"
            step="0.05"
            value={formData.similarity_threshold}
            onChange={(e) => handleChange("similarity_threshold", parseFloat(e.target.value))}
            disabled={saving}
          />
          {fieldErrors.similarity_threshold && <p className="field-error">{fieldErrors.similarity_threshold}</p>}
        </div>

        <div className="field">
          <label className="field-checkbox">
            <input
              type="checkbox"
              checked={formData.show_citations}
              onChange={(e) => handleChange("show_citations", e.target.checked)}
              disabled={saving}
            />
            Show source citations (e.g. [1]) to visitors
          </label>
        </div>

        <div className="field">
          <label>Answer length</label>
          <div className="settings-tone-grid" role="radiogroup" aria-label="Answer length">
            {[
              { id: "short", label: "Short", desc: "1-2 sentences, no matter the tone." },
              { id: "standard", label: "Standard", desc: "Clear and reasonably concise." },
              { id: "detailed", label: "Detailed", desc: "Thorough answers when helpful." },
            ].map((opt) => (
              <label key={opt.id} className={`settings-tone-option ${formData.max_answer_length === opt.id ? "selected" : ""}`}>
                <input
                  type="radio"
                  name="bot-max-answer-length"
                  value={opt.id}
                  checked={formData.max_answer_length === opt.id}
                  onChange={() => handleChange("max_answer_length", opt.id)}
                  disabled={saving}
                />
                <span className="settings-tone-title">{opt.label}</span>
                <span className="settings-tone-desc">{opt.desc}</span>
              </label>
            ))}
          </div>
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

        {/* Starter questions */}
        <div className="field">
          <label>Suggested starter questions</label>
          <p className="field-desc">Up to 4 clickable prompts shown when a visitor opens the chat. Leave blank to skip.</p>
          {formData.starter_questions.map((q, i) => (
            <input
              key={i}
              type="text"
              maxLength={150}
              placeholder={`Starter question ${i + 1}`}
              value={q}
              onChange={(e) => {
                const next = [...formData.starter_questions];
                next[i] = e.target.value;
                handleChange("starter_questions", next);
              }}
              disabled={saving}
              style={{ marginTop: i > 0 ? "0.5rem" : 0 }}
            />
          ))}
          {fieldErrors.starter_questions && <p className="field-error">{fieldErrors.starter_questions}</p>}
        </div>

        {/* Escalation email */}
        <div className="field">
          <label htmlFor="bot-escalation-email">Escalation contact email</label>
          <p className="field-desc">Added to the fallback message so visitors know where to go when the bot can't help.</p>
          <input
            id="bot-escalation-email"
            type="email"
            placeholder="e.g. support@yourcompany.com"
            value={formData.escalation_email}
            onChange={(e) => handleChange("escalation_email", e.target.value)}
            disabled={saving}
          />
          {fieldErrors.escalation_email && <p className="field-error">{fieldErrors.escalation_email}</p>}
        </div>

        {/* Avatar */}
        <div className="field">
          <label htmlFor="bot-avatar-url">Bot avatar URL</label>
          <p className="field-desc">A small image shown next to your bot's name in the chat.</p>
          <input
            id="bot-avatar-url"
            type="url"
            placeholder="https://example.com/avatar.png"
            value={formData.avatar_url}
            onChange={(e) => handleChange("avatar_url", e.target.value)}
            disabled={saving}
          />
          {fieldErrors.avatar_url && <p className="field-error">{fieldErrors.avatar_url}</p>}
          {formData.avatar_url && <img src={formData.avatar_url} alt="" className="bot-avatar-preview" />}
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
