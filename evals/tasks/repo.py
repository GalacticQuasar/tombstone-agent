"""Multi-phase codebase questions over a fake repo (list_dir + read_file only, no grep).

File names are neutral (core.py, helpers.py, ...), so the agent has to open files to
find constants. Every answer has a near-miss: a deprecated module with old values, or a
sibling channel's constant (SMS vs email). The final phase asks which billing function
applies the late fee — visible in a file read in phase 0 but not asked about then.
"""

from __future__ import annotations

import random

from evals.env.fs import FakeFS

from .base import Phase, SourceLabel, Task, final_phase

FILE_NAMES = ("core.py", "helpers.py", "policy.py", "models.py", "service.py", "utils.py")
_VERBS = "load build resolve compute merge apply sync collect render validate normalize fetch flush schedule".split()
_NOUNS = "batch record entry window ledger payload cursor bucket snapshot quota event token report profile".split()
_CONST_STEMS = "MAX_ITEMS PAGE_SIZE CACHE_SECONDS BATCH_LIMIT POOL_SIZE TIMEOUT_SECONDS QUEUE_DEPTH CHUNK_BYTES".split()


def _func(rng: random.Random, name: str | None = None, uses: str | None = None) -> str:
    name = name or f"{rng.choice(_VERBS)}_{rng.choice(_NOUNS)}"
    a, b = rng.sample(_NOUNS, 2)
    lines = [
        f"def {name}({a}, {b}=None):",
        f'    """{rng.choice(_VERBS).capitalize()} the {a} against the current {b}."""',
        f"    if {b} is None:",
        f"        {b} = {{}}",
        f"    result = [item for item in {a} if item.get('{rng.choice(_NOUNS)}') is not None]",
    ]
    for _ in range(rng.randint(2, 5)):
        lines.append(rng.choice([
            f"    result = sorted(result, key=lambda r: r.get('{rng.choice(_NOUNS)}', 0))",
            f"    if len(result) > {rng.randint(5, 500)}:\n        result = result[:{rng.randint(5, 500)}]",
            f"    {b}['{rng.choice(_NOUNS)}'] = len(result)",
            f"    total = sum(r.get('amount', 0) for r in result)",
            f"    log.debug('{name}: %d items', len(result))",
        ]))
    if uses:
        lines.append(f"    total = sum(r.get('amount', 0) for r in result)")
        lines.append(f"    return round(total * {uses}, 2)")
    else:
        lines.append("    return result")
    return "\n".join(lines)


def _module(rng: random.Random, pkg: str, consts: dict[str, str], docstring: str = "", special: list[str] | None = None) -> str:
    doc = docstring or f"{pkg.capitalize()} {rng.choice(_NOUNS)} handling."
    parts = [f'"""{doc}"""', "", "import logging", "", "log = logging.getLogger(__name__)", ""]
    noise = {f"{pkg.upper()}_{c}": str(rng.randint(2, 900)) for c in rng.sample(_CONST_STEMS, 3)}
    for k, v in {**noise, **consts}.items():
        parts.append(f"{k} = {v}")
    parts.append("")
    funcs = [_func(rng) for _ in range(rng.randint(9, 13))] + (special or [])
    rng.shuffle(funcs)
    parts.append("\n\n\n".join(funcs))
    return "\n".join(parts) + "\n"


