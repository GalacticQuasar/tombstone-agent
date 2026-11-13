"""Redesigned task suite (PLAN.md "Next: task suite redesign"): each task's targeted property."""

from __future__ import annotations

import re

from evals.env.queue import QueueEnv
from evals.metrics import SOURCE_ARG
from evals.tasks import SUITE_V2, TASKS, buried, exact, horizon, queue_task, rot, short
from tombstone.tools import ToolRegistry


def fetch(task, tool, key):
    out, err = ToolRegistry(task.make_tools()).dispatch(tool, {SOURCE_ARG[tool]: key})
    assert not err, out
    return out


def test_suite_v2_registered_and_deterministic():
    assert all(t in TASKS for t in SUITE_V2)
    for make in (horizon, rot, queue_task, exact, buried, short):
        a, b = make(1), make(1)
        assert a.prompts == b.prompts and a.labels == b.labels
        assert a.prompts != make(2).prompts


def test_phase_counts():
    assert len(horizon(1).phases) == 14
    assert len(short(1).phases) == 2
    assert len(buried(1).phases) == 5


def test_queue_delivers_once():
    env = QueueEnv({"q": ["m1", "m2"]})
    assert "2 pending" in env.list_queues()
    assert "m1" in env.poll_queue("q")
    assert "empty" in env.poll_queue("q") and "0 pending" in env.list_queues()


def test_queue_trap_commit_is_on_the_phase0_poll_only():
    t = queue_task(1)
    commit = t.phases[-1].expected[0]
    reg = ToolRegistry(t.make_tools())
    first, _ = reg.dispatch("poll_queue", {"queue": "deploys"})
    assert f"commit={commit} " in first
    again, _ = reg.dispatch("poll_queue", {"queue": "deploys"})
    assert commit not in again
    # The phase-0 answer is unique: one failed deploy in the asked region.
    region = re.search(r"deploy to (\S+) failed", t.prompts[0]).group(1)
    assert len(re.findall(rf"region={region} \S+ status=failed", first)) == 1


def test_rot_readings_differ_from_siblings():
    t = rot(1)
    files = {key: fetch(t, tool, key) for tool, key in t.labels}
    station = lambda txt: txt.split("\n", 1)[0].removeprefix("station: ")  # noqa: E731
    for i, phase in enumerate(t.phases[:-1]):
        sid = re.search(r"At station (\S+),", phase.prompt).group(1)
        family = sid.rstrip("AB")
        when = re.search(r"on (\S+) at (\S+)\?", phase.prompt).groups()
        rows = {station(txt): next(l for l in txt.splitlines() if l.startswith(f"{when[0]}  {when[1]}"))
                for txt in files.values() if txt.startswith("station:") and station(txt).rstrip("AB") == family}
        assert len(rows) == 3 and phase.grade("FINAL: " + ", ".join(phase.expected))
        for other, row in rows.items():
            if other != sid:
                _, _, temp, wind, gust, pres = row.split()
                assert not phase.grade(f"FINAL: {gust}, {pres}")


def test_exact_has_one_fix_per_asked_issue_and_no_search():
    t = exact(1)
    assert {tl.name for tl in t.make_tools()} == {"web_fetch"}
    pages = {key: fetch(t, tool, key) for tool, key in t.labels}
    for phase in t.phases[:-1]:
        issue = re.search(r"fixes issue #(\d+)", phase.prompt).group(1)
        fixes = [p for p in pages.values() if f"Fixes #{issue}:" in p]
        assert len(fixes) == 1 and f"build id: {phase.expected[0]}" in fixes[0]
        assert sum(f"#{issue}" in p for p in pages.values()) >= 3  # near misses exist
    # The trap prompt repeats no URL.
    assert "https://" not in t.prompts[-1]


def test_buried_fact_is_not_searchable():
    t = buried(1)
    boat = re.search(r"lifeboat (.+?)\. Who", t.prompts[-1]).group(1)
    reg = ToolRegistry(t.make_tools())
    for q in (f"lifeboat {boat}", boat, f"{t.phases[-1].expected[0]} lifeboat crew"):
        assert reg.dispatch("web_search", {"query": q})[0] == "No results."
    holders = [key for (tool, key), lab in t.labels.items() if boat in fetch(t, tool, key)]
    assert len(holders) == 1 and t.labels[("web_fetch", holders[0])].kind == "needed_later"
