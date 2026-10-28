"""Multi-phase web research: one structure per phase, then a trap question about phase 0.

Each structure has 6 search results with neutral titles. Two hold the answer (year on
one page, size on another); the rest carry near-misses: a legend with a wrong year, a
repairs page with an approach-ramp length, and a similar-named structure with its own
figures. The final phase asks who funded the phase-0 structure — a fact on a page read
in phase 0 but not asked about then.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from evals.env.web import MockWeb, Page

from .base import Phase, SourceLabel, Task, final_phase
from .world import ORGS, NameGen, Setting, make_setting, page_text, slug

# kind, measured attribute, decoy kind
KINDS = [
    ("Bridge", "main span", "Viaduct"),
    ("Lighthouse", "tower height", "Beacon"),
    ("Observatory", "dome diameter", "Signal Station"),
    ("Aqueduct", "total length", "Weir"),
    ("Pier", "deck length", "Jetty"),
]
DOMAINS = ("archive.example", "wiki.example", "heritage.example", "localhistory.example", "news.example", "travel.example")
TITLE_FORMS = ("{n}", "{n} — notes", "About the {n}", "{n} (archive record)", "{n}: a short account")


@dataclass
class Structure:
    name: str
    attr: str
    year: int
    size: int
    engineer: str
    funder: str
    decoy: str
    setting: Setting


def _structure(rng: random.Random, names: NameGen, kind: tuple[str, str, str]) -> Structure:
    k, attr, decoy_kind = kind
    place = names.place()
    return Structure(
        name=f"{place} {k}",
        attr=attr,
        year=rng.randint(1835, 1935),
        size=rng.randint(24, 480),
        engineer=names.person(),
        funder=f"{names.place()} {rng.choice(ORGS)}",
        decoy=f"{place} {decoy_kind}",
        setting=make_setting(rng, names),
    )


def _pages(rng: random.Random, s: Structure) -> tuple[list[Page], str, str]:
    """Pages for one structure. Returns (pages, url of year/funder page, url of size page)."""
    st = s.setting
    wrong_year = s.year + rng.choice([-1, 1]) * rng.randint(6, 30)
    specs = [
        ("history", [
            f"The {s.name} was completed in {s.year} after work led by the engineer {s.engineer}.",
            f"Construction of the {s.name} was funded by the {s.funder}.",
        ]),
        ("survey", [f"The {s.attr} of the {s.name} measures {s.size} metres."]),
        ("repairs", [
            f"Crews renewed the ironwork of the {s.name} in {s.year + rng.randint(40, 80)}.",
            f"The approach on the north side of the {s.name} is {rng.randint(10, 90)} metres long.",
        ]),
        ("legend", [f"A popular story holds that the {s.name} was finished in {wrong_year}, though no record supports it."]),
        ("tourism", [f"A visit to the {s.name} takes about {rng.randint(20, 90)} minutes."]),
        ("decoy", [
            f"The {s.decoy} was completed in {s.year + rng.randint(5, 25)}.",
            f"The {s.decoy} measures {rng.randint(24, 480)} metres end to end.",
        ]),
    ]
    titles = rng.sample(TITLE_FORMS, len(TITLE_FORMS))
    pages, by_kind = [], {}
    for i, (kind, facts) in enumerate(specs):
        if kind == "decoy":
            title, subject = s.decoy, s.decoy
        else:
            title, subject = titles[i].format(n=s.name), s.name
        url = f"https://{rng.choice(DOMAINS)}/{slug(subject)}-{rng.randint(100, 999)}"
        lead = f"This page collects material about the {subject} and the town of {st.town}."
        pages.append(Page(url, title, page_text(rng, st, lead, facts), keywords=tuple(subject.lower().split())))
        by_kind[kind] = url
    rng.shuffle(pages)
    return pages, by_kind["history"], by_kind["survey"]


def dossier(variant: int, n_structures: int = 4) -> Task:
    rng = random.Random(f"dossier-{variant}")
    names = NameGen(rng)
    kinds = rng.sample(KINDS, n_structures)
    structures = [_structure(rng, names, k) for k in kinds]

    pages: list[Page] = []
    labels: dict[tuple[str, str], SourceLabel] = {}
    phases: list[Phase] = []
    for i, s in enumerate(structures):
        ps, history_url, survey_url = _pages(rng, s)
        pages += ps
        for p in ps:
            labels[("web_fetch", p.url)] = SourceLabel("distractor", i)
        labels[("web_fetch", history_url)] = SourceLabel("needed_later" if i == 0 else "relevant", i)
        labels[("web_fetch", survey_url)] = SourceLabel("relevant", i)
        phases.append(final_phase(
            f"Using the web tools, find the year the {s.name} was completed and its {s.attr} in metres. "
            f"Sources disagree, so check them.",
            "<year>, <metres>", str(s.year), str(s.size),
        ))
    first = structures[0]
    phases.append(final_phase(
        f"Going back to the {first.name}: who funded its construction?", "<funder>", first.funder,
    ))

    return Task(
        id=f"dossier_{variant}",
        phases=phases,
        make_tools=lambda: MockWeb(pages).tools(),
        labels=labels,
    )
