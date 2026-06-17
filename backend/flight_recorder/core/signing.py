"""Cryptographic trace signing — Bonus 8.

Makes a recorded trace tamper-evident for audit:

  * Each step is hashed into a **hash chain** (step_i depends on step_{i-1}), so changing any
    step changes every hash after it.
  * The chain tip + session metadata form a SHA-256 **digest**.
  * The digest is signed with **HMAC-SHA256** using a server secret.

``verify`` recomputes everything; if a single byte of the trace changed, the signature no
longer matches. Pure and deterministic.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Optional

from flight_recorder.config import settings
from flight_recorder.core.schemas import Session, SignatureInfo

_EMPTY = hashlib.sha256(b"").hexdigest()


def _canonical(step) -> str:
    return json.dumps(step.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def step_hashes(session: Session) -> list[str]:
    """Per-step hash chain. h_i = sha256(h_{i-1} + canonical(step_i))."""
    hashes: list[str] = []
    prev = _EMPTY
    for step in session.steps:
        prev = hashlib.sha256((prev + _canonical(step)).encode("utf-8")).hexdigest()
        hashes.append(prev)
    return hashes


def digest(session: Session) -> str:
    """SHA-256 digest binding the chain tip to the session metadata."""
    chain = step_hashes(session)
    tip = chain[-1] if chain else _EMPTY
    meta = json.dumps(
        {
            "session_id": session.session_id,
            "ticket_id": session.ticket_id,
            "ticket_text": session.ticket_text,
            "mode": session.mode.value,
            "created_at": session.created_at,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256((meta + tip).encode("utf-8")).hexdigest()


def sign(session: Session, secret: Optional[str] = None) -> str:
    key = (secret or settings.signing_secret).encode("utf-8")
    return hmac.new(key, digest(session).encode("utf-8"), hashlib.sha256).hexdigest()


def verify(session: Session, signature: str, secret: Optional[str] = None) -> bool:
    return hmac.compare_digest(sign(session, secret), signature)


def signature_info(session: Session, secret: Optional[str] = None) -> SignatureInfo:
    sig = sign(session, secret)
    return SignatureInfo(
        digest=digest(session),
        signature=sig,
        verified=verify(session, sig, secret),
        step_hashes=step_hashes(session),
    )
