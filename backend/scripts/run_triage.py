"""Proof that the agent is NOT static: run it on several different tickets and watch it
route each one differently (different KB article, history, owner, notification).

Usage:
    python -m scripts.run_triage
"""
from __future__ import annotations

from flight_recorder.agent.graph import run_ticket

TICKETS = [
    ("JSM-2847", "Cannot connect to the corporate VPN, error 'authentication timeout' on Windows 11."),
    ("JSM-2901", "My account is locked, I typed my password wrong too many times and now I can't sign in."),
    ("JSM-2950", "The shared office printer shows offline and nobody on the floor can print."),
    ("JSM-2977", "Our internal app says 'database connection refused' since the last deployment."),
]


def main() -> None:
    for ticket_id, text in TICKETS:
        print("=" * 78)
        print(f"{ticket_id}: {text}")
        result = run_ticket(ticket_id, text)
        tools = " -> ".join(c["tool"] for c in result["tool_calls"]) or "(none)"
        print(f"  tools: {tools}")
        print(f"  {result['decision'].strip()}")
    print("=" * 78)


if __name__ == "__main__":
    main()
