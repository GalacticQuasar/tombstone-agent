# Stale-task process analysis (strategy none)

> **Correction:** the "trace-the-notices habit" conclusion below is wrong: it counts any arrow. Counting answers with two
> or more arrows gives 0/112 in the v1 control, so the history listing is a response to outdated values. See PLAN.md.

## Method
Runs: stale-* tasks in distract-calib (Qwen explicit), distract-calib-gptoss (gpt-oss explicit), distract-implicit (Qwen implicit), 2 variants x 2 lengths x 2 seeds per calibration = 8 v4/v1 pairs each (24 pairs, 192 phase pairs; 168 for phases 1-7). Phase boundaries come from "phase" events; fetches are attributed to the preceding turn. Outdated values = earlier-day "new" values plus the "old" value on the phase's day, from v4 notice pages (expected value excluded), matched as whole numbers; the same set is used for v1. P-values are exact sign tests on per-phase paired differences (scipy missing, so no Wilcoxon). Phases within a run are not independent, so p-values are optimistic; many metrics were tested, so treat any single p with caution. Hedging = word hits from the given list in the final answer (mean count per answer).

Script: stale_process.py. Per-calibration tables are in the sections below.

## Accuracy (phases correct, mean of 8)

- qwen-explicit v4: 8.00/8 over 8 runs
- qwen-explicit v1: 8.00/8 over 8 runs
- gptoss-explicit v4: 8.00/8 over 8 runs
- gptoss-explicit v1: 7.88/8 over 8 runs
- qwen-implicit v4: 8.00/8 over 8 runs
- qwen-implicit v1: 8.00/8 over 8 runs

## Paired comparisons (v4 vs v1)

**pooled all calibrations / both lengths / phases 1-7**  (run pairs: 24)

| metric | v4 mean | v1 mean | diff | n | sign p | wilcoxon p |
|---|---|---|---|---|---|---|
| turns | 4.29 | 4.36 | -0.08 | 168 | 0.461 | nan |
| fetch | 5.74 | 5.90 | -0.16 | 168 | 0.775 | nan |
| refetch | 0.07 | 0.21 | -0.14 | 168 | 0.189 | nan |
| earlier | 3.20 | 3.34 | -0.14 | 168 | 1.000 | nan |
| compl | 896 | 841 | 55.30 | 168 | 0.000 | nan |
| anslen | 217 | 188 | 28.45 | 168 | 0.000 | nan |
| hedge | 0.14 | 0.99 | -0.85 | 168 | 0.000 | nan |
| od_final | 0.68 | 0.00 | 0.68 | 168 | 0.000 | nan |
| od_any | 0.68 | 0.00 | 0.68 | 168 | 0.000 | nan |

**pooled all calibrations / both lengths / all phases 0-7**  (run pairs: 24)

| metric | v4 mean | v1 mean | diff | n | sign p | wilcoxon p |
|---|---|---|---|---|---|---|
| turns | 4.42 | 4.53 | -0.11 | 192 | 0.888 | nan |
| fetch | 6.15 | 6.34 | -0.19 | 192 | 0.410 | nan |
| refetch | 0.06 | 0.22 | -0.16 | 192 | 0.064 | nan |
| earlier | 3.68 | 3.84 | -0.17 | 192 | 0.678 | nan |
| compl | 885 | 832 | 52.32 | 192 | 0.000 | nan |
| anslen | 213 | 184 | 28.98 | 192 | 0.000 | nan |
| hedge | 0.14 | 0.99 | -0.85 | 192 | 0.000 | nan |
| od_final | 0.68 | 0.00 | 0.68 | 192 | 0.000 | nan |
| od_any | 0.69 | 0.00 | 0.69 | 192 | 0.000 | nan |

**pooled all calibrations / both lengths / phase 0 only**  (run pairs: 24)

