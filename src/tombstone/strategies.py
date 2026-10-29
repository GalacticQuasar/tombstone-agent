"""Context-management strategies, hooked into the agent loop.

Hooks per turn: `on_request` (before the model call; may return ephemeral text that is
sent but never stored) and `after_turn` (after tool results are appended; may rewrite
history in place). Baselines: NoOp (full context), Truncate (stub old tool results),
AutoCompact (summarize the transcript at a threshold).
"""

from __future__ import annotations

from pathlib import Path

from .client import ChatClient
from .context import ContextStore, describe_source, fmt_tokens
from .messages import Message
from .prefix import ApproxTokenizer, Tokenizer, serialize_request
from .tools import Tool, object_schema
from .trace import Trace


class Strategy:
    name = "base"

    def bind(self, trace: Trace, run_dir: Path | None, client: ChatClient) -> None:
        self.trace = trace
        self.run_dir = run_dir
        self.client = client

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

    def bind(self, trace: Trace, run_dir: Path | None, client: ChatClient) -> None:
        super().bind(trace, run_dir, client)
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


def context_tokens(history: list[Message], tokenizer: Tokenizer) -> int:
    return tokenizer.count(serialize_request(history, []))


class Truncate(Strategy):
    """Naive baseline: once context exceeds `trigger_tokens`, stub all but the last `keep_last`
    tool results. Stubs carry no summary and can't be retrieved (the agent can re-run the tool)."""

    name = "truncate"

    def __init__(self, keep_last: int = 5, trigger_tokens: int = 20_000, tokenizer: Tokenizer | None = None):
        self.keep_last = keep_last
        self.trigger_tokens = trigger_tokens
        self.tokenizer = tokenizer or ApproxTokenizer()

    def after_turn(self, history: list[Message], turn: int) -> None:
        if context_tokens(history, self.tokenizer) < self.trigger_tokens:
            return
        results = [m for m in history if m.role == "tool"]
        cut = results[: max(len(results) - self.keep_last, 0)]
        cleared, saved = [], 0
        for m in cut:
            if m.meta.get("cleared"):
                continue
            stub = (
                f"[{m.block_id} cleared: {describe_source(m.meta.get('tool', '?'), m.meta.get('arguments', {}))}, "
                f"{fmt_tokens(self.tokenizer.count(m.content or ''))} tok]"
            )
            saved += self.tokenizer.count(m.content or "") - self.tokenizer.count(stub)
            m.content = stub
            m.meta["cleared"] = True
            cleared.append(m.block_id)
        if cleared:
            self.trace.log("truncate_applied", turn=turn, block_ids=cleared, tokens_saved=saved)


COMPACT_PROMPT = """\
You are compacting the transcript of an AI agent's work so it can continue with a much \
shorter context. Write a summary the agent can rely on instead of the transcript:
- Each earlier question it was asked and the final answer it gave.
- Key facts found so far, with exact numbers, names, identifiers and their sources (URLs/paths).
- Which sources were checked and turned out irrelevant or misleading, and why.
- For the current question: what has been established and what still needs to be done.
Be concise but do not drop specific facts that might be needed later."""


def transcript_text(history: list[Message]) -> str:
    """Plain-text transcript for the summarizer (system prompt omitted)."""
    lines = []
    for m in history:
        if m.role == "system":
            continue
        if m.role == "tool":
            src = describe_source(m.meta.get("tool", "?"), m.meta.get("arguments", {}), limit=200)
            lines.append(f"[tool result {m.block_id}: {src}]\n{m.content}")
        elif m.role == "assistant":
            calls = "; ".join(describe_source(c.name, c.arguments, limit=200) for c in m.tool_calls)
            lines.append(f"[assistant]\n{m.content or ''}" + (f"\n(tool calls: {calls})" if calls else ""))
        else:
            lines.append(f"[user]\n{m.content}")
    return "\n\n".join(lines)


class AutoCompact(Strategy):
    """Baseline: once context exceeds `threshold_tokens`, have the model summarize the whole
    transcript and restart from [system, summary + current question]."""

    name = "compact"

    def __init__(self, threshold_tokens: int = 20_000, tokenizer: Tokenizer | None = None):
        self.threshold_tokens = threshold_tokens
        self.tokenizer = tokenizer or ApproxTokenizer()

    def after_turn(self, history: list[Message], turn: int) -> None:
        before = context_tokens(history, self.tokenizer)
        if before < self.threshold_tokens:
            return
        phase_msg = next(m for m in reversed(history) if "phase" in m.meta)
        question = phase_msg.meta.get("question", phase_msg.content)
        completion = self.client.complete(
            [Message("system", COMPACT_PROMPT), Message("user", transcript_text(history))], []
        )
        summary = (completion.message.content or "").strip()
        history[1:] = [
            Message(
                "user",
                f"<summary of earlier work>\n{summary}\n</summary>\n\nContinue with the current question:\n{question}",
                meta={"phase": phase_msg.meta["phase"], "question": question, "compacted": True},
            )
        ]
        self.trace.log(
            "compact_applied", turn=turn, tokens_before=before,
            tokens_after=context_tokens(history, self.tokenizer), usage=completion.usage, summary=summary,
        )


STRATEGIES: dict[str, type[Strategy]] = {
    NoOp.name: NoOp,
    SelfForget.name: SelfForget,
    Truncate.name: Truncate,
    AutoCompact.name: AutoCompact,
}
