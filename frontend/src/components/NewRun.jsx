import { useEffect, useState } from "react";
import { live } from "../api.js";

// The user describes the problem and picks which LLM to run. The backend assigns the ticket
// id automatically (a real Jira issue when Jira is configured).
export default function NewRun({ onRecorded }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [created, setCreated] = useState(null);
  const [models, setModels] = useState([]);
  const [model, setModel] = useState("");

  // Load the list of available LLMs once.
  useEffect(() => {
    live
      .models()
      .then((res) => {
        setModels(res.models || []);
        setModel(res.default || (res.models?.[0]?.id ?? ""));
      })
      .catch(() => setModels([]));
  }, []);

  const selected = models.find((m) => m.id === model);

  async function run() {
    if (!text.trim()) {
      setError("Describe the ticket first.");
      return;
    }
    setBusy(true);
    setError(null);
    setCreated(null);
    try {
      // Empty ticket id => the server creates/assigns one automatically.
      const session = await live.runTicket("", text.trim(), model);
      setCreated(session.ticket_id);
      onRecorded(session.session_id);
      setText("");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="newrun">
      <label className="newrun__label" htmlFor="model-select">🧠 LLM model</label>
      <select
        id="model-select"
        className="newrun__model"
        value={model}
        onChange={(e) => setModel(e.target.value)}
        disabled={busy || models.length === 0}
      >
        {models.map((m) => (
          <option key={m.id} value={m.id}>{m.label}</option>
        ))}
      </select>
      {selected?.note && <p className="muted small newrun__note">{selected.note}</p>}

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={busy}
        rows={3}
        placeholder="Describe the problem… a ticket is created & triaged automatically"
        aria-label="Ticket description"
      />
      <button className="btn btn--primary" onClick={run} disabled={busy}>
        {busy ? "Creating ticket & triaging… (~1–2 min)" : "▶ Run & record"}
      </button>
      {busy && (
        <p className="muted small">The agent is calling the LLM and tools; every step is being captured.</p>
      )}
      {created && !busy && <p className="muted small">✓ Triaged ticket <b>{created}</b></p>}
      {error && <p className="error small">⚠ {error}</p>}
    </div>
  );
}