| metric | v4 mean | v1 mean | diff | n | sign p | wilcoxon p |
|---|---|---|---|---|---|---|
| turns | 5.33 | 5.71 | -0.38 | 24 | 0.125 | nan |
| fetch | 9.00 | 9.38 | -0.38 | 24 | 0.125 | nan |
| refetch | 0.00 | 0.25 | -0.25 | 24 | 0.250 | nan |
| earlier | 7.00 | 7.38 | -0.38 | 24 | 0.125 | nan |
| compl | 803 | 772 | 31.50 | 24 | 0.023 | nan |
| anslen | 186 | 153 | 32.75 | 24 | 0.049 | nan |
| hedge | 0.12 | 1.04 | -0.92 | 24 | 0.002 | nan |
| od_final | 0.71 | 0.00 | 0.71 | 24 | 0.000 | nan |
| od_any | 0.71 | 0.00 | 0.71 | 24 | 0.000 | nan |

**pooled all calibrations / short / phases 1-7**  (run pairs: 12)

| metric | v4 mean | v1 mean | diff | n | sign p | wilcoxon p |
|---|---|---|---|---|---|---|
| turns | 4.21 | 4.43 | -0.21 | 84 | 0.541 | nan |
| fetch | 5.69 | 5.88 | -0.19 | 84 | 0.458 | nan |
| refetch | 0.04 | 0.17 | -0.13 | 84 | 0.180 | nan |
| earlier | 3.15 | 3.31 | -0.15 | 84 | 0.701 | nan |
| compl | 837 | 854 | -16.48 | 84 | 0.230 | nan |
| anslen | 212 | 195 | 16.56 | 84 | 0.000 | nan |
| hedge | 0.26 | 0.83 | -0.57 | 84 | 0.000 | nan |
| od_final | 0.69 | 0.00 | 0.69 | 84 | 0.000 | nan |
| od_any | 0.70 | 0.00 | 0.70 | 84 | 0.000 | nan |

**pooled all calibrations / long / phases 1-7**  (run pairs: 12)

| metric | v4 mean | v1 mean | diff | n | sign p | wilcoxon p |
|---|---|---|---|---|---|---|
| turns | 4.36 | 4.30 | 0.06 | 84 | 0.052 | nan |
| fetch | 5.80 | 5.93 | -0.13 | 84 | 0.824 | nan |
| refetch | 0.11 | 0.26 | -0.15 | 84 | 0.774 | nan |
| earlier | 3.25 | 3.37 | -0.12 | 84 | 0.664 | nan |
| compl | 956 | 828 | 127 | 84 | 0.000 | nan |
| anslen | 222 | 182 | 40.33 | 84 | 0.000 | nan |
| hedge | 0.02 | 1.14 | -1.12 | 84 | 0.000 | nan |
| od_final | 0.67 | 0.00 | 0.67 | 84 | 0.000 | nan |
| od_any | 0.67 | 0.00 | 0.67 | 84 | 0.000 | nan |

**qwen-explicit / both lengths / phases 1-7**  (run pairs: 8)

| metric | v4 mean | v1 mean | diff | n | sign p | wilcoxon p |
|---|---|---|---|---|---|---|
| turns | 3.12 | 3.02 | 0.11 | 56 | 0.070 | nan |
| fetch | 5.84 | 5.84 | 0.00 | 56 | 1.000 | nan |
| refetch | 0.00 | 0.00 | 0.00 | 56 | 1.000 | nan |
| earlier | 3.27 | 3.27 | 0.00 | 56 | 1.000 | nan |
| compl | 736 | 647 | 88.25 | 56 | 0.141 | nan |
| anslen | 319 | 365 | -45.84 | 56 | 0.419 | nan |
| hedge | 0.00 | 1.50 | -1.50 | 56 | 0.000 | nan |
| od_final | 1.00 | 0.00 | 1.00 | 56 | 0.000 | nan |
| od_any | 1.00 | 0.00 | 1.00 | 56 | 0.000 | nan |

**qwen-explicit / both lengths / all phases 0-7**  (run pairs: 8)

