# Tombstone Agent

A research prototype of an LLM agent that **prunes its own context**. LLMs get distracted by irrelevant
context and perform worse as their context grows longer ("context rot"). Tombstone Agent lets the model act on
that itself: each tool result gets an id, and once a result turns out to be irrelevant or no longer needed, the
agent replaces it with a short summary it writes (a "tombstone"). The original goes to an archive it can
retrieve from later.

The question is whether an agent that actively keeps its context clean **executes tasks more accurately** than
other harnesses (keeping everything, truncating old results, auto-compacting the transcript), because it isn't
led astray by stale or misleading material, while keeping an eye on what that costs.

The mechanism itself is already published (see "Related work" in [PLAN.md](PLAN.md)). This repo is a
controlled benchmark: matched baselines, seeded tasks with labelled distractors and near-miss decoys,
predictions fixed before each run, and multiple seeds.

## How it works
- `forget(block_id, summary)` queues a tool result to be replaced by the agent's summary. Forgets are applied in
  batches, since every rewrite invalidates the provider's prompt cache from that point on.
- `retrieve_context(block_id)` returns the original as a new tool result, so forgetting is never final.
  History is never reordered, so tool-call pairing stays valid.
- A per-turn ledger (block ids, sizes, ages) is sent at the end of each request but never stored in history.

Baselines: `none` (keep everything), `truncate` (stub all but the last 5 tool results), `compact` (summarize the
transcript at 20k tokens). Runs stop with `context_overflow` above a fixed context limit (60k tokens).

## Results so far
Qwen 3.8 27B, synthetic tasks with mocked web, filesystem and message-queue tools. Details and every finding
are in [PLAN.md](PLAN.md); per-run data is in [`results/`](results/).

Suite v2 matrix: 6 task families, each built around one harness's predicted weakness (long horizons, near-duplicate
decoys, output that can't be fetched again, exact strings, facts that only matter later, short tasks); 144 runs.

| strategy | phases correct | cost vs none (ideal cache) |
|---|---|---|
| none | 203/252 (overflows on long tasks) | — |
| self_forget | **250/252** | +51% |
| truncate | 230/252 | +89% |
| compact | 205/252 | +115% |

- self_forget is the most accurate harness and the only one with no task family it fails, at a moderate cost.
- Its edge so far comes from the other harnesses breaking: `none` runs out of context, `truncate` loses output it
  can't fetch again, `compact` drops state in its summaries. Where everything fit in context, `none` was just as
  accurate (167/168).
- **Not yet shown:** that pruning beats a full context on distraction or rot. At these sizes (up to ~55k tokens)
  Qwen 3.8 27B wasn't measurably distracted by look-alike decoys. Showing that effect needs harder or longer
  tasks, or weaker models.

## Running it
Requires [uv](https://docs.astral.sh/uv/) and an API key in a git-ignored `.env` (`OPENROUTER_API_KEY`, or
`GENAI_API_KEY` for Purdue GenAI Studio).

```bash
uv run pytest -q                                   # unit tests, no network
uv run python -m evals.run --task short_1 --strategy self_forget --backend or-qwen3.8-27b
TASKS="rot_1 queue_1" SEEDS="0 1 2" evals/matrix.sh runs/demo or-qwen3.8-27b 0.7   # resumable matrix
uv run python -m evals.report runs/demo            # per task/strategy table
```

## Layout
- `src/tombstone/`: agent loop, context store (blocks, batched forgets, archive, ledger), strategies, client
  backends, tokenizer-based prefix-cache metric.
- `evals/`: mock environments, seeded tasks with source labels, runner, report, matrix script.
- `PLAN.md`: design decisions and the dated log of every experiment. `IDEA.md`: the original idea.
