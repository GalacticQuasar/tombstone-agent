# Tombstone Agent: Plan

## Context
`IDEA.md` describes an agent that can **forget** parts of its own context. Context is split into addressable blocks. The agent can replace a block with a tombstone and recover it later from an archive. The research question is whether self-directed forgetting cuts token cost while keeping task success, compared with no management and with naive truncation/compaction. The mechanism itself has since been published (see **Related work**), so the contribution has to come from the controlled study and the cost-aware apply rule, not from the mechanism.

Greenfield repo (only `IDEA.md`). The deliverable is a research prototype plus experimental results.

**Reframe (2026-11-14): accuracy first, cost second.** The original motivation is that LLMs get distracted by irrelevant context and degrade at long contexts (context rot). The question is now whether an agent that actively prunes its own context **executes tasks more accurately** than other harnesses (no management, truncation, compaction) because it isn't led astray by stale or misleading material. Cost stays a reported constraint (ideal-cache $ and peak context), not the optimization target. Findings below that are framed around cost are unchanged as records. The cost-aware apply rule drops from the main contribution to a secondary item.
- Evidence so far (suite v2 matrix): self_forget is the most accurate harness (250/252) and the only one with no failing task family. Its lead comes from the others breaking: overflow, output that can't be fetched again, lossy summaries. **Distraction/rot hurting a full context hasn't been shown yet.** Where everything fit, none got 167/168, and Qwen 3.8 27B wasn't distracted by look-alike decoys at ≤55k tokens.
- Next: tasks where distraction or rot does hurt a full context (harder or more plausible decoys, longer contexts within the window, weaker or second-family models), with predictions fixed before running; then ablations (summary vs bare stub, ledger on/off).

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
| Headline metric | ~~Same accuracy, fewer tokens~~ → **task accuracy** (reframed 2026-11-14). Secondary: $ (with cache pricing), peak context, forget precision/recall vs distractor labels, retrieval rate |

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
| Free replication (added 2026-11-09) | `purdue-qwen3.8-27b` | `qwen3.8:27b` @ Purdue RCAC GenAI Studio (vLLM; quantization unpublished) | ❌ |

- GenAI Studio: free for Purdue users (pilot); key `GENAI_API_KEY`. Limit is 20 requests/min per user, so the client throttles to 18 across processes and retries a `null`/429 response with backoff. 65,536-token context. Seeds not reproducible.

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

## Replication on Purdue GenAI Studio (2026-11-09) — `runs/purdue-matrix`, $0
Per-run data: `results/purdue-matrix.jsonl`; table: `results/purdue-matrix_report.txt`.
Same suite, seeds and temperature (0.7) as the 2026-10-28 matrix, on backend `purdue-qwen3.8-27b`: Purdue RCAC GenAI Studio, `qwen3.8:27b` on vLLM 0.30.0. Its quantization isn't published, so don't assume it equals DeepInfra bf16. Costs use DeepInfra prices so they compare; the service itself is free.
The host reports no `cached_tokens`, so the real column equals no cache and the ideal (simulated) column is the only cache measure.

| strategy | phase acc (of 66) | prompt tok | $ no cache | $ ideal cache | peak prompt | re-reads |
|---|---|---|---|---|---|---|
| none | **66/66** | 4.75M | 0.80 | 0.34 | 35.1k | 0 |
| self_forget | 65/66 | 3.61M (−24%) | 0.67 (−17%) | 0.36 (+6%) | 22.3k | 26 |
| truncate | 65/66 | **2.89M (−39%)** | **0.55 (−32%)** | **0.30 (−10%)** | 16.4k | 52 |
| compact | 62/66 | 3.13M (−34%) | 0.65 (−20%) | 0.45 (+32%) | 16.1k | 168 |

Pooled with the DeepInfra matrix (6 seeds per cell, two hosts), ideal $: none 0.76, self_forget 0.85 (+12%), truncate 0.77 (+1%), compact 1.14 (+50%). Phase accuracy (of 132): none 132, self_forget 131, truncate 128, compact 127.

