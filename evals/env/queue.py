"""Message queues that deliver each message once: polling drains the queue.

Output that can't be fetched again, for testing strategies that clear tool results blindly.
"""

from __future__ import annotations

from tombstone.tools import Tool, ToolError, object_schema


class QueueEnv:
    def __init__(self, queues: dict[str, list[str]]):
        self.pending = {q: list(msgs) for q, msgs in queues.items()}

    def list_queues(self) -> str:
        return "\n".join(f"{q} ({len(m)} pending)" for q, m in self.pending.items())

    def poll_queue(self, queue: str) -> str:
        if queue not in self.pending:
            raise ToolError(f"no such queue: {queue}")
        msgs, self.pending[queue] = self.pending[queue], []
        if not msgs:
            return f"Queue {queue!r} is empty: its messages were delivered on an earlier poll and are gone."
        return f"{len(msgs)} messages from {queue!r} (now acknowledged and removed from the queue):\n" + "\n".join(msgs)

    def tools(self) -> list[Tool]:
        return [
            Tool("list_queues", "List message queues and how many messages each has pending.",
                 object_schema({}), self.list_queues),
            Tool("poll_queue",
                 "Receive all pending messages from a queue. Messages are acknowledged on delivery, "
                 "so each message is returned only once.",
                 object_schema({"queue": {"type": "string"}}), self.poll_queue),
        ]
