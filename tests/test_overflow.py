"""Agent-side context limit: runs stop with `context_overflow` instead of crashing (no network)."""

from __future__ import annotations

from tests.test_agent import ScriptedClient, call
from tombstone.agent import Agent
from tombstone.messages import Message
from tombstone.strategies import Strategy, Truncate
from tombstone.tools import Tool, ToolRegistry, object_schema
from tombstone.trace import Trace

BIG = "x" * 8000  # ~2k tokens with ApproxTokenizer


def big_tool() -> ToolRegistry:
    return ToolRegistry([Tool("fetch", "Return a big page.", object_schema({"url": {"type": "string"}}), lambda url: BIG)])


def fetches(n: int) -> list[Message]:
    return [Message("assistant", tool_calls=[call(f"c{i}", "fetch", url=f"u{i}")]) for i in range(n)]


def test_overflow_stops_before_sending_and_pads_answers():
    client = ScriptedClient([Message("assistant", content="a1"), *fetches(5), Message("assistant", content="a2")])
    trace = Trace(None)
    agent = Agent(client, big_tool(), "sys", trace=trace, max_context=5_000)
    result = agent.run(["q1", "q2", "q3"])

    assert result.stopped == "context_overflow"
    assert result.answers == ["a1", None, None]
    # Requests: q1 → a1, then fetches u0, u1, u2. With three ~2k pages in context the next
    # request would exceed 5k, so it is never sent.
    assert len(client.requests) == 4 == result.turns == len(result.usage) == len(result.prefix)
    assert agent.count_context(result.history) > 5_000
    end = trace.events[-1]
    assert end["event"] == "end" and end["stopped"] == "context_overflow"
    assert end["request_tokens"] > end["max_context"] == 5_000


def test_limit_counts_the_ephemeral_suffix():
    class BigLedger(Strategy):
        def on_request(self, history, turn, context_tokens):
            return BIG

    client = ScriptedClient([Message("assistant", content="a1")])
    result = Agent(client, big_tool(), "sys", strategy=BigLedger(), max_context=1_000).run("q")
    assert result.stopped == "context_overflow" and client.requests == []


def test_managed_strategy_stays_under_limit_where_noop_overflows():
    def run(strategy):
        client = ScriptedClient([*fetches(6), Message("assistant", content="done")])
        return Agent(client, big_tool(), "sys", strategy=strategy, max_context=9_000).run("q")

    assert run(None).stopped == "context_overflow"
    managed = run(Truncate(keep_last=2, trigger_tokens=4_000))
    assert managed.stopped == "answer" and managed.answer == "done"


def test_no_limit_by_default():
    client = ScriptedClient([*fetches(6), Message("assistant", content="done")])
    assert Agent(client, big_tool(), "sys").run("q").stopped == "answer"