- **Truncate's cost sign flipped.** It went from +11% vs NoOp (DeepInfra) to −10% here, ending cheapest of all on ideal cost. Pooled, it ties NoOp. One 72-run matrix can't rank truncate against NoOp; that needs more seeds.
- **Replicated:** self_forget costs a bit more than NoOp with ideal caching (+6% here, +15% before) and less without caching. It cuts peak context by about 37% (35.1k → 22.3k). Compact is worst on ideal cost both times.
- **self_forget's one miss isn't a forgetting failure.** In chain_1 s1, phase 2, the page said "Nadia Bruthora was born in Birholt." The model read it, didn't forget it, and answered `Birkholt` on the next turn: a copying error. Truncate's miss (repo_2 s0: `90, 10` vs `60, 10`) and compact's 4 chain misses (wrong birthplace) weren't inspected.
- **Forget behavior replicated almost exactly.** Forgets by label: 233 distractor, 95 relevant, 14 needed_later, 3 unlabeled (vs 232/96/13/4). There were 10 retrievals, 12/18 runs forgot a `needed_later` source, and every trap phase passed.
- **Re-reads were lower for truncate (52 vs 127) and higher for self_forget (26 vs 7).** Re-reads aren't stable across hosts either.
- **Operations:** 72 minutes at 18 requests/min with `JOBS=8`, and no rate-limit retries. One run (chain_2 self_forget s0) died on a transient HTTP 400 with an empty body at turn 2 (~1k-token prompt). Its trace was set aside and the configuration rerun, and the rerun passed. Seeds aren't reproducible on this host: the same seed gave different outputs at temperature 0.7.
- **Implication:** the cost differences between none, self_forget and truncate (±15%) are about the size of the host-to-host and seed-to-seed noise. The robust results are accuracy (self_forget ≥ truncate > compact, though small n), peak-context reduction, and compact's cost penalty. Claims about cost need more seeds (GenAI Studio makes these free) or the cost-aware apply rule plus longer horizons. Longer horizons on this host will hit its 65,536-token context cap.

## Next: task suite redesign (planned 2026-11-13, before the cost-aware apply rule)
**Why:** across both matrices NoOp got 132/132 phases, and the cost gaps between strategies (±15%) are within host and seed noise. The suite can't show any strategy's weakness, so tuning a strategy on it (cost-aware apply) would be tuning against noise. Build tasks that target each strategy's predicted failure first.

**Why the current tasks don't separate strategies:**
- Contexts peak at ~35–50k tokens, so NoOp suffers no rot or overflow.
- Every source can be fetched again for free (web pages, repo files), so truncate and compact lose nothing permanently; their cost shows up only as re-reads.
- Decoys win only after a re-read, which is rare.

**Planned tasks, with predictions written down before any run:**
| Weakness | Task design | Predicted loser | Predicted winner |
|---|---|---|---|
| Context growth | Long horizon (10+ phases) that pushes NoOp past the context limit | none (overflows) | any managed strategy |
| Context rot | Many near-duplicate decoys kept in context, then a question that needs the right one | none | self_forget, truncate |
| Blind clearing | Tool output that can't be fetched again (one-time log, changing search results, command output), needed several phases later | truncate | self_forget (summary + archive) |
| Lossy summaries | Later questions need exact strings (hashes, IDs) seen early | compact | self_forget (retrieves the original) |
| Forgetting too early | A source that looks irrelevant when read but matters later, and can't be found again without knowing it exists | self_forget | none |
| Overhead | Short tasks (1–2 phases) | self_forget | none |

**Design rules:**
- Include tasks where self_forget should lose (the last two rows), so the suite isn't rigged in its favor.
- The predictions above are fixed now. If a pilot contradicts one, report it; don't tune the task until the expected winner wins. Fixing a solvability bug is fine.
- Reuse `world.py`, MockWeb and FakeFS. The non-refetchable case needs a tool whose output is served only once, or changes between calls.

**Prerequisite, context overflow:**
- Today a too-long request crashes the run; GenAI Studio returns an HTTP 400.
- Add an agent-side context limit (e.g. `--max-context`, checked with `count_context` before each request) that ends the run with `stopped: "context_overflow"`. Unanswered phases count as failures, and the run's cost so far is still recorded.
- Enforcing the limit in the agent keeps behavior identical across hosts; DeepInfra's window is larger than GenAI Studio's 65,536. Set it below 65,536, leaving room for the completion.
- Keep provider 400s as a separate error. The 400 on 2026-11-09 was transient, with an empty body.

**Order** (1–4 done 2026-11-13, see the next section):
1. Implement overflow handling, with tests.
2. Build one task per row.
3. Pilot each new task on `purdue-qwen3.8-27b`: 1 seed, all 4 strategies. Keep a task only if the strategies differ on it.
4. Let `matrix.sh` take a seed list (it hard-codes `0 1 2`), then run the new suite with more seeds.
5. Then start the cost-aware apply rule (confirm before starting).

