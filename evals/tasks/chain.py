"""Multi-hop web research: ferry → bridge that replaced it → its engineer → birthplace.

Each hop has 5 search results; one holds the link, the others mention near-miss names
(a bridge visible from the ferry, an inspector of the bridge, a town the engineer lived
in). Once a hop is resolved its pages are dead weight, so forgetting can pay off within
a phase. Each phase is an independent chain.
"""

from __future__ import annotations

import random

from evals.env.web import MockWeb, Page

from .base import Phase, SourceLabel, Task, final_phase
from .dossier import DOMAINS
from .world import NameGen, Setting, make_setting, page_text, slug

# No article, so they work for people too.
TITLE_FORMS = ("{n}", "{n} — notes", "On {n}", "{n} (archive record)", "{n}: a short account")


def _hop_pages(
    rng: random.Random, st: Setting, subject: str, key_fact: str, decoy_facts: list[str]
) -> tuple[list[Page], str]:
    """5 pages about `subject`: one with key_fact, four each with one decoy fact."""
    titles = rng.sample(TITLE_FORMS, 5)
    facts = [[key_fact]] + [[d] for d in decoy_facts]
    pages, key_url = [], ""
    for i, fs in enumerate(facts):
        url = f"https://{rng.choice(DOMAINS)}/{slug(subject)}-{rng.randint(100, 999)}"
        lead = f"This page collects material about {subject} and the town of {st.town}."
        pages.append(Page(url, titles[i].format(n=subject), page_text(rng, st, lead, fs), keywords=tuple(slug(subject).split("-"))))
        if i == 0:
            key_url = url
    rng.shuffle(pages)
    return pages, key_url


def _chain(rng: random.Random, names: NameGen) -> tuple[str, str, list[Page], list[str]]:
    """Returns (question, answer town, pages, key urls)."""
    st = make_setting(rng, names)
    ferry = f"{names.place()} Ferry"
    bridge, other_bridge = f"{names.place()} Bridge", f"{names.place()} Bridge"
    engineer, inspector = names.person(), names.person()
    birthplace = names.place()
    lived, studied, worked = names.place(), names.place(), names.place()
    y = rng.randint(1850, 1925)

    hop1, k1 = _hop_pages(rng, st, ferry, f"In {y} the {ferry} was replaced by the {bridge}.", [
        f"Passengers on the {ferry} could see the {other_bridge} downstream.",
        f"The {ferry} carried about {rng.randint(40, 400)} passengers a day in {y - rng.randint(5, 30)}.",
        f"Proposals in {y - rng.randint(5, 20)} to build the {other_bridge} near the {ferry} landing were rejected.",
        f"A painting of the {ferry} hangs in the {st.town} town hall.",
    ])
    hop2, k2 = _hop_pages(rng, st, bridge, f"The {bridge} was designed by the engineer {engineer}.", [
        f"{inspector} inspected the {bridge} in {y + rng.randint(10, 50)}.",
        f"The {other_bridge} was designed by {names.person()}.",
        f"The {bridge} carries a road over the {st.river}.",
        f"Repairs to the {bridge} were overseen by {inspector}.",
    ])
    hop3, k3 = _hop_pages(rng, st, engineer, f"{engineer} was born in {birthplace}.", [
        f"{engineer} later lived in {lived}.",
        f"{engineer} studied in {studied}.",
        f"{engineer} worked for many years in {worked}.",
        f"{inspector} was born in {names.place()}.",
    ])
    question = (
        f"The {ferry} was eventually replaced by a bridge. In which town was the engineer who designed "
        f"that bridge born? Use the web tools."
    )
    return question, birthplace, hop1 + hop2 + hop3, [k1, k2, k3]


def chain(variant: int, n_chains: int = 2) -> Task:
    rng = random.Random(f"chain-{variant}")
    names = NameGen(rng)
    pages: list[Page] = []
    labels: dict[tuple[str, str], SourceLabel] = {}
    phases: list[Phase] = []
    for i in range(n_chains):
        question, town, ps, key_urls = _chain(rng, names)
        pages += ps
        for p in ps:
            labels[("web_fetch", p.url)] = SourceLabel("relevant" if p.url in key_urls else "distractor", i)
        phases.append(final_phase(question, "<town>", town))
    return Task(id=f"chain_{variant}", phases=phases, make_tools=lambda: MockWeb(pages).tools(), labels=labels)
