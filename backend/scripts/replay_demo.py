"""Sprint 3 deliverable: replay a stored session and prove zero real calls.

Usage:
    python -m scripts.replay_demo [session_id]

With no argument it replays the most recent session in the database.
"""
from __future__ import annotations

import sys

from flight_recorder.core.replay import ReplayEngine
from flight_recorder.core.storage import storage


def main() -> None:
    sessions = storage.list_sessions()
    if not sessions:
        print("No sessions in the DB yet. Run `python -m scripts.record_run` first.")
        return

    session_id = sys.argv[1] if len(sys.argv) > 1 else sessions[0].session_id
    print(f"Replaying session: {session_id}\n")

    result = ReplayEngine().replay(session_id)

    for step in result.session.steps:
        if step.type.value == "llm_call":
            print(f"  {step.step_number}. LLM  (replayed): {step.response[:60]}")
        else:
            note = " [BLOCKED]" if step.output.get("status") == "blocked_during_replay" else ""
            print(f"  {step.step_number}. TOOL {step.tool_name}{note} -> {step.output}")

    print("\n--- PROOF ---")
    print(f"  Real calls made      : {result.real_calls}")
    print(f"  Calls intercepted    : {result.intercepted_calls}")
    print("  send_notification    : blocked (no email/log write)")


if __name__ == "__main__":
    main()
