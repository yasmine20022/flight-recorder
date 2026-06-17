import { useEffect, useState } from "react";

// Lets the user edit a tool step's output, then launch a live divergence run.
export default function WhatIfEditor({ step, onRun, running }) {
  const [text, setText] = useState("");
  const [err, setErr] = useState(null);

  useEffect(() => {
    setText(JSON.stringify(step.output ?? {}, null, 2));
    setErr(null);
  }, [step]);

  function run() {
    let parsed;
    try {
      parsed = JSON.parse(text);
    } catch {
      setErr("Invalid JSON — fix it before diverging.");
      return;
    }
    onRun(step.tool_name, parsed);
  }

  return (
    <div className="whatif-editor">
      <div className="whatif-editor__title">
        ↯ WHAT-IF · edit <b>{step.tool_name}</b> output, then re-run live
      </div>
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={7} disabled={running} />
      {err && <p className="error small">{err}</p>}
      <button className="btn btn--whatif" onClick={run} disabled={running}>
        {running ? "Diverging… (~1–2 min)" : `↯ Run What-If from ${step.tool_name}`}
      </button>
    </div>
  );
}
