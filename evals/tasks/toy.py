"""Toy task for phase 1: one relevant page among bulky distractors."""

from __future__ import annotations

from evals.env.web import MockWeb, Page

from .base import Phase, SourceLabel, Task, filler, regex_grader

KW = ("velmora", "bridge", "history", "completed")
RELEVANT_URL = "https://archive.example/velmora-bridge-history"


def _pages() -> list[Page]:
    distractors = [
        ("https://wiki.example/Velmora_River", "Velmora River", "The Velmora River flows through the valley."),
        ("https://travel.example/velmora-guide", "Velmora travel guide", "Visitors to Velmora enjoy the old market."),
        ("https://news.example/velmora-bridge-repairs-2019", "Velmora bridge repairs", "In 2019 the bridge deck was resurfaced."),
        ("https://forum.example/t/velmora-bridge-myths", "Velmora bridge myths thread", "Some claim the bridge was finished in 1871, but sources disagree."),
    ]
    pages = [
        Page(url, title, f"{lead} {filler(i, 900)}", keywords=KW)
        for i, (url, title, lead) in enumerate(distractors)
    ]
    pages.append(
        Page(
            RELEVANT_URL,
            "History of the Velmora Bridge",
            f"{filler(99, 300)} Construction began in 1879 under engineer Ottilie Brandt. "
            f"After two flood seasons, the Velmora Bridge was completed in 1884 and opened to tolls. "
            f"{filler(100, 300)}",
            keywords=KW,
        )
    )
    return pages


def toy_bridge() -> Task:
    pages = _pages()
    return Task(
        id="toy_bridge",
        phases=[
            Phase(
                "In what year was the Velmora Bridge completed, and who was its engineer? "
                "Use the web tools and verify against a primary source. "
                "Reply with a final answer in the form: YEAR, ENGINEER.",
                regex_grader(r"1884.*Brandt|Brandt.*1884"),
            )
        ],
        make_tools=lambda: MockWeb(_pages()).tools(),
        labels={
            ("web_fetch", p.url): SourceLabel("relevant" if p.url == RELEVANT_URL else "distractor", 0) for p in pages
        },
    )