## Suite v2 + overflow handling + pilot (2026-11-13) — `runs/v2-pilot`, $0
Per-run data: `results/v2-pilot.jsonl`; table: `results/v2-pilot_report.txt`.

**Built (steps 1, 2 and 4 of the redesign order):**
- Overflow: `Agent(max_context=)` / `--max-context` (default 60,000) counts each request, ledger included, before sending it. If it's over the limit, the run ends with `stopped: "context_overflow"`, the request isn't sent, unanswered phases fail, and the cost so far is kept. The report shows `overflow=n/N`. `--max-turns` default 80 → 200 (no earlier run reached 80).
- Client: a 400 with an **empty body** is retried with the rate-limit backoff. It's transient on GenAI Studio: 6 of the 24 pilot runs hit it, 5 of them within 2 minutes, on requests of 0.4–20k tokens, and all 6 passed on rerun. A 400 with an error message (e.g. context too long) is still raised.
- Tasks (`SUITE_V2`, variants 1 and 2; `dossier_1/2` text checked byte-identical after the refactor):

| task | targets | design |
|---|---|---|
| `horizon` | growth | 14 dossier phases, ~130k tokens of sources |
| `rot` | rot | 45 station logs with neutral file names (`log_NN.txt`), in look-alike families (KV7/KV7A/KV7B) whose readings differ by small nonzero offsets; 8 lookups + a phase-0 trap; ~45k tokens if every log is read (under the limit) |
| `queue` | blind clearing | `poll_queue` delivers each message once (new `QueueEnv`); the last phase needs a commit hash from the phase-0 poll; ~21k tokens, so truncate fires |
| `exact` | lossy summaries | build catalog reachable only through opaque links (`web_fetch` only); each phase finds the release that "Fixes #N" among near misses; the trap asks for the 16-hex arm64 checksum of the phase-0 build and repeats no URL |
| `buried` | forgetting too early | dossier with an aside on the phase-0 history page (a lifeboat and its crew leader), asked in the last phase; search indexes titles only, so it can't be found again |
| `short` | overhead | 2 dossier phases |

- `matrix.sh` takes `TASKS`, `SEEDS`, `STRATEGIES` and `EXTRA` from the environment.

**Pilot:** `purdue-qwen3.8-27b`, variant 1, seed 0, temperature 0.7, all 4 strategies (24 runs). Ideal-cache $m (DeepInfra prices), phases correct:

| task | none | self_forget | truncate | compact | prediction |
|---|---|---|---|---|---|
| horizon_1 | **6/14** (overflow after phase 6), 42.4 | 14/14, 98.1 | 14/14, 55.2 | 14/14, 93.1 | none loses: ✅ |
| rot_1 | 9/9, 30.4 | 9/9, 34.6 | 9/9, 64.6 (180 re-reads) | **7/9**, 115.1 | none loses: ❌ (none was perfect) |
| queue_1 | 6/6, 11.5 | 6/6, 12.9 | **5/6**, 16.8 | **5/6**, 14.8 | truncate loses: ✅ (compact too) |
| exact_1 | **5/6**, 29.6 | 6/6, 40.6 | 6/6, 30.8 | **2/6**, 12.8 | compact loses: ✅, but not on the trap phase |
| buried_1 | 5/5, 19.1 | 5/5, 28.8 | 5/5, 25.6 | **4/5**, 23.3 | self_forget loses: ❌ |
| short_1 | 2/2, 9.0 | 2/2, 12.6 (+39%) | 2/2, 11.4 | 2/2, 13.5 | self_forget costs more than none: ✅ (n=1) |

