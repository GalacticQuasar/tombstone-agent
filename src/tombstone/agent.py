"""The agent loop: render → call → dispatch tools → strategy hook → log."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .client import ChatClient, Usage
from .messages import Message, validate_tool_pairing
from .prefix import ApproxTokenizer, PrefixReuse, PrefixTracker, Tokenizer, serialize_request
from .strategies import NoOp, Strategy
from .tools import ToolRegistry
from .trace import Trace


@dataclass
class RunResult:
    answers: list[str | None]  # one per phase; None for phases not reached
    turns: int
    stopped: str  # "answer" | "max_turns"
    history: list[Message]
    usage: list[Usage] = field(default_factory=list)
    prefix: list[PrefixReuse] = field(default_factory=list)

    @property
    def answer(self) -> str | None:
        return self.answers[-1]

    @property
    def prompt_tokens(self) -> int:
        return sum(u.prompt for u in self.usage)

    @property
    def cached_tokens(self) -> int | None:
        if any(u.cached is None for u in self.usage):
            return None
        return sum(u.cached or 0 for u in self.usage)

    @property
    def sim_reused_tokens(self) -> int:
        return sum(p.reused_tokens for p in self.prefix)


def with_suffix(history: list[Message], suffix: str | None) -> list[Message]:
    """Copy of history with ephemeral text appended as a trailing user message."""
    if not suffix:
        return history
    return [*history, Message(role="user", content=suffix, meta={"ephemeral": True})]


class Agent:
    def __init__(
        self,
        client: ChatClient,
        tools: ToolRegistry,
        system_prompt: str,
        strategy: Strategy | None = None,
        trace: Trace | None = None,
        max_turns: int = 30,
        run_dir: Path | None = None,
        tokenizer: Tokenizer | None = None,
    ):
        self.client = client
        self.trace = trace or Trace(None)
        self.strategy = strategy or NoOp()
        self.strategy.bind(self.trace, run_dir)
        self.tools = tools
        for t in self.strategy.tools():
            self.tools.add(t)
        addendum = self.strategy.system_prompt_addendum()
        self.system_prompt = f"{system_prompt}\n\n{addendum}" if addendum else system_prompt
        self.max_turns = max_turns
        self.tokenizer = tokenizer or ApproxTokenizer()
        self._block_counter = 0

    def _next_block_id(self) -> str:
        self._block_counter += 1
        return f"b{self._block_counter}"

    def run(self, phases: str | list[str]) -> RunResult:
        """Run one or more phases. Each phase is a user message sent after the previous answer."""
        phases = [phases] if isinstance(phases, str) else phases
        history = [
            Message(role="system", content=self.system_prompt),
            Message(role="user", content=phases[0]),
        ]
        answers: list[str | None] = []
        usages: list[Usage] = []
        prefixes: list[PrefixReuse] = []
        tracker = PrefixTracker(self.tokenizer)
        schemas = self.tools.schemas()
        self.trace.log("start", phases=phases, strategy=self.strategy.name)

        for turn in range(1, self.max_turns + 1):
            context_tokens = self.tokenizer.count(serialize_request(history, schemas))
            request = with_suffix(history, self.strategy.on_request(history, turn, context_tokens))
            reuse = tracker.observe(serialize_request(request, schemas))
            prefixes.append(reuse)
            completion = self.client.complete(request, schemas)
            usages.append(completion.usage)
            reply = completion.message
            history.append(reply)
            self.trace.log(
                "turn",
                turn=turn,
                usage=completion.usage,
                sim_prefix=reuse,
                finish_reason=completion.finish_reason,
                content=reply.content,
                tool_calls=[{"id": c.id, "name": c.name, "arguments": c.arguments} for c in reply.tool_calls],
            )

            if not reply.tool_calls:
                answers.append(reply.content)
                if len(answers) == len(phases):
                    self.trace.log("end", stopped="answer", turns=turn)
                    return RunResult(answers, turn, "answer", history, usages, prefixes)
                self.trace.log("phase", phase=len(answers), turn=turn)
                history.append(Message(role="user", content=phases[len(answers)]))
                continue

            for call in reply.tool_calls:
                content, is_error = self.tools.dispatch(call.name, call.arguments, call.raw_arguments)
                block_id = self._next_block_id()
                history.append(
                    Message(
                        role="tool",
                        content=content,
                        tool_call_id=call.id,
                        block_id=block_id,
                        meta={"tool": call.name, "arguments": call.arguments, "is_error": is_error},
                    )
                )
                self.trace.log(
                    "tool_result", block_id=block_id, tool=call.name, arguments=call.arguments,
                    is_error=is_error, chars=len(content),
                )

            self.strategy.after_turn(history, turn)
            validate_tool_pairing(history)

        self.trace.log("end", stopped="max_turns", turns=self.max_turns)
        answers += [None] * (len(phases) - len(answers))
        return RunResult(answers, self.max_turns, "max_turns", history, usages, prefixes)
