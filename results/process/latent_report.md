# Latent-task process analysis (strategy none)

## Method

Per run, phases 1-7 (phase 0 has no cross decoy) are delimited by the trace `phase` events (phase k = turns after the turn that answered k-1 up to the turn answering k). Metrics: turns, web_fetch/web_search counts, re-fetches of URLs fetched earlier in the run, completion tokens, final-answer length, hedge-word count in final answer, `dec_ment` = cross-decoy resident's full name appears in any assistant content in the phase (on-task: the cross-decoy resident; off-task: the same slot resident, baseline), `dec_final` = name in final answer, `lex_final` = lexical-decoy resident name in final answer. Each on-run is paired with the off-run of the same calibration/length/scope/variant/seed; the unit is the phase (phases within a run are not independent, so p-values are optimistic). p = exact two-sided sign test on nonzero per-phase differences; no multiple-comparison correction (10 metrics x many strata). Runs with duplicate dirs: latest kept. Incomplete runs contribute only phases they finished (a phase is included only if the next phase event or the run end exists).

## Run pairs and accuracy

| calib | length | run pairs | phase-pairs | on acc | off acc |
|---|---|---|---|---|---|
| gptoss-explicit | long | 4 | 28 | 1.000 | 1.000 |
| gptoss-explicit | short | 4 | 28 | 1.000 | 1.000 |
| qwen-explicit | long | 4 | 28 | 1.000 | 1.000 |
| qwen-explicit | short | 4 | 28 | 1.000 | 1.000 |
| qwen-implicit | long | 4 | 28 | 1.000 | 1.000 |
| qwen-implicit | short | 4 | 28 | 1.000 | 1.000 |

## Tables per calibration and length

### gptoss-explicit / long  (n phase-pairs = 28)

| metric | on | off | diff (on-off) | sign-test p (n nonzero) |
|---|---|---|---|---|
| turns | 8.07 | 8.86 | -0.79 | 1.000 (23) |
| fetch | 4.86 | 5.29 | -0.43 | 0.824 (20) |
| search | 1.86 | 2.29 | -0.43 | 0.383 (21) |
| refetch | 0.11 | 0.43 | -0.32 | 0.375 (5) |
| comp | 828.64 | 889.00 | -60.36 | 0.851 (28) |
| anslen | 21.82 | 21.11 | +0.71 | 1.000 (2) |
| hedge | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| dec_ment | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| dec_final | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| lex_final | 0.00 | 0.00 | +0.00 | 1.000 (0) |

### gptoss-explicit / short  (n phase-pairs = 28)

| metric | on | off | diff (on-off) | sign-test p (n nonzero) |
|---|---|---|---|---|
| turns | 7.61 | 7.71 | -0.11 | 0.481 (18) |
| fetch | 4.79 | 4.64 | +0.14 | 1.000 (13) |
| search | 1.75 | 2.00 | -0.25 | 0.109 (10) |
| refetch | 0.04 | 0.00 | +0.04 | 1.000 (1) |
| comp | 687.86 | 720.36 | -32.50 | 0.572 (28) |
| anslen | 21.14 | 42.64 | -21.50 | 0.625 (4) |
| hedge | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| dec_ment | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| dec_final | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| lex_final | 0.00 | 0.00 | +0.00 | 1.000 (0) |

### qwen-explicit / long  (n phase-pairs = 28)

| metric | on | off | diff (on-off) | sign-test p (n nonzero) |
|---|---|---|---|---|
| turns | 3.43 | 3.54 | -0.11 | 0.581 (13) |
| fetch | 5.75 | 5.82 | -0.07 | 1.000 (3) |
| search | 1.75 | 1.93 | -0.18 | 0.238 (18) |
| refetch | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| comp | 433.43 | 483.14 | -49.71 | 0.036 (28) |
| anslen | 236.46 | 265.14 | -28.68 | 0.185 (28) |
| hedge | 0.61 | 0.25 | +0.36 | 0.039 (9) |
| dec_ment | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| dec_final | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| lex_final | 0.93 | 0.89 | +0.04 | 1.000 (1) |

### qwen-explicit / short  (n phase-pairs = 28)

