import { useState } from "react";
import { api } from "../api.js";

export default function Contact() {
  const [form, setForm] = useState({ name: "", email: "", message: "" });
  const [errors, setErrors] = useState({});
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErrors({});
    setNotice("");
    try {
      const res = await api.sendContact(form);
      setNotice(res.message);
      setForm({ name: "", email: "", message: "" });
    } catch (err) {
      setErrors(err.fieldErrors || {});
      setNotice(err.message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page page-narrow">
      <h1>Contact us</h1>
      <p className="page-lede">Questions, feedback, or need a higher plan? Send us a message.</p>

      <form className="form" onSubmit={submit}>
        {notice && (
          <p className={errors && Object.keys(errors).length ? "form-error" : "notice"} role="status">
            {notice}
          </p>
        )}
        <div className="field">
          <label htmlFor="contact-name">Name</label>
          <input id="contact-name" value={form.name} onChange={(e) => update("name", e.target.value)} required />
          {errors.name && <p className="field-error">{errors.name}</p>}
        </div>
        <div className="field">
          <label htmlFor="contact-email">Email</label>
          <input
            id="contact-email"
            type="email"
            value={form.email}
            onChange={(e) => update("email", e.target.value)}
            required
          />
          {errors.email && <p className="field-error">{errors.email}</p>}
        </div>
        <div className="field">
          <label htmlFor="contact-message">Message</label>
          <textarea
            id="contact-message"
            rows={5}
            maxLength={2000}
            value={form.message}
            onChange={(e) => update("message", e.target.value)}
            required
          />
          {errors.message && <p className="field-error">{errors.message}</p>}
        </div>
        <button className="button button-block" type="submit" disabled={busy}>
          {busy ? "Sending…" : "Send message"}
        </button>
      </form>
    </main>
  );
}