| metric | v4 mean | v1 mean | diff | n | sign p | wilcoxon p |
|---|---|---|---|---|---|---|
| turns | 3.11 | 3.02 | 0.09 | 64 | 0.070 | nan |
| fetch | 6.23 | 6.23 | 0.00 | 64 | 1.000 | nan |
| refetch | 0.00 | 0.00 | 0.00 | 64 | 1.000 | nan |
| earlier | 3.73 | 3.73 | 0.00 | 64 | 1.000 | nan |
| compl | 721 | 635 | 86.22 | 64 | 0.033 | nan |
| anslen | 315 | 354 | -39.27 | 64 | 0.314 | nan |
| hedge | 0.03 | 1.52 | -1.48 | 64 | 0.000 | nan |
| od_final | 1.00 | 0.00 | 1.00 | 64 | 0.000 | nan |
| od_any | 1.00 | 0.00 | 1.00 | 64 | 0.000 | nan |

**qwen-explicit / both lengths / phase 0 only**  (run pairs: 8)

| metric | v4 mean | v1 mean | diff | n | sign p | wilcoxon p |
|---|---|---|---|---|---|---|
| turns | 3.00 | 3.00 | 0.00 | 8 | 1.000 | nan |
| fetch | 9.00 | 9.00 | 0.00 | 8 | 1.000 | nan |
| refetch | 0.00 | 0.00 | 0.00 | 8 | 1.000 | nan |
| earlier | 7.00 | 7.00 | 0.00 | 8 | 1.000 | nan |
| compl | 619 | 547 | 72.00 | 8 | 0.070 | nan |
| anslen | 284 | 277 | 6.75 | 8 | 0.727 | nan |
| hedge | 0.25 | 1.62 | -1.38 | 8 | 0.070 | nan |
| od_final | 1.00 | 0.00 | 1.00 | 8 | 0.008 | nan |
| od_any | 1.00 | 0.00 | 1.00 | 8 | 0.008 | nan |

**qwen-explicit / short / phases 1-7**  (run pairs: 4)

| metric | v4 mean | v1 mean | diff | n | sign p | wilcoxon p |
|---|---|---|---|---|---|---|
| turns | 3.11 | 3.04 | 0.07 | 28 | 0.625 | nan |
| fetch | 5.82 | 5.82 | 0.00 | 28 | 1.000 | nan |
| refetch | 0.00 | 0.00 | 0.00 | 28 | 1.000 | nan |
| earlier | 3.25 | 3.25 | 0.00 | 28 | 1.000 | nan |
| compl | 710 | 640 | 69.36 | 28 | 0.851 | nan |
| anslen | 329 | 390 | -60.79 | 28 | 0.701 | nan |
| hedge | 0.00 | 1.21 | -1.21 | 28 | 0.000 | nan |
| od_final | 1.00 | 0.00 | 1.00 | 28 | 0.000 | nan |
| od_any | 1.00 | 0.00 | 1.00 | 28 | 0.000 | nan |

**qwen-explicit / long / phases 1-7**  (run pairs: 4)

| metric | v4 mean | v1 mean | diff | n | sign p | wilcoxon p |
|---|---|---|---|---|---|---|
| turns | 3.14 | 3.00 | 0.14 | 28 | 0.125 | nan |
| fetch | 5.86 | 5.86 | 0.00 | 28 | 1.000 | nan |
| refetch | 0.00 | 0.00 | 0.00 | 28 | 1.000 | nan |
| earlier | 3.29 | 3.29 | 0.00 | 28 | 1.000 | nan |
| compl | 761 | 654 | 107 | 28 | 0.087 | nan |
| anslen | 310 | 341 | -30.89 | 28 | 0.572 | nan |
| hedge | 0.00 | 1.79 | -1.79 | 28 | 0.000 | nan |
| od_final | 1.00 | 0.00 | 1.00 | 28 | 0.000 | nan |
| od_any | 1.00 | 0.00 | 1.00 | 28 | 0.000 | nan |

**gptoss-explicit / both lengths / phases 1-7**  (run pairs: 8)

