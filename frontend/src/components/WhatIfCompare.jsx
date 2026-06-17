function summarize(step) {
  if (!step) return "—";
  if (step.type === "llm_call") return step.response || step.prompt || "…";
  return `${step.tool_name}(${JSON.stringify(step.input ?? {})})`;
}

function decisionOf(session) {
  const steps = session.steps ?? [];
  const withDecision = [...steps].reverse().find(
    (s) => s.type === "llm_call" && /decision/i.test(s.response || "")
  );
  return withDecision?.response || steps[steps.length - 1]?.response || "—";
}

function Column({ title, badge, steps, otherSteps, overridden }) {
  return (
    <div className={"cmp__col" + (badge === "WHAT-IF" ? " cmp__col--new" : "")}>
      <div className="cmp__title">{title}</div>
      <ol className="cmp__steps">
        {steps.map((step, i) => {
          const diverged =
            badge === "WHAT-IF" && summarize(step) !== summarize(otherSteps[i]);
          const edited = badge === "WHAT-IF" && step.tool_name === overridden;
          return (
            <li
              key={step.step_number}
              className={"cmp__step" + (diverged ? " is-diverged" : "") + (edited ? " is-edited" : "")}
            >
              <span className="cmp__num">{step.step_number}</span>
              <span className="cmp__type">
                {step.type === "llm_call" ? "🧠" : "🔧"}{" "}
                {step.type === "tool_call" ? step.tool_name : "LLM"}
              </span>
              {edited && <span className="blocked-badge">EDITED</span>}
              {diverged && !edited && <span className="diverged-badge">DIVERGED</span>}
              <span className="cmp__sum">{summarize(step)}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export default function WhatIfCompare({ result, onBack }) {
  const { original, whatif, overridden_tool } = result;
  const decA = decisionOf(original);
  const decB = decisionOf(whatif);
  const changed = decA.trim() !== decB.trim();

  return (
    <div className="panel cmp">
      <div className="cmp__head">
        <button className="btn" onClick={onBack}>← Back to recorder</button>
        <span className="cmp__headtitle">
          ↯ WHAT-IF DIVERGENCE · overrode <b>{overridden_tool}</b>
        </span>
      </div>

      <div className="cmp__grid">
        <Column title="ORIGINAL FLIGHT" badge="ORIGINAL" steps={original.steps} otherSteps={whatif.steps} overridden={overridden_tool} />
        <Column title="WHAT-IF FLIGHT (re-run live)" badge="WHAT-IF" steps={whatif.steps} otherSteps={original.steps} overridden={overridden_tool} />
      </div>

      <div className="cmp__decisions">
        <div>
          <div className="field__label">Original decision</div>
          <pre>{decA}</pre>
        </div>
        <div>
          <div className="field__label">New decision</div>
          <pre className={changed ? "is-changed" : ""}>{decB}</pre>
        </div>
      </div>

      <div className={"cmp__verdict " + (changed ? "is-changed" : "is-same")}>
        {changed
          ? "✔ The agent reached a DIFFERENT decision — corrected without touching the real Jira system, without redeploying, without re-running the live agent."
          : "= Same decision: the modified value did not change the outcome."}
      </div>
    </div>
  );
}