- **horizon:** none overflowed with 57.7k in context. self_forget forgot 76 blocks (48 distractors, 28 relevant from finished phases) in 7 batch applies, but cost 1.8× truncate (55 turns vs 43). Each apply re-prefills the suffix, so this is the task the cost-aware apply rule should be measured on.
- **rot:** the confusion it targets didn't happen. none answered all 9 at 48k context. Compact's 2 misses (e.g. `40, 1016.4` for WX7B, whose row reads `37, 1016.3`) match none of the 3 sibling rows, so they're post-compaction confabulation. Truncate re-read 180 times (it can't remember which file holds which station) and cost 2× none. As built, rot measures re-read cost, not rot.
- **queue:** truncate and compact both re-polled the drained queue, found it empty, and declined to answer (no guess). self_forget forgot the deploys block, then retrieved it.
- **exact:** compact's summary dropped the catalog URL, and phases 1+ say "from the same catalog", so it stalled in phase 2 ("I don't have access to the catalog"). That's a lossy summary, but in an earlier phase than the trap. none got the trap wrong by copying the darwin-arm64 row instead of linux-arm64 from the right page at 55.6k context: a rot-type error, and the only one in the pilot. self_forget answered the trap from its own summary, without retrieving.
- **buried:** self_forget didn't lose. Asked about a lifeboat it hadn't summarized, it retrieved 15 forgotten blocks in bulk until it found it (peak 39.7k, +50% ideal cost vs none). Its weakness here shows up as **cost**, not accuracy. Compact said no page mentioned the lifeboat.
- **Which tasks separate strategies (step 3 criterion):** horizon, queue, exact and buried separate strategies on accuracy; short and rot only on cost. Keep all six for the multi-seed run. Rot and short are cheap, and one seed can't show an accuracy gap of a few percent.
- **Open decision, not applied (it would mean tuning after seeing results):** restating the catalog URL in exact's phases 1–4 (not in the trap) would make compact fail on the targeted phase rather than earlier. The current failure is a legitimate lossy summary, so the task is unchanged.
- **Next:** multi-seed v2 matrix on GenAI Studio (free): `TASKS="<SUITE_V2>" SEEDS="0 1 2" evals/matrix.sh runs/v2-matrix purdue-qwen3.8-27b 0.7`, 144 runs. horizon dominates the runtime (~50 turns per run), so expect several hours at 18 req/min. Then the cost-aware apply rule (confirm first), measured on horizon.

## Suite v2 matrix (2026-11-13/14) — `runs/v2-matrix`, $0
Per-run data: `results/v2-matrix.jsonl`; table: `results/v2-matrix_report.txt`.
`purdue-qwen3.8-27b`, temperature 0.7, `SUITE_V2` (6 task families × 2 variants) × 4 strategies × seeds 0–2 = 144 runs, so each family/strategy cell has 6 runs. `--max-context 60000`. Costs use DeepInfra prices. The host reports no `cached_tokens`, so the ideal (simulated prefix) column is the only cache measure.

**Operations:** 139 runs passed on the first pass (17:12–20:56). 5 crashed on host errors: three 400s and two 504 gateway timeouts, none of them overflow. That led to two client fixes: retry a 400 without an error message, and retry 5xx (`0232c87`). One 400 after the fix had a message in its body, and the client now logs bodies so the next one is visible. The 5 were rerun with the resumable `matrix.sh` and all passed, with no retries needed. Runs started after the fix used the new retry code. This changes error handling only, not the requests.

**Suite totals** (phases correct of 252; $ = sum over the 36 runs per strategy):

| strategy | phases | $ no cache | $ ideal cache | mean peak prompt |
|---|---|---|---|---|
| none | 203 (80.6%) | 2.14 | **0.86** | 40.2k |
| self_forget | **250 (99.2%)** | 2.74 (+28%) | 1.30 (+51%) | 28.7k |
| truncate | 230 (91.3%) | 3.67 (+71%) | 1.62 (+89%) | 20.0k |
| compact | 205 (81.3%) | 2.50 (+17%) | 1.85 (+115%) | 17.2k |

Excluding horizon, where none can't finish (168 phases): none 167, self_forget 166, truncate 146, compact 122. Ideal $ vs none: self_forget +23%, truncate +101%, compact +99%. No-cache $: self_forget ±0%.

**Per family** (phases correct, ideal $):

| family | none | self_forget | truncate | compact | prediction → verdict |
|---|---|---|---|---|---|
| horizon | **36/84**, 0.22 | 84/84, 0.52 | 84/84, 0.35 | 83/84, 0.59 | none loses → ✅ 6/6 runs overflowed after exactly 6 phases (peak 52.7–57.3k) |
| rot | 54/54, 0.19 | 54/54, 0.22 | **41/54**, 0.77 | **44/54**, 0.77 | none loses (rot) → ❌ none perfect; truncate/compact lose instead |
| queue | 36/36, 0.07 | 35/36, 0.08 | **30/36**, 0.09 | **30/36**, 0.09 | truncate loses → ✅ 6/6 trap misses; compact also 6/6 |
| exact | 35/36, 0.19 | 36/36, 0.21 | 36/36, 0.20 | **12/36**, 0.08 | compact loses → ✅ but before the trap phase |
| buried | 30/30, 0.14 | 29/30, 0.20 | 27/30, 0.15 | **24/30**, 0.23 | self_forget loses → ❌ on accuracy (1/6 trap misses), ✅ on cost (+44%) |
| short | 12/12, 0.05 | 12/12, 0.08 | 12/12, 0.06 | 12/12, 0.09 | self_forget costs most → ❌ narrowly: +53% vs none, but compact +68% |

