"""Deterministic replay engine — Sprint 3.

Replaying a session re-emits its recorded steps **from the stored trace**. It never
instantiates the LLM and never executes a real tool, so:

  * the recorded LLM responses are re-injected (no temperature, no re-divergence),
  * the recorded tool outputs are re-injected (no real lookups),
  * side-effecting tools (send_notification) are explicitly **blocked** — they cannot send.

The proof shown to the user is a pair of counters: real calls = 0, intercepted calls = N.
This is the airplane black-box analogy: you replay the recorded data on a simulator, you
never re-fly the plane.
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

# Tools whose execution would have a real-world effect; never run during replay.
SIDE_EFFECT_TOOLS = {"send_notification"}


@dataclass
class ReplayResult:
    session: Session       # the replayed trajectory (mode = "replay")
    real_calls: int        # calls that actually hit the LLM or a real tool — always 0
    intercepted_calls: int # recorded steps served from the trace instead


class ReplayEngine:
    """Replays a stored session without performing any real call."""

    def __init__(self, store: Storage | None = None) -> None:
        self.store = store or default_storage

    def replay(self, session_id: str) -> ReplayResult:
        original = self.store.get_session(session_id)
        if original is None:
            raise KeyError(session_id)

        real_calls = 0
        intercepted = 0
        replayed_steps = []

        for step in original.steps:
            # Every step is served from the recording — nothing executes for real.
            intercepted += 1
            new_step = step.model_copy(deep=True)

            if step.type == StepType.TOOL_CALL and step.tool_name in SIDE_EFFECT_TOOLS:
                # Make the safety visible in the trace itself.
                new_step.output = {
                    "status": "blocked_during_replay",
                    "would_have_notified": (step.input or {}).get("user"),
                }

            replayed_steps.append(new_step)

        replayed = Session(
            session_id=f"{original.session_id}__replay",
            ticket_id=original.ticket_id,
            ticket_text=original.ticket_text,
            status=SessionStatus.COMPLETED,
            mode=SessionMode.REPLAY,
            steps=replayed_steps,
        )
        return ReplayResult(
            session=replayed,
            real_calls=real_calls,
            intercepted_calls=intercepted,
        )
