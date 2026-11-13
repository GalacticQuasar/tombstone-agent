"""Context rot: many near-identical station logs kept in context, then lookups that need the right one.

45 weather-station logs under /logs with neutral names (log_01.txt …), so the agent has to
open files to find a station. Stations come in families of near-duplicate IDs (KV7, KV7A,
KV7B) whose readings differ by small amounts, over the same dates and hours. Each phase
asks for two readings at one station; the last phase asks for a phase-0 station's reading
that wasn't asked then. A full context ends up holding dozens of look-alike tables.

Predicted loser: none (rot). Predicted winners: self_forget, truncate.
"""

from __future__ import annotations

import random
import string

from evals.env.fs import FakeFS

from .base import Phase, SourceLabel, Task, final_phase
from .world import NameGen

DATES = ("2026-03-14", "2026-03-15")
HOURS = range(0, 24, 2)
N_FAMILIES = 15
N_PHASES = 8


def _family_ids(rng: random.Random, used: set[str]) -> list[str]:
    while True:
        base = "".join(rng.choices(string.ascii_uppercase, k=2)) + str(rng.randint(2, 9))
        if base not in used:
            used.add(base)
            return [base, base + "A", base + "B"]


def _readings(rng: random.Random) -> dict[tuple[str, int], tuple[str, int, int, str]]:
    """(date, hour) → (temp, wind, gust, pressure) for one family's base station."""
    out = {}
    temp, pres = rng.uniform(8, 16), rng.uniform(1002, 1022)
    for d in DATES:
        for h in HOURS:
            temp = min(max(temp + rng.uniform(-0.8, 0.8), 5.0), 24.0)
            pres = min(max(pres + rng.uniform(-0.6, 0.6), 990.0), 1035.0)
            wind = rng.randint(4, 30)
            out[(d, h)] = (f"{temp:.1f}", wind, wind + rng.randint(3, 15), f"{pres:.1f}")
    return out


def _siblings(rng: random.Random, base: dict) -> tuple[dict, dict]:
    """Two sibling stations: same weather, every reading off by a small nonzero amount that
    differs between the siblings, so no sibling row matches another station's."""
    a, b = {}, {}
    for k, (t, w, g, p) in base.items():
        (dta, dtb), (dwa, dwb), (dga, dgb), (dpa, dpb) = (
            rng.sample(opts, 2) for opts in
            ((-0.3, -0.2, -0.1, 0.1, 0.2, 0.3), (-1, 1), (-2, -1, 1, 2), (-0.4, -0.2, 0.2, 0.4))
        )
        # Gust ≥ wind + 3 in the base, so gust stays above wind after the offsets.
        a[k] = (f"{float(t) + dta:.1f}", w + dwa, g + dga, f"{float(p) + dpa:.1f}")
        b[k] = (f"{float(t) + dtb:.1f}", w + dwb, g + dgb, f"{float(p) + dpb:.1f}")
    return a, b


def _log(station: str, site: str, rows: dict) -> str:
    lines = [f"station: {station}", f"site: {site}", "units: temp C, wind/gust km/h, pressure hPa", "",
             "date        hour   temp   wind  gust  pressure"]
    for (d, h), (t, w, g, p) in rows.items():
        lines.append(f"{d}  {h:02d}:00  {t:>5}  {w:>4}  {g:>4}  {p:>8}")
    return "\n".join(lines) + "\n"


def rot(variant: int) -> Task:
    rng = random.Random(f"rot-{variant}")
    names = NameGen(rng)
    used: set[str] = set()
    stations: dict[str, dict] = {}
    sites: dict[str, str] = {}
    families: list[list[str]] = []
    for _ in range(N_FAMILIES):
        ids = _family_ids(rng, used)
        families.append(ids)
        base = _readings(rng)
        site = names.place()
        for j, (sid, rows) in enumerate(zip(ids, (base, *_siblings(rng, base)))):
            stations[sid] = rows
            sites[sid] = f"{site} {('North', 'Quay', 'Hill')[j]}"

    order = list(stations)
    rng.shuffle(order)
    path_of = {sid: f"/logs/log_{i + 1:02d}.txt" for i, sid in enumerate(order)}
    files = {path_of[sid]: _log(sid, sites[sid], stations[sid]) for sid in order}
    files["/README.md"] = ("# station-archive\n\nHourly logs from the coastal weather network, one file per "
                           "station under /logs. Station IDs are in each file's header.\n")

    # One station per phase, from distinct families, so siblings stay decoys.
    asked = [rng.choice(fam) for fam in rng.sample(families, N_PHASES)]

    labels = {("read_file", p): SourceLabel("distractor", 0) for p in files}
    phases: list[Phase] = []
    for i, sid in enumerate(asked):
        d, h = rng.choice(DATES), rng.choice(list(HOURS))
        _, _, gust, pres = stations[sid][(d, h)]
        labels[("read_file", path_of[sid])] = SourceLabel("needed_later" if i == 0 else "relevant", i)
        lead = ("The station logs are under /logs (use list_dir and read_file). " if i == 0 else "Next: ")
        phases.append(final_phase(
            f"{lead}At station {sid}, what gust speed and pressure were recorded on {d} at {h:02d}:00? "
            f"Station IDs are similar, so make sure you use station {sid} exactly.",
            "<gust>, <pressure>", str(gust), pres,
        ))
    first = asked[0]
    d, h = rng.choice(DATES), rng.choice(list(HOURS))
    phases.append(final_phase(
        f"Back to station {first}: what temperature was recorded there on {d} at {h:02d}:00?",
        "<temp>", stations[first][(d, h)][0],
    ))
    return Task(id=f"rot_{variant}", phases=phases, make_tools=lambda: FakeFS(files).tools(), labels=labels)
