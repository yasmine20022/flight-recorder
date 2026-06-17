function Gauge({ label, value, accent }) {
  return (
    <div className={"gauge" + (accent ? ` gauge--${accent}` : "")}>
      <div className="gauge__value">{value}</div>
      <div className="gauge__label">{label}</div>
    </div>
  );
}

// Cockpit instrument cluster. Shows run metrics, and during a replay the safety counters.
export default function InstrumentBar({ session, replay }) {
  const steps = session.steps ?? [];
  const llmSteps = steps.filter((s) => s.type === "llm_call");
  const llm = llmSteps.length;
  const tools = steps.filter((s) => s.type === "tool_call").length;
  const ms = steps.reduce((a, s) => a + (s.duration_ms || 0), 0);
  const tokens = llmSteps.reduce((a, s) => a + (s.tokens || 0), 0);
  const model = llmSteps.find((s) => s.model)?.model;
  const isReplay = session.mode === "replay";

  return (
    <>
    {model && (
      <div className="model-line">
        🛰 real LLM call · <b>{model}</b> via Groq{tokens ? ` · ${tokens} tokens billed` : ""}
      </div>
    )}
    <div className={"instruments" + (isReplay ? " instruments--sim" : "")}>
      <Gauge label="LLM CALLS" value={llm} />
      <Gauge label="TOOL CALLS" value={tools} />
      <Gauge label="STEPS" value={steps.length} />
      <Gauge label="DURATION" value={`${ms} ms`} />
      {tokens > 0 && <Gauge label="LLM TOKENS" value={tokens} accent="cyan" />}
      {replay && (
        <>
          <div className="instruments__sep" />
          <Gauge label="REAL CALLS" value={replay.real_calls} accent="ok" />
          <Gauge label="INTERCEPTED" value={replay.intercepted_calls} accent="cyan" />
          <Gauge label="SIDE EFFECTS" value="BLOCKED" accent="warn" />
        </>
      )}
    </div>
    </>
  );
}
