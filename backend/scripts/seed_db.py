"""Seed the SQLite database with one demo session.

This is the same trace the frontend mock (frontend/src/mock_data.json) renders, so the
UI looks identical whether it reads the mock or the live API.

Usage:
    python -m scripts.seed_db
"""
from __future__ import annotations

from flight_recorder.core.schemas import (
    Session,
    SessionMode,
    SessionStatus,
    Step,
    StepType,
)
from flight_recorder.core.storage import storage

DEMO_SESSION = Session(
    session_id="run_2026-06-17_001",
    ticket_id="JSM-2847",
    ticket_text=(
        "Cannot connect to the corporate VPN since this morning. "
        "It fails with error 'authentication timeout' on Windows 11."
    ),
    status=SessionStatus.COMPLETED,
    mode=SessionMode.LIVE,
    created_at="2026-06-17T09:00:00Z",
    synthetic=True,  # hand-written demo data — never produced by a real LLM
    steps=[
        Step(
            step_number=1,
            type=StepType.LLM_CALL,
            timestamp="2026-06-17T09:00:00Z",
            duration_ms=420,
            prompt=(
                "You are a Jira triage assistant. Ticket JSM-2847: Cannot connect to the "
                "corporate VPN... Decide the first action."
            ),
            response="I will first search the knowledge base for the VPN timeout error.",
        ),
        Step(
            step_number=2,
            type=StepType.TOOL_CALL,
            timestamp="2026-06-17T09:00:01Z",
            duration_ms=15,
            tool_name="search_kb",
            input={"query": "VPN authentication timeout Windows 11"},
            output={"article_id": "KB-12", "title": "Resolving VPN auth timeouts"},
        ),
        Step(
            step_number=3,
            type=StepType.TOOL_CALL,
            timestamp="2026-06-17T09:00:02Z",
            duration_ms=22,
            tool_name="get_user_info",
            input={"team_name": "Network"},
            output={"name": "Alice Martin", "email": "alice.martin@corp.example"},
        ),
        Step(
            step_number=4,
            type=StepType.LLM_CALL,
            timestamp="2026-06-17T09:00:03Z",
            duration_ms=510,
            prompt="Given KB-12 and the Network team owner Alice Martin, decide priority and assignee.",
            response="Priority: High. Assign to Alice Martin (Network team). Notify her.",
        ),
        Step(
            step_number=5,
            type=StepType.TOOL_CALL,
            timestamp="2026-06-17T09:00:04Z",
            duration_ms=8,
            tool_name="send_notification",
            input={"user": "alice.martin@corp.example", "message": "Ticket JSM-2847 assigned to you (High)."},
            output={"status": "written_to_log"},
        ),
    ],
)


def main() -> None:
    storage.save_session(DEMO_SESSION)
    print(f"Seeded demo session: {DEMO_SESSION.session_id} "
          f"({len(DEMO_SESSION.steps)} steps) into {storage.db_path}")


if __name__ == "__main__":
    main()
