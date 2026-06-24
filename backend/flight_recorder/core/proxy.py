"""The transparent LLM proxy — Sprint A.

``ProxiedChatModel`` is a real chat model that sits **between the agent and the LLM
provider**. The agent talks to the proxy and cannot tell the difference; the proxy decides
what to do with each call:

  * **RECORD**  — forward the call to the wrapped provider model (Groq). No behaviour change;
    every prompt/response still flows through and is captured.
  * **REPLAY**  — answer from the recorded trace, in order, and **never touch the network**.
    This is what makes deterministic replay literally "cached responses, zero real LLM calls".

It is a genuine proxy (the Proxy design pattern at the model boundary), not a logging hook:
the agent's ``model.invoke(...)`` is physically routed through this object.
"""
from __future__ import annotations

from typing import Any, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class ReplayState:
    """Shared cursor over the recorded AI messages.

    Shared by reference so that the copies ``bind_tools`` creates all advance the same
    cursor (the agent binds tools before the first call).
    """

    def __init__(self, messages: list[AIMessage]) -> None:
        self.messages = messages
        self.index = 0

    def next_message(self) -> AIMessage:
        if self.index >= len(self.messages):
            raise RuntimeError(
                "Replay exhausted: the agent requested more LLM calls than were recorded."
            )
        msg = self.messages[self.index]
        self.index += 1
        return msg


class CallCounter:
    """Counts real provider calls made during RECORD (shared across bind_tools copies)."""

    def __init__(self) -> None:
        self.count = 0


class ProxiedChatModel(BaseChatModel):
    """A chat model that proxies to a real provider (record) or to a cache (replay)."""

    inner: Any = None            # wrapped provider model, or its tool-bound form
    mode: str = "record"         # "record" | "replay"
    replay_state: Any = None     # ReplayState, in replay mode
    call_counter: Any = None     # CallCounter, in record mode

    model_config = {"arbitrary_types_allowed": True}

    @property
    def _llm_type(self) -> str:
        return "proxied-chat-model"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ProxiedChatModel":
        """Forward tool-binding to the inner model, preserving the proxy wrapper."""
        bound_inner = self.inner.bind_tools(tools, **kwargs) if self.inner is not None else None
        return ProxiedChatModel(
            inner=bound_inner,
            mode=self.mode,
            replay_state=self.replay_state,
            call_counter=self.call_counter,
        )

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        if self.mode == "replay":
            # Serve the recorded decision; no provider, no network.
            ai = self.replay_state.next_message()
            return ChatResult(generations=[ChatGeneration(message=ai)])

        # RECORD: forward to the real provider. Suppress the inner model's own callbacks so
        # the trace recorder (attached to the proxy's run) captures each call exactly once.
        if self.call_counter is not None:
            self.call_counter.count += 1
        invoke_kwargs: dict[str, Any] = {"config": {"callbacks": []}}
        if stop is not None:
            invoke_kwargs["stop"] = stop
        ai = self.inner.invoke(messages, **invoke_kwargs)
        if not isinstance(ai, AIMessage):
            ai = AIMessage(content=str(getattr(ai, "content", ai)))

        meta = getattr(ai, "response_metadata", None) or {}
        usage = meta.get("token_usage") or (getattr(ai, "usage_metadata", None) or {})
        llm_output = {"model_name": meta.get("model_name") or meta.get("model"),
                      "token_usage": usage}
        return ChatResult(generations=[ChatGeneration(message=ai)], llm_output=llm_output)
