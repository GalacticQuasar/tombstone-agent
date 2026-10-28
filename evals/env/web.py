"""Mock web over a fixed local corpus. Deterministic; relevance labels live on the Task."""

from __future__ import annotations

import re
from dataclasses import dataclass

from tombstone.tools import Tool, ToolError, object_schema


_STOPWORDS = frozenset("a an and at by for from in is of on or the to was what when where which who with".split())


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", text.lower()) if w not in _STOPWORDS}


@dataclass
class Page:
    url: str
    title: str
    text: str
    keywords: tuple[str, ...] = ()


class MockWeb:
    def __init__(self, pages: list[Page]):
        self.pages = {p.url: p for p in pages}

    def search(self, query: str) -> str:
        terms = _words(query)
        scored = []
        for p in self.pages.values():
            haystack = _words(" ".join((*p.keywords, p.title)))
            score = len(terms & haystack)
            if score:
                scored.append((score, p))
        # Stable order: score desc, then url, so results don't depend on dict order.
        scored.sort(key=lambda sp: (-sp[0], sp[1].url))
        if not scored:
            return "No results."
        return "\n".join(f"- {p.title} — {p.url}" for _, p in scored[:8])

    def fetch(self, url: str) -> str:
        page = self.pages.get(url)
        if page is None:
            raise ToolError(f"404 Not Found: {url}")
        return f"# {page.title}\n\n{page.text}"

    def tools(self) -> list[Tool]:
        return [
            Tool(
                "web_search",
                "Search the web. Returns a list of page titles and URLs.",
                object_schema({"query": {"type": "string"}}),
                self.search,
            ),
            Tool(
                "web_fetch",
                "Fetch the full text of a web page by URL.",
                object_schema({"url": {"type": "string"}}),
                self.fetch,
            ),
        ]
