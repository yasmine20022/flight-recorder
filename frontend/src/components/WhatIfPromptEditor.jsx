import { useEffect, useState } from "react";

// Sprint B: inject a CORRECTED system prompt at the agent's reasoning step, then re-run
// live. This is the "fix the buggy instructions at step 1" correction from the demo.
export default function WhatIfPromptEditor({ prompts, onRun, running }) {
  const [text, setText] = useState("");

  // Pre-fill with the agent's CURRENT (buggy) prompt once it loads.
  useEffect(() => {
    if (prompts?.system_prompt != null) setText(prompts.system_prompt);
  }, [prompts]);

  const loadCorrected = () => {
    if (prompts?.corrected_system_prompt != null) setText(prompts.corrected_system_prompt);
  };

  return (
    <div className="whatif-editor">
      <div className="whatif-editor__title">
        ↯ WHAT-IF · correct the agent's <b>instructions</b>, then re-run live
      </div>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={10}
        disabled={running}
        spellCheck={false}
      />
      <div className="whatif-editor__row">
        <button
          className="btn btn--ghost"
          onClick={loadCorrected}
          disabled={running || !prompts?.corrected_system_prompt}
          title="Replace with the suggested corrected prompt"
        >
          ⤵ Load corrected prompt
        </button>
        <button
          className="btn btn--whatif"
          onClick={() => onRun(text)}
          disabled={running || !text.trim()}
        >
          {running ? "Diverging… (~1–2 min)" : "↯ Re-run with corrected prompt"}
        </button>
      </div>
    </div>
  );
}
