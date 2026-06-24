"""Verify the real Jira connection is configured and working.

Usage:
    python -m scripts.check_jira
"""
from __future__ import annotations

from flight_recorder.config import settings


def main() -> None:
    if not settings.jira_enabled:
        print("[--] Jira is NOT configured. The agent uses the local mock.")
        print("     Set JIRA_BASE_URL, JIRA_EMAIL and JIRA_API_TOKEN in backend/.env to go live.")
        return

    from flight_recorder.agent import jira_client

    print(f"[..] Connecting to {settings.jira_base_url} as {settings.jira_email} ...")
    try:
        me = jira_client.whoami()
    except jira_client.JiraError as exc:
        print(f"[FAIL] Could not authenticate: {exc}")
        print("       Check the URL, email, and API token.")
        return

    print(f"[OK] Authenticated as: {me.get('displayName')} <{me.get('emailAddress', 'hidden')}>")

    # Probe a real search so you can see live data flow.
    try:
        sample = jira_client.search_past_tickets("Network", limit=3)
        print(f"[OK] Sample search returned {len(sample)} past ticket(s):")
        for t in sample:
            print(f"       {t['ticket_id']} [{t['priority']}/{t['status']}] {t['summary'][:60]}")
    except jira_client.JiraError as exc:
        print(f"[warn] Auth works but search failed: {exc}")


if __name__ == "__main__":
    main()
