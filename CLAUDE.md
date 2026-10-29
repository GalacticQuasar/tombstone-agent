# Tombstone Agent

Research prototype: an LLM agent that forgets its own tool results, replacing them with
agent-written tombstones, and can retrieve them later from an archive. The question is
whether self-directed forgetting cuts token cost at equal accuracy vs. no management,
truncation and auto-compaction. Origin: `IDEA.md`.

**`PLAN.md` is the source of truth**: design decisions, model choices, and every
experiment's findings. Read it before changing behavior, and append new findings there
(dated section, suite-level table, conclusions) after each experiment.

## Commands
```bash
uv run pytest -q                                   # unit tests, no network
uv run python -m evals.run --task toy_bridge --strategy self_forget --backend or-qwen3.8-27b
evals/matrix.sh runs/<name> or-qwen3.8-27b 0.7     # 6 tasks × 4 strategies × 3 seeds, JOBS=8 parallel (~$2.60)
uv run python -m evals.report runs/<name>          # per task/strategy table, $ under none/real/ideal cache
```
Each run writes `runs/<dir>/<run-id>/{trace.jsonl,summary.json,archive/}`. `runs/` is git-ignored.

## Layout
- `src/tombstone/`: `messages.py` (canonical types → OpenAI format), `client.py` (backend
  profiles), `context.py` (ContextStore: blocks, pending forgets, batched apply, archive,
  ledger), `strategies.py` (NoOp, SelfForget, Truncate, AutoCompact), `agent.py` (loop),
  `prefix.py` (tokenizers, `serialize_request`, simulated prefix-reuse metric), `trace.py`.
- `evals/`: `env/` (MockWeb, FakeFS), `tasks/` (seeded multi-phase tasks with source labels
  distractor/relevant/needed_later), `metrics.py`, `run.py`, `report.py`, `matrix.sh`.

## Invariants (tests cover these; keep them)
- Only tool-result *content* is ever rewritten, so tool_call/tool_result pairing stays valid.
- Retrieval is append-only (a new tool result); tombstones stay in place.
- The ledger is ephemeral: a trailing user message rendered per request, never stored in history.
- All strategy thresholds use the agent's `count_context` (full request incl. tool schemas,
  model tokenizer) so they share units with the real prompt.
- Graders are token-exact on the `FINAL:` line; decoys differ by small details (e.g. `legacy_` prefix).

## Models and secrets
- Primary: `or-qwen3.8-27b` (OpenRouter, pinned to DeepInfra bf16, exact HF tokenizer).
  Second family: `or-llama3.3-70b` (approx tokenizer; HF repo is gated). `ollama-glm-flash`
  is the CLI default for cheap local iteration.
- `OPENROUTER_API_KEY` lives in git-ignored `.env`. Never print or commit it.
- Paid runs cost real money: say roughly what a batch will cost before launching it.

## Measurement gotchas
- Compare strategies on the **ideal (simulated prefix) cost** and suite totals across seeds.
  Provider `cached_tokens` is noisy (identical behavior gave a 34% cost difference) and
  per-run variance is ±40–80%.
- Use temperature 0.7 for multi-seed runs; at 0 seeds mostly repeat.
- `report.PRICES` only has Qwen; add an entry for any new backend you want priced.

## Status
Done: core loop, forgetting, baselines, task suite, full Qwen matrix (see PLAN.md).
Open, in rough priority: cost-aware apply rule (confirm before starting),
longer horizons, harder tasks that separate accuracy, Llama second-family run, ablations
(immediate vs batched apply, ledger on/off, summary vs bare stub).
