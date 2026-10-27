"""Context store, forgetting flow, and prefix-metric tests (no network)."""

from __future__ import annotations

import json

import pytest

from evals.tasks import TASKS
from tests.test_agent import ScriptedClient, call
from tombstone.agent import Agent
from tombstone.context import ContextStore, tombstone_text
from tombstone.messages import Message, validate_tool_pairing
from tombstone.prefix import ApproxTokenizer, PrefixTracker, common_prefix_len
from tombstone.strategies import SelfForget
from tombstone.tools import ToolError, ToolRegistry
from tombstone.trace import Trace

BIG = "x" * 8000  # ~2k tokens with ApproxTokenizer
SMALL = "y" * 100


def history_with(*contents: str) -> list[Message]:
    h = [Message("system", "s"), Message("user", "u")]
    for i, c in enumerate(contents, 1):
        h.append(Message("assistant", tool_calls=[call(f"c{i}", "web_fetch", url=f"u{i}")]))
        h.append(Message("tool", c, tool_call_id=f"c{i}", block_id=f"b{i}",
                         meta={"tool": "web_fetch", "arguments": {"url": f"u{i}"}}))
    return h


def test_forget_is_deferred_until_threshold():
    h = history_with(BIG, BIG, BIG)
    store = ContextStore(apply_threshold=3000)
    store.index(h, 1)

    store.request_forget("b1", "irrelevant page about rivers")
    assert store.maybe_apply(h) == []  # ~2k savings < 3k threshold
    assert h[3].content == BIG
    assert store.blocks["b1"].status == "pending"

    store.request_forget("b2", "travel guide, nothing on the bridge")
    assert store.maybe_apply(h) == ["b1", "b2"]
    assert h[3].content == tombstone_text(store.blocks["b1"])
    assert "Summary: irrelevant page about rivers" in h[3].content
    assert h[5].content.startswith("[b2 forgotten: web_fetch(url=u2)")
    assert h[7].content == BIG  # untouched
    validate_tool_pairing(h)


def test_threshold_zero_applies_immediately():
    h = history_with(BIG)
    store = ContextStore(apply_threshold=0)
    store.index(h, 1)
    store.request_forget("b1", "s")
    assert store.maybe_apply(h) == ["b1"]


def test_apply_only_rewrites_tool_result_content():
    h = history_with(BIG, BIG)
    before = [(m.role, m.tool_call_id, m.block_id, len(m.tool_calls)) for m in h]
    store = ContextStore(apply_threshold=0)
    store.index(h, 1)
    store.request_forget("b2", "s")
    store.maybe_apply(h)
    assert [(m.role, m.tool_call_id, m.block_id, len(m.tool_calls)) for m in h] == before


def test_forget_errors():
    h = history_with(BIG)
    store = ContextStore(apply_threshold=0)
    store.index(h, 1)
    with pytest.raises(ToolError, match="unknown"):
        store.request_forget("b9", "s")
    with pytest.raises(ToolError, match="empty"):
        store.request_forget("b1", "  ")
    store.request_forget("b1", "s")
    with pytest.raises(ToolError, match="already pending"):
        store.request_forget("b1", "s")
    store.maybe_apply(h)
    with pytest.raises(ToolError, match="already forgotten"):
        store.request_forget("b1", "s")


def test_retrieve_roundtrip_and_archive(tmp_path):
    h = history_with(BIG)
    store = ContextStore(apply_threshold=0, archive_dir=tmp_path)
    store.index(h, 1)
    with pytest.raises(ToolError, match="never forgotten"):
        store.retrieve("b1")
    store.request_forget("b1", "s")
    store.maybe_apply(h)

    out = store.retrieve("b1")
    assert out.startswith("[retrieved b1: web_fetch(url=u1)]\n") and out.endswith(BIG)
    rec = json.loads((tmp_path / "b1.json").read_text())
    assert rec["content"] == BIG and rec["summary"] == "s"
    # Retrieval doesn't restore in place; the tombstone stays.
    assert h[3].content.startswith("[b1 forgotten")


def test_retrieve_pending_cancels_forget():
    h = history_with(BIG)
    store = ContextStore(apply_threshold=10_000)
    store.index(h, 1)
    store.request_forget("b1", "s")
    assert "Cancelled" in store.retrieve("b1")
    assert store.blocks["b1"].status == "live"
    assert store.pending_savings() == 0


def test_ledger_hides_small_live_blocks():
    h = history_with(BIG, SMALL)
    store = ContextStore(min_block_tokens=300)
    store.index(h, 1)
    store.index(h, 3)
    ledger = store.ledger(context_tokens=2100)
    assert "b1 | web_fetch(url=u1) | 2.0k | 2 | live" in ledger
    assert "b2" not in ledger


def test_common_prefix_len():
    assert common_prefix_len("abcdef", "abcxyz") == 3
    assert common_prefix_len("abc", "abc") == 3
    assert common_prefix_len("", "abc") == 0


def test_prefix_tracker():
    t = PrefixTracker(ApproxTokenizer())
    assert t.observe("a" * 400).reused_tokens == 0
    r = t.observe("a" * 400 + "b" * 400)
    assert r.prev_tokens == 100 and r.reused_tokens == 100 and r.frac_of_prev == 1.0
    r = t.observe("a" * 200 + "c" * 600)
    assert r.reused_tokens == 50


def test_self_forget_end_to_end(tmp_path):
    """Scripted agent fetches 2 pages, forgets one, batch applies, retrieves it."""
    task = TASKS["toy_bridge"]
    river = "https://wiki.example/Velmora_River"
    archive = "https://archive.example/velmora-bridge-history"
    client = ScriptedClient([
        Message("assistant", tool_calls=[call("c1", "web_fetch", url=river), call("c2", "web_fetch", url=archive)]),
        Message("assistant", tool_calls=[call("c3", "forget", block_id="b1", summary="river page, irrelevant")]),
        Message("assistant", tool_calls=[call("c4", "retrieve_context", block_id="b1")]),
        Message("assistant", content="1884, Ottilie Brandt"),
    ])
    trace = Trace(None)
    strategy = SelfForget(apply_threshold=0)
    agent = Agent(client, ToolRegistry(task.make_tools()), "sys", strategy=strategy, trace=trace, run_dir=tmp_path)
    result = agent.run(task.prompt)

    assert result.stopped == "answer" and task.grade(result.answer)
    assert "## Context management" in result.history[0].content
    tools = {m.block_id: m for m in result.history if m.role == "tool"}
    assert tools["b1"].content.startswith("[b1 forgotten: web_fetch(url=https://wiki.example/Velmora_River)")
    assert "Velmora River flows" in tools["b4"].content  # retrieval appended as a new block
    assert (tmp_path / "archive" / "b1.json").exists()
    assert [e["event"] for e in trace.events if e["event"] in ("forget_requested", "forget_applied", "retrieve")] == [
        "forget_requested", "forget_applied", "retrieve",
    ]

    # Ledger is sent each turn but never stored.
    assert all(r[-1].content.startswith("[context ledger]") for r in client.requests)
    assert not any((m.content or "").startswith("[context ledger]") for m in result.history)

    # Prefix reuse: near-full on turn 2; the forget applies after turn 2, rewriting b1 early in
    # history, so turn 3 loses most of the prefix; turn 4 is near-full again (retrieval appends).
    # "Near-full" = everything except the previous request's ephemeral ledger.
    reuse = [p.frac_of_prev for p in result.prefix]
    assert reuse[1] > 0.9
    assert reuse[2] < 0.5
    assert reuse[3] > 0.95
