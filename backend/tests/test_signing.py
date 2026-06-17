"""Tests for cryptographic trace signing (Bonus 8)."""
from __future__ import annotations

from flight_recorder.core.schemas import Session, Step, StepType
from flight_recorder.core.signing import digest, sign, signature_info, verify


def _session() -> Session:
    return Session(
        session_id="s1", ticket_id="JSM-1", ticket_text="vpn",
        created_at="2026-06-17T09:00:00Z",
        steps=[
            Step(step_number=1, type=StepType.LLM_CALL, prompt="p", response="r"),
            Step(step_number=2, type=StepType.TOOL_CALL, tool_name="search_kb",
                 input={"query": "vpn"}, output={"found": True}),
        ],
    )


def test_sign_then_verify_succeeds():
    s = _session()
    assert verify(s, sign(s)) is True


def test_signature_is_deterministic():
    assert sign(_session()) == sign(_session())


def test_tampering_a_step_breaks_signature():
    s = _session()
    signature = sign(s)
    # Mutate a recorded value — exactly what an attacker editing the DB would do.
    s.steps[1].output = {"found": False}
    assert verify(s, signature) is False


def test_wrong_secret_fails_verification():
    s = _session()
    signature = sign(s, secret="secret-A")
    assert verify(s, signature, secret="secret-B") is False


def test_signature_info_self_consistent():
    info = signature_info(_session())
    assert info.algorithm == "HMAC-SHA256"
    assert info.verified is True
    assert info.digest == digest(_session())
    assert len(info.step_hashes) == 2
