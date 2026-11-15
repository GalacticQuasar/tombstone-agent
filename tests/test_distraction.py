"""Distraction calibration tasks (PLAN.md "Next: distraction suite"): knobs change only the treatment."""

from __future__ import annotations

import re

from evals.metrics import SOURCE_ARG
from evals.tasks import CALIB, TASKS
from evals.tasks.latent import CONCEPTS, latent
from evals.tasks.stale import stale
from tombstone.tools import ToolRegistry

STOP = set("a an and the of to in at for on as with by had has was were their it its into from who that".split())


def words(s: str) -> set[str]:
    return {w.strip("'s") for w in re.findall(r"[a-z']+", s.lower())} - STOP


def pages(task):
    reg = ToolRegistry(task.make_tools())
    return {key: reg.dispatch(tool, {SOURCE_ARG[tool]: key})[0] for tool, key in task.labels}


def test_calib_registered_and_deterministic():
    assert len(CALIB) == 16 and all(t in TASKS for t in CALIB)
    assert latent(1, True, False).prompts == latent(1, True, False).prompts
    assert stale(1, 4, True).prompts == stale(1, 4, True).prompts
    assert latent(1, True, False).prompts != latent(2, True, False).prompts


def test_latent_answers_share_no_content_words_with_questions():
    for desc, answer, _, decoy in CONCEPTS:
        assert not words(desc) & words(answer), (desc, answer)
        assert words(desc) & words(decoy), (desc, decoy)  # the lexical decoy does overlap


def test_latent_knobs_only_change_the_treatment():
    base = latent(1, False, False)
    for cross, long in ((True, False), (False, True), (True, True)):
        t = latent(1, cross, long)
        assert t.prompts == base.prompts and [p.expected for p in t.phases] == [p.expected for p in base.phases]
        assert t.labels == base.labels


def test_latent_cross_decoys_sit_in_earlier_towns_only_when_on():
    for cross in (False, True):
        t = latent(1, cross, False)
        texts = pages(t)
        for k, phase in enumerate(t.phases):
            town = re.search(r"people of (\S+), who", phase.prompt).group(1)
            concept = next(c for c in CONCEPTS if c[0] in phase.prompt)
            holders = [u for u, txt in texts.items() if concept[2] in txt]
            if cross and k > 0:
                assert len(holders) == 1 and f"/{town.lower()}/" not in holders[0]
                assert t.labels[("web_fetch", holders[0])].phase < k
            else:
                assert holders == []
            answer_pages = [u for u, txt in texts.items() if concept[1] in txt]
            assert len(answer_pages) == 1 and f"/{town.lower()}/" in answer_pages[0]
            assert phase.expected[0] in texts[answer_pages[0]]


def test_stale_knobs_only_change_the_treatment():
    base = stale(1, 1, False)
    for versions, long in ((4, False), (1, True), (4, True)):
        t = stale(1, versions, long)
        assert t.prompts == base.prompts and [p.expected for p in t.phases] == [p.expected for p in base.phases]
        assert set(t.labels) == set(base.labels)


def test_stale_versions_put_outdated_values_in_earlier_notices():
    for versions in (1, 4):
        t = stale(1, versions, False)
        texts = pages(t)
        for k, phase in enumerate(t.phases):
            key, service = re.search(r"current (.+) of (\S+), after", phase.prompt).groups()
            day = 4 + k
            changes = []  # (day, new value) for this setting, from notices of this service
            for url, txt in texts.items():
                m = re.match(r"https://ops.example/notices/(\d+)-\d+-(\S+)$", url)
                if not m or m.group(2) != service:
                    continue
                for old, new in re.findall(rf"- {re.escape(key)}: (\d+) → (\d+)", txt):
                    changes.append((int(m.group(1)), new))
            assert max(changes)[0] == day and [n for d, n in changes if d == day] == [phase.expected[0]]
            assert len(changes) == versions and all(n != phase.expected[0] for d, n in changes if d < day)
