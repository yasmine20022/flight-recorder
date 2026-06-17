"""Run the triage agent on a single sample ticket and print its decision + tool calls.

Usage:
    python -m scripts.run_agent
"""
from __future__ import annotations

from flight_recorder.agent.graph import run_ticket

SAMPLE_TICKET_ID = "JSM-2847"
SAMPLE_TICKET_TEXT = (
    "Cannot connect to the corporate VPN since this morning. "
    "It fails with error 'authentication timeout' on Windows 11."
)


def main() -> None:
    print("=== Flight Recorder — triage agent run ===")
    print(f"Ticket: {SAMPLE_TICKET_ID}")
    print(f"Text  : {SAMPLE_TICKET_TEXT}\n")

    result = run_ticket(SAMPLE_TICKET_ID, SAMPLE_TICKET_TEXT)

    print("Tool calls (chosen by the agent):")
    for i, call in enumerate(result["tool_calls"], 1):
        print(f"  {i}. {call['tool']}({call['args']})")
    print(f"\n{result['decision']}")


if __name__ == "__main__":
    main()
