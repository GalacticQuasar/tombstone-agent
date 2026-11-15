from .base import Task
from .chain import chain
from .dossier import dossier, dossier_task
from .exact import exact
from .latent import latent
from .queue import queue_task
from .repo import repo
from .rot import rot
from .stale import stale
from .toy import toy_bridge


def horizon(variant: int) -> Task:
    """Context growth: 14 dossier phases, more than a full context can hold (predicted loser: none)."""
    return dossier_task(f"horizon_{variant}", f"horizon-{variant}", 14, trap=None)


def buried(variant: int) -> Task:
    """Forgetting too early: an aside on a phase-0 page, asked later and not findable by search
    (predicted loser: self_forget)."""
    return dossier_task(f"buried_{variant}", f"buried-{variant}", 4, trap="lifeboat")


def short(variant: int) -> Task:
    """Overhead: two phases, too short for forgetting to pay off (predicted loser: self_forget)."""
    return dossier_task(f"short_{variant}", f"short-{variant}", 2, trap=None)


# The original suite, then the redesigned one (PLAN.md "Next: task suite redesign").
SUITE_V1 = ["dossier_1", "dossier_2", "chain_1", "chain_2", "repo_1", "repo_2"]
SUITE_V2 = [f"{name}_{v}" for v in (1, 2) for name in ("horizon", "rot", "queue", "exact", "buried", "short")]
# Distraction calibration (PLAN.md "Next: distraction suite"): each family with its knob off/on, short/long.
_CALIB_TASKS = [
    *(latent(v, cross, long) for v in (1, 2) for cross in (False, True) for long in (False, True)),
    *(stale(v, versions, long) for v in (1, 2) for versions in (1, 4) for long in (False, True)),
]
CALIB = [t.id for t in _CALIB_TASKS]

TASKS: dict[str, Task] = {
    t.id: t
    for t in [
        toy_bridge(),
        dossier(1), dossier(2),
        chain(1), chain(2),
        repo(1), repo(2),
        *(make(v) for v in (1, 2) for make in (horizon, rot, queue_task, exact, buried, short)),
        *_CALIB_TASKS,
    ]
}