**How each strategy failed** (all 72 failed phases outside horizon/none inspected):
- **Truncate on rot is a re-read loop, not rot.** Its stubs keep the path but drop the station ID in each file's header, so it can't remember which log holds which station. It averaged 363 re-reads and 92 turns per run, against 18 for none. rot_1 s1 hit the 200-turn limit while still in phase 1, re-reading each log 15–16 times. rot_1 s0 overflowed: one turn read 10 logs in parallel (~17k tokens) and took the request from 43k past 60k before truncate's after-turn clearing could run. So **clearing after each turn doesn't bound the context** when a single turn is large. The other 2 truncate rot misses were wrong rows.
- **The rot errors aren't the targeted rot.** Of 12 wrong rot answers (truncate 2, compact 10), only 1 is a same-time sibling row (compact: MH3A's row for MH3B). 6 match no row in any log (made up after compaction), and 5 match some row of an unrelated station or time. none read up to 48k of look-alike tables and made no errors. At this size and with IDs in each file header, Qwen 3.8 27B doesn't rot.
- **queue:** all 12 truncate/compact trap misses re-polled, or remembered the poll, found the deploys queue drained, and declined: "unknown", or asked the user to re-share the data. None guessed a decoy commit. self_forget retrieved the block in 6 of 6 runs. Its one miss (queue_2 s2) had the correct commit `3eed385` in a turn that also called `forget`, then ended the phase with "Ready for the next question" and no `FINAL:` line: housekeeping displaced the answer.
- **exact:** compact failed identically in 6/6 runs. The first compaction (phase 1–2) dropped the catalog URL, the following prompts say "from the same catalog", and from phase 2 on it asked the user for the URL. It never reached the trap with a usable context. none's one miss is the wrong row on the right page (darwin-arm64 for linux-arm64, at 55k context), the same error as in the pilot. self_forget got 6/6 traps right with only 2 retrievals in total: its forget summaries kept the checksum, or it had not yet forgotten the page.
- **buried:** self_forget missed once (buried_1 s2): it had forgotten the history page and never retrieved, answering "unknown". In the other 5 runs it retrieved forgotten blocks in bulk until it found the aside (55 retrievals over 6 runs), which is where its +44% cost comes from. Truncate (3 misses) and compact (6/6 misses) said no page mentioned the lifeboat. They can't search for it, and they don't re-fetch every page on a hunch.
- **horizon:** compact's one miss was `1880, 1` for `1880, 114`, a truncated number. self_forget averaged 6.8 batch applies and 54 turns per run, against truncate's 44.5. That accounts for its 1.5× ideal cost vs truncate.

**Forget precision (self_forget, 1,119 forget requests):** 769 distractor (69%), 303 relevant from finished phases (27%), 23 needed_later (2%), 24 unlabeled. 89 retrievals, most on buried (55) and rot (24).

**Conclusions:**
1. **self_forget is the only strategy without a systematic failure mode:** 250/252, at most 1 miss per family. Every other strategy fails a whole family: none overflows on horizon, truncate fails queue and loops on rot, compact fails exact, queue and buried. This is the robust result. It has 6 runs per cell, on one host and one model.
2. **Cost: none is cheapest whenever it can finish.** Excluding horizon, self_forget costs +23% ideal (±0% without caching), and truncate and compact cost about 2× through re-reads and summarizer calls. The extra cost of self_forget is concentrated in horizon (many batch applies) and buried (bulk retrieval).
3. **Two predictions failed and are reported as such.** Rot didn't appear in none at ≤48k context. Buried hurt self_forget's cost, not its accuracy. Short's predicted overhead is real (+53%) but compact's is larger.
4. **Truncate's real weakness is information in the content that its stubs don't keep** (station IDs), more than unrefetchable output. Its context limit is also not enforced within a turn.
5. **Compact's failures are summaries that drop navigational state** (catalog URL, deploy data, the lifeboat aside). Its failure is "can't continue", not "answers wrong".

**Caveats:** one host (GenAI Studio, unknown quantization) and one model. Seeds aren't reproducible on this host. Each cell is 2 task variants × 3 seeds. The rot and exact designs leak information: file headers carry station IDs, and the phases rely on "same catalog". Both are kept as built, per the fixed-predictions rule.