| metric | v4 mean | v1 mean | diff | n | sign p | wilcoxon p |
|---|---|---|---|---|---|---|
| turns | 6.59 | 7.07 | -0.48 | 56 | 0.200 | nan |
| fetch | 5.59 | 6.05 | -0.46 | 56 | 0.265 | nan |
| refetch | 0.21 | 0.45 | -0.23 | 56 | 0.359 | nan |
| earlier | 3.11 | 3.50 | -0.39 | 56 | 0.572 | nan |
| compl | 1250 | 1401 | -152 | 56 | 0.141 | nan |
| anslen | 47.09 | 11.54 | 35.55 | 56 | 0.092 | nan |
| hedge | 0.27 | 0.00 | 0.27 | 56 | 0.500 | nan |
| od_final | 0.04 | 0.00 | 0.04 | 56 | 0.500 | nan |
| od_any | 0.05 | 0.00 | 0.05 | 56 | 0.250 | nan |

**gptoss-explicit / both lengths / all phases 0-7**  (run pairs: 8)

| metric | v4 mean | v1 mean | diff | n | sign p | wilcoxon p |
|---|---|---|---|---|---|---|
| turns | 7.02 | 7.58 | -0.56 | 64 | 0.058 | nan |
| fetch | 6.02 | 6.56 | -0.55 | 64 | 0.080 | nan |
| refetch | 0.19 | 0.48 | -0.30 | 64 | 0.134 | nan |
| earlier | 3.59 | 4.08 | -0.48 | 64 | 0.215 | nan |
| compl | 1246 | 1389 | -143 | 64 | 0.103 | nan |
| anslen | 46.56 | 11.39 | 35.17 | 64 | 0.057 | nan |
| hedge | 0.23 | 0.00 | 0.23 | 64 | 0.500 | nan |
| od_final | 0.05 | 0.00 | 0.05 | 64 | 0.250 | nan |
| od_any | 0.06 | 0.00 | 0.06 | 64 | 0.125 | nan |

**gptoss-explicit / both lengths / phase 0 only**  (run pairs: 8)

| metric | v4 mean | v1 mean | diff | n | sign p | wilcoxon p |
|---|---|---|---|---|---|---|
| turns | 10.00 | 11.12 | -1.12 | 8 | 0.125 | nan |
| fetch | 9.00 | 10.12 | -1.12 | 8 | 0.125 | nan |
| refetch | 0.00 | 0.75 | -0.75 | 8 | 0.250 | nan |
| earlier | 7.00 | 8.12 | -1.12 | 8 | 0.125 | nan |
| compl | 1222 | 1302 | -80.00 | 8 | 0.727 | nan |
| anslen | 42.88 | 10.38 | 32.50 | 8 | 1.000 | nan |
| hedge | 0.00 | 0.00 | 0.00 | 8 | 1.000 | nan |
| od_final | 0.12 | 0.00 | 0.12 | 8 | 1.000 | nan |
| od_any | 0.12 | 0.00 | 0.12 | 8 | 1.000 | nan |

**gptoss-explicit / short / phases 1-7**  (run pairs: 4)

| metric | v4 mean | v1 mean | diff | n | sign p | wilcoxon p |
|---|---|---|---|---|---|---|
| turns | 6.43 | 7.25 | -0.82 | 28 | 0.049 | nan |
| fetch | 5.43 | 6.25 | -0.82 | 28 | 0.049 | nan |
| refetch | 0.11 | 0.50 | -0.39 | 28 | 0.180 | nan |
| earlier | 2.96 | 3.68 | -0.71 | 28 | 0.118 | nan |
| compl | 1172 | 1459 | -287 | 28 | 0.087 | nan |
| anslen | 82.43 | 12.11 | 70.32 | 28 | 0.289 | nan |
| hedge | 0.54 | 0.00 | 0.54 | 28 | 0.500 | nan |
| od_final | 0.07 | 0.00 | 0.07 | 28 | 0.500 | nan |
| od_any | 0.11 | 0.00 | 0.11 | 28 | 0.250 | nan |

