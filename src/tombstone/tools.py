"""Tool registry: schemas the model sees plus the handlers that run them."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., str]

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolError(Exception):
    """Raised by handlers for errors that should be reported to the model."""


def object_schema(required: dict[str, dict[str, Any]], optional: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    props = {**required, **(optional or {})}
    return {"type": "object", "properties": props, "required": list(required)}


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None):
        self._tools: dict[str, Tool] = {}
        for t in tools or []:
            self.add(t)

    def add(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool {tool.name!r}")
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self._tools.values()]

    def dispatch(self, name: str, arguments: dict[str, Any], raw_arguments: str = "") -> tuple[str, bool]:
        """Run a tool. Returns (content, is_error)."""
        tool = self._tools.get(name)
        if tool is None:
            return f"Error: unknown tool {name!r}", True
        if not arguments and raw_arguments.strip() not in ("", "{}"):
            return f"Error: could not parse arguments as a JSON object: {raw_arguments!r}", True
        try:
            return tool.handler(**arguments), False
        except ToolError as e:
            return f"Error: {e}", True
        except TypeError as e:
            return f"Error: bad arguments for {name}: {e}", True
