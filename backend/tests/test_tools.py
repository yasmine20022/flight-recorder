"""Deterministic tests for the four simulated tools.

These run with no network and no LLM. They prove the tools are *data-driven* — different
inputs produce different, correct lookups — which is what makes the agent non-static.
"""
from __future__ import annotations

from pathlib import Path

from flight_recorder.agent import tools
from flight_recorder.agent.tools import (
    get_user_info,
    query_db,
    search_kb,
    send_notification,
)


# LangChain tools are invoked via .invoke({...}); these helpers keep tests readable.
def _search(query: str) -> dict:
    return search_kb.invoke({"query": query})


def _db(category: str) -> dict:
    return query_db.invoke({"category": category})


def _user(team: str) -> dict:
    return get_user_info.invoke({"team_name": team})


# --- search_kb ---

def test_search_kb_routes_vpn_and_password_to_different_articles():
    vpn = _search("vpn authentication timeout windows")
    pwd = _search("account locked cannot sign in password")
    assert vpn["found"] and pwd["found"]
    assert vpn["id"] != pwd["id"]  # not static: different query -> different article
    assert vpn["category"] == "Network"
    assert pwd["category"] == "Identity & Access"


def test_search_kb_no_match_returns_not_found():
    res = _search("xyzzy unrelated gibberish")
    assert res["found"] is False


# --- query_db ---

def test_query_db_returns_only_matching_category():
    res = _db("Network")
    assert res["count"] >= 1
    assert all(t["ticket_id"].startswith("JSM-") for t in res["tickets"])
    # Every returned ticket really is in that category history.
    network_summaries = {t["summary"] for t in res["tickets"]}
    assert any("VPN" in s for s in network_summaries)


def test_query_db_unknown_category_is_empty():
    res = _db("Astrophysics")
    assert res["count"] == 0
    assert res["tickets"] == []


# --- get_user_info ---

def test_get_user_info_exact_team():
    res = _user("Database")
    assert res["found"] is True
    assert res["email"] == "elena.rossi@corp.example"


def test_get_user_info_falls_back_to_helpdesk():
    res = _user("Nonexistent Team")
    assert res["found"] is False
    assert res.get("fallback") is True
    assert res["team"] == "Helpdesk"


# --- send_notification (side effect, redirected to a temp file) ---

def test_send_notification_writes_to_log(tmp_path: Path, monkeypatch):
    log = tmp_path / "notifications.log"
    monkeypatch.setattr(tools, "NOTIFICATIONS_LOG", log)

    res = send_notification.invoke(
        {"user": "alice.martin@corp.example", "message": "Ticket JSM-1 assigned (High)."}
    )

    assert res["status"] == "sent"
    assert res["to"] == "alice.martin@corp.example"
    contents = log.read_text(encoding="utf-8")
    assert "alice.martin@corp.example" in contents
    assert "Ticket JSM-1 assigned" in contents


def test_send_notification_rejects_unknown_recipient(tmp_path: Path, monkeypatch):
    log = tmp_path / "notifications.log"
    monkeypatch.setattr(tools, "NOTIFICATIONS_LOG", log)

    res = send_notification.invoke(
        {"user": "john.doe@example.com", "message": "hi"}  # fabricated address
    )

    assert res["status"] == "rejected"
    assert not log.exists()  # nothing was written for a bogus recipient
