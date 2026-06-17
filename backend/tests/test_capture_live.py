"""Live end-to-end capture test: run the real agent, prove the trace is captured & stored.

Skipped without a Groq key; skips (not fails) when the free quota is exhausted.
"""
from __future__ import annotations

import groq
import pytest

from flight_recorder.core.runner import record_ticket
from flight_recorder.core.schemas import SessionStatus, StepType
from flight_recorder.core.storage import Storage
from flight_recorder.config import settings

pytestmark = pytest.mark.skipif(
    not settings.groq_api_key,
    reason="No Groq API key configured; skipping live capture test.",
)


def test_live_run_is_captured_and_stored(tmp_storage: Storage):
    try:
        session = record_ticket(
            "JSM-CAP",
            "Cannot connect to the corporate VPN, 'authentication timeout' on Windows 11.",
            store=tmp_storage,
        )
    except groq.RateLimitError as exc:
        pytest.skip(f"Groq free-tier rate limit reached: {exc}")

    assert session.status == SessionStatus.COMPLETED
    # A real triage run produces multiple interleaved steps.
    assert len(session.steps) >= 4
    types = {s.type for s in session.steps}
    assert StepType.LLM_CALL in types
    assert StepType.TOOL_CALL in types

    # The trace is genuinely persisted and reloadable.
    reloaded = tmp_storage.get_session(session.session_id)
    assert reloaded is not None
    assert len(reloaded.steps) == len(session.steps)

    # Captured LLM steps carry the exact prompt; tool steps carry name + io.
    llm_steps = [s for s in reloaded.steps if s.type == StepType.LLM_CALL]
    tool_steps = [s for s in reloaded.steps if s.type == StepType.TOOL_CALL]
    assert all(s.prompt for s in llm_steps)
    assert any(s.tool_name == "search_kb" for s in tool_steps)