**gptoss-explicit / long / phases 1-7**  (run pairs: 4)

| metric | v4 mean | v1 mean | diff | n | sign p | wilcoxon p |
|---|---|---|---|---|---|---|
| turns | 6.75 | 6.89 | -0.14 | 28 | 1.000 | nan |
| fetch | 5.75 | 5.86 | -0.11 | 28 | 0.774 | nan |
| refetch | 0.32 | 0.39 | -0.07 | 28 | 1.000 | nan |
| earlier | 3.25 | 3.32 | -0.07 | 28 | 0.581 | nan |
| compl | 1327 | 1344 | -17.11 | 28 | 0.851 | nan |
| anslen | 11.75 | 10.96 | 0.79 | 28 | 0.375 | nan |
| hedge | 0.00 | 0.00 | 0.00 | 28 | 1.000 | nan |
| od_final | 0.00 | 0.00 | 0.00 | 28 | 1.000 | nan |
| od_any | 0.00 | 0.00 | 0.00 | 28 | 1.000 | nan |

**qwen-implicit / both lengths / phases 1-7**  (run pairs: 8)

| metric | v4 mean | v1 mean | diff | n | sign p | wilcoxon p |
|---|---|---|---|---|---|---|
| turns | 3.14 | 3.00 | 0.14 | 56 | 0.008 | nan |
| fetch | 5.80 | 5.82 | -0.02 | 56 | 0.454 | nan |
| refetch | 0.00 | 0.20 | -0.20 | 56 | 0.500 | nan |
| earlier | 3.23 | 3.25 | -0.02 | 56 | 0.454 | nan |
| compl | 704 | 474 | 230 | 56 | 0.000 | nan |
| anslen | 284 | 188 | 95.62 | 56 | 0.000 | nan |
| hedge | 0.16 | 1.46 | -1.30 | 56 | 0.000 | nan |
| od_final | 1.00 | 0.00 | 1.00 | 56 | 0.000 | nan |
| od_any | 1.00 | 0.00 | 1.00 | 56 | 0.000 | nan |

**qwen-implicit / both lengths / all phases 0-7**  (run pairs: 8)

| metric | v4 mean | v1 mean | diff | n | sign p | wilcoxon p |
|---|---|---|---|---|---|---|
| turns | 3.12 | 3.00 | 0.12 | 64 | 0.008 | nan |
| fetch | 6.20 | 6.22 | -0.02 | 64 | 0.454 | nan |
| refetch | 0.00 | 0.17 | -0.17 | 64 | 0.500 | nan |
| earlier | 3.70 | 3.72 | -0.02 | 64 | 0.454 | nan |
| compl | 687 | 473 | 214 | 64 | 0.000 | nan |
| anslen | 277 | 186 | 91.05 | 64 | 0.000 | nan |
| hedge | 0.16 | 1.47 | -1.31 | 64 | 0.000 | nan |
| od_final | 1.00 | 0.00 | 1.00 | 64 | 0.000 | nan |
| od_any | 1.00 | 0.00 | 1.00 | 64 | 0.000 | nan |

**qwen-implicit / both lengths / phase 0 only**  (run pairs: 8)

| metric | v4 mean | v1 mean | diff | n | sign p | wilcoxon p |
|---|---|---|---|---|---|---|
| turns | 3.00 | 3.00 | 0.00 | 8 | 1.000 | nan |
| fetch | 9.00 | 9.00 | 0.00 | 8 | 1.000 | nan |
| refetch | 0.00 | 0.00 | 0.00 | 8 | 1.000 | nan |
| earlier | 7.00 | 7.00 | 0.00 | 8 | 1.000 | nan |
| compl | 569 | 466 | 102 | 8 | 0.008 | nan |
| anslen | 230 | 171 | 59.00 | 8 | 0.070 | nan |
| hedge | 0.12 | 1.50 | -1.38 | 8 | 0.031 | nan |
| od_final | 1.00 | 0.00 | 1.00 | 8 | 0.008 | nan |
| od_any | 1.00 | 0.00 | 1.00 | 8 | 0.008 | nan |

