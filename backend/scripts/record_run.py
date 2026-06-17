"""Sprint 2 deliverable: run the agent live, capture the trace, store it, print it.

Usage:
    python -m scripts.record_run
"""
from __future__ import annotations

from flight_recorder.core.runner import record_ticket
from flight_recorder.core.storage import storage

TICKET_ID = "JSM-2847"
TICKET_TEXT = (
    "Cannot connect to the corporate VPN since this morning. "
    "It fails with error 'authentication timeout' on Windows 11."
)


def main() -> None:
    print("Running and recording the agent (this hits the LLM, ~1-2 min)...\n")
    session = record_ticket(TICKET_ID, TICKET_TEXT)

    print(f"Session {session.session_id} stored — {len(session.steps)} steps captured:\n")
    for step in session.steps:
        if step.type.value == "llm_call":
            print(f"  {step.step_number}. LLM  ({step.duration_ms} ms): {step.response[:70]}")
        else:
            print(f"  {step.step_number}. TOOL {step.tool_name}({step.input}) "
                  f"-> {step.output} ({step.duration_ms} ms)")

    # Prove it is queryable from storage, just like the API would read it.
    reloaded = storage.get_session(session.session_id)
    print(f"\n[OK] Reloaded from DB: {reloaded.session_id} with {len(reloaded.steps)} steps.")


if __name__ == "__main__":
    main()
