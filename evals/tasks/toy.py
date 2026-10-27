"""Toy task for phase 1: one relevant page among bulky distractors."""

from __future__ import annotations

from evals.env.web import MockWeb, Page

from .base import Task, filler, regex_grader

KW = ("velmora", "bridge", "history", "completed")


def _pages() -> list[Page]:
    distractors = [
        ("https://wiki.example/Velmora_River", "Velmora River", "The Velmora River flows through the valley."),
        ("https://travel.example/velmora-guide", "Velmora travel guide", "Visitors to Velmora enjoy the old market."),
        ("https://news.example/velmora-bridge-repairs-2019", "Velmora bridge repairs", "In 2019 the bridge deck was resurfaced."),
        ("https://forum.example/t/velmora-bridge-myths", "Velmora bridge myths thread", "Some claim the bridge was finished in 1871, but sources disagree."),
    ]
    pages = [
        Page(url, title, f"{lead} {filler(i, 900)}", relevant=False, keywords=KW)
        for i, (url, title, lead) in enumerate(distractors)
    ]
    pages.append(
        Page(
            "https://archive.example/velmora-bridge-history",
            "History of the Velmora Bridge",
            f"{filler(99, 300)} Construction began in 1879 under engineer Ottilie Brandt. "
            f"After two flood seasons, the Velmora Bridge was completed in 1884 and opened to tolls. "
            f"{filler(100, 300)}",
            relevant=True,
            keywords=KW,
        )
    )
    return pages


def toy_bridge() -> Task:
    return Task(
        id="toy_bridge",
        prompt=(
            "In what year was the Velmora Bridge completed, and who was its engineer? "
            "Use the web tools and verify against a primary source. "
            "Reply with a final answer in the form: YEAR, ENGINEER."
        ),
        make_tools=lambda: MockWeb(_pages()).tools(),
        grade=regex_grader(r"1884.*Brandt|Brandt.*1884"),
        relevant_sources={("web_fetch", "https://archive.example/velmora-bridge-history")},
    )