def repo(variant: int) -> Task:
    rng = random.Random(f"repo-{variant}")
    late_rate, grace = rng.choice(["0.015", "0.025", "0.035", "0.045"]), rng.randint(5, 30)
    email_retries, backoff = rng.randint(3, 9), rng.randint(2, 30)
    ttl, lockout = rng.choice([15, 20, 30, 45, 60, 90]), rng.randint(3, 10)
    fee_fn = f"{rng.choice(['accrue', 'assess', 'levy'])}_{rng.choice(['overdue', 'arrears', 'lapsed'])}_charge"

    # pkg → modules as (constants, docstring, special functions); file names are drawn from FILE_NAMES.
    plan: dict[str, list[tuple[dict[str, str], str, list[str]]]] = {
        "billing": [
            ({"LATE_FEE_RATE": late_rate}, "Active billing flow: invoices and late fees.",
             [_func(rng, fee_fn, uses="LATE_FEE_RATE")]),
            ({"GRACE_PERIOD_DAYS": str(grace)}, "Billing policy settings.", []),
            ({"LATE_FEE_RATE": str(round(float(late_rate) + 0.02, 3)), "GRACE_PERIOD_DAYS": str(grace + 7)},
             "DEPRECATED: v1 billing, kept only for the old import path. Not used by the active billing flow.",
             [_func(rng, "legacy_" + fee_fn, uses="LATE_FEE_RATE")]),
            ({}, "", []), ({}, "", []),
        ],
        "notify": [
            ({"EMAIL_MAX_RETRIES": str(email_retries)}, "Email delivery.", []),
            ({"SMS_MAX_RETRIES": str(email_retries + rng.randint(1, 4))}, "SMS delivery.", []),
            ({"BACKOFF_BASE_SECONDS": str(backoff)}, "Retry scheduling shared by all notification channels.", []),
            ({"PUSH_BACKOFF_BASE_SECONDS": str(backoff + rng.randint(3, 10))}, "Push notification delivery.", []),
            ({}, "", []),
        ],
        "auth": [
            ({"SESSION_TTL_MINUTES": str(ttl), "REFRESH_TTL_MINUTES": str(ttl * 24)}, "Session tokens.", []),
            ({"LOCKOUT_THRESHOLD": str(lockout)}, "Login lockout policy for user accounts.", []),
            ({"API_KEY_LOCKOUT_THRESHOLD": str(lockout + rng.randint(5, 20))}, "Lockout policy for API keys (not user logins).", []),
            ({}, "", []), ({}, "", []),
        ],
        "storage": [({}, "", []) for _ in range(4)],
        "reports": [({}, "", []) for _ in range(4)],
    }

    files: dict[str, str] = {"/README.md": "# acme-platform\n\nInternal services: billing, notify, auth, storage, reports.\n"}
    where: dict[str, str] = {}  # constant/function in the *active* code → path
    for pkg, mods in plan.items():
        names = rng.sample(FILE_NAMES, len(mods))
        for fname, (consts, doc, special) in zip(names, mods):
            deprecated = doc.startswith("DEPRECATED")
            path = f"/{pkg}/{'compat.py' if deprecated else fname}"
            files[path] = _module(rng, pkg, consts, doc, special)
            if not deprecated:
                where.update({k: path for k in consts})
                if special:
                    where[fee_fn] = path
        files[f"/{pkg}/__init__.py"] = f'"""{pkg} package."""\n'

    pkg_phase = {"billing": 0, "notify": 1, "auth": 2}
    labels = {("read_file", p): SourceLabel("distractor", pkg_phase.get(p.split("/")[1], 0)) for p in files}
    for phase, keys in enumerate([("LATE_FEE_RATE", "GRACE_PERIOD_DAYS"), ("EMAIL_MAX_RETRIES", "BACKOFF_BASE_SECONDS"),
                                  ("SESSION_TTL_MINUTES", "LOCKOUT_THRESHOLD")]):
        for k in keys:
            labels[("read_file", where[k])] = SourceLabel("relevant", phase)
    labels[("read_file", where[fee_fn])] = SourceLabel("needed_later", 0)

    phases = [
        final_phase("This repo is at /. Using list_dir and read_file, answer: in the *active* billing code, what "
                    "late-fee rate is applied, and what is the grace period in days? Give values exactly as written "
                    "in code.", "<rate>, <days>", late_rate, str(grace)),
        final_phase("Next question: for failed *email* notifications, what is the maximum retry count, and what "
                    "is the retry backoff base in seconds?", "<retries>, <seconds>", str(email_retries), str(backoff)),
        final_phase("Next: how many minutes is a user session token valid, and after how many failed user logins "
                    "is the account locked?", "<minutes>, <attempts>", str(ttl), str(lockout)),
        final_phase("Back to billing: what is the name of the function in the active billing code that applies "
                    "the late fee?", "<function name>", fee_fn),
    ]
    return Task(id=f"repo_{variant}", phases=phases, make_tools=lambda: FakeFS(files).tools(), labels=labels)
