"""Canonical, wire-format-neutral conversation types.

The context store operates on these; `render` converts them to the OpenAI
chat-completions shape right before a request.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    # Raw argument string as the model emitted it; kept so malformed calls can be logged.
    raw_arguments: str = ""


@dataclass
class Message:
    role: Role
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    # For role == "tool": the call this result answers.
    tool_call_id: str | None = None
    # For role == "tool": stable block id (b1, b2, ...) assigned by the context store.
    block_id: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


def render_message(m: Message) -> dict[str, Any]:
    out: dict[str, Any] = {"role": m.role}
    if m.role == "assistant":
        out["content"] = m.content
        if m.tool_calls:
            out["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": tc.raw_arguments or json.dumps(tc.arguments),
                    },
                }
                for tc in m.tool_calls
            ]
    elif m.role == "tool":
        out["tool_call_id"] = m.tool_call_id
        out["content"] = m.content or ""
    else:
        out["content"] = m.content or ""
    return out


def render(messages: list[Message]) -> list[dict[str, Any]]:
    return [render_message(m) for m in messages]


def validate_tool_pairing(messages: list[Message]) -> None:
    """Raise if any tool call lacks exactly one result, or a result has no call.

    Results must follow their assistant message before the next assistant turn.
    """
    pending: set[str] = set()
    for i, m in enumerate(messages):
        if m.role == "assistant":
            if pending:
                raise ValueError(f"message {i}: unanswered tool calls {sorted(pending)}")
            pending = {tc.id for tc in m.tool_calls}
        elif m.role == "tool":
            if m.tool_call_id not in pending:
                raise ValueError(f"message {i}: tool result for unknown call {m.tool_call_id!r}")
            pending.discard(m.tool_call_id)
    if pending:
        raise ValueError(f"unanswered tool calls at end {sorted(pending)}")
