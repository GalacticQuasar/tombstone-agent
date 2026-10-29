"""Token counting and the simulated prefix-reuse metric.

The simulated metric compares consecutive serialized requests and reports how much of
the previous request is a prefix of the next one. It's what any prefix/KV cache could
at best reuse, independent of what a backend reports.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Protocol

from .messages import Message, render


class Tokenizer(Protocol):
    def count(self, text: str) -> int: ...


class ApproxTokenizer:
    """~4 chars/token. Deterministic and dependency-free; fine for ledgers and thresholds."""

    def count(self, text: str) -> int:
        return math.ceil(len(text) / 4)


class HFTokenizer:
    """Exact counts from a Hugging Face tokenizer (downloaded once, then cached)."""

    def __init__(self, repo_id: str):
        from tokenizers import Tokenizer as _Tok

        self._tok = _Tok.from_pretrained(repo_id)

    def count(self, text: str) -> int:
        return len(self._tok.encode(text, add_special_tokens=False).ids)


def serialize_request(messages: list[Message], tools: list[dict[str, Any]]) -> str:
    """Stable text form of a request, laid out like a chat template.

    Tools come first, as templates usually place them. Content is raw text, not JSON, so
    newlines and quotes in pages aren't escaped (escaping inflated counts by ~10%).
    """
    def dump(o: Any) -> str:
        return json.dumps(o, sort_keys=True, ensure_ascii=False)

    parts = [f"<|tools|>\n{dump(tools)}"]
    for m in render(messages):
        if m["role"] == "tool":
            parts.append(f"<|tool {m['tool_call_id']}|>\n{m['content']}")
            continue
        parts.append(f"<|{m['role']}|>\n{m.get('content') or ''}")
        for tc in m.get("tool_calls", []):
            parts.append(f"<tool_call {tc['id']} {tc['function']['name']}>{tc['function']['arguments']}</tool_call>")
    return "\n".join(parts)


def common_prefix_len(a: str, b: str) -> int:
    n = min(len(a), len(b))
    lo, hi = 0, n
    # Binary search on prefix equality; slices compare in C so this is fast for long prompts.
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if a[:mid] == b[:mid]:
            lo = mid
        else:
            hi = mid - 1
    return lo


@dataclass
class PrefixReuse:
    prev_tokens: int
    reused_tokens: int
    total_tokens: int

    @property
    def frac_of_prev(self) -> float:
        return self.reused_tokens / self.prev_tokens if self.prev_tokens else 0.0


class PrefixTracker:
    def __init__(self, tokenizer: Tokenizer):
        self.tokenizer = tokenizer
        self._prev: str | None = None

    def observe(self, request_text: str) -> PrefixReuse:
        total = self.tokenizer.count(request_text)
        if self._prev is None:
            reuse = PrefixReuse(0, 0, total)
        else:
            lcp = common_prefix_len(self._prev, request_text)
            reuse = PrefixReuse(self.tokenizer.count(self._prev), self.tokenizer.count(request_text[:lcp]), total)
        self._prev = request_text
        return reuse
