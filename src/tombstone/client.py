"""OpenAI-compatible chat client with named backend profiles."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

from openai import OpenAI

from .messages import Message, ToolCall, render


@dataclass(frozen=True)
class Backend:
    name: str
    base_url: str
    model: str
    api_key_env: str | None = None
    # Extra request body fields (e.g. OpenRouter provider pinning).
    extra_body: dict[str, Any] | None = None


BACKENDS: dict[str, Backend] = {
    # Reports real prefix-cache hits in usage.prompt_tokens_details.cached_tokens.
    "ollama-glm": Backend("ollama-glm", "http://localhost:11434/v1", "glm-5.3:cloud"),
    "ollama-glm-flash": Backend("ollama-glm-flash", "http://localhost:11434/v1", "glm-5.3-flash:cloud"),
    # Tool calling works; cached_tokens is always reported as 0.
    "ollama-kimi": Backend("ollama-kimi", "http://localhost:11434/v1", "kimi-k3:cloud"),
}


def _openrouter(name: str, model: str, provider: str) -> Backend:
    """OpenRouter backend pinned to one provider endpoint, so runs stay reproducible."""
    return Backend(
        name,
        "https://openrouter.ai/api/v1",
        model,
        api_key_env="OPENROUTER_API_KEY",
        extra_body={"provider": {"order": [provider], "allow_fallbacks": False}},
    )


BACKENDS.update({
    b.name: b
    for b in [
        # Both report real prefix-cache hits.
        _openrouter("or-qwen3.8-27b", "qwen/qwen3.8-27b", "deepinfra/bf16"),
        _openrouter("or-llama3.3-70b", "meta-llama/llama-3.3-70b-instruct", "akashml/fp8"),
    ]
})


@dataclass
class Usage:
    prompt: int = 0
    cached: int | None = None  # None when the backend doesn't report it
    completion: int = 0

    @classmethod
    def from_openai(cls, u: Any) -> Usage:
        if u is None:
            return cls()
        details = getattr(u, "prompt_tokens_details", None)
        cached = getattr(details, "cached_tokens", None) if details is not None else None
        return cls(prompt=u.prompt_tokens or 0, cached=cached, completion=u.completion_tokens or 0)


@dataclass
class Completion:
    message: Message
    usage: Usage
    finish_reason: str | None


class ChatClient(Protocol):
    def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> Completion: ...


def parse_tool_call(id: str, name: str, raw: str) -> ToolCall:
    try:
        args = json.loads(raw) if raw else {}
        if not isinstance(args, dict):
            raise ValueError("arguments must be a JSON object")
    except ValueError:
        # Leave arguments empty; the dispatcher reports the malformed call back to the model.
        return ToolCall(id=id, name=name, arguments={}, raw_arguments=raw)
    return ToolCall(id=id, name=name, arguments=args, raw_arguments=raw)


class OpenAIChatClient:
    def __init__(self, backend: Backend, temperature: float = 0.0, seed: int | None = None):
        self.backend = backend
        self.temperature = temperature
        self.seed = seed
        if backend.api_key_env:
            api_key = os.environ.get(backend.api_key_env)
            if not api_key:
                raise RuntimeError(f"backend {backend.name!r} needs ${backend.api_key_env} (set it in .env)")
        else:
            api_key = "unused"
        self._client = OpenAI(base_url=backend.base_url, api_key=api_key)

    def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> Completion:
        resp = self._client.chat.completions.create(
            model=self.backend.model,
            messages=render(messages),
            tools=tools or None,
            temperature=self.temperature,
            seed=self.seed,
            extra_body=self.backend.extra_body,
        )
        choice = resp.choices[0]
        msg = choice.message
        calls = [
            parse_tool_call(tc.id, tc.function.name, tc.function.arguments)
            for tc in (msg.tool_calls or [])
        ]
        return Completion(
            message=Message(role="assistant", content=msg.content, tool_calls=calls),
            usage=Usage.from_openai(resp.usage),
            finish_reason=choice.finish_reason,
        )
