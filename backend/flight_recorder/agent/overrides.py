"""Tool overrides for the What-If engine.

Given the real toolset, ``apply_overrides`` returns a new toolset where the named tools are
replaced by versions that always return a fixed, user-supplied output. This is how a
divergence is injected: the agent calls the same tool, but gets the modified value, then
re-reasons live from there.
"""
from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, StructuredTool


def apply_overrides(
    tools: list[BaseTool], overrides: dict[str, dict[str, Any]]
) -> list[BaseTool]:
    """Return a copy of ``tools`` with the named tools pinned to fixed outputs."""
    patched: list[BaseTool] = []
    for tool in tools:
        if tool.name in overrides:
            patched.append(_pinned_tool(tool, overrides[tool.name]))
        else:
            patched.append(tool)
    return patched


def _pinned_tool(tool: BaseTool, value: dict[str, Any]) -> StructuredTool:
    """A tool with the same name/description/args, that ignores input and returns ``value``."""

    def _fixed(**_kwargs: Any) -> dict[str, Any]:
        return value

    return StructuredTool(
        name=tool.name,
        description=tool.description,
        args_schema=tool.args_schema,
        func=_fixed,
    )
