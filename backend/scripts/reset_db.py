"""Reset the trace DB to a clean, predictable state for demos (no LLM, no tokens).

Wipes all sessions and re-seeds the single curated demo session.

Usage:
    python -m scripts.reset_db
"""
from __future__ import annotations

from flight_recorder.core.storage import storage
from scripts.seed_db import DEMO_SESSION


def main() -> None:
    storage.clear_all()
    storage.save_session(DEMO_SESSION)
    print(f"[OK] DB reset. Seeded 1 clean demo session: {DEMO_SESSION.session_id} "
          f"({len(DEMO_SESSION.steps)} steps).")


if __name__ == "__main__":
    main()
