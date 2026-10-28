"""Task spec shared by all synthetic tasks."""

from __future__ import annotations

import random
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from tombstone.tools import Tool

Grader = Callable[[str | None], bool]

# distractor:   never needed.
# relevant:     needed during its own phase only (safe to forget once that phase is answered).
# needed_later: needed again in a later phase (forgetting it without a good summary should hurt).
LabelKind = Literal["distractor", "relevant", "needed_later"]


@dataclass(frozen=True)
class SourceLabel:
    kind: LabelKind
    phase: int  # phase (0-based) the source belongs to


@dataclass
class Phase:
    prompt: str
    grade: Grader
    expected: tuple[str, ...] = ()  # values the grader looks for, when it has them


def final_phase(prompt: str, fmt: str, *expected: str) -> Phase:
    """Phase graded on its `FINAL:` line containing every expected value."""
    return Phase(f"{prompt} " + FINAL_INSTRUCTION.format(fmt=fmt), final_grader(*expected), expected)


@dataclass
class Task:
    id: str
    phases: list[Phase]
    make_tools: Callable[[], list[Tool]]  # fresh environment per run
    # Keyed by (tool name, key argument), e.g. ("web_fetch", url) or ("read_file", path).
    labels: dict[tuple[str, str], SourceLabel] = field(default_factory=dict)

    @property
    def prompts(self) -> list[str]:
        return [p.prompt for p in self.phases]

    def grade(self, answers: list[str | None]) -> list[bool]:
        return [p.grade(a) for p, a in zip(self.phases, answers, strict=True)]


def regex_grader(pattern: str) -> Grader:
    rx = re.compile(pattern, re.IGNORECASE)
    return lambda answer: bool(answer and rx.search(answer))


FINAL_INSTRUCTION = "End your reply with a single line of the form `FINAL: {fmt}`."


def final_line(answer: str | None) -> str | None:
    """Value of the last `FINAL:` line, stripped of markdown emphasis/backticks.

    Underscores are only stripped at the edges (`__x__` emphasis), not inside identifiers.
    """
    if not answer:
        return None
    hits = re.findall(r"^\W*FINAL:\s*(.+?)\s*$", answer, re.MULTILINE | re.IGNORECASE)
    return re.sub(r"[*`]", "", hits[-1]).strip().strip("_").strip() if hits else None


def _norm(s: str) -> str:
    # Keep "." inside tokens (decimals) and "_" (identifiers: legacy_foo must not match foo).
    tokens = (t.strip(".") for t in re.sub(r"[^a-z0-9._]+", " ", s.lower()).split())
    return " ".join(t for t in tokens if t)


def final_grader(*expected: str) -> Grader:
    """Pass iff the FINAL line contains every expected value as a whole token sequence."""

    def grade(answer: str | None) -> bool:
        line = final_line(answer)
        if line is None:
            return False
        padded = f" {_norm(line)} "
        return all(f" {_norm(e)} " in padded for e in expected)

    return grade


_FILLER_WORDS = (
    "the committee regional survey archive council report annual district harbor "
    "trade route municipal records engineers granite timber ferry toll merchants "
    "census river valley northern southern ledger proposal funding delay winter"
).split()


def filler(seed: int, n_words: int) -> str:
    """Deterministic word-salad used by the toy task's distractor pages."""
    rng = random.Random(seed)
    sentences = []
    words = 0
    while words < n_words:
        k = rng.randint(8, 18)
        s = " ".join(rng.choice(_FILLER_WORDS) for _ in range(k))
        sentences.append(s.capitalize() + ".")
        words += k
    return " ".join(sentences)
