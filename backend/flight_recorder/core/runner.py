"""Orchestrates a *recorded* agent run: attach the recorder, run, persist the trace.

This is the bridge between the agent (Sprint 1) and the storage (Sprint 0). Note that the
agent itself is untouched — interception happens purely through the callback handler passed
in ``config``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from flight_recorder.core.recorder import TraceRecorder
from flight_recorder.core.schemas import Session, SessionMode, SessionStatus, StepType
from flight_recorder.core.storage import Storage, storage as default_storage


def _write_jira_labels(issue_key: str, steps) -> None:
    """After a run, tag the real Jira issue with the routed team + priority (best-effort)."""
    from flight_recorder.config import settings

    if not settings.jira_enabled:
        return
    from flight_recorder.agent import jira_client
    from flight_recorder.core.ai_common import parse_decision

    team = None
    for s in steps:
        if s.type == StepType.TOOL_CALL and s.tool_name == "get_user_info":
            team = (s.input or {}).get("team_name") or team
    decision = next((s.response for s in reversed(steps)
                     if s.type == StepType.LLM_CALL and "decision" in (s.response or "").lower()), "")
    labels = ["ai-triaged"]
    if team:
        labels.append(jira_client.label_for(team))
    prio = parse_decision(decision).get("priority")
    if prio:
        labels.append(prio)
    try:
        jira_client.add_labels(issue_key, labels)
    except jira_client.JiraError:
        pass


def new_session_id() -> str:
    """Human-readable, collision-resistant session id, e.g. run_2026-06-17_4f9c2a."""
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"run_{day}_{uuid4().hex[:6]}"


def record_ticket(
    ticket_id: str,
    ticket_text: str,
    *,
    store: Optional[Storage] = None,
    agent: Any = None,
    model_name: Optional[str] = None,
) -> Session:
    """Run the agent on a ticket while capturing every step, then save the trace.

    ``agent`` and ``store`` are injectable for testing; by default the real triage agent
    and the default SQLite storage are used. ``model_name`` selects which Groq model to run.
    """
    from langchain_core.messages import HumanMessage

    store = store or default_storage
    if agent is None:
        from flight_recorder.agent.graph import build_agent

        agent = build_agent(model_name=model_name)

    from flight_recorder.agent import tools as agent_tools

    recorder = TraceRecorder()
    session = Session(
        session_id=new_session_id(),
        ticket_id=ticket_id,
        ticket_text=ticket_text,
        status=SessionStatus.RUNNING,
        mode=SessionMode.LIVE,
    )

    # Tell the tools which Jira issue this run is about (used by send_notification when a
    # real Jira is configured); reset afterwards so it never leaks into another run.
    token = agent_tools.set_current_issue(ticket_id)
    try:
        agent.invoke(
            {"messages": [HumanMessage(content=f"Ticket {ticket_id}:\n{ticket_text}")]},
            config={"callbacks": [recorder]},
        )
        session.status = SessionStatus.COMPLETED
    except Exception:
        session.status = SessionStatus.ERROR
        session.steps = recorder.steps
        store.save_session(session)
        raise
    finally:
        agent_tools.reset_current_issue(token)

    session.steps = recorder.steps
    _write_jira_labels(ticket_id, recorder.steps)  # real labels written to Jira per run
    store.save_session(session)
    return session
