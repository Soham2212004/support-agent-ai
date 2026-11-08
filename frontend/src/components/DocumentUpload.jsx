import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api.js";

const MAX_BYTES = 5 * 1024 * 1024;
const ALLOWED = [".pdf", ".docx", ".txt"];

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DocumentUpload() {
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const data = await api.getDocument();
      setDoc(data.document);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function upload(file) {
    setError("");
    if (!file) return;

    const name = file.name.toLowerCase();
    if (!ALLOWED.some((ext) => name.endsWith(ext))) {
      setError("Only PDF, DOCX and TXT files are supported.");
      return;
    }
    if (file.size === 0) {
      setError("That file is empty.");
      return;
    }
    if (file.size > MAX_BYTES) {
      setError("That file is larger than 5 MB.");
      return;
    }

    setBusy(true);
    try {
      const data = await api.uploadDocument(file);
      setDoc(data.document);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function remove() {
    if (!window.confirm("Delete this document? You can upload a new one afterwards.")) return;
    setError("");
    setBusy(true);
    try {
      await api.deleteDocument();
      setDoc(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function onDrop(e) {
    e.preventDefault();
    setDragging(false);
    if (!busy) upload(e.dataTransfer.files?.[0]);
  }

  if (loading) {
    return <p className="page-lede">Loading your document…</p>;
  }

  if (!doc) {
    return (
      <section className="upload-card">
        <h2>Upload your document</h2>
        <p className="upload-help">PDF, DOCX or TXT, up to 5 MB. You can have one document at a time.</p>

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        <div
          className={`dropzone${dragging ? " dropzone-active" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <p>{busy ? "Uploading and reading your document…" : "Drag a file here, or"}</p>
          <button type="button" className="button" disabled={busy} onClick={() => inputRef.current?.click()}>
            Choose file
          </button>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx,.txt"
            hidden
            aria-label="Choose a document to upload"
            onChange={(e) => upload(e.target.files?.[0])}
          />
        </div>
      </section>
    );
  }

  return (
    <section className="upload-card">
      <h2>Your document</h2>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      <dl className="doc-meta">
        <div>
          <dt>File</dt>
          <dd>{doc.filename}</dd>
        </div>
        <div>
          <dt>Type</dt>
          <dd>{doc.file_type.toUpperCase()}</dd>
        </div>
        <div>
          <dt>Size</dt>
          <dd>{formatSize(doc.size_bytes)}</dd>
        </div>
        {doc.page_count != null && (
          <div>
            <dt>Pages</dt>
            <dd>{doc.page_count}</dd>
          </div>
        )}
        <div>
          <dt>Words</dt>
          <dd>{doc.word_count.toLocaleString()}</dd>
        </div>
        <div>
          <dt>Uploaded</dt>
          <dd>{new Date(doc.uploaded_at).toLocaleString()}</dd>
        </div>
      </dl>

      <h3>Text we extracted</h3>
      <pre className="doc-preview">
        {doc.preview}
        {doc.preview_truncated ? "…" : ""}
      </pre>

      <div className="doc-actions">
        <button type="button" className="button button-ghost" onClick={remove} disabled={busy}>
          {busy ? "Deleting…" : "Delete document"}
        </button>
        <p className="upload-help">To upload a different file, delete this one first.</p>
      </div>
    </section>
  );
}