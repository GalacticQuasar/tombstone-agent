"""Agent loop tests against a scripted fake client (no network)."""

from __future__ import annotations

import pytest

from evals.tasks import TASKS
from tombstone.agent import Agent
from tombstone.client import Completion, Usage, parse_tool_call
from tombstone.messages import Message, ToolCall, render, validate_tool_pairing
from tombstone.strategies import Strategy
from tombstone.tools import ToolRegistry


class ScriptedClient:
    """Replays a fixed list of assistant messages and records each request."""

    def __init__(self, replies: list[Message]):
        self.replies = list(replies)
        self.requests: list[list[Message]] = []

    def complete(self, messages, tools):
        self.requests.append(list(messages))
        return Completion(self.replies.pop(0), Usage(prompt=100, cached=0, completion=10), "stop")


def call(id: str, name: str, **args) -> ToolCall:
    return ToolCall(id=id, name=name, arguments=args)


def test_toy_task_end_to_end_with_scripted_client():
    task = TASKS["toy_bridge"]
    url = "https://archive.example/velmora-bridge-history"
    client = ScriptedClient([
        Message("assistant", tool_calls=[call("c1", "web_search", query="velmora bridge history")]),
        Message("assistant", tool_calls=[call("c2", "web_fetch", url=url)]),
        Message("assistant", content="1884, Ottilie Brandt"),
    ])
    agent = Agent(client, ToolRegistry(task.make_tools()), "sys")
    result = agent.run(task.prompts)

    assert result.stopped == "answer"
    assert all(task.grade(result.answers))
    tool_msgs = [m for m in result.history if m.role == "tool"]
    assert [m.block_id for m in tool_msgs] == ["b1", "b2"]
    assert "completed in 1884" in tool_msgs[1].content
    validate_tool_pairing(result.history)


def test_tool_errors_are_reported_not_raised():
    task = TASKS["toy_bridge"]
    client = ScriptedClient([
        Message("assistant", tool_calls=[
            call("c1", "web_fetch", url="https://nope.example"),
            call("c2", "no_such_tool"),
            ToolCall("c3", "web_fetch", {}, raw_arguments="{not json"),
        ]),
        Message("assistant", content="done"),
    ])
    result = Agent(client, ToolRegistry(task.make_tools()), "sys").run("q")
    errs = [m for m in result.history if m.role == "tool"]
    assert all(m.meta["is_error"] for m in errs)
    assert "404" in errs[0].content
    assert "unknown tool" in errs[1].content
    assert "could not parse" in errs[2].content


def test_ephemeral_suffix_sent_but_never_stored():
    class Ledger(Strategy):
        def on_request(self, history, turn, context_tokens):
            return f"LEDGER n={len(history)}"

    client = ScriptedClient([
        Message("assistant", tool_calls=[call("c1", "web_search", query="velmora")]),
        Message("assistant", content="ok"),
    ])
    task = TASKS["toy_bridge"]
    result = Agent(client, ToolRegistry(task.make_tools()), "sys", strategy=Ledger()).run("q")

    assert all(r[-1].content.startswith("LEDGER") for r in client.requests)
    assert not any((m.content or "").startswith("LEDGER") for m in result.history)
    # Prefix stability: request 2 minus its suffix extends request 1 minus its suffix.
    first, second = client.requests[0][:-1], client.requests[1][:-1]
    assert render(second[: len(first)]) == render(first)


def test_max_turns_stops():
    client = ScriptedClient([
        Message("assistant", tool_calls=[call(f"c{i}", "web_search", query="x")]) for i in range(3)
    ])
    task = TASKS["toy_bridge"]
    result = Agent(client, ToolRegistry(task.make_tools()), "sys", max_turns=3).run("q")
    assert result.stopped == "max_turns"
    assert result.answer is None


def test_validate_tool_pairing_rejects_orphans():
    with pytest.raises(ValueError):
        validate_tool_pairing([Message("tool", content="x", tool_call_id="ghost")])
    with pytest.raises(ValueError):
        validate_tool_pairing([Message("assistant", tool_calls=[call("c1", "t")])])


def test_parse_tool_call_handles_bad_json():
    tc = parse_tool_call("c1", "t", "{oops")
    assert tc.arguments == {} and tc.raw_arguments == "{oops"
    assert parse_tool_call("c2", "t", '{"a": 1}').arguments == {"a": 1}