**qwen-implicit / short / phases 1-7**  (run pairs: 4)

| metric | v4 mean | v1 mean | diff | n | sign p | wilcoxon p |
|---|---|---|---|---|---|---|
| turns | 3.11 | 3.00 | 0.11 | 28 | 0.250 | nan |
| fetch | 5.82 | 5.57 | 0.25 | 28 | 0.289 | nan |
| refetch | 0.00 | 0.00 | 0.00 | 28 | 1.000 | nan |
| earlier | 3.25 | 3.00 | 0.25 | 28 | 0.289 | nan |
| compl | 629 | 461 | 168 | 28 | 0.000 | nan |
| anslen | 223 | 183 | 40.14 | 28 | 0.000 | nan |
| hedge | 0.25 | 1.29 | -1.04 | 28 | 0.000 | nan |
| od_final | 1.00 | 0.00 | 1.00 | 28 | 0.000 | nan |
| od_any | 1.00 | 0.00 | 1.00 | 28 | 0.000 | nan |

**qwen-implicit / long / phases 1-7**  (run pairs: 4)

| metric | v4 mean | v1 mean | diff | n | sign p | wilcoxon p |
|---|---|---|---|---|---|---|
| turns | 3.18 | 3.00 | 0.18 | 28 | 0.062 | nan |
| fetch | 5.79 | 6.07 | -0.29 | 28 | 1.000 | nan |
| refetch | 0.00 | 0.39 | -0.39 | 28 | 0.500 | nan |
| earlier | 3.21 | 3.50 | -0.29 | 28 | 1.000 | nan |
| compl | 779 | 487 | 291 | 28 | 0.000 | nan |
| anslen | 344 | 193 | 151 | 28 | 0.000 | nan |
| hedge | 0.07 | 1.64 | -1.57 | 28 | 0.000 | nan |
| od_final | 1.00 | 0.00 | 1.00 | 28 | 0.000 | nan |
| od_any | 1.00 | 0.00 | 1.00 | 28 | 0.000 | nan |

## Hedging marker rates in final answers (phases 1-7, pooled; share of answers containing marker)

| marker | v4 | v1 |
|---|---|---|
| however | 0.006 | 0.000 |
| but | 0.012 | 0.000 |
| although | 0.000 | 0.000 |
| note | 0.000 | 0.000 |
| earlier | 0.012 | 0.149 |
| previous | 0.000 | 0.000 |
| was | 0.012 | 0.244 |
| changed | 0.048 | 0.220 |
| from | 0.006 | 0.304 |
| superseded | 0.000 | 0.000 |
| conflict | 0.000 | 0.000 |
| unclear | 0.000 | 0.000 |
| possibly | 0.006 | 0.000 |
| might | 0.000 | 0.000 |

## Chance-collision check

