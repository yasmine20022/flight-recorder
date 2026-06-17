"""Sprint 5 deliverable: a What-If divergence from a stored session.

Overrides get_user_info to point at a different owner, re-runs the agent live, and prints
the original vs new decision side by side.

Usage:
    python -m scripts.whatif_demo [session_id]
"""
from __future__ import annotations

import sys

from flight_recorder.core.whatif import run_whatif
from flight_recorder.core.storage import storage


def _decision(session):
    for step in reversed(session.steps):
        if step.type.value == "llm_call" and "decision" in (step.response or "").lower():
            return step.response
    return session.steps[-1].response if session.steps else "—"


def main() -> None:
    sessions = storage.list_sessions()
    if not sessions:
        print("No sessions yet. Run `python -m scripts.record_run` first.")
        return

    session_id = sys.argv[1] if len(sys.argv) > 1 else sessions[0].session_id
    new_owner = {
        "found": True,
        "name": "Grace Kim",
        "email": "grace.kim@corp.example",
        "team": "Security",
        "role": "Security Analyst",
    }

    print(f"Diverging session {session_id}: overriding get_user_info -> Grace Kim (Security)\n")
    result = run_whatif(session_id, "get_user_info", new_owner)

    print("ORIGINAL decision:")
    print(f"  {_decision(result.original).strip()}\n")
    print("WHAT-IF decision (re-run live):")
    print(f"  {_decision(result.whatif).strip()}")


if __name__ == "__main__":
    main()
