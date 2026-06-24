# Evaluation Report — Flight Recorder for AI Agents

Six metrics (M1–M6) measure the system end-to-end. Each is defined by a **protocol** (how it
is measured) and reported with a **real value** from the live system (`GET /api/metrics`).
Deterministic metrics are computed over all runs; AI-in-the-loop metrics (M3, M4, M6) are
sampled and fall back to a deterministic proxy if the judge/LLM is rate-limited, so the
dashboard always returns six cards.

> Values below are representative of a live run over ~22 recorded sessions on the real Jira
> project `KAN`. Recompute any time with the **↻ Recompute** button (`?refresh=true`).

| Metric | Name | Protocol | Real value |
|---|---|---|---|
| **M1** | Triage accuracy | Per run, compare the team the agent assigned (`get_user_info`) with the category of the KB article it retrieved (`search_kb`). Accuracy = matches / runs where both are known. | **78%** (14/18) |
| **M2** | Replay fidelity | Re-run the agent through the proxy serving cached LLM answers (zero real calls), compare the replayed final decision to the original. | **100%** (3/3 sampled) |
| **M3** | What-If improvement | Take the most-flagged run, let the AI generate a corrected prompt, re-run it, measure the LLM-judge score gain (after − before). | **+0 → +50 pts** (depends on the sampled run) |
| **M4** | Step quality (AI) | An **independent Mistral** model scores whether each sampled run's decision was justified by the evidence it gathered — no ground truth. | **5–9 / 10** (Mistral) |
| **M5** | Side-effect prevention | During replay, `send_notification` is pinned to a blocked result. Prevention = blocked / total notification attempts across replays. | **100%** (0 real side effects) |
| **M6** | RCA confidence | The AI root-cause analysis reports its own confidence (0–100) in the diagnosis used to generate the fix, quoting the exact faulty prompt rule. | **90%** |

## Why these are meaningful

- **No ground truth.** M1 measures *self-consistency* (did the agent follow the evidence it
  itself retrieved?), and M4 uses an **independent judge from another provider** (Mistral
  judging a Groq agent). Neither needs a pre-labelled "correct answer" — which is the
  realistic production setting.
- **Determinism is provable.** M2 = 100% because replay re-executes the agent against cached
  responses; M5 = 100% because the side-effecting tool is physically blocked during replay.
- **The loop closes.** M3 + M6 come from the auto-fix loop: the system diagnoses its own
  failure, rewrites the prompt, re-runs, and the judge confirms the gain.

## Aggregate run statistics (`GET /api/patterns`)

Over the recorded runs:

- **Routed team:** Network 8 · Security 3 · Hardware 2 · Frontend 2 · Backend 1 · Telephony 1
  · Identity & Access 1 · Email & Collaboration 1
- **Priority:** Medium 11 · High 7
- **Anomalies:** tool_error 6 · no_decision 3 · reasoning_loop 3 · suspicious_argument 3 ·
  excessive_steps 1

The LLM pattern layer flags the **structural** weaknesses behind these numbers (e.g.
"API/payment tickets misrouted", "production outages under-prioritised") and recommends fixes.

## Reproduce

```bash
cd backend && pytest -q          # 80+ unit tests across the layers
uvicorn flight_recorder.api.main:app --port 8000
curl http://127.0.0.1:8000/api/metrics      # M1–M6
curl http://127.0.0.1:8000/api/patterns     # aggregate insights
```