Across 8 distinct v4 tasks: 80/192 (42%) (phase, outdated value) pairs also appear as a whole number somewhere else in the notice corpus (other settings' lines or rationale text; ignores 'Effective: day N' text). So a chance mention of an outdated value in an answer is possible but mostly requires the model to be quoting the asked setting's history.

v1 rows give the empirical chance baseline: od_final/od_any in the v1 columns above (in v1 the 'outdated' numbers are never shown, except possibly the pre-change value on today's line when it coincides).

## Excerpts: v4 final answers (phases 1-7) mentioning an outdated value

114 of 168 v4 phase-final answers (phases 1-7) mention an outdated value.

- qwen-explicit long var1 s0 phase 4 (search / replica count; outdated [22, 23, 39]):
  >   Tracing the replica count of search across all change notices:  - Day 1 (1-4): 28 → 22 - Day 3 (3-5): 22 → 23 - Day 4 (4-3): 23 → 39 - Day 8 (8-1): 39 → 48  (Other search notices on days 2, 6, 7, and 8-2/8-4 do not touch replica count.)  FINAL: 48
- qwen-implicit long var1 s0 phase 1 (billing-api / rate limit (requests/min); outdated [1080, 1390, 1410]):
  > ll change notices:  1. **Day 1 (1-2):** rate limit: 1960 → **1410** 2. **Day 2 (2-2):** rate limit: 1410 → **1390** 3. **Day 3 (3-2):** rate limit: 1390 → **1080** 4. **Day 3 (3-6):** no rate limit change 5. **Day 4 (4-4):** no rate limit change 6. **Day 5 (5-1):** rate limit: 1080 → **1130**  The current rate limit for billing-api after all changes through day 5 is 1130 requests/min.  FINAL: 1130
- qwen-implicit long var2 s1 phase 2 (auth / max connections; outdated [510, 540, 900]):
  >   Tracing the max connections of auth across all change notices:  - **Day 2 (2-3-auth):** 40 → 900 - **Day 3 (3-3-auth):** 900 → 540 - **Day 5 (5-2-auth):** 540 → 510 - **Day 6 (6-1-auth):** 510 → 260 - **Day 6 (6-2-auth):** no max connections change (timeout, retry budget, rate limit only)  After the day 6 changes, the max connections of auth is 260.  FINAL: 260
- qwen-implicit long var2 s0 phase 3 (auth / rate limit (requests/min); outdated [400, 1150, 1230]):
  >   Tracking the auth rate limit (requests/min) across days: - Day 2 (2-4): 820 → 1150 - Day 5 (5-3): 1150 → 400 - Day 6 (6-2): 400 → 1230 - Day 7 (7-1): 1230 → 510  The current rate limit is 510 requests/min.  FINAL: 510

## Extra: answers enumerating history with arrows (phases 1-7)

| calibration | v4 | v1 |
|---|---|---|
| qwen-explicit | 56/56 | 49/56 |
| gptoss-explicit | 2/56 | 0/56 |
| qwen-implicit | 56/56 | 47/56 |

## Conclusions
- Accuracy is ceiling in both arms (v4 and v1 8/8 for Qwen; gpt-oss 8.00 v4 vs 7.88 v1), so any signal is in process only.
- Qwen (explicit and implicit) writes out the whole value history of the asked setting in every v4 final answer (56/56 in each calibration: "Day 1: 28 -> 22, Day 3: 22 -> 23 ... FINAL: 48") and reasons correctly. Mentioning outdated values is therefore explicit bookkeeping, not confusion. It also enumerates arrows in ~85-88% of v1 answers (a single change), so this is a trace-the-notices habit, not a response to stale material.
- Qwen v4 produces longer answers and more completion tokens (explicit +88 tokens/phase, not significant; implicit +230 tokens/phase and +96 chars, sign p < 0.001) simply because there are more changes to list. Fetch counts, re-fetches and earlier-day fetches are essentially identical between v4 and v1 (diff about 0, p about 1). No sign of re-reading or double-checking.
- The hedging markers show no hedging in v4 (0.00-0.16 hits/answer). v1 scores higher (about 1.5) only because "from", "was", "earlier" appear in descriptions like "notices from days 1-4"; the marker list is confounded by that and says nothing about uncertainty.
- gpt-oss: no clear process signal. Outdated values are mentioned in 4% of v4 final answers (none at all in the long tasks); answers are mostly a bare FINAL line (about 10-45 chars). v4 shows slightly fewer turns/fetches than v1 (short: -0.8 turns, sign p 0.049; not robust across lengths), which is the opposite of a distraction effect and would not survive multiple-comparison correction.
- Overall: no evidence that stale values degrade or visibly disturb the agent's process; the visible effect is just longer enumeration in Qwen. Caveats: n = 8 run pairs per calibration, reasoning tokens of gpt-oss are not logged, and 42% of outdated values also occur as numbers elsewhere in the corpus (chance mentions are possible, but v1 shows 0 mentions so false matches are rare in practice).
