"""End-to-end agent tests that hit the real Groq LLM.

These are skipped automatically when no Groq key is configured (env var or backend/.env),
so the suite still passes in CI / offline. When a key is present they prove the agent
genuinely reasons and routes *differently* for different tickets (i.e. it is not static).
"""
from __future__ import annotations

import groq
import pytest

from flight_recorder.agent.graph import run_ticket
from flight_recorder.config import settings

pytestmark = pytest.mark.skipif(
    not settings.groq_api_key,
    reason="No Groq API key configured; skipping live LLM tests.",
)


def _run_or_skip(ticket_id: str, text: str) -> dict:
    """Run the agent, but skip (not fail) if the free Groq quota is exhausted."""
    try:
        return run_ticket(ticket_id, text)
    except groq.RateLimitError as exc:  # daily token budget hit — environmental, not a bug
        pytest.skip(f"Groq free-tier rate limit reached: {exc}")


def test_agent_handles_vpn_ticket_end_to_end():
    result = _run_or_skip(
        "JSM-T1",
        "Cannot connect to the corporate VPN, 'authentication timeout' on Windows 11.",
    )
    calls = result["tool_calls"]
    tools_used = [c["tool"] for c in calls]
    # It must actually use tools (not answer from thin air)...
    assert "search_kb" in tools_used
    assert "get_user_info" in tools_used
    assert "send_notification" in tools_used
    # ...and reach a structured decision.
    assert "DECISION" in result["decision"].upper()

    # Grounding: the notification must ultimately reach the real corp.example address the
    # agent looked up. The defensive guard rejects any fabricated email, so the final
    # send_notification call must use a real one.
    notifies = [c for c in calls if c["tool"] == "send_notification"]
    assert notifies[-1]["args"]["user"].endswith("@corp.example")


def test_agent_routes_two_tickets_differently():
    vpn = _run_or_skip("JSM-T2", "VPN authentication timeout, cannot reach the tunnel.")
    db = _run_or_skip("JSM-T3", "Our app reports 'database connection refused' after deploy.")

    vpn_kb = [c for c in vpn["tool_calls"] if c["tool"] == "search_kb"]
    db_kb = [c for c in db["tool_calls"] if c["tool"] == "search_kb"]
    assert vpn_kb and db_kb
    # Different problems -> different knowledge-base queries: proof it is not static.
    assert vpn_kb[0]["args"] != db_kb[0]["args"]
