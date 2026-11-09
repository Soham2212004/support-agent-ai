import { useState } from "react";
import { api } from "../api.js";

export default function DocumentSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [asked, setAsked] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    const question = query.trim();
    if (!question) return;

    setError("");
    setBusy(true);
    try {
      const data = await api.searchDocument(question);
      setResults(data.results);
      setAsked(data.query);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="search-box" aria-labelledby="search-title">
      <h3 id="search-title">Try a search</h3>
      <p className="upload-help">Ask a question about your document to see which passages match best.</p>

      <form className="search-form" onSubmit={submit}>
        <input
          type="text"
          value={query}
          maxLength={300}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="For example, What are your opening hours?"
          aria-label="Your question"
        />
        <button className="button" type="submit" disabled={busy || !query.trim()}>
          {busy ? "Searching…" : "Search"}
        </button>
      </form>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      {results && results.length === 0 && <p className="upload-help">No matching passages found.</p>}

      {results && results.length > 0 && (
        <ol className="search-results" aria-label={`Best matches for ${asked}`}>
          {results.map((r) => (
            <li key={r.rank}>
              <div className="result-head">
                <span className="result-score">Score {r.score.toFixed(3)}</span>
                <span className="result-where">{r.page ? `Page ${r.page}` : r.section}</span>
              </div>
              <p>{r.text}</p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}