**Next:**
- The cost-aware apply rule (confirm first), measured on horizon, where self_forget's batch applies cost the most.
- Ablations: forget summaries vs bare stubs, and ledger on/off, to see whether summaries are what save queue and exact.
- Optionally, a DeepInfra replication of the v2 suite. That's a paid run: one seed of all 4 strategies (48 runs) is about $2–4 (ideal-cache to no-cache prices from this matrix), so 3 seeds is about $6–11. Confirm before launching.

## Next: distraction suite (planned 2026-11-15, predictions fixed before any run)
**Why:** under the accuracy framing, the open question is whether a full context actually misleads the model. In suite v2 it didn't: every decoy shared exact words with the question (station IDs, issue numbers), and models find exact matches even in long contexts. Published degradation comes from (a) relevance that has to be inferred rather than string-matched (NoLiMa-style), (b) stale or conflicting information, and (c) plausible irrelevant material during reasoning.

**Two task families, each with an on/off knob that serves as a within-task control:**

| family | design | knob (control → treatment) | length knob |
|---|---|---|---|
| `latent` | Each phase names a new town; searching the town returns 6 resident bio pages. The question describes a life fact without naming it ("who had worked on the town's water supply?"), and the answer bio paraphrases it with no shared words ("spent a decade building the reservoir and pumping station"). Each phase also has a lexical decoy, a resident whose bio shares the question's words but not its meaning ("complained about the taste of the water supply"). | **cross-phase decoys** off → on. On: a resident of an *earlier* phase's town has a different paraphrase of the current phase's fact. The question restricts to the current town, so that resident is wrong, but a full context still holds a perfect semantic match | bios of ~25 vs ~50 filler sentences |
| `stale` | A platform posts change notices each day; each phase says "read today's notices" (search by day) and asks for the current value of one service setting. The asked setting is always last changed today. | **stale versions** 1 → 4. At 4, the same setting was set to other values on 3 earlier days, so a full context holds 3 outdated values for it | notices of short vs long rationale text |

- Rejected: **superseded instructions in user messages.** No strategy prunes user messages (only tool results are ever rewritten), so such a task can't separate the strategies.
- Both families: 8 phases, sized so that `none` stays under the 60k limit even at the long setting. Overflow must not be the failure mode here.

**Step 1, calibration (`none` only, free on GenAI Studio):** 2 families × knob off/on × short/long = 8 configs, variants 1–2 × seeds 0–1 (32 runs).
- Premise holds if `none` loses **≥ 10 points of phase accuracy** with the knob on vs off, at either length.
- If it doesn't, the distraction premise fails for Qwen 3.8 27B at ≤60k context. Record that, and repeat the calibration on a weaker or second-family model before building more tasks.
- Calibration varies the task, not the strategies, and the thresholds above are fixed now. Fixing a solvability bug is allowed; making the treatment harder until `none` fails is not, unless that's reported as a new configuration.

**Step 2, predictions for the strategy pilot** (only if the premise holds; knob on, setting chosen from step 1):

| family | none | self_forget | truncate | compact |
|---|---|---|---|---|
| latent (cross decoys) | loses: picks the earlier-town match | wins: earlier towns' bios were forgotten | wins when the decoy is more than 5 results back, loses otherwise | middle: summaries may carry the decoy resident's fact |
| stale (4 versions) | loses: picks an outdated value | wins if it forgets superseded notices; ties truncate | wins: old notices cleared | middle: a summary of "current values" helps, unless it records outdated ones |

self_forget is exposed to the misleading material like everyone else on the turn it reads it, so any gain has to come from what it forgets afterwards.

## Distraction calibration (2026-11-15) — `runs/distract-calib`, $0
Per-run data: `results/distract-calib.jsonl`; table: `results/distract-calib_report.txt`.
`purdue-qwen3.8-27b`, `none` only, temperature 0.7: 16 configs (`latent`/`stale` × knob off/on × short/long × variants 1–2) × seeds 0–1 = 32 runs. All completed, with no host errors.

| family | knob off, short | knob on, short | knob off, long | knob on, long | drop (on vs off) |
|---|---|---|---|---|---|
| latent (cross-phase decoys) | 32/32 | 32/32 | 32/32 | 32/32 | 0 points |
| stale (4 vs 1 versions) | 32/32 | 32/32 | 32/32 | 32/32 | 0 points |

