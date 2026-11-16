"""Distraction by inferred relevance: questions describe a life fact; answers paraphrase it.

Each phase names a new town. Searching the town returns 6 resident bios. The question
describes a fact ("who had worked on the town's water supply?") and the answer bio states
it with no content words in common ("spent a decade building the reservoir and pumping
station"). One resident is a lexical decoy (shares the question's words, not its meaning).

Knob `cross` (the treatment): a resident of an earlier phase's town gets a second
paraphrase of the current phase's fact. The question restricts to the current town, so
that resident is wrong, but a context that still holds the earlier bios has a perfect
semantic match in it. With cross=False the task is otherwise identical (the control).

Knob `length`: bios of ~12 (tiny), ~25 (short) or ~42 (long) filler sentences; same facts and people.
`tiny` was added 2026-11-15 for models with a ~32k window (qwen3:8b on GenAI Studio).
"""

from __future__ import annotations

import random

from evals.env.web import MockWeb, Page

from .base import Phase, SourceLabel, Task, final_phase
from .world import NameGen, make_setting, page_text

# (question description, answer paraphrase, cross-phase paraphrase, lexical decoy).
# The answer paraphrase shares no content word with the description (tested).
CONCEPTS = [
    ("had worked on the town's water supply", "spent a decade building the reservoir and pumping station",
     "laid the mains that first brought clean drinking water into the houses",
     "complained in letters about the taste of the town's water supply"),
    ("had trained as a physician", "qualified in medicine at the university before turning to trade",
     "practised as a country doctor for some years",
     "was nursed back to health by a physician who had trained in the capital"),
    ("survived a shipwreck", "was one of four people rescued when the schooner went down off the cape",
     "clung to floating timbers through a night after the steamer foundered",
     "painted a well-known picture of a shipwreck that nobody survived"),
    ("was a published poet", "brought out two slim volumes of verse",
     "had sonnets printed in the county magazine for many years",
     "published a newspaper that refused to print any poet's work"),
    ("held elected office", "won the mayoralty twice",
     "sat on the borough council for a decade after topping the poll",
     "kept the office where elected officials stored their records"),
    ("emigrated abroad and later returned home", "left for the colonies as a young man but came back in middle age",
     "spent twenty years overseas before settling once more in the district",
     "lent money to families who emigrated abroad and never returned home"),
    ("was imprisoned", "served eighteen months in the county gaol",
     "was locked up for a year after the bread riot",
     "designed the iron gates of the new prison where debtors were imprisoned"),
    ("taught at a school", "ran the village classroom and its thirty pupils for three decades",
     "instructed generations of children in reading and arithmetic",
     "paid for a new roof on the school where the children were taught"),
    ("was a competitive athlete", "won the county rowing championship three years running",
     "ran in the national cross-country race and finished among the leaders",
     "laid out the running track used by athletes in competitions"),
    ("lost their fortune", "was ruined when the private bank collapsed",
     "went bankrupt after fire destroyed the mill",
     "made a large fortune in the wool trade and never lost it"),
    ("spoke several foreign languages", "was fluent in French, German and Dutch",
     "interpreted for visiting merchants in four tongues",
     "printed dictionaries of foreign languages without speaking any of them"),
    ("served in the navy", "was a midshipman aboard a frigate until the war ended",
     "spent nine years at sea on warships",
     "sold rope and canvas to the navy yard but never served"),
    ("invented a patented device", "registered a design for a new plough that bore their name and earned royalties",
     "devised an improved door lock and was granted exclusive rights to it",
     "challenged a rival's patented device in a long court case"),
    ("was an amateur astronomer", "discovered a comet with a telescope in their garden",
     "kept nightly records of the planets from a rooftop observatory",
     "donated land to the amateur society for an astronomer's lecture hall"),
    ("fought a duel", "met a rival with pistols at dawn on the common",
     "was wounded in an affair of honour with a cavalry officer",
     "wrote a pamphlet condemning anyone who fought a duel"),
    ("kept bees", "tended forty hives and sold honey at the market",
     "was known across the district for the honey from their apiary",
     "was badly stung by bees as a child and kept away from them"),
]
N_PHASES = 8
RESIDENTS = 6
TITLE_FORMS = ("{p} of {t}", "{p} ({t})", "Notes on {p}, {t}", "{p}: a {t} life", "{t} people: {p}", "{p} — {t} archive")


LENGTHS = {"tiny": 12, "short": 25, "long": 42}


def latent(variant: int, cross: bool, length: str) -> Task:
    rng = random.Random(f"latent-{variant}")
    names = NameGen(rng)
    order = rng.sample(range(len(CONCEPTS)), len(CONCEPTS))
    asked, fillers = order[:N_PHASES], order[N_PHASES:]

    # Structure first (independent of the knobs): towns, residents and their facts.
    towns = []
    for k, c in enumerate(asked):
        setting = make_setting(rng, names)
        people = [names.person() for _ in range(RESIDENTS)]
        facts = [("answer", CONCEPTS[c][1]), ("lexical", CONCEPTS[c][3])]
        facts += [("filler", CONCEPTS[f][1]) for f in rng.sample(fillers, RESIDENTS - 2)]
        rng.shuffle(facts)
        towns.append({"setting": setting, "people": people, "facts": facts, "concept": c})
    # Cross-phase decoy for phase k: a filler resident of a random earlier town.
    cross_slots = {}
    for k in range(1, N_PHASES):
        j = rng.randrange(k)
        slot = rng.choice([i for i, (kind, _) in enumerate(towns[j]["facts"]) if kind == "filler"
                           and (j, i) not in cross_slots.values()])
        cross_slots[k] = (j, slot)
    if cross:
        for k, (j, slot) in cross_slots.items():
            towns[j]["facts"][slot] = ("cross", CONCEPTS[towns[k]["concept"]][2])

    page_rng = random.Random(f"latent-{variant}-pages-{length}")
    n_sentences = LENGTHS[length]
    pages: list[Page] = []
    labels: dict[tuple[str, str], SourceLabel] = {}
    phases: list[Phase] = []
    for k, town in enumerate(towns):
        st = town["setting"]
        answer = ""
        for person, (kind, fact) in zip(town["people"], town["facts"]):
            title = page_rng.choice(TITLE_FORMS).format(p=person, t=st.town)
            url = f"https://people.example/{st.town.lower()}/{person.lower().replace(' ', '-')}"
            lead = f"This page collects material about {person}, who lived in {st.town}."
            text = page_text(page_rng, st, lead, [f"{person} {fact}."], n_sentences=n_sentences)
            pages.append(Page(url, title, text, keywords=(st.town.lower(), *person.lower().split())))
            labels[("web_fetch", url)] = SourceLabel("relevant" if kind == "answer" else "distractor", k)
            if kind == "answer":
                answer = person
        desc = CONCEPTS[town["concept"]][0]
        lead = "Use the web tools (search by town name). " if k == 0 else "Next: "
        phases.append(final_phase(
            f"{lead}Among the people of {st.town}, who {desc}? Only people of {st.town} count.",
            "<person>", answer,
        ))
    knobs = f"{'on' if cross else 'off'}-{length}"
    return Task(id=f"latent-{knobs}_{variant}", phases=phases, make_tools=lambda: MockWeb(pages).tools(), labels=labels)
