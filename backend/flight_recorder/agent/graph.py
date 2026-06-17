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

SYSTEM_PROMPT = """You are an IT service-desk triage agent for Jira tickets.

For every ticket, follow this process using the tools available to you:
1. Call search_kb with keywords from the ticket to find the most relevant knowledge article.
2. Use the article's category to call query_db and review how similar past tickets were handled.
3. Call get_user_info with the team that should own this issue, to find the assignee.
4. Decide a priority (Low, Medium, or High) and the assignee.
5. Call send_notification to inform the assignee. The `user` argument MUST be exactly the
   `email` value returned by get_user_info in step 3 — never make up an email address.

You are NOT finished until send_notification has returned status "sent". Never write your
final answer before that — if you skipped a step, go back and call the missing tool.

Only after send_notification succeeds, reply with a short final decision in exactly this form:
DECISION: priority=<Low|Medium|High>; assignee=<name> <email>; reason=<one sentence>.

Only use information returned by the tools. Do not invent article ids, users, emails, or
history. Every email you use must come verbatim from a get_user_info result."""


def _build_llm():
    """Create the Groq chat model used by the agent."""
    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Copy backend/.env.example to backend/.env and add "
            "your free key from https://console.groq.com"
        )
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=settings.groq_model,
        temperature=0,  # determinism matters for recording/replay
        api_key=settings.groq_api_key,
    )


def build_agent(tools=None):
    """Compile and return the ReAct triage agent (LLM + tools).

    ``tools`` defaults to the real toolset; the What-If engine passes an overridden set.
    """
    from langgraph.prebuilt import create_react_agent

    # langgraph 0.2.x uses ``state_modifier`` for the system prompt (``prompt`` is newer).
    return create_react_agent(_build_llm(), tools or ALL_TOOLS, state_modifier=SYSTEM_PROMPT)


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
