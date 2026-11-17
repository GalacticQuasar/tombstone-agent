"""Distraction by stale state: change notices that set the same setting to different values over time.

A platform posts 4 change notices a day; each changes 2-3 settings of one service
("- timeout (ms): 800 → 650"). Phase 0 catches up on days 1-4, then each phase is one more
day: read that day's notices (via a per-day index page; web_fetch only) and report the
current value of one setting. The asked setting is always last changed that same day.

Knob `versions` (treatment 4 vs control 1): the asked setting was also changed on
versions-1 earlier days, so a full context holds that many outdated values for it.
Every other part of the task is identical between the two settings.

Knob `long`: notices carry longer rationale text (same changes).
"""

from __future__ import annotations

import random

from evals.env.web import MockWeb, Page

from .base import Phase, SourceLabel, Task, final_phase
from .world import NameGen

SERVICES = ("billing-api", "search", "auth", "media", "orders")
KEYS = {
    "rate limit (requests/min)": (60, 2000, 10),
    "timeout (ms)": (200, 5000, 50),
    "max connections": (20, 900, 10),
    "cache TTL (s)": (30, 3600, 30),
    "replica count": (2, 48, 1),
    "retry budget (%)": (5, 60, 5),
}
CATCHUP_DAYS = 4
N_PHASES = 8
PER_DAY = 4
INDEX = "https://ops.example/notices/day-{d}"
_RATIONALE = [
    "The change was reviewed by {p} and rolled out in {n} stages over the afternoon.",
    "Dashboards for the {s} service showed no regression during the canary period.",
    "{p} noted that the previous setting had been chosen before the {s} traffic pattern changed.",
    "The on-call engineer, {p}, approved the rollout after a short load test.",
    "This notice supersedes nothing else in the {s} runbook; other settings are unchanged.",
    "Customer-facing latency for {s} stayed within its objective of {n}0 ms at the median.",
    "The change ticket was opened by {p} after an incident review the previous week.",
    "A rollback plan was prepared but not needed; the {s} error rate stayed flat.",
    "Capacity planning for {s} assumes roughly {n}0 thousand requests per hour at peak.",
    "{p} will revisit the {s} configuration at the next quarterly review.",
    "The deployment pipeline for {s} ran its full integration suite before the change.",
    "Two regions received the change first; the remaining {n} regions followed an hour later.",
]


def _value(rng: random.Random, key: str, avoid: set[int]) -> int:
    lo, hi, step = KEYS[key]
    while (v := rng.randrange(lo, hi + 1, step)) in avoid:
        pass
    return v


