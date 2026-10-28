"""Synthetic task generation, graders, metrics, and multi-phase agent flow (no network)."""

from __future__ import annotations

from evals.metrics import forget_breakdown, reads_breakdown
from evals.tasks import TASKS
from evals.tasks.base import final_grader, final_line
from evals.tasks.chain import chain
from evals.tasks.dossier import dossier
from evals.tasks.repo import repo
from tests.test_agent import ScriptedClient, call
from tombstone.agent import Agent
from tombstone.messages import Message
from tombstone.strategies import SelfForget
from tombstone.tools import ToolRegistry
from tombstone.trace import Trace

SOURCE_ARG = {"web_fetch": "url", "read_file": "path"}


def test_final_line_parsing():
    assert final_line("blah\nFINAL: 1884, 212") == "1884, 212"
    assert final_line("**FINAL: 1884, 212**") == "1884, 212"
    assert final_line("FINAL: `accrue_overdue_charge`") == "accrue_overdue_charge"
    assert final_line("FINAL: a\nmore\nFINAL: b") == "b"
    assert final_line("no final here") is None


def test_final_grader_is_token_exact():
    g = final_grader("1884", "212")
    assert g("FINAL: 1884, 212 m")
    assert not g("FINAL: 1884, 2120")
    assert not g("FINAL: 18845, 212")
    f = final_grader("accrue_overdue_charge")
    assert f("FINAL: accrue_overdue_charge")
    assert not f("FINAL: legacy_accrue_overdue_charge")
    assert final_grader("0.035", "14")("FINAL: 0.035, 14")
    assert final_grader("Harbor Trust")("FINAL: the harbor trust.")


def test_tasks_are_deterministic():
    for make in (dossier, chain, repo):
        a, b = make(1), make(1)
        assert a.prompts == b.prompts and a.labels == b.labels
        assert [p.expected for p in a.phases] == [p.expected for p in b.phases]
        assert a.labels != make(2).labels


def test_every_label_resolves_and_answers_are_present():
    for task in TASKS.values():
        reg = ToolRegistry(task.make_tools())
        for tool, key in task.labels:
            out, err = reg.dispatch(tool, {SOURCE_ARG[tool]: key})
            assert not err, (task.id, key, out)
        kinds = {lab.kind for lab in task.labels.values()}
        assert "distractor" in kinds and "relevant" in kinds, task.id


def test_answers_live_on_non_distractor_sources():
    """Each phase's expected values appear in its own phase's (or a needed_later) source."""
    for t in TASKS.values():
        if t.id == "toy_bridge":
            continue
        reg = ToolRegistry(t.make_tools())
        for i, phase in enumerate(t.phases):
            keys = [k for k, lab in t.labels.items()
                    if lab.kind == "needed_later" or (lab.kind == "relevant" and lab.phase == i)]
            text = "\n".join(reg.dispatch(tool, {SOURCE_ARG[tool]: key})[0] for tool, key in keys)
            assert phase.expected, t.id
            for value in phase.expected:
                assert value in text, (t.id, i, value)
            assert phase.grade("FINAL: " + ", ".join(phase.expected))


def test_repo_decoys_differ_from_answers():
    t = repo(1)
    fs = t.make_tools()
    files = {tl.name: tl for tl in fs}
    compat = files["read_file"].handler("/billing/compat.py")
    assert "DEPRECATED" in compat
    expected_rate = t.phases[0].expected[0]
    assert f"LATE_FEE_RATE = {expected_rate}\n" not in compat


def test_multi_phase_agent_flow_and_metrics():
    task = TASKS["toy_bridge"]
    url = "https://archive.example/velmora-bridge-history"
    river = "https://wiki.example/Velmora_River"
    client = ScriptedClient([
        Message("assistant", tool_calls=[call("c1", "web_fetch", url=river), call("c2", "web_fetch", url=url)]),
        Message("assistant", content="1884, Ottilie Brandt"),
        Message("assistant", tool_calls=[call("c3", "forget", block_id="b1", summary="river page")]),
        Message("assistant", content="second answer"),
    ])
    trace = Trace(None)
    agent = Agent(client, ToolRegistry(task.make_tools()), "sys", strategy=SelfForget(apply_threshold=0), trace=trace)
    result = agent.run(["first question", "second question"])

    assert result.answers == ["1884, Ottilie Brandt", "second answer"]
    # Phase 2's question arrives as a user message right after phase 1's answer.
    users = [m.content for m in result.history if m.role == "user"]
    assert users == ["first question", "second question"]
    assert [e["phase"] for e in trace.events if e["event"] == "phase"] == [1]
    assert forget_breakdown(trace.events, task) == {"distractor": 1}
    assert reads_breakdown(trace.events, task) == {"distractor": 1, "relevant": 1}


def test_max_turns_pads_unreached_phases():
    task = TASKS["toy_bridge"]
    client = ScriptedClient([Message("assistant", content="a1")] + [
        Message("assistant", tool_calls=[call(f"c{i}", "web_search", query="x")]) for i in range(2)
    ])
    result = Agent(client, ToolRegistry(task.make_tools()), "sys", max_turns=3).run(["q1", "q2", "q3"])
    assert result.answers == ["a1", None, None]
