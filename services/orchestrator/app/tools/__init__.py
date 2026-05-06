"""Tools exposés au LLM (tool calling)."""

from .registry import TOOL_DEFS, dispatch_tool

__all__ = ["TOOL_DEFS", "dispatch_tool"]
