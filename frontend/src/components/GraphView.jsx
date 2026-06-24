// "Midnight Azure" agent execution graph — a node/edge view of a recorded run, driven by the
// real session steps. Clicking a node selects that step (so the existing detail + What-If
// panel keeps working); the node at `cursor` is highlighted as the current step.

const COLOR = {
  llm: "#00BFFF", tool: "#F59E0B", success: "#34D399",
  error: "#F87171", blocked: "#F43F5E", final: "#34D399",
};
const ICON = { llm: "🧠", tool: "🔧", success: "✓", error: "⚠", blocked: "🚫", final: "🏁" };
const TAG = { llm: "blue", tool: "amber", success: "emerald", error: "red", blocked: "rose", final: "emerald" };
const TAGLABEL = { llm: "LLM", tool: "TOOL", success: "OK", error: "ERROR", blocked: "BLOCKED", final: "DECISION" };

const NODE = 56, GAPY = 138, TOP = 22, COLW = 540, CARD_W = 180;
const xFor = (i) => (i % 2 === 0 ? 80 : 320);
const yFor = (i) => TOP + i * GAPY;
const cx = (i) => xFor(i) + NODE / 2;
const cy = (i) => yFor(i) + NODE / 2;

function classify(step, i, steps) {
  if (step.type === "llm_call") {
    const last = i === steps.length - 1;
    if (last && /decision/i.test(step.response || "")) return "final";
    return "llm";
  }
  const status = String(step.output?.status || "").toLowerCase();
  if (status.includes("blocked")) return "blocked";
  if (["rejected", "error", "failed"].includes(status)) return "error";
  return "tool";
}

function titleOf(step, t) {
  if (step.type === "tool_call") return step.tool_name || "tool";
  return t === "final" ? "Final decision" : "LLM reasoning";
}

function summarize(step) {
  if (step.type === "llm_call") return step.response || step.prompt || "…";
  try {
    return `${step.tool_name}(${JSON.stringify(step.input ?? {})})`;
  } catch {
    return step.tool_name || "tool";
  }
}

function cvars(c) {
  return { "--c": c, "--c44": `${c}44`, "--c66": `${c}66`, "--c77": `${c}77`, "--cbb": `${c}bb` };
}

export default function GraphView({ session, cursor, anomalySteps, onSelect }) {
  const steps = session?.steps ?? [];
  const meta = steps.map((s, i) => ({ step: s, i, t: classify(s, i, steps) }));
  const height = TOP + steps.length * GAPY + 80;

  if (!steps.length) {
    return <p className="muted small">No steps to graph yet.</p>;
  }

  return (
    <div className="graph">
      <div className="graph__inner" style={{ width: COLW, height }}>
        {/* animated edges */}
        <svg className="graph__edges" width={COLW} height={height}>
          {meta.slice(1).map(({ i }) => (
            <line
              key={`e${i}`}
              x1={cx(i - 1)} y1={cy(i - 1)} x2={cx(i)} y2={cy(i)}
              stroke={COLOR[meta[i - 1].t]} strokeWidth="1.5" strokeLinecap="round"
              strokeDasharray="10 12" className="graph__edge" opacity="0.85"
            />
          ))}
        </svg>

        {/* nodes */}
        {meta.map(({ step, i, t }) => (
          <button
            key={`n${i}`}
            type="button"
            className={`gnode gnode--${t} ${i === cursor ? "is-selected" : ""}`}
            style={{ left: xFor(i), top: yFor(i), ...cvars(COLOR[t]) }}
            onClick={() => onSelect(i)}
            title={summarize(step)}
          >
            <span className="gnode__icon">{ICON[t]}</span>
            <span className="gnode__step">{String(i + 1).padStart(2, "0")}</span>
          </button>
        ))}

        {/* cards */}
        {meta.map(({ step, i, t }) => {
          const flagged = anomalySteps?.has(step.step_number);
          return (
            <div
              key={`c${i}`}
              className={`gcard ${i === cursor ? "is-active" : ""} ${flagged ? "is-flagged" : ""}`}
              style={{ left: xFor(i) - 62, top: yFor(i) + 64, width: CARD_W }}
              onClick={() => onSelect(i)}
            >
              <div className="gcard__row">
                <span className="gcard__title">{titleOf(step, t)}</span>
                <span className="gcard__ms">{step.duration_ms} ms</span>
              </div>
              <div className="gcard__body">{summarize(step)}</div>
              <div className="gcard__tags">
                <span className={`gtag gtag--${TAG[t]}`}>{TAGLABEL[t]}</span>
                {flagged && <span className="gtag gtag--rose">⚠ ANOMALY</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
