"""Context-management strategies, hooked into the agent loop.

Hooks per turn: `on_request` (before the model call; may return ephemeral text that is
sent but never stored) and `after_turn` (after tool results are appended; may rewrite
history in place). Truncate and AutoCompact arrive in phase 3.
"""

from __future__ import annotations

from pathlib import Path

from .context import ContextStore
from .messages import Message
from .prefix import ApproxTokenizer, Tokenizer
from .tools import Tool, object_schema
from .trace import Trace


class Strategy:
    name = "base"

    def bind(self, trace: Trace, run_dir: Path | None) -> None:
        self.trace = trace
        self.run_dir = run_dir

    def system_prompt_addendum(self) -> str:
        return ""

    def tools(self) -> list[Tool]:
        """Extra tools this strategy exposes to the agent (e.g. forget)."""
        return []

    def on_request(self, history: list[Message], turn: int, context_tokens: int) -> str | None:
        """Ephemeral text appended to the request (never stored in history)."""
        return None

    def after_turn(self, history: list[Message], turn: int) -> None:
        """Mutate history in place after tool results are appended."""


class NoOp(Strategy):
    name = "none"


SELF_FORGET_POLICY = """\
## Context management
Your context window is limited and you pay for every token in it on every turn. Each tool \
result is a numbered block (b1, b2, ...). A ledger at the end of each request lists the \
larger blocks with their size, age and status.

- When a block is irrelevant (e.g. a page that turned out not to help) or no longer needed \
(e.g. files for a subtask you have finished), call forget(block_id, summary). The summary \
replaces the block, so put in it anything you might still need: key facts, numbers, names, \
and why you're dropping it.
- Forgets are applied in batches, so a block stays visible for a while after you forget it.
- If you later need a forgotten block's full content, call retrieve_context(block_id).
- Don't forget blocks you still need for the current task."""


class SelfForget(Strategy):
    name = "self_forget"

    def __init__(
        self,
        apply_threshold: int = 10_000,
        min_block_tokens: int = 300,
        tokenizer: Tokenizer | None = None,
        show_ledger: bool = True,
    ):
        self.store = ContextStore(tokenizer or ApproxTokenizer(), apply_threshold, min_block_tokens)
        self.show_ledger = show_ledger

    def bind(self, trace: Trace, run_dir: Path | None) -> None:
        super().bind(trace, run_dir)
        self.store.archive_dir = run_dir / "archive" if run_dir else None

    def system_prompt_addendum(self) -> str:
        return SELF_FORGET_POLICY

    def tools(self) -> list[Tool]:
        return [
            Tool(
                "forget",
                "Replace a tool-result block with your summary to free context. Recoverable via retrieve_context.",
                object_schema({
                    "block_id": {"type": "string", "description": "Block id, e.g. 'b7'"},
                    "summary": {"type": "string", "description": "What the block contained that is still worth knowing"},
                }),
                self._forget,
            ),
            Tool(
                "retrieve_context",
                "Recover the full content of a forgotten block (or cancel a pending forget).",
                object_schema({"block_id": {"type": "string"}}),
                self._retrieve,
            ),
        ]

    def _forget(self, block_id: str, summary: str) -> str:
        out = self.store.request_forget(block_id, summary)
        self.trace.log("forget_requested", block_id=block_id, summary=summary)
        return out

    def _retrieve(self, block_id: str) -> str:
        out = self.store.retrieve(block_id)
        self.trace.log("retrieve", block_id=block_id)
        return out

    def on_request(self, history: list[Message], turn: int, context_tokens: int) -> str | None:
        self.store.index(history, turn)
        return self.store.ledger(context_tokens) if self.show_ledger else None

    def after_turn(self, history: list[Message], turn: int) -> None:
        self.store.index(history, turn)
        savings = self.store.pending_savings()
        applied = self.store.maybe_apply(history)
        if applied:
            self.trace.log("forget_applied", turn=turn, block_ids=applied, tokens_saved=savings)


STRATEGIES: dict[str, type[Strategy]] = {
    NoOp.name: NoOp,
    SelfForget.name: SelfForget,
}
