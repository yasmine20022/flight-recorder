"""The Jira triage agent — Sprint 1.

This is a real ReAct agent: the LLM is given the four simulated tools and **decides on its
own** which to call and in what order. Nothing about the routing is hard-coded — feed it a
different ticket and it searches the KB, looks up different history, assigns a different
owner, and sends a different notification.

Requires a Groq API key (tool-calling needs a real LLM). Use ``GROQ_API_KEY`` in
``backend/.env``.
"""
from __future__ import annotations

from typing import Any

from flight_recorder.agent.tools import ALL_TOOLS
from flight_recorder.config import settings

# Models the user can pick from in the UI. All are free on Groq and support tool-calling
# (required for this ReAct agent). The first entry is the default.
AVAILABLE_MODELS = [
    {"id": "llama-3.1-8b-instant", "label": "Llama 3.1 8B (rapide)",
     "note": "Petit & rapide. Oublie parfois des étapes; limite de tokens basse."},
    {"id": "llama-3.3-70b-versatile", "label": "Llama 3.3 70B (fiable)",
     "note": "Grand modèle, suit bien les instructions. Recommandé pour la démo."},
    {"id": "meta-llama/llama-4-scout-17b-16e-instruct", "label": "Llama 4 Scout 17B",
     "note": "Récent, bon équilibre vitesse/qualité."},
    {"id": "openai/gpt-oss-20b", "label": "GPT-OSS 20B (OpenAI ouvert)",
     "note": "Modèle ouvert d'OpenAI, taille moyenne."},
    {"id": "openai/gpt-oss-120b", "label": "GPT-OSS 120B (OpenAI ouvert)",
     "note": "Grand modèle ouvert d'OpenAI."},
    {"id": "qwen/qwen3-32b", "label": "Qwen3 32B (multilingue)",
     "note": "Bon en multilingue (utile pour les tickets en français)."},
]
_MODEL_IDS = {m["id"] for m in AVAILABLE_MODELS}


def resolve_model(model: str | None) -> str:
    """Pick a valid model id: the requested one if known, else the configured default."""
    if model and model in _MODEL_IDS:
        return model
    return settings.groq_model

_PROCESS = """For every ticket, follow this process using the tools available to you:
1. Call search_kb with keywords from the ticket to find the most relevant knowledge article.
2. Use the article's category to call query_db and review how similar past tickets were handled.
3. Call get_user_info with the team that should own this issue, to find the assignee. Valid
   teams: Network, Identity & Access, Email & Collaboration, Hardware, Software, Database,
   Security, Cloud, Telephony, Backend, Frontend.
4. Decide a priority (Low, Medium, High, or Critical) and the assignee.
5. Call send_notification to inform the assignee. The `user` argument MUST be exactly the
   `email` value returned by get_user_info in step 3 — never make up an email address.

You are NOT finished until send_notification has returned status "sent". Never write your
final answer before that — if you skipped a step, go back and call the missing tool.

Only after send_notification succeeds, reply with a short final decision in exactly this form:
DECISION: priority=<Low|Medium|High|Critical>; assignee=<name> <email>; reason=<one sentence>.

Only use information returned by the tools. Do not invent article ids, users, emails, or
history. Every email you use must come verbatim from a get_user_info result."""

# --- The DEFAULT (intentionally buggy) prompt ----------------------------------------
# This is the agent shipped to "production". It carries a real, subtle prompt bug: an
# over-broad routing rule that sends any API / HTTP-500 / payment ticket to the Frontend
# team. So a production outage like "HTTP 500 on /api/payments" is silently misrouted to
# Frontend / High instead of Backend / Critical — no error fires, the wrong team is paged.
# This is the exact failure the Flight Recorder is built to catch and the What-If engine
# fixes (inject the corrected instructions at step 1 — see CORRECTED_SYSTEM_PROMPT).
SYSTEM_PROMPT = f"""You are an IT service-desk triage agent for Jira tickets.

{_PROCESS}

Routing note: even if the knowledge base suggests another category, any ticket that mentions
an API, an endpoint, an HTTP 500, or payments is almost always a front-end display problem —
assign it to the Frontend team with priority High."""

# --- The CORRECTED prompt (used by the What-If demo to fix the bug above) -------------
CORRECTED_SYSTEM_PROMPT = f"""You are an IT service-desk triage agent for Jira tickets.

{_PROCESS}

Routing note: an HTTP 500 on an API endpoint, or a payment service failing in production, is
a server-side outage — assign it to the Backend team with priority Critical. Only assign to
the Frontend team for purely visual/client-side defects (layout, CSS, rendering)."""


def _build_llm(model: str | None = None):
    """Create the Groq chat model used by the agent (``model`` defaults to the configured one)."""
    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Copy backend/.env.example to backend/.env and add "
            "your free key from https://console.groq.com"
        )
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=model or settings.groq_model,
        temperature=0,  # determinism matters for recording/replay
        api_key=settings.groq_api_key,
        max_retries=settings.groq_max_retries,  # ride out transient free-tier TPM 429s
    )


def build_agent(tools=None, system_prompt: str | None = None, *, model=None,
                model_name: str | None = None):
    """Compile and return the ReAct triage agent (LLM + tools).

    ``tools`` defaults to the real toolset; the What-If engine passes an overridden set.
    ``system_prompt`` defaults to the (buggy) production prompt; the What-If engine passes
    ``CORRECTED_SYSTEM_PROMPT`` to inject a corrected instruction at step 1.
    ``model_name`` selects which Groq model to run (the user's choice). ``model`` lets the
    replay engine inject a ready-made model object instead.
    """
    from langgraph.prebuilt import create_react_agent

    # langgraph 0.2.x uses ``state_modifier`` for the system prompt (``prompt`` is newer).
    return create_react_agent(
        model or _build_llm(model_name), tools or ALL_TOOLS,
        state_modifier=system_prompt or SYSTEM_PROMPT,
    )


def run_ticket(ticket_id: str, ticket_text: str) -> dict[str, Any]:
    """Run the agent on one ticket.

    Returns a dict with the final decision text and the ordered list of tool calls the
    agent made (so callers can see it behaved dynamically).
    """
    from langchain_core.messages import HumanMessage

    agent = build_agent()
    user_msg = HumanMessage(content=f"Ticket {ticket_id}:\n{ticket_text}")
    result = agent.invoke({"messages": [user_msg]})
    messages = result["messages"]

    tool_calls: list[dict[str, Any]] = []
    for msg in messages:
        for call in getattr(msg, "tool_calls", None) or []:
            tool_calls.append({"tool": call["name"], "args": call["args"]})

    final = messages[-1].content
    return {"ticket_id": ticket_id, "decision": final, "tool_calls": tool_calls}
