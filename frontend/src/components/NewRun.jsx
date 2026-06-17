import { useState } from "react";
import { live } from "../api.js";

// Generate a plausible Jira-style id so the user doesn't have to invent one.
function freshTicketId() {
  return "JSM-" + Math.floor(1000 + Math.random() * 9000);
}

export default function NewRun({ onRecorded }) {
  const [ticketId, setTicketId] = useState(freshTicketId);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function run() {
    if (!text.trim()) {
      setError("Describe the ticket first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const session = await live.runTicket(ticketId.trim() || freshTicketId(), text.trim());
      onRecorded(session.session_id);
      setText("");
      setTicketId(freshTicketId());
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="newrun">
      <input
        className="newrun__id"
        value={ticketId}
        onChange={(e) => setTicketId(e.target.value)}
        disabled={busy}
        placeholder="Ticket ID"
        aria-label="Ticket ID"
      />
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={busy}
        rows={3}
        placeholder="Describe the IT ticket in your own words…"
        aria-label="Ticket description"
      />
      <button className="btn btn--primary" onClick={run} disabled={busy}>
        {busy ? "Running & recording… (~1–2 min)" : "▶ Run & record"}
      </button>
      {busy && (
        <p className="muted small">The agent is calling the LLM and tools; every step is being captured.</p>
      )}
      {error && <p className="error small">⚠ {error}</p>}
    </div>
  );
}
