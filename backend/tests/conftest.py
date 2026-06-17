"""Shared pytest fixtures."""
from __future__ import annotations

from pathlib import Path

import pytest

from flight_recorder.core.storage import Storage


@pytest.fixture()
def tmp_storage(tmp_path: Path) -> Storage:
    """A Storage backed by a throwaway SQLite file (no shared state between tests)."""
    return Storage(db_path=tmp_path / "test.db")