- **Premise fails (pre-registered threshold: ≥10 points).** Qwen 3.8 27B answered all 256 phases correctly, with or without the treatment, at peak contexts of 13–50k tokens.
- **The treatment was present.** In latent-on runs, the earlier-town decoy was already in context before its question in 52 of 56 cases, and the agent read 41–48 of 48 bios per run. The stale-v4 runs read 42–43 of the 43 pages carrying asked-setting changes or day indexes (all of them in 7 of 8 runs), so the 3 outdated values were in context for nearly every question. The model saw the misleading material and wasn't misled.
- **Interpretation:** at ≤50k tokens, a 27B model with explicit scoping in the question ("only people of X count", "today's notices", "current") separates relevant from irrelevant reliably, even when relevance has to be inferred and the decoys are semantic matches. This adds to the suite v2 rot result. On this model and at these lengths, a full context costs money, not accuracy.
- **Next, per the plan:** repeat the same calibration (same tasks, knobs and threshold) on weaker models. GenAI Studio serves them for free, including `llama3.3:70b` (second family), `qwen3:8b`/`qwen3:14b` (weaker, same family) and `gemma3:27b`. Each needs a tool-calling smoke test first, as in phase 1.

## Model screening + gpt-oss calibration (2026-11-15) — `runs/distract-calib-gptoss`, $0
Per-run data: `results/distract-calib-gptoss.jsonl`; table: `results/distract-calib-gptoss_report.txt`.

