function Field({ label, children }) {
  return (
    <div className="field">
      <div className="field__label">{label}</div>
      <div className="field__value">{children}</div>
    </div>
  );
}

export default function StepDetail({ step }) {
  if (!step) return <p className="muted small">Click a waypoint to read the black box.</p>;

  const blocked = step.output?.status === "blocked_during_replay";

  return (
    <div className="detail">
      <div className="detail__head">
        ◉ STEP #{step.step_number} · {step.type.toUpperCase()} · {step.duration_ms} ms
        {blocked && "  ·  🚫 BLOCKED"}
      </div>

      {step.type === "llm_call" ? (
        <>
          {step.model && (
            <Field label="LLM (real call)">
              🛰 {step.model} via Groq{step.tokens ? ` · ${step.tokens} tokens` : ""}
            </Field>
          )}
          <Field label="Prompt (exact, as sent)">
            <pre>{step.prompt}</pre>
          </Field>
          <Field label="Response">
            <pre>{step.response}</pre>
          </Field>
        </>
      ) : (
        <>
          <Field label="Tool">{step.tool_name}</Field>
          <Field label="Input">
            <pre>{JSON.stringify(step.input, null, 2)}</pre>
          </Field>
          <Field label="Output">
            <pre>{JSON.stringify(step.output, null, 2)}</pre>
          </Field>
        </>
      )}
    </div>
  );
}
