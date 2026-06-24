"""Proxy-based deterministic replay — Sprint A.

Unlike :mod:`flight_recorder.core.replay` (which re-emits the stored steps), this engine
**actually re-runs the agent**, but with the LLM swapped for the proxy in *replay* mode:

  * the agent's reasoning calls are served from the recorded ``ai_message`` decisions,
  * the real tools execute locally (deterministic lookups), and
  * ``send_notification`` is pinned to a blocked result, so no notification is ever sent.

The result is a freshly executed trajectory that is identical to the original, produced with
**zero real LLM calls and zero side effects** — the strongest possible proof of determinism.
"""
from __future__ import annotations

from dataclasses import dataclass

from flight_recorder.core.schemas import (
    Session,
    SessionMode,
    SessionStatus,
    StepType,
)
from flight_recorder.core.storage import Storage, storage as default_storage

# Pinned output for the one side-effecting tool while replaying.
_BLOCKED_NOTIFICATION = {"status": "blocked_during_replay", "note": "no notification sent"}


@dataclass
class ProxyReplayResult:
    session: Session        # the re-executed trajectory (mode = "replay")
    real_calls: int         # real LLM/provider calls — always 0
    intercepted_calls: int  # recorded LLM decisions served from the trace


def replay_through_proxy(session_id: str, *, store: Storage | None = None) -> ProxyReplayResult:
    """Re-run ``session_id``'s agent with the proxy serving cached LLM responses."""
    from langchain_core.messages import HumanMessage, messages_from_dict
    from langgraph.prebuilt import create_react_agent

    from flight_recorder.agent.graph import SYSTEM_PROMPT
    from flight_recorder.agent.overrides import apply_overrides
    from flight_recorder.agent.tools import ALL_TOOLS
    from flight_recorder.core.proxy import ProxiedChatModel, ReplayState
    from flight_recorder.core.recorder import TraceRecorder

    store = store or default_storage
    original = store.get_session(session_id)
    if original is None:
        raise KeyError(session_id)

    # Reconstruct the recorded LLM decisions (with their tool calls) in order.
    recorded = [
        messages_from_dict([step.ai_message])[0]
        for step in original.steps
        if step.type == StepType.LLM_CALL and step.ai_message
    ]
    if not recorded:
        raise ValueError(
            "This session was recorded before proxy-replay support; re-record it to replay "
            "through the proxy."
        )

    state = ReplayState(recorded)
    proxy = ProxiedChatModel(inner=None, mode="replay", replay_state=state)
    tools = apply_overrides(ALL_TOOLS, {"send_notification": _BLOCKED_NOTIFICATION})
    agent = create_react_agent(proxy, tools, state_modifier=SYSTEM_PROMPT)

    recorder = TraceRecorder()
    agent.invoke(
        {"messages": [HumanMessage(content=f"Ticket {original.ticket_id}:\n{original.ticket_text}")]},
        config={"callbacks": [recorder]},
    )

    replayed = Session(
        session_id=f"{original.session_id}__proxyreplay",
        ticket_id=original.ticket_id,
        ticket_text=original.ticket_text,
        status=SessionStatus.COMPLETED,
        mode=SessionMode.REPLAY,
        steps=recorder.steps,
    )
    # Persist it so the replay is a first-class session: anomalies, signature, PDF export
    # and What-If all read it from storage, exactly like a recorded run.
    store.save_session(replayed)
    # real_calls is 0 by construction: the proxy has no provider and never goes to network.
    return ProxyReplayResult(session=replayed, real_calls=0, intercepted_calls=state.index)


def replay_live(session_id: str, *, store: Storage | None = None) -> ProxyReplayResult:
    """Re-run ``session_id``'s agent while **actually re-calling the LLM**.

    Unlike :func:`replay_through_proxy` (which serves cached decisions), this re-flies the
    agent for real: it runs the live triage agent against the Groq provider exactly as the
    original recording did. Side effects stay blocked — ``send_notification`` is pinned — so
    it is still a *safe* replay (real reasoning, zero real notifications).

    It does not route through the proxy: the agent talks to the provider directly, just like
    :func:`flight_recorder.core.runner.record_ticket`, so each LLM call is recorded once.
    """
    from langchain_core.messages import HumanMessage

    from flight_recorder.agent import tools as agent_tools
    from flight_recorder.agent.graph import build_agent
    from flight_recorder.agent.overrides import apply_overrides
    from flight_recorder.agent.tools import ALL_TOOLS
    from flight_recorder.core.recorder import TraceRecorder

    store = store or default_storage
    original = store.get_session(session_id)
    if original is None:
        raise KeyError(session_id)

    # Re-use whichever model the original run recorded, so the re-flight is comparable.
    model_name = next(
        (s.model for s in original.steps if s.type == StepType.LLM_CALL and s.model), None
    )

    tools = apply_overrides(ALL_TOOLS, {"send_notification": _BLOCKED_NOTIFICATION})
    agent = build_agent(tools=tools, model_name=model_name)

    recorder = TraceRecorder()
    token = agent_tools.set_current_issue(original.ticket_id)
    try:
        agent.invoke(
            {"messages": [HumanMessage(content=f"Ticket {original.ticket_id}:\n{original.ticket_text}")]},
            config={"callbacks": [recorder]},
        )
    finally:
        agent_tools.reset_current_issue(token)

    # Every reasoning step hit the real provider this time; only the notification was blocked.
    real_calls = sum(1 for s in recorder.steps if s.type == StepType.LLM_CALL)
    replayed = Session(
        session_id=f"{original.session_id}__livereplay",
        ticket_id=original.ticket_id,
        ticket_text=original.ticket_text,
        status=SessionStatus.COMPLETED,
        mode=SessionMode.REPLAY,
        steps=recorder.steps,
    )
    # Persist it so the replay gets the same first-class treatment as a recorded run:
    # anomalies, signature, PDF export and What-If all read the session from storage.
    store.save_session(replayed)
    return ProxyReplayResult(session=replayed, real_calls=real_calls, intercepted_calls=0)
