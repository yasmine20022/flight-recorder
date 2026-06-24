// Data access layer — talks ONLY to the live FastAPI backend. No static/mock data.
export const API_BASE = "http://127.0.0.1:8000/api";

// Direct URL for the compliance PDF (used as an <a download> href).
export function reportUrl(session_id) {
  return `${API_BASE}/sessions/${session_id}/report.pdf`;
}

async function call(path, opts) {
  const res = await fetch(`${API_BASE}${path}`, opts);
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${path} → ${res.status} ${detail}`);
  }
  return res.json();
}

export const live = {
  async health() {
    return call("/health");
  },
  async listSessions() {
    return call("/sessions");
  },
  async getSession(id) {
    return call(`/sessions/${id}`);
  },
  async models() {
    return call("/models");
  },
  async runTicket(ticket_id, ticket_text, model) {
    return call("/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticket_id, ticket_text, model }),
    });
  },
  async replay(session_id) {
    // engine=proxy re-runs the real agent but serves the LLM answers from the recorded
    // cache — zero real LLM calls, zero tokens, side effects blocked. Deterministic & safe.
    return call(`/sessions/${session_id}/replay?engine=proxy`, { method: "POST" });
  },
  async whatif(session_id, tool_name, new_output) {
    return call(`/sessions/${session_id}/whatif`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tool_name, new_output }),
    });
  },
  async whatifPrompt(session_id, system_prompt) {
    return call(`/sessions/${session_id}/whatif`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ system_prompt }),
    });
  },
  async whatifTicket(session_id, ticket_text) {
    // Counterfactual: re-run the agent on a reworded ticket (robustness test).
    return call(`/sessions/${session_id}/whatif`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticket_text }),
    });
  },
  async agentPrompt() {
    return call("/agent/prompt");
  },
  // --- AI analysis layer ---
  async judge(session_id) {
    return call(`/sessions/${session_id}/judge`);
  },
  async autofix(session_id) {
    return call(`/sessions/${session_id}/autofix`, { method: "POST" });
  },
  async patterns() {
    return call("/patterns");
  },
  async metrics(refresh) {
    return call(`/metrics${refresh ? "?refresh=true" : ""}`);
  },
  async rca(session_id) {
    return call(`/sessions/${session_id}/rca`);
  },
  async diff(limit, refresh) {
    const q = [];
    if (limit) q.push(`limit=${limit}`);
    if (refresh) q.push("refresh=true");
    return call(`/diff${q.length ? `?${q.join("&")}` : ""}`);
  },
  async anomalies(session_id) {
    return call(`/sessions/${session_id}/anomalies`);
  },
  async signature(session_id) {
    return call(`/sessions/${session_id}/signature`);
  },
};

// Probe the backend; the UI uses this to show an online/offline state.
export async function checkOnline() {
  try {
    await live.health();
    return true;
  } catch {
    return false;
  }
}
