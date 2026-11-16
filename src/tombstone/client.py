"""OpenAI-compatible chat client with named backend profiles."""

from __future__ import annotations

import fcntl
import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from openai import APIResponseValidationError, BadRequestError, InternalServerError, OpenAI, RateLimitError

from .messages import Message, ToolCall, render


@dataclass(frozen=True)
class Backend:
    name: str
    base_url: str
    model: str
    api_key_env: str | None = None
    # Extra request body fields (e.g. OpenRouter provider pinning).
    extra_body: dict[str, Any] | None = None
    # Hugging Face repo whose tokenizer matches the model; None → approximate counts.
    tokenizer: str | None = None
    # Requests per minute allowed for this backend, shared by all local processes.
    max_rpm: int | None = None
    # Backends that share one rate limit (e.g. per-user on one host) share a throttle; default: own name.
    rate_group: str | None = None


BACKENDS: dict[str, Backend] = {
    # Reports real prefix-cache hits in usage.prompt_tokens_details.cached_tokens.
    "ollama-glm": Backend("ollama-glm", "http://localhost:11434/v1", "glm-5.3:cloud"),
    "ollama-glm-flash": Backend("ollama-glm-flash", "http://localhost:11434/v1", "glm-5.3-flash:cloud"),
    # Tool calling works; cached_tokens is always reported as 0.
    "ollama-kimi": Backend("ollama-kimi", "http://localhost:11434/v1", "kimi-k3:cloud"),
}


def _purdue(name: str, model: str, tokenizer: str | None) -> Backend:
    """Purdue RCAC GenAI Studio (free for Purdue users). The limit is 20 requests/min per user across
    all models, so every Purdue backend shares one throttle at 18. Usage has no cached_tokens."""
    return Backend(name, "https://genai.rcac.purdue.edu/api", model, api_key_env="GENAI_API_KEY",
                   tokenizer=tokenizer, max_rpm=18, rate_group="purdue")


BACKENDS.update({
    b.name: b
    for b in [
        # vLLM; context capped at 65,536 tokens.
        _purdue("purdue-qwen3.8-27b", "qwen3.8:27b", "Qwen/Qwen3.8-27B"),
        # Weaker / second-family models for the distraction calibration (added 2026-11-15).
        # The Llama tokenizer repo is gated, so counts are approximate.
        _purdue("purdue-llama3.3-70b", "llama3.3:70b", None),
        _purdue("purdue-qwen3-8b", "qwen3:8b", "Qwen/Qwen3-8B"),
        # Second family with the full context on this host; tokenizer counts are approximate.
        _purdue("purdue-gpt-oss-120b", "gpt-oss:120b", None),
    ]
})


def _openrouter(name: str, model: str, provider: str, tokenizer: str | None = None) -> Backend:
    """OpenRouter backend pinned to one provider endpoint, so runs stay reproducible."""
    return Backend(
        name,
        "https://openrouter.ai/api/v1",
        model,
        api_key_env="OPENROUTER_API_KEY",
        extra_body={"provider": {"order": [provider], "allow_fallbacks": False}},
        tokenizer=tokenizer,
    )


BACKENDS.update({
    b.name: b
    for b in [
        # Both report real prefix-cache hits.
        _openrouter("or-qwen3.8-27b", "qwen/qwen3.8-27b", "deepinfra/bf16", tokenizer="Qwen/Qwen3.8-27B"),
        # The Llama tokenizer repo is gated on Hugging Face; approximate counts until a token is set up.
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


# Waits before retrying a rate-limited or transiently failed request. GenAI Studio may signal these with
# a JSON null body (HTTP 200), an HTTP 400 with no error message, or a 5xx (e.g. 504 gateway timeout).
RETRY_DELAYS = (15.0, 30.0, 60.0, 120.0, 240.0)


def _error_message(body: Any) -> str | None:
    """The error message in an API error body (already unwrapped from {"error": ...} by the SDK)."""
    if isinstance(body, dict):
        msg = body.get("message") or body.get("detail")
        return msg if isinstance(msg, str) and msg.strip() else None
    if isinstance(body, str):
        return body.strip() or None
    return None


class SlotThrottle:
    """Spaces requests evenly across processes by reserving send times in a locked file."""

    def __init__(self, name: str, rpm: int):
        self.path = Path(tempfile.gettempdir()) / f"tombstone-throttle-{name}"
        self.interval = 60.0 / rpm

    def wait(self) -> None:
        with self.path.open("a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)  # released when the file closes
            f.seek(0)
            raw = f.read().strip()
            now = time.time()
            slot = max(now, float(raw) if raw else 0.0)
            f.truncate(0)
            f.write(str(slot + self.interval))
        time.sleep(max(0.0, slot - now))


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
        self._throttle = SlotThrottle(backend.rate_group or backend.name, backend.max_rpm) if backend.max_rpm else None

    def _create(self, messages: list[Message], tools: list[dict[str, Any]]) -> Any:
        """Send one request, backing off when the backend rate-limits it or fails transiently.

        A 400 with no error message is transient on GenAI Studio (the same request succeeds later), and
        so is a 400 whose message reports a server error (its LiteLLM proxy wraps upstream failures such
        as "InternalServerError ... Unknown role: final" in a 400). Any other 400 that explains itself
        (e.g. context too long) is a real error and is raised."""
        for delay in (*RETRY_DELAYS, None):
            if self._throttle:
                self._throttle.wait()
            try:
                resp = self._client.chat.completions.create(
                    model=self.backend.model,
                    messages=render(messages),
                    tools=tools or None,
                    temperature=self.temperature,
                    seed=self.seed,
                    extra_body=self.backend.extra_body,
                )
                if resp is not None and getattr(resp, "choices", None):
                    return resp
            except (RateLimitError, APIResponseValidationError):
                pass
            except BadRequestError as e:
                msg = _error_message(e.body)
                if msg and "InternalServerError" not in msg:
                    print(f"HTTP 400 from {self.backend.name}, not retried, body={e.body!r}", file=sys.stderr)
                    raise
                print(f"HTTP 400 without a message from {self.backend.name}, body={e.body!r}", file=sys.stderr)
            except InternalServerError as e:
                print(f"HTTP {e.status_code} from {self.backend.name}", file=sys.stderr)
            if delay is not None:
                print(f"rate-limited or transient error from {self.backend.name}; retrying in {delay:.0f}s", file=sys.stderr)
                time.sleep(delay)
        raise RuntimeError(f"backend {self.backend.name!r} still rate-limiting after {len(RETRY_DELAYS)} retries")

    def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> Completion:
        resp = self._create(messages, tools)
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
