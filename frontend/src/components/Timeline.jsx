function summarize(step) {
  if (step.type === "llm_call") return step.response ?? step.prompt ?? "";
  return `${step.tool_name}(${JSON.stringify(step.input ?? {})})`;
}

function isBlocked(step) {
  return step.type === "tool_call" && step.output?.status === "blocked_during_replay";
}

export default function Timeline({ session, selectedStep, onSelectStep }) {
  const steps = session.steps ?? [];
  const llmCount = steps.filter((s) => s.type === "llm_call").length;
  const toolCount = steps.filter((s) => s.type === "tool_call").length;
  const totalMs = steps.reduce((sum, s) => sum + (s.duration_ms || 0), 0);

  return (
    <>
      <p className="ticket">
        <strong>{session.ticket_id}</strong> — {session.ticket_text}
      </p>

      <div className="summary">
        <span className={`tag tag--${session.mode}`}>{session.mode}</span>
        <span className={`tag tag--status-${session.status}`}>{session.status}</span>
        <span className="summary__metric">🧠 {llmCount} LLM</span>
        <span className="summary__metric">🔧 {toolCount} tools</span>
        <span className="summary__metric">⏱ {totalMs} ms</span>
      </div>

      <ol className="timeline">
        {steps.map((step) => (
          <li
            key={step.step_number}
            className={
              "timeline__step timeline__step--" +
              step.type +
              (selectedStep?.step_number === step.step_number ? " is-selected" : "") +
              (isBlocked(step) ? " is-blocked" : "")
            }
            onClick={() => onSelectStep(step)}
          >
            <span className="timeline__num">{step.step_number}</span>
            <span className="timeline__type">
              {step.type === "llm_call" ? "🧠 LLM" : `🔧 ${step.tool_name}`}
            </span>
            <span className="timeline__summary">
              {isBlocked(step) && <span className="blocked-badge">🚫 BLOCKED</span>}
              {summarize(step)}
            </span>
            <span className="timeline__dur muted">{step.duration_ms} ms</span>
          </li>
        ))}
      </ol>
    </>
  );
}