| metric | on | off | diff (on-off) | sign-test p (n nonzero) |
|---|---|---|---|---|
| turns | 3.25 | 3.14 | +0.11 | 1.000 (5) |
| fetch | 5.86 | 5.93 | -0.07 | 0.500 (2) |
| search | 1.89 | 1.54 | +0.36 | 0.289 (8) |
| refetch | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| comp | 433.64 | 422.82 | +10.82 | 1.000 (27) |
| anslen | 214.57 | 232.46 | -17.89 | 0.013 (28) |
| hedge | 0.32 | 0.68 | -0.36 | 0.006 (12) |
| dec_ment | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| dec_final | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| lex_final | 0.96 | 0.89 | +0.07 | 0.500 (2) |

### qwen-implicit / long  (n phase-pairs = 28)

| metric | on | off | diff (on-off) | sign-test p (n nonzero) |
|---|---|---|---|---|
| turns | 3.36 | 3.18 | +0.18 | 0.146 (12) |
| fetch | 6.00 | 5.64 | +0.36 | 0.125 (4) |
| search | 1.36 | 1.18 | +0.18 | 0.267 (13) |
| refetch | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| comp | 448.96 | 394.29 | +54.68 | 0.001 (28) |
| anslen | 255.96 | 207.96 | +48.00 | 0.851 (28) |
| hedge | 0.43 | 0.32 | +0.11 | 0.727 (8) |
| dec_ment | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| dec_final | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| lex_final | 0.61 | 0.68 | -0.07 | 0.791 (14) |

### qwen-implicit / short  (n phase-pairs = 28)

| metric | on | off | diff (on-off) | sign-test p (n nonzero) |
|---|---|---|---|---|
| turns | 3.71 | 3.14 | +0.57 | 0.004 (9) |
| fetch | 5.61 | 5.96 | -0.36 | 0.219 (6) |
| search | 1.93 | 1.36 | +0.57 | 0.143 (17) |
| refetch | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| comp | 430.32 | 429.93 | +0.39 | 0.851 (28) |
| anslen | 190.54 | 197.32 | -6.79 | 0.345 (28) |
| hedge | 0.54 | 0.57 | -0.04 | 1.000 (11) |
| dec_ment | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| dec_final | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| lex_final | 0.46 | 0.39 | +0.07 | 0.791 (14) |

### qwen-explicit / both lengths  (n phase-pairs = 56)

| metric | on | off | diff (on-off) | sign-test p (n nonzero) |
|---|---|---|---|---|
| turns | 3.34 | 3.34 | +0.00 | 0.815 (18) |
| fetch | 5.80 | 5.88 | -0.07 | 0.375 (5) |
| search | 1.82 | 1.73 | +0.09 | 0.845 (26) |
| refetch | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| comp | 433.54 | 452.98 | -19.45 | 0.105 (55) |
| anslen | 225.52 | 248.80 | -23.29 | 0.005 (56) |
| hedge | 0.46 | 0.46 | +0.00 | 0.664 (21) |
| dec_ment | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| dec_final | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| lex_final | 0.95 | 0.89 | +0.05 | 0.250 (3) |

### gptoss-explicit / both lengths  (n phase-pairs = 56)

| metric | on | off | diff (on-off) | sign-test p (n nonzero) |
|---|---|---|---|---|
| turns | 7.84 | 8.29 | -0.45 | 0.533 (41) |
| fetch | 4.82 | 4.96 | -0.14 | 0.728 (33) |
| search | 1.80 | 2.14 | -0.34 | 0.071 (31) |
| refetch | 0.07 | 0.21 | -0.14 | 0.688 (6) |
| comp | 758.25 | 804.68 | -46.43 | 0.894 (56) |
| anslen | 21.48 | 31.88 | -10.39 | 0.688 (6) |
| hedge | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| dec_ment | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| dec_final | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| lex_final | 0.00 | 0.00 | +0.00 | 1.000 (0) |

### qwen-implicit / both lengths  (n phase-pairs = 56)

| metric | on | off | diff (on-off) | sign-test p (n nonzero) |
|---|---|---|---|---|
| turns | 3.54 | 3.16 | +0.38 | 0.001 (21) |
| fetch | 5.80 | 5.80 | +0.00 | 1.000 (10) |
| search | 1.64 | 1.27 | +0.38 | 0.043 (30) |
| refetch | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| comp | 439.64 | 412.11 | +27.54 | 0.044 (56) |
| anslen | 223.25 | 202.64 | +20.61 | 0.689 (56) |
| hedge | 0.48 | 0.45 | +0.04 | 0.648 (19) |
| dec_ment | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| dec_final | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| lex_final | 0.54 | 0.54 | +0.00 | 1.000 (28) |

