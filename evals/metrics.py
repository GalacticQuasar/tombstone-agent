"""Per-run metrics computed from a trace and a task's source labels."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .tasks.base import Task

# Argument that identifies a source for each labelled tool.
SOURCE_ARG = {"web_fetch": "url", "read_file": "path"}


def block_labels(events: list[dict[str, Any]], task: Task) -> dict[str, str]:
    """block id → label kind ('unlabeled' for tool results that aren't labelled sources)."""
    out = {}
    for e in events:
        if e["event"] != "tool_result":
            continue
        arg = SOURCE_ARG.get(e["tool"])
        label = task.labels.get((e["tool"], e["arguments"].get(arg, ""))) if arg and not e["is_error"] else None
        out[e["block_id"]] = label.kind if label else "unlabeled"
    return out


def forget_breakdown(events: list[dict[str, Any]], task: Task) -> dict[str, int]:
    """Count of forget requests by the forgotten block's label kind."""
    labels = block_labels(events, task)
    return dict(Counter(labels.get(e["block_id"], "unknown") for e in events if e["event"] == "forget_requested"))


def reads_breakdown(events: list[dict[str, Any]], task: Task) -> dict[str, int]:
    """Count of labelled sources read, by kind (shows whether distractors were actually read)."""
    return dict(Counter(k for k in block_labels(events, task).values() if k != "unlabeled"))
