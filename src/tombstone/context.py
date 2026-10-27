"""ContextStore: addressable tool-result blocks, deferred forgetting, archive, ledger.

Blocks are tool-result messages (ids b1, b2, ... assigned by the agent). Forgetting
swaps only a block's *content* for a tombstone, so tool_call/tool_result pairing is
never broken. Forgets are queued and applied in batches, to pay for one prefix-cache
miss per batch rather than one per forget.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from .messages import Message
from .prefix import ApproxTokenizer, Tokenizer
from .tools import ToolError

Status = Literal["live", "pending", "forgotten"]


@dataclass
class Block:
    id: str
    tool: str
    arguments: dict[str, Any]
    tokens: int
    turn: int
    status: Status = "live"
    summary: str | None = None


def describe_source(tool: str, arguments: dict[str, Any], limit: int = 60) -> str:
    args = ", ".join(f"{k}={v}" for k, v in arguments.items())
    s = f"{tool}({args})"
    return s if len(s) <= limit else s[: limit - 1] + "…"


def fmt_tokens(n: int) -> str:
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def tombstone_text(block: Block) -> str:
    return (
        f"[{block.id} forgotten: {describe_source(block.tool, block.arguments)}, "
        f"{fmt_tokens(block.tokens)} tok. Summary: {block.summary}]"
    )


class ContextStore:
    def __init__(
        self,
        tokenizer: Tokenizer | None = None,
        apply_threshold: int = 10_000,
        min_block_tokens: int = 300,
        archive_dir: Path | None = None,
    ):
        self.tokenizer = tokenizer or ApproxTokenizer()
        self.apply_threshold = apply_threshold
        self.min_block_tokens = min_block_tokens
        self.archive_dir = archive_dir
        self.blocks: dict[str, Block] = {}
        self._archive: dict[str, str] = {}  # in-memory copy; also written to archive_dir if set
        self.turn = 0

    # --- indexing -------------------------------------------------------------

    def index(self, history: list[Message], turn: int) -> None:
        """Register tool-result blocks not seen before."""
        self.turn = turn
        for m in history:
            if m.role == "tool" and m.block_id and m.block_id not in self.blocks:
                self.blocks[m.block_id] = Block(
                    id=m.block_id,
                    tool=m.meta.get("tool", "?"),
                    arguments=m.meta.get("arguments", {}),
                    tokens=self.tokenizer.count(m.content or ""),
                    turn=turn,
                )

    # --- forgetting -----------------------------------------------------------

    def request_forget(self, block_id: str, summary: str) -> str:
        block = self.blocks.get(block_id)
        if block is None:
            raise ToolError(f"unknown block {block_id!r}")
        if block.status != "live":
            raise ToolError(f"block {block_id} is already {block.status}")
        if not summary.strip():
            raise ToolError("summary must not be empty; say what the block contained and why it's safe to drop")
        block.status = "pending"
        block.summary = summary.strip()
        return (
            f"{block_id} queued for forgetting ({fmt_tokens(block.tokens)} tok). "
            f"It stays visible until the next batch is applied; retrieve_context({block_id}) cancels."
        )

    def pending_savings(self) -> int:
        return sum(
            b.tokens - self.tokenizer.count(tombstone_text(b)) for b in self.blocks.values() if b.status == "pending"
        )

    def maybe_apply(self, history: list[Message]) -> list[str]:
        """Apply all pending forgets if savings reach the threshold. Returns applied ids."""
        pending = [b for b in self.blocks.values() if b.status == "pending"]
        if not pending or self.pending_savings() < self.apply_threshold:
            return []
        by_id = {m.block_id: m for m in history if m.role == "tool" and m.block_id}
        for b in pending:
            msg = by_id[b.id]
            self._save(b, msg.content or "")
            msg.content = tombstone_text(b)
            b.status = "forgotten"
        return [b.id for b in pending]

    # --- archive / retrieval --------------------------------------------------

    def _save(self, block: Block, content: str) -> None:
        self._archive[block.id] = content
        if self.archive_dir is not None:
            self.archive_dir.mkdir(parents=True, exist_ok=True)
            rec = {**asdict(block), "content": content}
            (self.archive_dir / f"{block.id}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))

    def retrieve(self, block_id: str) -> str:
        block = self.blocks.get(block_id)
        if block is None:
            raise ToolError(f"unknown block {block_id!r}")
        if block.status == "live":
            raise ToolError(f"block {block_id} was never forgotten; its content is still in context")
        if block.status == "pending":
            block.status = "live"
            block.summary = None
            return f"Cancelled pending forget of {block_id}; its content is still in context."
        return f"[retrieved {block.id}: {describe_source(block.tool, block.arguments)}]\n{self._archive[block_id]}"

    # --- ledger ---------------------------------------------------------------

    def ledger(self, context_tokens: int) -> str:
        rows = [b for b in self.blocks.values() if b.status != "live" or b.tokens >= self.min_block_tokens]
        head = (
            f"[context ledger] turn {self.turn} · context ≈ {fmt_tokens(context_tokens)} tok · "
            f"pending-forget saves {fmt_tokens(self.pending_savings())} tok "
            f"(batch applies at ≥{fmt_tokens(self.apply_threshold)})"
        )
        if not rows:
            return head + "\n(no forgettable blocks yet)"
        lines = [head, "id | source | tok | age | status"]
        for b in rows:
            lines.append(
                f"{b.id} | {describe_source(b.tool, b.arguments)} | {fmt_tokens(b.tokens)} | "
                f"{self.turn - b.turn} | {b.status}"
            )
        return "\n".join(lines)
