import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";

const STATUS_LABEL = {
  pending: "Indexing…",
  processing: "Indexing…",
  ready: "Ready",
  failed: "Failed",
};

export default function FaqManager() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [editingId, setEditingId] = useState(null);

  const load = useCallback(async () => {
    setError("");
    try {
      const data = await api.getFaqEntries();
      setEntries(data.entries);
    } catch (err) {
      setError(err.message || "Could not load FAQ entries.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // poll while anything is still indexing
  useEffect(() => {
    if (!entries.some((e) => e.index_status === "pending" || e.index_status === "processing")) return undefined;
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, [entries, load]);

  function startEdit(entry) {
    setEditingId(entry.id);
    setQuestion(entry.question);
    setAnswer(entry.answer);
  }

  function cancelEdit() {
    setEditingId(null);
    setQuestion("");
    setAnswer("");
  }

  async function submit(e) {
    e.preventDefault();
    if (!question.trim() || !answer.trim()) return;
    setBusy(true);
    setError("");
    try {
      if (editingId) {
        await api.updateFaqEntry(editingId, { question, answer });
      } else {
        await api.createFaqEntry({ question, answer });
      }
      cancelEdit();
      await load();
    } catch (err) {
      setError(err.message || "Could not save this FAQ entry.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id) {
    if (!window.confirm("Delete this FAQ entry?")) return;
    setBusy(true);
    try {
      await api.deleteFaqEntry(id);
      await load();
    } catch (err) {
      setError(err.message || "Could not delete this entry.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <section className="upload-card" style={{ marginTop: "1.5rem" }}>
        <p className="page-lede">Loading FAQ entries…</p>
      </section>
    );
  }

  return (
    <section className="upload-card" style={{ marginTop: "1.5rem" }}>
      <h2>FAQ entries</h2>
      <p className="upload-help">
        Typed question-and-answer pairs, searched and answered from alongside your uploaded document.
      </p>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      <form className="form" onSubmit={submit} style={{ marginTop: "1.25rem" }}>
        <div className="field">
          <label htmlFor="faq-question">Question</label>
          <input
            id="faq-question"
            type="text"
            maxLength={300}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. What are your business hours?"
            disabled={busy}
          />
        </div>
        <div className="field">
          <label htmlFor="faq-answer">Answer</label>
          <textarea
            id="faq-answer"
            rows={3}
            maxLength={2000}
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="e.g. We're open Monday to Friday, 9am to 6pm."
            disabled={busy}
          />
        </div>
        <div className="doc-actions">
          <button className="button button-small" type="submit" disabled={busy || !question.trim() || !answer.trim()}>
            {editingId ? "Save changes" : "Add FAQ entry"}
          </button>
          {editingId && (
            <button type="button" className="button button-ghost button-small" onClick={cancelEdit} disabled={busy}>
              Cancel
            </button>
          )}
        </div>
      </form>

      {entries.length === 0 ? (
        <p className="upload-help" style={{ marginTop: "1.5rem" }}>
          No FAQ entries yet.
        </p>
      ) : (
        <ul className="publish-version-list" style={{ marginTop: "1.5rem" }}>
          {entries.map((entry) => (
            <li key={entry.id}>
              <div>
                <strong>{entry.question}</strong>
                <span
                  className={`publish-badge ${entry.index_status === "ready" ? "publish-badge-live" : ""}`}
                  style={entry.index_status === "failed" ? { borderColor: "#f5b5b5", background: "#fde8e8", color: "#8f1d1d" } : undefined}
                >
                  {STATUS_LABEL[entry.index_status] || entry.index_status}
                </span>
                <p>{entry.answer}</p>
                {entry.index_error && <p className="field-error">{entry.index_error}</p>}
              </div>
              <div className="doc-actions" style={{ marginTop: 0 }}>
                <button type="button" className="button button-ghost button-small" onClick={() => startEdit(entry)} disabled={busy}>
                  Edit
                </button>
                <button type="button" className="button button-ghost button-small" onClick={() => remove(entry.id)} disabled={busy}>
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}