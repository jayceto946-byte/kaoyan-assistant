"""Small registry for controlled learning tools.

Tools are plain Python functions with explicit metadata. The first agent phase
uses read-only tools plus "proposal" tools that return confirmation plans
instead of mutating user data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolContext:
    book_name: str = ""
    subject: str = ""
    conversation_id: str = ""


@dataclass
class ToolResult:
    success: bool
    data: Any = None
    message: str = ""
    pending_action: dict | None = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "pending_action": self.pending_action,
        }


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    read_only: bool
    handler: Callable[[ToolContext, dict[str, Any]], ToolResult] = field(repr=False)

    def public_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "read_only": self.read_only,
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec):
        if spec.name in self._tools:
            raise ValueError(f"duplicate tool: {spec.name}")
        self._tools[spec.name] = spec

    def list_tools(self, *, include_write: bool = False) -> list[dict]:
        specs = [
            spec.public_dict()
            for spec in self._tools.values()
            if include_write or spec.read_only
        ]
        return sorted(specs, key=lambda item: item["name"])

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name}")
        return self._tools[name]

    def call(
        self,
        name: str,
        args: dict[str, Any] | None,
        context: ToolContext,
        *,
        allow_write: bool = False,
    ) -> ToolResult:
        spec = self.get(name)
        if not spec.read_only and not allow_write:
            return ToolResult(
                success=False,
                message=f"tool '{name}' requires explicit write confirmation",
            )
        try:
            return spec.handler(context, args or {})
        except Exception as exc:
            return ToolResult(success=False, message=str(exc))


_REGISTRY: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        from backend.tools.learning_tools import register_learning_tools

        registry = ToolRegistry()
        register_learning_tools(registry)
        _REGISTRY = registry
    return _REGISTRY
