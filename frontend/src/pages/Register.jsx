import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";

const empty = {
  name: "",
  email: "",
  company_name: "",
  role: "",
  company_description: "",
  website: "",
  reason: "",
  password: "",
  confirm_password: "",
};

function Field({ label, name, error, hint, children }) {
  return (
    <div className="field">
      <label htmlFor={name}>{label}</label>
      {children}
      {hint && !error && <p className="field-hint">{hint}</p>}
      {error && (
        <p className="field-error" id={`${name}-error`}>
          {error}
        </p>
      )}
    </div>
  );
}

export default function Register() {
  const navigate = useNavigate();
  const [form, setForm] = useState(empty);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);

  const update = (e) => setForm((f) => ({ ...f, [e.target.name]: e.target.value }));

  const props = (name) => ({
    id: name,
    name,
    value: form[name],
    onChange: update,
    "aria-invalid": errors[name] ? "true" : undefined,
    "aria-describedby": errors[name] ? `${name}-error` : undefined,
  });

  async function submit(e) {
    e.preventDefault();
    setFormError("");

    if (form.password !== form.confirm_password) {
      setErrors({ confirm_password: "Passwords do not match." });
      return;
    }

    setErrors({});
    setBusy(true);
    try {
      await api.register(form);
      navigate("/login", { state: { registered: true, email: form.email } });
    } catch (err) {
      setErrors(err.fieldErrors || {});
      setFormError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page">
      <h1>Try Support Agent AI</h1>
      <p className="page-lede">
        Tell us about your company. We review every request and unlock your dashboard once it’s
        approved.
      </p>

      <form className="form" onSubmit={submit} noValidate>
        {formError && (
          <p className="form-error" role="alert">
            {formError}
          </p>
        )}

        <div className="field-row">
          <Field label="Name" name="name" error={errors.name}>
            <input {...props("name")} type="text" autoComplete="name" required />
          </Field>
          <Field label="Email" name="email" error={errors.email}>
            <input {...props("email")} type="email" autoComplete="email" required />
          </Field>
        </div>

        <div className="field-row">
          <Field label="Company name" name="company_name" error={errors.company_name}>
            <input {...props("company_name")} type="text" autoComplete="organization" required />
          </Field>
          <Field label="Your role" name="role" error={errors.role}>
            <input
              {...props("role")}
              type="text"
              autoComplete="organization-title"
              placeholder="For example, Head of Support"
              required
            />
          </Field>
        </div>

        <Field
          label="What does your company do?"
          name="company_description"
          error={errors.company_description}
          hint="A short description is enough."
        >
          <textarea {...props("company_description")} rows={3} maxLength={1000} required />
        </Field>

        <Field label="Company website" name="website" error={errors.website}>
          <input
            {...props("website")}
            type="text"
            inputMode="url"
            autoComplete="url"
            placeholder="https://yourcompany.com"
            required
          />
        </Field>

        <Field
          label="Why do you need this chatbot on your website?"
          name="reason"
          error={errors.reason}
          hint="A few sentences help us review your request faster."
        >
          <textarea {...props("reason")} rows={4} maxLength={1000} required />
        </Field>

        <div className="field-row">
          <Field label="Password" name="password" error={errors.password} hint="At least 8 characters.">
            <input {...props("password")} type="password" autoComplete="new-password" required />
          </Field>
          <Field label="Confirm password" name="confirm_password" error={errors.confirm_password}>
            <input {...props("confirm_password")} type="password" autoComplete="new-password" required />
          </Field>
        </div>

        <button className="button button-block" type="submit" disabled={busy}>
          {busy ? "Sending your request…" : "Send request"}
        </button>

        <p className="form-foot">
          Already registered? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </main>
  );
}