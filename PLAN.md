# Tombstone Agent: Plan

## Context
`IDEA.md` describes an agent that can **forget** parts of its own context. Context is split into addressable blocks. The agent can replace a block with a tombstone and recover it later from an archive. The research question is whether self-directed forgetting cuts token cost while keeping task success, compared with no management and with naive truncation/compaction. The mechanism itself has since been published (see **Related work**), so the contribution has to come from the controlled study and the cost-aware apply rule, not from the mechanism.

Greenfield repo (only `IDEA.md`). The deliverable is a research prototype plus experimental results.

## Related work (searched 2026-10-29)
The mechanism is **not novel**. Closest prior work:

| Work | What it does | Gap relative to us |
|---|---|---|
| Franke, *Agent-Controlled Forgetting for Tool-Using Agents* ([2610.10590](https://arxiv.org/abs/2610.10590), 6 Oct 2026) | Nearly identical: tool results only, agent-written note in place, archive, batch `context_apply`, `context_recover` as a new tool result, ephemeral reminder. Also used glm-5.3-flash. 50% fewer input tokens on one task, slightly more on another, worse on an adverse case (4/12 vs 6/12) | One run pair per task, no variance, one model; recovery not exercised in the main pair; only a keep-everything baseline; cache costed as a range. Their future work (repeated runs, a recovery-demand task, matched clearing/compaction baselines) is what our suite does |
| VISTA ([2606.30005](https://arxiv.org/abs/2606.30005), Jun 2026) | Every message is an addressable block; a per-turn dashboard (≈ our ledger); archive (recoverable) or delete. LOCA-Bench 22.7% → 50.7%; removing the dashboard costs more than removing recovery | Ignores prompt caching; costs are raw token counts |
| Cache Engineering for Agents ([2610.28577](https://arxiv.org/abs/2610.28577), Oct 2026) | Agent drops entries from the KV cache instead of editing text, so nothing is re-prefilled. −27.7% cost vs threshold summarization | Needs serving-side cache control, not just an API |
| Beyond Compaction ([2606.11213](https://arxiv.org/abs/2606.11213)), Beyond Token Savings ([2609.32961](https://arxiv.org/abs/2609.32961)), TokenPilot ([2606.17016](https://arxiv.org/abs/2606.17016)), CliffCompaction ([2609.26779](https://arxiv.org/abs/2609.26779)) | Rewriting history invalidates the cached suffix, so token savings ≠ cost savings; designs that keep the prefix stable or compact rarely | Our "caching eats the savings" finding is already known. *Only seen via search snippets; read before citing* |
| MemGPT ([2310.08560](https://arxiv.org/abs/2310.08560)), Anthropic `clear_tool_uses`, ACON ([2510.00615](https://arxiv.org/abs/2510.00615)) | Agent pages memory via function calls; automatic oldest-first tool-result clearing; optimized compression guidelines | Ancestors / automatic baselines |

**What may still be ours:**
1. A controlled, labelled study: matched truncate/compact baselines, seeds, trap phases, ideal prefix-reuse cost. Needs more seeds and a second model to be convincing.
2. Forget precision against ground-truth source labels. Not seen in the papers above.
3. A **cost-aware apply rule** deciding *when* agent-chosen forgets take effect (break-even: saved × cache price × remaining turns > invalidated suffix × (input − cache price)). The cache papers instead keep the prefix stable or edit the KV cache. Check *Beyond Token Savings* in full before claiming this.

**Baselines to add:** threshold clearing as in Franke's comparison plan, and possibly a VISTA-style archive. Cache-engineering drop needs a local serving stack (vLLM/SGLang), so treat it as discussion unless we self-host.

## Decisions (from the grilling)
| Topic | Decision |
|---|---|
| Goal | Research prototype; the output is findings |
| Block unit | **Tool results only**. Each `tool_result` gets an ID `b<N>`. Only the result *content* is swapped, so tool_use/tool_result pairing never breaks |
| Tombstone | Agent-written summary: `forget(block_id, summary)` → `[b17 forgotten: web_fetch(url), 4.2k tok. Summary: …]` |
| Cache | **Deferred/batched apply.** Forgets queue up and are applied when pending savings ≥ threshold (default 10k tok). Threshold=0 gives the "immediate" ablation |
| Retrieval | `retrieve_context(block_id)` returns content as a **new tool result** (append-only). The tombstone stays in place |
| Trigger | System prompt policy + a per-turn **block ledger** (id, source, tokens, age, status) |
| Baselines | (1) full context, no management; (2) naive truncation (stub all but the last K tool results); (3) auto-compact (summarize history at a token threshold) |
| Tasks | Custom synthetic suite with **fully mocked** tools (local corpus web, fake FS) and known distractor labels |
| Stack | Python + uv, **open-source models** via one **OpenAI-compatible** client (`base_url` profiles for OpenRouter / Ollama / llama.cpp server / vLLM), hand-rolled loop, no framework |
| Headline metric | Same accuracy, fewer tokens. Secondary: $ (with cache pricing), cache hit rate, forget precision/recall vs distractor labels, retrieval rate |

## Key design details
- **Canonical message format.** An internal list of messages and blocks, rendered to OpenAI chat-completions format (`tool_calls` / `role: tool`). Keeping it canonical lets the context store work without a particular wire format and makes rendering easy to unit-test.
- **Backend profiles.** A config such as `{name, base_url, api_key_env, model, tokenizer}`. Start with one strong tool-calling open model (e.g. a Qwen-class instruct model), plus one alternative for generality.
- **Cache measurement.** With open models, prefix-cache behavior depends on the backend, so we measure it rather than assume it:
  - Local (Ollama / llama.cpp `cache_prompt` / vLLM prefix caching): record tokens actually evaluated vs. total prompt tokens, from backend timing/usage fields (e.g. llama.cpp `timings.prompt_n`, vLLM metrics). Verify which field means what in phase 1.
  - OpenRouter: record `prompt_tokens_details.cached_tokens` when present. Treat it as provider-dependent and possibly missing.
  - Fallback: a **simulated cache metric**, the longest common token prefix between consecutive rendered prompts. It's deterministic and backend-independent, and it's the main number for comparing strategies.
- **Ledger placement (cache-safe).** The ledger is rendered **ephemerally** at the tail of the final message and never stored in history. Without this, a stored ledger would change on every turn and break prefix reuse.
- **Pending state.** A queued forget shows as `pending-forget` in the ledger. Content stays visible until it's applied, so the agent can change its mind. A batch applies the forgets in one rewrite and logs the cache miss.
- **Archive.** Each run gets `runs/<id>/archive/b<N>.json` with the original content and metadata. Retrieving an unknown or never-forgotten ID returns a tool error.
- **Min block size.** Only blocks ≥ ~300 tokens appear in the ledger as forgettable, so the agent doesn't fuss over tiny results.
- **Token counting.** Use the model's own HF tokenizer (via `tokenizers`) for the ledger, thresholds and the simulated prefix metric. Backend `usage` serves as a cross-check.

## Layout
```
pyproject.toml
src/tombstone/
  messages.py        # canonical Message/Block/ToolCall types
  client.py          # OpenAI-compatible client, backend profiles, normalized Usage
  prefix.py          # tokenizer + simulated prefix-reuse metric
  context.py         # ContextStore: blocks, ids, pending queue, apply, archive, ledger render
  tools.py           # forget / retrieve_context schemas + handlers
  strategies.py      # NoOp, Truncate(K), AutoCompact(threshold), SelfForget(threshold)
  agent.py           # loop: render → call → dispatch tools → strategy hook → log
  logging.py         # per-turn JSONL trace (usage, ledger, forgets, applies)
evals/
  env/               # mock web_fetch/search over corpus, fake fs read/list/grep
  tasks/             # task specs: prompt, corpus, distractor labels, grader
  run.py             # matrix: tasks × strategies × models × seeds
  report.py          # tables + success-vs-cost plot
tests/
```

## Phase 1 findings (2026-10-27)
- Backends: `glm-5.3:cloud` (primary) and `kimi-k3:cloud` via Ollama both do valid tool calls. `qwen3.5:cloud`, `deepseek-v4-flash:cloud` and `glm-5.1:cloud` are retired.
- GLM reports real prefix-cache hits in `prompt_tokens_details.cached_tokens`, in 128-token granularity (≈ the full prior prompt is cached each turn). Kimi always reports 0, so treat it as unreported.
- The ephemeral ledger goes in as a separate trailing `user` message, not appended into the last tool result. That's equivalent for caching and cleaner.
- On the toy task, the NoOp agent fetches all 5 pages (1 relevant + 4 ~1k-token distractors), so the distractor build-up we want to prune shows up naturally.

## Models (decided after OpenRouter smoke test, 2026-10-27)
| Role | Backend profile | Model @ pinned provider | Cache reported |
|---|---|---|---|
| **Primary** | `or-qwen3.8-27b` | `qwen/qwen3.8-27b` @ DeepInfra bf16 | ✅ |
| **Second family** | `or-llama3.3-70b` | `meta-llama/llama-3.3-70b-instruct` @ AkashML fp8 | ✅ |
| Cheap iteration | `ollama-glm-flash` (CLI default) | `glm-5.3-flash:cloud` | ✅ |

- Pinning: `provider.order=[tag]`, `allow_fallbacks=false`. Key in git-ignored `.env` (`OPENROUTER_API_KEY`).
- Rejected: llama-3.1-8b (dropped a required tool argument); qwen3-235b-a22b-2507 and qwen3.6-35b-a3b (no cache reporting).
- **Eval-design implication:** Llama solved the toy task after fetching only the relevant page, so it had no distractors to forget. Tasks must *force* distractor reads (relevance only knowable after reading, multi-phase work). Otherwise token savings measure how curious each model is, not whether forgetting works.

## Phase 2 findings (2026-10-27, toy_bridge)
- The mechanism works live. Qwen 3.8 27B forgot exactly the 4 distractors, with accurate summaries, on both seeds. GLM-flash forgot the primary source early, then recovered it via `retrieve_context`.
- **Qwen forgets only right before answering** ("tidy up at the end"). Forgetting then saves nothing and adds a turn. self_forget used 18.6k–23.2k prompt tokens vs 6.6k–9.3k for NoOp. On a 5-turn task the policy/ledger/tool overhead plus the extra turn outweighs any savings.
- At the default 10k threshold a batch never applies on a task this short, so it's pure overhead.
- Real `cached_tokens` is noisy and coarse on DeepInfra (often 784 when ~4k was reusable) and was 0 throughout this GLM-flash run. This confirms the simulated prefix metric as the primary cache measure.
- Implications for phases 3–4: tasks must be long, with distractors read early and many turns after them, or savings can't pay for the overhead. Consider prompting for forgetting *when relevance becomes clear*, plus the pressure-nudge ablation. Report the per-turn overhead (policy + ledger + tools) separately.

## Multi-phase task suite + pilot (2026-10-27)
Tasks (all seeded, labelled, tested solvable): `dossier_{1,2}` (5 phases: 4 structures, then a trap asking a phase-0 detail), `chain_{1,2}` (2 phases × 3-hop ferry→bridge→engineer→birthplace), `repo_{1,2}` (4 phases over a fake repo with deprecated/sibling-constant decoys, plus a trap asking a phase-0 function name). ~1.4k-token pages, 27–41k tokens of sources per task.

Pilot: Qwen 3.8 27B, 1 seed, threshold 10k. **Every run got every phase right.**
| task | strategy | prompt tok | $ no cache | $ real cache | $ ideal cache (sim) |
|---|---|---|---|---|---|
| dossier_1 | none | 339k | 50.8m | 20.5m | 21.2m |
| dossier_1 | self_forget | 249k (−27%) | 37.4m | 23.3m (+13%) | 17.5m (−17%) |
| chain_1 | none | 226k | 33.8m | 13.0m | 14.8m |
| chain_1 | self_forget | 200k (−12%) | 29.9m | 19.7m (+51%) | 16.0m (+8%) |
| repo_1 | none | 108k | 16.1m | 7.6m | 6.9m |
| repo_1 | self_forget | 126k (+17%) | 18.9m | 9.3m (+23%) | 8.5m (+23%) |
(m = $0.001; DeepInfra: $0.15/M input, $0.0375/M cache read.)

- **Behavior is now right.** Qwen forgets at phase boundaries (when the next question arrives) and within chains after each hop resolves. Forgets are ~70–80% distractors, the rest finished-phase relevant pages. On the dossier trap it correctly ran `retrieve_context` on the phase-0 page.
- **Caching eats the savings.** NoOp's append-only context gets ~80% cache hits, so the tokens self_forget removes were already cheap (25% price). Each batch apply re-prefills the whole suffix at full price. Real provider caching recovers more slowly than the simulated metric after a rewrite.
- **Accuracy can't separate the strategies yet:** both are at 100%. The tasks are too easy to show context-rot effects.
- **Next decisions:** (a) a cost-aware apply rule: apply only when (tokens saved per turn × expected remaining turns × cache price) > (invalidated suffix × (input price − cache price)); (b) longer horizons, where savings compound; (c) harder/longer tasks so accuracy can differ; (d) run baselines (phase 3) before more tuning.

## Baselines (2026-10-28)
`truncate` (once context ≥ trigger, stub all but the last K=5 tool results; no summary or retrieval) and `compact` (once context ≥ trigger, the same model summarizes the transcript and history resets to [system, summary + current question]; summarizer tokens are counted). Default trigger is 20k. Report: `uv run python -m evals.report runs/pilot`.

Pilot, Qwen 3.8 27B, 1 seed. All 4 strategies got 100% of phases on all 3 tasks. $m = $0.001, output tokens included.
| task | none real/ideal | self_forget | truncate | compact | re-reads (sf / trunc / compact) |
|---|---|---|---|---|---|
| dossier_1 | 31.0 / 31.7 | 40.2 / 34.4 | 44.7 / 37.8 | 55.4 / 52.0 | 0 / 11 / 15 |
| chain_1 | 17.5 / 19.3 | 28.7 / 25.0 | 27.1 / 23.8 | 58.3 / 53.1 | 0 / 0 / 7 |
| repo_1 | 13.3 / 12.6 | 18.3 / 17.5 | 17.8 / 13.2 | 34.3 / 29.5 | 0 / 0 / 9 |

- NoOp is cheapest with caching on every task. Among the managing strategies, self_forget wins on dossier, roughly ties truncate on chain, and compact is worst everywhere (extra turns, re-reads, summarizer cost).
- self_forget never re-reads (it retrieves instead) and cuts peak context the most on the web tasks (44.5k → 28.1k dossier).
- **Caveat: the token-count mismatch.** Strategy thresholds use ApproxTokenizer over messages only (no tool schemas), which undercounts the real prompt. repo_1 truncate never triggered (21k real peak), so it behaved exactly like NoOp. **Its real-cache cost still differed by 34% (17.8 vs 13.3m), which is provider cache noise.** Use the ideal (simulated) column for comparisons, and multiple seeds. Follow-up: an exact Qwen tokenizer (HFTokenizer) and counting schemas in thresholds.

## Tokenizer fix (2026-10-28)
- Each backend names its HF tokenizer (`Backend.tokenizer`). Qwen uses `Qwen/Qwen3.8-27B`; Llama's repo is gated, so it uses approximate counts for now.
- The agent hands every strategy one `count_context` (full request including tool schemas), so all thresholds share units with the real prompt.
- `serialize_request` is now chat-template-like plain text. JSON escaping had inflated counts by ~10%. Calibrated against DeepInfra `usage.prompt`: within ~1.5% above 7k tokens, plus a fixed ~230-token template offset.
- The matrix runs at temperature 0.7 (`--temperature`). At temperature 0, seeds mostly repeat the same run.

## Full matrix (2026-10-28) — `runs/matrix`, $2.60 total
Per-run data: `results/matrix.jsonl` (summary + trace-derived cost per run); table: `results/matrix_report.txt`.
Qwen 3.8 27B, temperature 0.7, 6 task variants × 4 strategies × 3 seeds = 72 runs, all completed. Thresholds use exact Qwen token counts.

| strategy | phase acc (of 66) | $ no cache | $ real cache | $ ideal cache | peak prompt | re-reads |
|---|---|---|---|---|---|---|
| none | 66/66 | 0.93 | **0.58** | **0.42** | 38.4k | 15 |
| self_forget | **66/66** | 0.82 (−12%) | 0.64 (+11%) | 0.49 (+15%) | 23.3k | **7** |
| truncate | 63/66 | **0.80 (−14%)** | 0.61 (+5%) | 0.47 (+11%) | 17.4k | 127 |
| compact | 65/66 | 0.95 (+2%) | 0.77 (+34%) | 0.69 (+63%) | 17.5k | 232 |

- **With caching, NoOp is cheapest overall.** Without caching, self_forget and truncate both save 12–14%.
- **self_forget is the only managing strategy with no wrong answers.** Truncate's 3 errors came after clearing: it picked a decoy (legend year ×2, deprecated `0.05` fee rate); compact had 1 error. 3/66 isn't statistically significant, but the failure mode matches the hypothesis: blind clearing loses context, and re-reading lets decoys win.
- **self_forget re-reads almost never** (7, vs 127 truncate and 232 compact). It forgot `needed_later` sources in 11/18 runs, yet every trap phase passed: 9 retrievals in total, and the summaries covered the rest.
- Forget precision: 232 distractor, 96 relevant (finished phases), 13 needed_later, 4 unlabeled.
- **Per-run variance is large** (±40–80% relative cost vs NoOp across seeds/tasks). Use suite totals, not per-task means.
- Implication: self_forget's advantage is reliability plus lower peak context, not cost. To win on cost with caching, it needs the cost-aware apply rule and/or longer horizons, and accuracy needs harder tasks to separate the strategies.

## Build phases
1. **Core loop + one backend.** Canonical types, OpenAI-compatible client, agent loop, mock tools, NoOp strategy, JSONL trace. Confirm the chosen model does reliable tool calls on the backend, and work out which backend usage/timing fields show prefix reuse. Exit: an agent solves a toy task end-to-end.
2. **Context store + forgetting.** Block IDs, ledger, `forget` / `retrieve_context`, deferred apply, archive, simulated prefix metric. Unit tests for render/apply/retrieve and tool-pair integrity.
3. **Baselines.** Truncate(K) and AutoCompact strategies behind the same hook.
4. **Synthetic suite (~6–10 tasks).** e.g. (a) a research question where 70% of fetched pages are distractors; (b) sequential subtasks in a fake repo where task 1's files are irrelevant to task 2; (c) a "trap" task where forgotten info is needed later, which tests retrieval. Graders are deterministic (exact/regex/checklist).
5. **Experiments + report.** Matrix runs with ≥3 seeds. Ablations: immediate vs batched apply, ledger on/off, summary vs bare stub.

## Verification
- `uv run pytest`: context-store unit tests (IDs stable, apply only rewrites tool_result content, pairing valid, archive round-trip, ephemeral ledger never persisted).
- `uv run python -m evals.run --task <toy> --strategy self_forget --backend ollama`: inspect the trace and confirm forgets, a batch apply, and a drop in prefix reuse only on batch-apply turns.
- Cache check: on a turn with no batch apply, the simulated prefix reuse should be ≈100% of the prior prompt. On a local backend, evaluated prompt tokens should be ≈ only the new tail.
- `uv run python -m evals.report`: produces the strategy comparison table and plot.

## Open risks
- The model may under-use `forget` even with the ledger. If so, the pressure-nudge ablation is the fallback.
- Open models vary in tool-calling reliability, and smaller models may misuse `forget` (e.g. forgetting needed info or writing empty summaries). Pick the model in phase 1 based on a tool-call smoke test. Log malformed calls as a metric.
- OpenRouter routes to different upstream providers with different caching. Pin the provider (OpenRouter `provider.order` / `allow_fallbacks: false`) for reproducibility, or use local backends for the cache experiments.
