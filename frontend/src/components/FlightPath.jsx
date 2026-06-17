function summarize(step) {
  if (step.type === "llm_call") return step.response || step.prompt || "…";
  return `${step.tool_name}(${JSON.stringify(step.input ?? {})})`;
}

function isBlocked(step) {
  return step.type === "tool_call" && step.output?.status === "blocked_during_replay";
}

// The agent run drawn as a flight path: takeoff → waypoints → landing.
// `cursor` is the playback position; steps before it are "done", at it "current",
// after it "upcoming" (dimmed).
export default function FlightPath({ session, cursor, onSelect, anomalySteps }) {
  const steps = session.steps ?? [];
  const flagged = anomalySteps ?? new Set();

  return (
    <>
      <p className="ticket">
        <strong>{session.ticket_id}</strong> — {session.ticket_text}
      </p>
      <div className="fmark">▲ TAKEOFF · ticket received</div>

      <ol className="fpath">
        {steps.map((step, i) => {
          const state = i < cursor ? "done" : i === cursor ? "current" : "upcoming";
          const blocked = isBlocked(step);
          return (
            <li
              key={step.step_number}
              className={
                `fnode fnode--${step.type} is-${state}` + (blocked ? " is-blocked" : "")
              }
              onClick={() => onSelect(i)}
            >
              <span className="fnode__dot">{step.step_number}</span>
              <div className="fnode__body">
                <div className="fnode__head">
                  <span className="fnode__type">
                    {step.type === "llm_call" ? "🧠 LLM" : `🔧 ${step.tool_name}`}
                  </span>
                  {flagged.has(step.step_number) && <span className="anomaly-badge">⚠ ANOMALY</span>}
                  {blocked && <span className="blocked-badge">🚫 BLOCKED</span>}
                  <span className="fnode__dur">{step.duration_ms} ms</span>
                </div>
                <div className="fnode__summary">{summarize(step)}</div>
              </div>
            </li>
          );
        })}
      </ol>

      <div className="fmark fmark--land">▼ LANDING · decision recorded</div>
    </>
  );
}