### POOLED all calibrations and lengths  (n phase-pairs = 168)

| metric | on | off | diff (on-off) | sign-test p (n nonzero) |
|---|---|---|---|---|
| turns | 4.90 | 4.93 | -0.02 | 0.434 (80) |
| fetch | 5.48 | 5.55 | -0.07 | 0.471 (48) |
| search | 1.76 | 1.71 | +0.04 | 1.000 (87) |
| refetch | 0.02 | 0.07 | -0.05 | 0.688 (6) |
| comp | 543.81 | 556.59 | -12.78 | 1.000 (167) |
| anslen | 156.75 | 161.11 | -4.36 | 0.013 (118) |
| hedge | 0.32 | 0.30 | +0.01 | 1.000 (40) |
| dec_ment | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| dec_final | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| lex_final | 0.49 | 0.48 | +0.02 | 0.720 (31) |

### POOLED, Qwen only (explicit + implicit)  (n phase-pairs = 112)

| metric | on | off | diff (on-off) | sign-test p (n nonzero) |
|---|---|---|---|---|
| turns | 3.44 | 3.25 | +0.19 | 0.053 (39) |
| fetch | 5.80 | 5.84 | -0.04 | 0.607 (15) |
| search | 1.73 | 1.50 | +0.23 | 0.229 (56) |
| refetch | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| comp | 436.59 | 432.54 | +4.04 | 0.850 (111) |
| anslen | 224.38 | 225.72 | -1.34 | 0.018 (112) |
| hedge | 0.47 | 0.46 | +0.02 | 1.000 (40) |
| dec_ment | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| dec_final | 0.00 | 0.00 | +0.00 | 1.000 (0) |
| lex_final | 0.74 | 0.71 | +0.03 | 0.720 (31) |

## Decoy-name mention counts (phases)

| calib | length | on mentions | off mentions | on in final | off in final | phase-pairs |
|---|---|---|---|---|---|---|
| gptoss-explicit | long | 0 | 0 | 0 | 0 | 28 |
| gptoss-explicit | short | 0 | 0 | 0 | 0 | 28 |
| qwen-explicit | long | 0 | 0 | 0 | 0 | 28 |
| qwen-explicit | short | 0 | 0 | 0 | 0 | 28 |
| qwen-implicit | long | 0 | 0 | 0 | 0 | 28 |
| qwen-implicit | short | 0 | 0 | 0 | 0 | 28 |
| ALL | | 0 | 0 | 0 | 0 | 168 |

## Excerpts (on-run phases where decoy name is mentioned)

(no on-run phase mentions the decoy name)

Sanity check: name extraction verified on latent-on-short_1 (cross decoys e.g. Sevrin Gundwick for phase 1, Quentin Zarwick for phase 2; expected answers match the answer residents, and expected names do appear in the traces). The decoy names simply never appear in assistant content. Typical Qwen final answer (phase 1, on-short_1 s0): `Anselm Karnis of Hiswick "met a rival with pistols at dawn on the common" ...` -- it quotes only the matching sentence of the answer page and never discusses other candidates. gpt-oss final answers are essentially just `FINAL: <name>` (~21 chars), so hedging/mention metrics are uninformative there.

## Conclusions

- No decoy signal in the process: the cross-decoy resident's name was never mentioned in any assistant content (0/168 phase-pairs on, 0/168 off), not even in tool-call turns, so there is no visible "considered and rejected" behaviour. There are no excerpts to show.
- Hedging, re-fetches (0.02 vs 0.07, almost all zero), final-answer lexical-decoy mentions, fetch counts: no on/off difference.
- Isolated nominal p<0.05 results go in opposite directions (Qwen explicit/short: shorter answers and less hedging with decoys; implicit/short: +0.57 turns, p=.004; implicit/both: +27 completion tokens). With ~60 tests, 8 phase-pairs per run not independent, and n=4 run pairs per cell, these are consistent with chance; no consistent direction across explicit/implicit/gpt-oss.
- Weak hint only: Qwen implicit wording shows slightly more turns/searches with the decoy (+0.38 turns, p=.001 uncorrected; +0.38 searches, p=.04), not replicated in explicit wording (0.00 turns); treat as a hypothesis for more seeds.
- gpt-oss outputs are too terse (no reasoning in content) for a content-based process probe; reasoning tokens are not visible in these traces.
- Overall: accuracy is 100% and process is indistinguishable on/off at this n.
