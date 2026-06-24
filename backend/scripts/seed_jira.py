"""Seed a REAL Jira project with lots of demo tickets for the Flight Recorder demo.

Loads the full local dataset (backend/data/tickets_seed.json, ~34 tickets across every
category), creates each as a real Jira issue labelled by category, and transitions the
resolved ones to Done so query_db has rich real history. Also creates the JSM-001 payments
ticket you triage live.

Usage:
    python -m scripts.seed_jira            # seed everything
    python -m scripts.seed_jira --demo     # only the payments demo ticket
"""
from __future__ import annotations

import json
import sys

from flight_recorder.config import settings
from flight_recorder.agent import jira_client
from flight_recorder.agent.data_loader import TICKETS_SEED_FILE

DEMO_SUMMARY = "Erreur 500 sur /api/payments en production - les clients ne peuvent plus payer"
RESOLVED = {"Resolved", "Done", "Closed"}


def _resolve_project() -> str:
    key = settings.jira_project_key
    if key:
        try:
            jira_client._get(f"/rest/api/3/project/{key}")
            return key
        except jira_client.JiraError:
            pass
    projects = jira_client._get("/rest/api/3/project/search", params={"maxResults": 1})
    values = projects.get("values", [])
    if not values:
        raise SystemExit("No Jira project found. Create one first.")
    return values[0]["key"]


def _pick_issue_type(project: str) -> str:
    proj = jira_client._get(f"/rest/api/3/project/{project}")
    types = [t for t in proj.get("issueTypes", []) if not t.get("subtask")]
    for t in types:
        if t["name"] not in ("Epic", "Feature"):
            return t["name"]
    return types[0]["name"]


def _create(project: str, issuetype: str, reporter_id: str, summary: str, labels=None) -> str:
    fields = {
        "project": {"key": project},
        "summary": summary,
        "issuetype": {"name": issuetype},
        "reporter": {"id": reporter_id},
    }
    if labels:
        fields["labels"] = labels
    return jira_client._post("/rest/api/3/issue", {"fields": fields})["key"]


def _transition_to_done(key: str) -> str | None:
    data = jira_client._get(f"/rest/api/3/issue/{key}/transitions")
    for t in data.get("transitions", []):
        if (t.get("to", {}).get("statusCategory", {}) or {}).get("key") == "done":
            jira_client._post(f"/rest/api/3/issue/{key}/transitions", {"transition": {"id": t["id"]}})
            return t["to"]["name"]
    return None


def main() -> None:
    if not settings.jira_enabled:
        raise SystemExit("Jira is not configured. Fill JIRA_* in backend/.env first.")
    demo_only = "--demo" in sys.argv

    me = jira_client.whoami()
    reporter_id = me["accountId"]
    project = _resolve_project()
    issuetype = _pick_issue_type(project)
    print(f"Seeding project {project} (issue type: {issuetype}) as {me.get('displayName')}\n")

    created, skipped = 0, 0
    if not demo_only:
        seed = json.loads(TICKETS_SEED_FILE.read_text(encoding="utf-8"))
        for i, t in enumerate(seed, 1):
            try:
                label = jira_client.label_for(t["category"])
                key = _create(project, issuetype, reporter_id, t["summary"], labels=[label])
                status = "open"
                if t.get("status") in RESOLVED:
                    try:
                        status = _transition_to_done(key) or "open"
                    except jira_client.JiraError:
                        status = "open (transition failed)"
                created += 1
                print(f"  [{i:2}/{len(seed)}] {key}  ({t['category']:>18})  {status:>10}  {t['summary'][:40]}")
            except jira_client.JiraError as exc:
                skipped += 1
                print(f"  [{i:2}/{len(seed)}] SKIPPED ({t['category']}): {str(exc)[:60]}")

    try:
        demo_key = _create(project, issuetype, reporter_id, DEMO_SUMMARY, labels=["Backend"])
        print(f"\nSeeded {created} past tickets ({skipped} skipped).")
        print(f">>> DEMO TICKET TO TRIAGE: {demo_key}")
        print(f"    In the UI, set Ticket ID = {demo_key} and paste the text:")
        print(f'    "{DEMO_SUMMARY}"')
    except jira_client.JiraError as exc:
        print(f"\n[FAIL] Could not create the demo ticket: {exc}")


if __name__ == "__main__":
    main()
