# Tombstone Agent

Research prototype: an LLM agent that prunes its own context, replacing tool results with
agent-written tombstones it can retrieve later from an archive. LLMs get distracted by irrelevant
context and degrade at long contexts (context rot); the question is whether self-directed pruning
makes the agent **execute tasks more accurately** than no management, truncation and
auto-compaction. Cost is tracked as a secondary constraint, not the target (reframed 2026-11-14,
see PLAN.md "Context"). Origin: `IDEA.md`.

**`PLAN.md` is the source of truth**: design decisions, model choices, and every
experiment's findings. Read it before changing behavior, and append new findings there
(dated section, suite-level table, conclusions) after each experiment.

## Commands
```bash
uv run pytest -q                                   # unit tests, no network
uv run python -m evals.run --task toy_bridge --strategy self_forget --backend or-qwen3.8-27b
evals/matrix.sh runs/<name> or-qwen3.8-27b 0.7     # 6 tasks × 4 strategies × 3 seeds, JOBS=8 parallel (~$2.60)
evals/matrix.sh runs/<name> purdue-qwen3.8-27b 0.7 # same matrix, free on Purdue GenAI Studio (~75 min, throttled)
TASKS="rot_1 queue_1" SEEDS="0 1 2 3 4" evals/matrix.sh runs/<name> purdue-qwen3.8-27b 0.7  # pick tasks/seeds (SUITE_V2 in evals/tasks)
# matrix.sh is resumable: rerun the same command and it skips finished runs (moves unfinished dirs to <out>-unfinished/)
uv run python -m evals.report runs/<name>          # per task/strategy table, $ under none/real/ideal cache
```
Each run writes `runs/<dir>/<run-id>/{trace.jsonl,summary.json,archive/}`. `runs/` is git-ignored;
after an experiment, `uv run python -m evals.export runs/<name> results/<name>.jsonl` and save the
report to `results/<name>_report.txt` so the numbers are committed (`results/` has matrix, purdue-matrix, pilot, v2-pilot, v2-matrix and distract-calib).

## Layout
- `src/tombstone/`: `messages.py` (canonical types → OpenAI format), `client.py` (backend
  profiles), `context.py` (ContextStore: blocks, pending forgets, batched apply, archive,
  ledger), `strategies.py` (NoOp, SelfForget, Truncate, AutoCompact), `agent.py` (loop),
  `prefix.py` (tokenizers, `serialize_request`, simulated prefix-reuse metric), `trace.py`.
- `evals/`: `env/` (MockWeb, FakeFS, QueueEnv: output delivered once), `tasks/` (seeded multi-phase tasks with source labels
  distractor/relevant/needed_later; v1 = dossier/chain/repo, v2 = horizon/rot/queue/exact/buried/short, one per
  strategy weakness), `metrics.py`, `run.py`, `report.py`, `matrix.sh`.

## Invariants (tests cover these; keep them)
- Only tool-result *content* is ever rewritten, so tool_call/tool_result pairing stays valid.
- Retrieval is append-only (a new tool result); tombstones stay in place.
- The ledger is ephemeral: a trailing user message rendered per request, never stored in history.
- Runs stop with `stopped: "context_overflow"` before sending a request over `--max-context` (default 60,000,
  counted with the ledger); unanswered phases fail. Provider errors (HTTP 400) still crash the run.
- All strategy thresholds use the agent's `count_context` (full request incl. tool schemas,
  model tokenizer) so they share units with the real prompt.
- Graders are token-exact on the `FINAL:` line; decoys differ by small details (e.g. `legacy_` prefix).

## Models and secrets
- Primary: `or-qwen3.8-27b` (OpenRouter, pinned to DeepInfra bf16, exact HF tokenizer).
  Second family: `or-llama3.3-70b` (approx tokenizer; HF repo is gated). `ollama-glm-flash`
  is the CLI default for cheap local iteration. Free: `purdue-qwen3.8-27b` (Purdue RCAC GenAI Studio,
  same model name, unknown quantization; throttled to 18 req/min across processes; 65,536-token
  context; no `cached_tokens`; seeds not reproducible). Don't mix its runs with DeepInfra runs in one comparison.
- `OPENROUTER_API_KEY` and `GENAI_API_KEY` live in git-ignored `.env`. Never print or commit them.
- Paid runs cost real money: say roughly what a batch will cost before launching it.

## Measurement gotchas
- Compare strategies on the **ideal (simulated prefix) cost** and suite totals across seeds.
  Provider `cached_tokens` is noisy (identical behavior gave a 34% cost difference) and
  per-run variance is ±40–80%.
- Use temperature 0.7 for multi-seed runs; at 0 seeds mostly repeat.
- `report.PRICES` only has the Qwen backends; add an entry for any new backend you want priced.

## Status
Done: core loop, forgetting, baselines, task suite, full Qwen matrix, and its replication on GenAI Studio
(see PLAN.md; strategy cost differences of ±15% didn't replicate across hosts, so cost claims need more seeds).
Prior work: the mechanism is already published (PLAN.md "Related work"); frame results as a controlled
accuracy benchmark, not as a new mechanism.
Suite v2 (one task per strategy weakness) + overflow handling built, and its 144-run matrix done (PLAN.md
"Suite v2 matrix"): self_forget 250/252 phases and the only strategy with no failing task family; none is
cheapest wherever it can finish.
Not yet shown: that pruning beats a full context on distraction/rot. Where everything fit, none was 167/168, and
Qwen 3.8 27B wasn't distracted by look-alike decoys at ≤55k tokens; self_forget's lead comes from other harnesses
breaking (overflow, unrefetchable output, lossy summaries).
Distraction calibration (latent/stale tasks, PLAN.md "Distraction calibration"): Qwen 3.8 27B none got 256/256
with decoys or stale values in context, so the premise fails on this model at ≤50k tokens.
Open, in rough priority: the same calibration on weaker models (free on GenAI Studio: llama3.3:70b, qwen3:8b/14b),
then tasks where distraction/rot actually hurts a full context (harder decoys, longer contexts,
weaker or second-family models such as Llama), with predictions fixed first; ablations (summary vs bare stub, ledger
on/off, immediate vs batched apply); the cost-aware apply rule (confirm before starting).
