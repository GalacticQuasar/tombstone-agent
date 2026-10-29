"""Truncate and AutoCompact baseline tests (no network)."""

from __future__ import annotations

from evals.tasks import TASKS
from tests.test_agent import ScriptedClient, call
from tests.test_context import BIG, history_with
from tombstone.agent import Agent
from tombstone.messages import Message, validate_tool_pairing
from tombstone.prefix import ApproxTokenizer, serialize_request
from tombstone.strategies import AutoCompact, Truncate, transcript_text
from tombstone.tools import ToolRegistry
from tombstone.trace import Trace


def bound(strategy, client=None):
    tok = ApproxTokenizer()
    strategy.bind(Trace(None), None, client, tok, lambda h: tok.count(serialize_request(h, [])))
    return strategy


def test_truncate_waits_for_trigger():
    h = history_with(BIG, BIG, BIG)  # ~6k tokens
    t = bound(Truncate(keep_last=1, trigger_tokens=10_000))
    t.after_turn(h, 1)
    assert all(m.content == BIG for m in h if m.role == "tool")


def test_truncate_stubs_all_but_last_k():
    h = history_with(BIG, BIG, BIG)
    t = bound(Truncate(keep_last=1, trigger_tokens=0))
    t.after_turn(h, 1)
    tools = [m for m in h if m.role == "tool"]
    assert tools[0].content == "[b1 cleared: web_fetch(url=u1), 2.0k tok]"
    assert tools[1].content.startswith("[b2 cleared")
    assert tools[2].content == BIG
    validate_tool_pairing(h)
    ev = t.trace.events[-1]
    assert ev["event"] == "truncate_applied" and ev["block_ids"] == ["b1", "b2"]

    # Idempotent: already-cleared blocks aren't re-stubbed or re-logged.
    t.after_turn(h, 2)
    assert len(t.trace.events) == 1


def test_compact_replaces_history_with_summary_and_question():
    h = history_with(BIG, BIG)
    h[1].meta["phase"] = 0
    h.append(Message("assistant", content="FINAL: 1884"))
    h.append(Message("user", "second question?", meta={"phase": 1}))
    h.append(Message("assistant", tool_calls=[call("c9", "web_fetch", url="u9")]))
    h.append(Message("tool", BIG, tool_call_id="c9", block_id="b9", meta={"tool": "web_fetch", "arguments": {"url": "u9"}}))

    client = ScriptedClient([Message("assistant", content="Q1 answered 1884 from u1. Now on Q2; u9 irrelevant.")])
    s = bound(AutoCompact(threshold_tokens=1000), client)
    s.after_turn(h, 5)

    assert [m.role for m in h] == ["system", "user"]
    assert "Q1 answered 1884" in h[1].content
    assert h[1].content.endswith("Continue with the current question:\nsecond question?")
    assert h[1].meta == {"phase": 1, "question": "second question?", "compacted": True}
    # Summarizer saw the full transcript, with no tools offered.
    sent = client.requests[0]
    assert sent[0].content.startswith("You are compacting")
    assert BIG in sent[1].content and "second question?" in sent[1].content
    ev = s.trace.events[-1]
    assert ev["event"] == "compact_applied" and ev["usage"]["prompt"] == 100

    # A second compaction keeps the original question, not the summary blob.
    h.append(Message("assistant", tool_calls=[call("c10", "web_fetch", url="u10")]))
    h.append(Message("tool", BIG, tool_call_id="c10", block_id="b10", meta={"tool": "web_fetch", "arguments": {"url": "u10"}}))
    client.replies.append(Message("assistant", content="still on Q2"))
    s.after_turn(h, 6)
    assert h[1].content.endswith("Continue with the current question:\nsecond question?")
    assert h[1].content.count("<summary of earlier work>") == 1


def test_compact_end_to_end_with_agent():
    task = TASKS["toy_bridge"]
    url = "https://archive.example/velmora-bridge-history"
    client = ScriptedClient([
        Message("assistant", tool_calls=[call("c1", "web_fetch", url=url)]),
        Message("assistant", content="SUMMARY: completed 1884, engineer Ottilie Brandt"),  # summarizer
        Message("assistant", content="1884, Ottilie Brandt"),
    ])
    trace = Trace(None)
    agent = Agent(client, ToolRegistry(task.make_tools()), "sys", strategy=AutoCompact(threshold_tokens=500), trace=trace)
    result = agent.run(task.prompts)
    assert all(task.grade(result.answers))
    # Request after compaction is [system, summary+question] (no ephemeral suffix).
    assert [m.role for m in client.requests[2]] == ["system", "user"]
    assert "SUMMARY: completed 1884" in client.requests[2][1].content


def test_transcript_text_includes_sources():
    h = history_with("page body")
    text = transcript_text(h)
    assert "[tool result b1: web_fetch(url=u1)]\npage body" in text
    assert "(tool calls: web_fetch(url=u1))" in text
    assert ApproxTokenizer().count(text) > 0
