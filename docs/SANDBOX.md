# Sandboxed replay (Bonus 10)

Replay is already side-effect-free by design (it re-injects recorded values and blocks
`send_notification`). The Docker **sandbox** turns that guarantee into something you can
*prove* on stage: a container that runs a replay with **no network and a read-only
filesystem**.

If the replay still completes with zero real calls inside a container that physically
cannot reach the LLM or any external system, the "black box is safe" claim is demonstrated
at the infrastructure level — not just in code.

## Run the API in a container

```bash
# from the repo root
export GROQ_API_KEY=gsk_...     # only needed for live runs / what-if
docker compose up --build api
# → http://localhost:8000/api/sessions
```

## Run an isolated replay (the proof)

```bash
docker compose --profile sandbox run --build replay-sandbox
```

That container is started with:

| Hardening            | Compose setting        | What it proves                                  |
|----------------------|------------------------|-------------------------------------------------|
| No network           | `network_mode: none`   | Replay cannot call the LLM or any external API. |
| Read-only filesystem | `read_only: true`      | Replay cannot write a notification / side effect.|
| tmpfs for `/tmp`     | `tmpfs: [/tmp]`        | Only scratch space, wiped on exit.              |

The image is seeded with a clean demo session at build time, so the sandbox is fully
self-contained. Expected output ends with:

```
--- PROOF ---
  Real calls made      : 0
  Calls intercepted    : N
  send_notification    : blocked (no email/log write)
```

## Why this is meaningful

A reviewer can unplug the network, lock the disk, and the recorder still reconstructs the
exact past execution — exactly like replaying an aircraft's flight data on a grounded
simulator.
