"""Seeded generator for a fictional world: names, places, and plausible filler prose.

Filler is deliberately noisy (many years, names and numbers) so key facts can't be
found by scanning for the only year on a page. Filler never uses the verbs that key
facts use ("completed", "designed", "funded", "born", "replaced", "measures").
"""

from __future__ import annotations

import random
from dataclasses import dataclass

_ONSETS = "b br c d dr f g gr h k l m n p r s st t th v w z".split()
_VOWELS = "a e i o u ae ia ou".split()
_CODAS = "n r l s th m rn nd sk ck".split()
_SUFFIXES = ("ora", "ent", "ach", "wick", "dale", "mere", "holt", "by", "ton", "ford", "is", "an")
_FIRST = (
    "Ottilie Anselm Brigitte Casimir Dagny Emeric Fenna Gideon Hedda Ivo Jorunn Kaspar Linnea Matthias "
    "Nadia Osric Petra Quentin Rosalind Sevrin Tamsin Ulric Vesna Wendel Ximena Yorick Zelda"
).split()
ORGS = (
    "Harbor Trust", "Board of Works", "Merchant Guild", "County Council", "Rail Syndicate",
    "Historical Society", "Survey Office", "Canal Company", "Chamber of Commerce", "Water Board",
)
_MONTHS = "January February March April May June July August September October November December".split()


class NameGen:
    """Unique fictional names from a seeded RNG."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.used: set[str] = set()

    def _word(self) -> str:
        r = self.rng
        w = r.choice(_ONSETS) + r.choice(_VOWELS) + r.choice(_CODAS) + r.choice(_SUFFIXES)
        return w.capitalize()

    def place(self) -> str:
        while (w := self._word()) in self.used:
            pass
        self.used.add(w)
        return w

    def person(self) -> str:
        while (p := f"{self.rng.choice(_FIRST)} {self._word()}") in self.used:
            pass
        self.used.add(p)
        return p


@dataclass
class Setting:
    """Background a page's filler draws on."""

    town: str
    region: str
    river: str
    people: list[str]  # bystander names for filler (decoys)


_FILLER = [
    "The {org} met in {month} {year} to discuss the state of the roads around {town}.",
    "Records from {year} list {num} households in the parish of {town}.",
    "{person} kept a ledger of river traffic on the {river} for nearly {small} years.",
    "A severe winter in {year} froze the {river} as far as the {region} border.",
    "Merchants from {region} brought timber, salt and wool to the {town} market each autumn.",
    "In {year} the {org} commissioned a survey of the flood meadows east of {town}.",
    "{person} wrote in {year} that the old toll road had fallen into disrepair.",
    "The population of {town} rose to roughly {num} by the census of {year}.",
    "Several mills along the {river} changed hands between {year} and {year2}.",
    "A local newspaper, founded in {year}, reported regularly on the {org}.",
    "The {region} uplands supplied most of the granite used in the district.",
    "{person} and {person2} disputed the boundary of the common grazing land in {year}.",
    "Flooding in {month} {year} damaged warehouses along the {town} waterfront.",
    "The {org} kept its offices on the high street of {town} until {year}.",
    "Trade along the {river} declined after a customs dispute in {year}.",
    "A school opened in {town} in {year} with {small} pupils on its first register.",
    "Archive boxes from the {org} cover the years {year} to {year2}, though many are incomplete.",
    "Photographs from {year} show the market square crowded with carts.",
    "{person} served as clerk to the {org} from {year} to {year2}.",
    "Visitors in the {decade}s described {town} as quiet outside of market days.",
    "The {river} is navigable for small craft for about {small} kilometres above {town}.",
    "Debates in {year} over a new road through {region} ended without a decision.",
    "Accounts from {year} mention a toll of {small} pence for each laden cart.",
    "A fire in {year} destroyed part of the parish records of {town}.",
    "The {org} published a short pamphlet on local trade in {year}.",
    "{person} donated a collection of letters to the {town} library in {year}.",
    "Wool prices in {region} fell sharply during the {decade}s.",
    "A footpath along the {river} was laid out by volunteers in {year}.",
    "{person} recorded {small} days of heavy rain in the spring of {year}.",
    "The old coaching inn at {town} closed its doors in {year}.",
    "In {month} {year} a petition signed by {num} residents reached the {org}.",
    "Maps drawn in {year} show the {river} on a slightly different course near {town}.",
    "{person} ran the {town} post office for {small} years from {year}.",
    "The {region} fair drew traders from as far as the coast during the {decade}s.",
    "A dispute between the {org} and local landowners lasted from {year} to {year2}.",
    "Notes kept by {person} describe the market at {town} in {month} {year}.",
    "Brick kilns south of {town} employed about {small} workers in {year}.",
    "During the {decade}s, small boats carried coal up the {river} to {town}.",
    "{person} gave a lecture on the history of {region} to the {org} in {year}.",
    "Parish accounts from {year} record repairs to the church roof at {town}.",
]


def filler_sentence(rng: random.Random, s: Setting, template: str) -> str:
    y = rng.randint(1790, 1985)
    person, person2 = rng.sample(s.people, 2)
    return template.format(
        org=rng.choice(ORGS),
        month=rng.choice(_MONTHS),
        year=y,
        year2=y + rng.randint(3, 40),
        decade=y // 10 * 10,
        num=rng.randint(300, 9000),
        small=rng.randint(3, 60),
        town=s.town,
        region=s.region,
        river=s.river,
        person=person,
        person2=person2,
    )


def page_text(rng: random.Random, s: Setting, lead: str, facts: list[str], n_sentences: int = 72) -> str:
    """A page: a lead sentence, then filler with `facts` buried at random interior positions."""
    # Cycle through shuffled templates so no template repeats more than necessary.
    templates: list[str] = []
    while len(templates) < n_sentences:
        templates += rng.sample(_FILLER, len(_FILLER))
    body = [filler_sentence(rng, s, t) for t in templates[:n_sentences]]
    for f in facts:
        body.insert(rng.randint(len(body) // 5, len(body) - 3), f)
    paras = [" ".join(body[i : i + 6]) for i in range(0, len(body), 6)]
    return lead + "\n\n" + "\n\n".join(paras)


def make_setting(rng: random.Random, names: NameGen) -> Setting:
    return Setting(
        town=names.place(),
        region=names.place(),
        river=names.place(),
        people=[names.person() for _ in range(6)],
    )


def slug(s: str) -> str:
    return "-".join(s.lower().split())
