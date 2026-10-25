"""Records every tool call made by any agent: name, arguments, nesting depth and result.

The audit log stores this trace, and the grounding check reads the results of the leaf
tools (the calculator, market data) to verify every figure in the final answer.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from agent_framework import FunctionInvocationContext, FunctionMiddleware
from pydantic import BaseModel

MAX_RESULT_CHARS = 20_000


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    depth: int  # 0 = called by the coordinator, 1+ = by a specialist it delegated to
    ok: bool | None = None
    error: str | None = None
    result: str | None = None


def _as_text(result: Any) -> str | None:
    if result is None:
        return None
    if isinstance(result, list):
        parts = [getattr(c, "text", None) or str(getattr(c, "result", "") or "") for c in result]
        text = "\n".join(p for p in parts if p)
    else:
        text = str(result)
    return text[:MAX_RESULT_CHARS]


class ToolCallTrace(FunctionMiddleware):
    def __init__(self, agent_tool_names: set[str] | None = None) -> None:
        self.calls: list[ToolCall] = []
        self.agent_tool_names = agent_tool_names or set()
        self._depth = 0

    async def process(
        self, context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]
    ) -> None:
        args = context.arguments
        args = args.model_dump() if isinstance(args, BaseModel) else dict(args or {})
        call = ToolCall(name=context.function.name, arguments=args, depth=self._depth)
        self.calls.append(call)
        self._depth += 1
        try:
            await call_next()
            call.ok = True
            call.result = _as_text(context.result)
        except Exception as e:
            call.ok, call.error = False, str(e)
            raise
        finally:
            self._depth -= 1

    def leaf_results(self) -> list[str]:
        """Results from data tools only. Specialists' prose is excluded: it is what we verify."""
        return [
            c.result
            for c in self.calls
            if c.ok and c.result and c.name not in self.agent_tool_names
        ]

    def reset(self) -> None:
        self.calls.clear()
        self._depth = 0
