"""Task spec shared by all synthetic tasks."""

from __future__ import annotations

import random
import re
from collections.abc import Callable
from dataclasses import dataclass

from tombstone.tools import Tool


@dataclass
class Task:
    id: str
    prompt: str
    make_tools: Callable[[], list[Tool]]  # fresh environment per run
    grade: Callable[[str | None], bool]
    # (tool name, key argument) pairs whose results are needed to solve the task.
    relevant_sources: set[tuple[str, str]]


def regex_grader(pattern: str) -> Callable[[str | None], bool]:
    rx = re.compile(pattern, re.IGNORECASE)
    return lambda answer: bool(answer and rx.search(answer))


_FILLER_WORDS = (
    "the committee regional survey archive council report annual district harbor "
    "trade route municipal records engineers granite timber ferry toll merchants "
    "census river valley northern southern ledger proposal funding delay winter"
).split()


def filler(seed: int, n_words: int) -> str:
    """Deterministic plausible-ish prose used to bulk up distractor pages."""
    rng = random.Random(seed)
    sentences = []
    words = 0
    while words < n_words:
        k = rng.randint(8, 18)
        s = " ".join(rng.choice(_FILLER_WORDS) for _ in range(k))
        sentences.append(s.capitalize() + ".")
        words += k
    return " ".join(sentences)