def stale(variant: int, versions: int, long: bool, scope: str = "explicit") -> Task:
    """`scope`: "explicit" asks for the current value after all changes; "implicit" just asks for the value."""
    assert 1 <= versions <= 4
    rng = random.Random(f"stale-{variant}")
    names = NameGen(rng)
    people = [names.person() for _ in range(10)]
    pairs = [(s, k) for s in SERVICES for k in KEYS]
    rng.shuffle(pairs)
    asked: list[tuple[str, str]] = []
    for pair in pairs:  # at most 3 asked settings per service, so every notice has filler changes
        if len(asked) < N_PHASES and sum(a[0] == pair[0] for a in asked) < 3:
            asked.append(pair)
    filler_pairs = [p for p in pairs if p not in asked]
    n_days = CATCHUP_DAYS + N_PHASES - 1
    phase_day = [CATCHUP_DAYS + k for k in range(N_PHASES)]  # phase 0 = day 4, after catching up on days 1-4

    # Structure, identical for every knob setting: 3 candidate stale days and a chain of
    # distinct values (initial, 3 stale, final) per asked setting. versions=v keeps the last
    # v-1 stale changes; the slots of dropped ones still exist and carry only filler changes.
    slots: dict[int, list[tuple[int, int] | None]] = {d: [] for d in range(1, n_days + 1)}  # (phase, chain idx)
    chains = []
    for k, pair in enumerate(asked):
        for i, d in enumerate(sorted(rng.sample(range(1, phase_day[k]), 3)), start=1):
            slots[d].append((k, i))
        slots[phase_day[k]].append((k, 4))
        chain: list[int] = []
        for _ in range(5):
            chain.append(_value(rng, pair[1], set(chain)))
        chains.append(chain)
    for d in slots:
        slots[d] += [None] * max(0, PER_DAY - len(slots[d]))
    keep = lambda i: i == 4 or i > 4 - versions  # noqa: E731  (chain idx 1..3 stale, 4 final)

    text_rng = random.Random(f"stale-{variant}-text-{'long' if long else 'short'}")
    n_rationale = 40 if long else 8
    current = {p: None for p in filler_pairs}
    last_asked = {k: chains[k][0] for k in range(N_PHASES)}
    pages: list[Page] = []
    labels: dict[tuple[str, str], SourceLabel] = {}
    for d in range(1, n_days + 1):
        index_lines = [f"Change notices for day {d}", ""]
        phase = max(0, d - CATCHUP_DAYS)
        for n, slot in enumerate(slots[d]):
            srng = random.Random(f"stale-{variant}-{d}-{n}")
            service = asked[slot[0]][0] if slot else srng.choice(SERVICES)
            lines = []
            applied = slot is not None and keep(slot[1])
            if applied:
                k, i = slot
                lines.append(f"- {asked[k][1]}: {last_asked[k]} → {chains[k][i]}")
                last_asked[k] = chains[k][i]
            for pair in srng.sample([p for p in filler_pairs if p[0] == service], 2):
                old = current[pair] if current[pair] is not None else _value(srng, pair[1], set())
                current[pair] = _value(srng, pair[1], {old})
                lines.append(f"- {pair[1]}: {old} → {current[pair]}")
            srng.shuffle(lines)
            rationale = " ".join(
                text_rng.choice(_RATIONALE).format(p=text_rng.choice(people), s=service, n=text_rng.randint(2, 9))
                for _ in range(n_rationale))
            url = f"https://ops.example/notices/{d}-{n + 1}-{service}"
            title = f"Change notice {d}-{n + 1}: {service}"
            body = "\n".join([title, f"Effective: day {d}", "", "Changes:", *lines, "", rationale])
            pages.append(Page(url, title, body))
            labels[("web_fetch", url)] = SourceLabel("relevant" if applied else "distractor", phase)
            index_lines.append(f"- {url}")
        pages.append(Page(INDEX.format(d=d), f"Change notices for day {d}", "\n".join(index_lines)))
        labels[("web_fetch", INDEX.format(d=d))] = SourceLabel("relevant", phase)

    phases: list[Phase] = []
    for k, (service, key) in enumerate(asked):
        d = phase_day[k]
        idx = ", ".join(INDEX.format(d=i) for i in range(1, CATCHUP_DAYS + 1))
        if scope == "explicit":
            if k == 0:
                lead = (f"You are joining the platform team on day {d}. Catch up by reading every change notice from "
                        f"days 1-{d} (index pages: {idx}; use web_fetch). ")
            else:
                lead = f"Day {d}: read today's change notices (index: {INDEX.format(d=d)}). "
            prompt = f"{lead}What is the current {key} of {service}, after all changes so far?"
        else:
            if k == 0:
                lead = f"You are joining the platform team on day {d}. Change notices from days 1-{d}: {idx} (use web_fetch). "
            else:
                lead = f"Day {d} notices: {INDEX.format(d=d)}. "
            prompt = f"{lead}What's the {key} of {service}?"
        phases.append(final_phase(prompt, "<value>", str(chains[k][4])))
    knobs = f"v{versions}-{'long' if long else 'short'}" + ("" if scope == "explicit" else f"-{scope}")

    def tools():
        return [t for t in MockWeb(pages).tools() if t.name == "web_fetch"]

    return Task(id=f"stale-{knobs}_{variant}", phases=phases, make_tools=tools, labels=labels)
