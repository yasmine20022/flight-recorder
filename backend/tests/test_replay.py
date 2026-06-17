"""Tests for the deterministic replay engine (no LLM, no network)."""
from __future__ import annotations

from pathlib import Path

from flight_recorder.agent import tools
from flight_recorder.core.replay import ReplayEngine
from flight_recorder.core.schemas import (
    Session,
    SessionMode,
    Step,
    StepType,
)
from flight_recorder.core.storage import Storage


def _recorded_session(session_id: str = "run_1") -> Session:
    return Session(
        session_id=session_id,
        ticket_id="JSM-1",
        ticket_text="VPN broken",
        steps=[
            Step(step_number=1, type=StepType.LLM_CALL, prompt="p1", response="search the kb"),
            Step(
                step_number=2,
                type=StepType.TOOL_CALL,
                tool_name="search_kb",
                input={"query": "vpn"},
                output={"id": "KB-12"},
            ),
            Step(step_number=3, type=StepType.LLM_CALL, prompt="p2", response="decision"),
            Step(
                step_number=4,
                type=StepType.TOOL_CALL,
                tool_name="send_notification",
                input={"user": "alice.martin@corp.example", "message": "assigned"},
                output={"status": "sent"},
            ),
        ],
    )


def test_replay_counters_zero_real_all_intercepted(tmp_storage: Storage):
    tmp_storage.save_session(_recorded_session())
    result = ReplayEngine(store=tmp_storage).replay("run_1")

    assert result.real_calls == 0
    assert result.intercepted_calls == 4
    assert result.session.mode == SessionMode.REPLAY


def test_replay_reinjects_recorded_values(tmp_storage: Storage):
    tmp_storage.save_session(_recorded_session())
    steps = ReplayEngine(store=tmp_storage).replay("run_1").session.steps

    # LLM responses and tool outputs come straight from the recording.
    assert steps[0].response == "search the kb"
    assert steps[1].output == {"id": "KB-12"}


def test_replay_blocks_side_effect_tool(tmp_storage: Storage):
    tmp_storage.save_session(_recorded_session())
    steps = ReplayEngine(store=tmp_storage).replay("run_1").session.steps

    notify = steps[3]
    assert notify.tool_name == "send_notification"
    assert notify.output["status"] == "blocked_during_replay"
    assert notify.output["would_have_notified"] == "alice.martin@corp.example"


def test_replay_never_executes_real_tools_or_writes_log(
    tmp_storage: Storage, tmp_path: Path, monkeypatch
):
    tmp_storage.save_session(_recorded_session())

    # Point the notification log at a temp file and fail loudly if anything tries to call
    # the real send_notification during replay.
    log = tmp_path / "notifications.log"
    monkeypatch.setattr(tools, "NOTIFICATIONS_LOG", log)

    called = {"n": 0}
    original_func = tools.send_notification.func

    def spy(*args, **kwargs):
        called["n"] += 1
        return original_func(*args, **kwargs)

    monkeypatch.setattr(tools.send_notification, "func", spy)

    ReplayEngine(store=tmp_storage).replay("run_1")

    assert called["n"] == 0          # the real tool was never invoked
    assert not log.exists()          # and nothing was written to the notification log


def test_replay_unknown_session_raises(tmp_storage: Storage):
    import pytest

    with pytest.raises(KeyError):
        ReplayEngine(store=tmp_storage).replay("does-not-exist")