**Screening weaker or second-family models on GenAI Studio.** Each model got a long-prompt probe (a code at the start of a 6–55k-token prompt, comparing the host's `prompt_tokens` with our count) and, where context was enough, one real task as a tool-calling smoke test:

| model | effective context on the host | tool calling | usable |
|---|---|---|---|
| `llama3.3:70b` | **~4k**: a 30.9k prompt arrived as 4,098 tokens; `options.num_ctx`, `num_ctx` and `max_context_length` were all ignored | — | no |
| `qwen3:8b` | ~32k: a 30k prompt was intact, 40k and 55k were cut to 16,386 | **fails**: called `FINAL` as a tool 63×, repeated one search 73×, 0/8 | no |
| `qwen3:14b`, `gemma3:27b` | ~8k | — | no |
| `qwen2.5:72b`, `llama3.1:70b-instruct-q4_K_M` | ~4k | — | no |
| `llama4:latest` | HTTP 400 | — | no |
| **`gpt-oss:120b`** | ≥55k (56.0k sent, 57.8k counted by the host) | works (2 errors in 63 calls on a smoke run, 7/8) | **yes** |

- Most GenAI Studio models are Ollama-served with a small default `num_ctx` and **truncate silently**: no error, just a model that can't see the start of the prompt. Any new backend needs the long-prompt probe before use.
- No model on the host is both weaker than Qwen 3.8 27B and usable. A weaker model means a paid backend: OpenRouter `or-llama3.3-70b`, already profiled.
- Client: all GenAI Studio backends now share one throttle (`rate_group="purdue"`), because the 20 requests/min limit is per user across models. The new 400 logging identified the remaining "400 with a message": the host's LiteLLM proxy wraps upstream failures as `400 {"detail": "litellm.InternalServerError: ... Unknown role: final"}`. Those are now retried.
- The `latent` "tiny" length (12-sentence bios, ~14k tokens of pages) was added for ~32k-window models. It's unused, because qwen3:8b failed tool calling.

**gpt-oss:120b calibration:** `none` only, the same 16 configs × seeds 0–1, 32 runs. One run crashed on the wrapped 500 above and passed on rerun after the client fix.

| family | knob off, short | knob on, short | knob off, long | knob on, long | drop |
|---|---|---|---|---|---|
| latent | 32/32 | 32/32 | 32/32 | 32/32 | 0 points |
| stale | 32/32 | 32/32 | 31/32 | 32/32 | −1.6 points (the miss was in the control) |

- **The premise fails on a second family too:** 255/256 phases. The only miss (stale-v1-long_2 s0, `510` for `1760`) had no stale versions in context.
- gpt-oss reads more selectively than Qwen (peaks of 11–44k; 54–77 turns per run). The earlier-town decoy was in context before its question in 33 of 56 cases, and it was never chosen.
- **Combined conclusion:** at ≤50k tokens, with explicit scoping in each question, neither Qwen 3.8 27B nor gpt-oss-120b is misled by inferred-relevance decoys or stale values. The hypothesis that pruning improves accuracy by avoiding distraction gets no support from strong models at these lengths. What remains to test is a weaker model (paid; Llama 3.3 70B about $1.50–2.50 for the 32 runs, price to be checked before launch), longer contexts (needs a host with a bigger window than 65k), or less explicit scoping in the questions (a new configuration, to be pre-registered).

## Next: implicit-scoping calibration (planned 2026-11-16, fixed before any run)
**Why:** in both calibrations every question stated its scope explicitly, often twice ("Among the people of X, … Only people of X count"; "the current value, after all changes so far"). Real tasks usually leave the scope implied by the flow of work. A full context should mislead most when the model has to infer which material the question is about.

**Knob `scope`: explicit (as before) → implicit.** It changes only the prompt wording; pages, answers and labels are identical.
- latent, explicit: "Among the people of {town}, who {fact}? Only people of {town} count."
- latent, implicit: "Next, look into {town}. Who {fact}?" The scope is implied by the instruction to look into the town. The earlier-town match is still graded wrong.
- stale, explicit: "Day {d}: read today's change notices (index: …). What is the current {key} of {service}, after all changes so far?"
- stale, implicit: "Day {d} notices: {index}. What's the {key} of {service}?" ("current", "after all changes so far" and "today's" are dropped.)

**Caveat, written down now:** the implicit latent question is literally satisfiable by the earlier-town resident. An answer naming them can be read as a defensible interpretation rather than distraction. So the comparison that counts is **on-implicit vs off-implicit**: in the off setting no such resident exists, so the wording alone can't explain a drop. Each wrong answer will also be classified (decoy pick / other).

**Calibration:** `purdue-qwen3.8-27b` (primary model), `none` only, implicit wording, the same 8 knob/length cells × variants 1–2 × seeds 0–1 = 32 runs.
- Threshold unchanged: **≥ 10 points** drop, on vs off, at either length, in either family.
- If met: replicate on `purdue-gpt-oss-120b`, then pilot all 4 strategies with the predictions from "Next: distraction suite".
- If not met: record it. The remaining options are paid (a weaker model, or contexts beyond 65k).

## Implicit-scoping calibration (2026-11-16) — `runs/distract-implicit`, $0
Per-run data: `results/distract-implicit.jsonl`; table: `results/distract-implicit_report.txt`.
`purdue-qwen3.8-27b`, `none` only, implicit wording, 8 cells × variants 1–2 × seeds 0–1 = 32 runs, all completed with no host errors.

| family | knob off, short | knob on, short | knob off, long | knob on, long | drop |
|---|---|---|---|---|---|
| latent (implicit) | 32/32 | 32/32 | 32/32 | 32/32 | 0 points |
| stale (implicit) | 32/32 | 32/32 | 32/32 | 32/32 | 0 points |

- **Threshold not met: 256/256, no misses at all.** So the miss classification planned for the latent caveat (decoy pick vs other) had nothing to classify.
- **The treatment was present:** the earlier-town match was in context before its question in 55 of 56 cases (41–48 of 48 bios read per run). The stale-v4 runs read 42–43 of the 43 pages carrying asked-setting changes or day indexes.
- Dropping the explicit scope ("only people of X count", "current, after all changes so far", "today's") changed nothing. Given "look into X. Who …?", Qwen answered from X every time, never naming the matching resident of an earlier town, though that resident was still in context.

**Where the distraction premise stands after three calibrations (none only, 96 runs, 767/768 phases):**

| calibration | model | wording | phases | drop on vs off |
|---|---|---|---|---|
| distract-calib | Qwen 3.8 27B | explicit | 256/256 | 0 |
| distract-calib-gptoss | gpt-oss-120b | explicit | 255/256 | 0 (the miss was a control) |
| distract-implicit | Qwen 3.8 27B | implicit | 256/256 | 0 |

- For strong models at ≤50k tokens, semantic decoys and stale values in context don't measurably cost accuracy, with or without explicit scoping. The accuracy case for self-pruning rests, so far, on the harness failures from suite v2 (overflow, unrefetchable output, lossy summaries), not on distraction.
- **Remaining tests of the premise are all paid or need a new host:** a weaker model with full context (OpenRouter `or-llama3.3-70b`, about $1.50–2.50 per 32-run calibration), or contexts beyond 65k (DeepInfra Qwen supports more; `--max-context` would have to rise, and total prompt tokens grow faster than linearly with context length, since every turn resends the whole context).
- A free alternative is to change what's measured rather than the model: distraction may show up in the **process** (extra turns, re-checks, hedged answers) before it shows up in accuracy. That can be read from the existing traces (e.g. turns and tokens, on vs off) at no cost.

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
