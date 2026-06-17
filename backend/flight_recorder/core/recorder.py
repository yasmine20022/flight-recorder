"""The interception layer — the technical heart of the project.

``TraceRecorder`` is a LangChain callback handler. You attach it to an agent run via
``config={"callbacks": [recorder]}`` and it captures every LLM call and every tool call as
an ordered list of ``Step`` objects — **without modifying a single line of the agent**.

How LangChain drives it:
    on_chat_model_start  →  an LLM call begins (chat models use this, not on_llm_start)
    on_llm_end           →  that LLM call finished
    on_tool_start        →  a tool call begins
    on_tool_end          →  that tool call finished

We match each start/end pair by ``run_id`` to measure duration, then append a finished step
to ``self.steps`` in completion order (which, for a sequential ReAct agent, is the true
execution order).
"""
from __future__ import annotations

import json
import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

from flight_recorder.core.schemas import Step, StepType


def _messages_to_text(messages: list[list[BaseMessage]]) -> str:
    """Flatten the chat prompt LangChain is about to send into readable text."""
    if not messages:
        return ""
    return "\n".join(f"{m.type}: {m.content}" for m in messages[0])


def _llm_provenance(response: LLMResult) -> tuple[str | None, int | None]:
    """Pull the model name and total token count out of an LLM result.

    This is the proof a step really hit Groq: the model id and the tokens it billed.
    """
    model = None
    tokens = None

    out = getattr(response, "llm_output", None) or {}
    model = out.get("model_name") or out.get("model")
    usage = out.get("token_usage") or {}
    tokens = usage.get("total_tokens")

    # Fall back to per-message metadata (langchain-groq populates these too).
    if (model is None or tokens is None) and response.generations:
        message = getattr(response.generations[0][0], "message", None)
        if message is not None:
            meta = getattr(message, "response_metadata", None) or {}
            model = model or meta.get("model_name") or meta.get("model")
            usage_meta = getattr(message, "usage_metadata", None) or {}
            tokens = tokens or usage_meta.get("total_tokens")
            tokens = tokens or (meta.get("token_usage") or {}).get("total_tokens")

    return model, tokens


def _coerce_to_dict(value: Any) -> dict[str, Any]:
    """Best-effort conversion of a tool input/output into a JSON-able dict."""
    if isinstance(value, dict):
        return value
    # ToolMessage / generation objects expose their payload on ``.content``.
    content = getattr(value, "content", value)
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else {"result": parsed}
        except (json.JSONDecodeError, TypeError):
            return {"result": content}
    return {"result": str(content)}


class TraceRecorder(BaseCallbackHandler):
    """Captures an agent run as an ordered list of :class:`Step`."""

    def __init__(self) -> None:
        self.steps: list[Step] = []
        # run_id -> partial data collected at *_start, completed at *_end.
        self._pending: dict[UUID, dict[str, Any]] = {}

    # --- LLM calls ---

    def on_chat_model_start(
        self, serialized: dict, messages: list[list[BaseMessage]], *, run_id: UUID, **kwargs
    ) -> None:
        self._pending[run_id] = {
            "prompt": _messages_to_text(messages),
            "start": time.perf_counter(),
        }

    def on_llm_start(
        self, serialized: dict, prompts: list[str], *, run_id: UUID, **kwargs
    ) -> None:
        # Fallback for non-chat (completion) models.
        self._pending[run_id] = {
            "prompt": "\n".join(prompts),
            "start": time.perf_counter(),
        }

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs) -> None:
        pending = self._pending.pop(run_id, None)
        if pending is None:
            return
        gen = response.generations[0][0] if response.generations else None
        text = getattr(gen, "text", "") if gen is not None else ""
        if not text and gen is not None:
            message = getattr(gen, "message", None)
            tool_calls = getattr(message, "tool_calls", None) or []
            if tool_calls:
                text = "(decided to call: " + ", ".join(tc["name"] for tc in tool_calls) + ")"
        model, tokens = _llm_provenance(response)
        self._append(
            StepType.LLM_CALL,
            pending["start"],
            prompt=pending["prompt"],
            response=text,
            model=model,
            tokens=tokens,
        )

    # --- Tool calls ---

    def on_tool_start(
        self,
        serialized: dict,
        input_str: str,
        *,
        run_id: UUID,
        inputs: dict | None = None,
        **kwargs,
    ) -> None:
        name = (serialized or {}).get("name", "unknown_tool")
        tool_input = inputs if inputs is not None else _coerce_to_dict(input_str)
        self._pending[run_id] = {
            "tool_name": name,
            "input": tool_input,
            "start": time.perf_counter(),
        }

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs) -> None:
        pending = self._pending.pop(run_id, None)
        if pending is None:
            return
        self._append(
            StepType.TOOL_CALL,
            pending["start"],
            tool_name=pending["tool_name"],
            input=pending["input"],
            output=_coerce_to_dict(output),
        )

    # --- internal ---

    def _append(self, step_type: StepType, start: float, **fields: Any) -> None:
        duration_ms = int((time.perf_counter() - start) * 1000)
        self.steps.append(
            Step(
                step_number=len(self.steps) + 1,
                type=step_type,
                duration_ms=duration_ms,
                **fields,
            )
        )
