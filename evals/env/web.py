"""Mock web over a fixed local corpus. Deterministic; every page carries a relevance label."""

from __future__ import annotations

from dataclasses import dataclass

from tombstone.tools import Tool, ToolError, object_schema


@dataclass
class Page:
    url: str
    title: str
    text: str
    relevant: bool  # ground-truth label: is this page needed to solve the task?
    keywords: tuple[str, ...] = ()


class MockWeb:
    def __init__(self, pages: list[Page]):
        self.pages = {p.url: p for p in pages}

    def search(self, query: str) -> str:
        terms = {t.lower() for t in query.split()}
        scored = []
        for p in self.pages.values():
            haystack = {w.lower() for w in (*p.keywords, *p.title.split())}
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
