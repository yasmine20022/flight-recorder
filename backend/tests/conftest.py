"""Shared pytest fixtures."""
from __future__ import annotations

from pathlib import Path

import pytest

from flight_recorder.core.storage import Storage


@pytest.fixture(autouse=True)
def _disable_jira(monkeypatch):
    """Force the local mock for every test so none accidentally hit a real Jira."""
    from flight_recorder.config import settings

    monkeypatch.setattr(settings, "jira_base_url", "", raising=False)
    monkeypatch.setattr(settings, "jira_email", "", raising=False)
    monkeypatch.setattr(settings, "jira_api_token", "", raising=False)


@pytest.fixture()
def tmp_storage(tmp_path: Path) -> Storage:
    """A Storage backed by a throwaway SQLite file (no shared state between tests)."""
    return Storage(db_path=tmp_path / "test.db")
