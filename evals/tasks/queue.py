"""Blind clearing: tool output that can't be fetched again, needed several phases later.

Each phase drains one or two message queues (deploys, alerts, billing, ...). Polling
acknowledges the messages, so a second poll returns nothing. Phase 0 asks about one failed
deploy; the last phase asks for the commit of another deploy from that same phase-0 poll.
Commits of the same service in other regions are near misses.

Predicted loser: truncate (its stub can't be re-polled). Predicted winner: self_forget
(summary + archive).
"""

from __future__ import annotations

import random

from evals.env.queue import QueueEnv

from .base import Phase, SourceLabel, Task, final_phase
from .world import NameGen

SERVICES = ("checkout", "search", "payments", "inventory", "accounts", "shipping", "ledger", "media")
REGIONS = ("eu-west", "eu-central", "eu-north", "us-east", "us-west", "us-central", "ap-south", "ap-east")
HOSTS = [f"{p}-{n:02d}" for p in ("web", "db", "cache", "worker") for n in range(1, 9)]


def _hex(rng: random.Random, n: int) -> str:
    return "".join(rng.choices("0123456789abcdef", k=n))


def _ts(rng: random.Random, day: int) -> str:
    return f"2026-11-{day:02d}T{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}Z"


def queue_task(variant: int) -> Task:
    rng = random.Random(f"queue-{variant}")
    names = NameGen(rng)
    people = [names.person() for _ in range(8)]

    # Deploys: every service to every region (64 messages); exactly one failure in the asked region.
    fail_service, fail_region = rng.choice(SERVICES), rng.choice(REGIONS)
    fail_by = rng.choice(people)
    later_service = rng.choice([s for s in SERVICES if s != fail_service])
    later_region = rng.choice([r for r in REGIONS if r != fail_region])
    deploys, commits = [], {}
    for svc in SERVICES:
        for reg in REGIONS:
            commits[(svc, reg)] = _hex(rng, 7)
            failed = (svc, reg) == (fail_service, fail_region) or (reg != fail_region and rng.random() < 0.1)
            by = fail_by if (svc, reg) == (fail_service, fail_region) else rng.choice(people)
            deploys.append((_ts(rng, 3), f"deploy id=dp-{rng.randint(1000, 9999)} service={svc} region={reg} "
                            f"commit={commits[(svc, reg)]} status={'failed' if failed else 'succeeded'} by={by}"))
    deploys = [f"[{t}] {m}" for t, m in sorted(deploys)]

    # Alerts: one host (made unique below) has the most critical alerts.
    favored = rng.choice(HOSTS)
    alerts = []
    for _ in range(100):
        host = favored if rng.random() < 0.2 else rng.choice(HOSTS)
        sev = "critical" if host == favored and rng.random() < 0.7 else rng.choice(["warning", "info", "warning", "critical"])
        alerts.append((_ts(rng, 4), f"alert id=al-{rng.randint(10000, 99999)} host={host} severity={sev} "
                       f"check={rng.choice(['disk', 'cpu', 'latency', 'memory', 'errors'])} value={rng.randint(50, 99)}%"))
    crit = {h: sum(f"host={h} severity=critical" in m for _, m in alerts) for h in HOSTS}
    top_host = max(crit, key=lambda h: (crit[h], h))
    if sorted(crit.values())[-1] == sorted(crit.values())[-2]:  # make the winner unique
        alerts.append((_ts(rng, 4), f"alert id=al-{rng.randint(10000, 99999)} host={top_host} severity=critical "
                       f"check=disk value=97%"))
    alerts = [f"[{t}] {m}" for t, m in sorted(alerts)]

    # Billing + refunds: which invoice was refunded twice.
    invoices = [f"inv-{rng.randint(100000, 999999)}" for _ in range(80)]
    billing = [f"[{_ts(rng, 5)}] invoice {inv} customer={rng.choice(people)} amount={rng.randint(20, 2000)}.{rng.randint(0, 99):02d} "
               f"currency={rng.choice(['EUR', 'USD', 'GBP'])}" for inv in invoices]
    twice = rng.choice(invoices)
    refunded = rng.sample([i for i in invoices if i != twice], 26) + [twice, twice]
    rng.shuffle(refunded)
    refunds = [f"[{_ts(rng, 6)}] refund rf-{rng.randint(1000, 9999)} invoice={inv} reason="
               f"{rng.choice(['duplicate', 'damaged', 'late', 'cancelled'])}" for inv in refunded]

    # Audit: which person rotated the production database credentials.
    rotator = rng.choice(people)
    audit = [f"[{_ts(rng, 7)}] audit user={rng.choice(people)} action={rng.choice(['login', 'export', 'role-change', 'key-create', 'logout'])} "
             f"target={rng.choice(['staging', 'production', 'dev'])}-{rng.choice(['db', 'bucket', 'cluster'])}" for _ in range(100)]
    audit.insert(rng.randint(5, 95), f"[{_ts(rng, 7)}] audit user={rotator} action=credential-rotate target=production-db")
    audit.insert(rng.randint(5, 95), f"[{_ts(rng, 7)}] audit user={rng.choice([p for p in people if p != rotator])} "
                                     f"action=credential-rotate target=staging-db")

    # Backups: which database's backup was smallest.
    dbs = [f"{s}-db" for s in SERVICES]
    sizes = rng.sample(range(20, 900), len(dbs))
    backups = [f"[{_ts(rng, 8)}] backup db={d} size_gb={sz} status=ok snapshot=sn-{_hex(rng, 10)}" for d, sz in zip(dbs, sizes)]
    backups += [f"[{_ts(rng, 8)}] backup db={rng.choice(dbs)} size_gb={rng.randint(min(sizes) + 1, 900)} status=ok "
                f"snapshot=sn-{_hex(rng, 10)}" for _ in range(50)]
    backups.sort()
    smallest = dbs[sizes.index(min(sizes))]

    queues = {
        "deploys": deploys, "alerts": alerts, "billing": billing, "refunds": refunds,
        "audit": audit, "backups": backups,
        "signups": [f"[{_ts(rng, 9)}] signup user=u{rng.randint(1000, 9999)} plan={rng.choice(['free', 'pro'])}" for _ in range(30)],
    }
    phase_of = {"deploys": 0, "alerts": 1, "billing": 2, "refunds": 2, "audit": 3, "backups": 4}
    labels = {("poll_queue", q): SourceLabel("relevant", phase_of.get(q, 0)) for q in queues}
    labels[("poll_queue", "deploys")] = SourceLabel("needed_later", 0)
    labels[("poll_queue", "signups")] = SourceLabel("distractor", 0)

    phases: list[Phase] = [
        final_phase(f"You are on call. Poll the `deploys` queue: which service's deploy to {fail_region} failed, "
                    f"and who ran it?", "<service>, <person>", fail_service, fail_by),
        final_phase("Next: poll the `alerts` queue. Which host raised the most `critical` alerts?", "<host>", top_host),
        final_phase("Next: poll the `billing` and `refunds` queues. Which invoice was refunded twice?",
                    "<invoice>", twice),
        final_phase("Next: poll the `audit` queue. Who rotated the credentials of the production database?",
                    "<person>", rotator),
        final_phase("Next: poll the `backups` queue. Which database had the smallest single backup?",
                    "<db>", smallest),
        final_phase(f"Back to the deploys from the first question: which commit was deployed for {later_service} "
                    f"in {later_region}?", "<commit>", commits[(later_service, later_region)]),
    ]
    return Task(id=f"queue_{variant}", phases=phases, make_tools=lambda: QueueEnv(queues).tools(), labels=labels)
