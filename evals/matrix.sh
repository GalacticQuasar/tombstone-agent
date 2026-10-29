#!/usr/bin/env bash
# Run the full matrix: tasks × strategies × seeds, N runs in parallel.
#   evals/matrix.sh runs/matrix or-qwen3.8-27b 0.7
set -u
out=${1:-runs/matrix}; backend=${2:-or-qwen3.8-27b}; temp=${3:-0.7}; jobs=${JOBS:-8}
tasks="dossier_1 dossier_2 chain_1 chain_2 repo_1 repo_2"
strategies="none self_forget truncate compact"
seeds="0 1 2"
mkdir -p "$out/logs"
for t in $tasks; do for s in $strategies; do for seed in $seeds; do echo "$t $s $seed"; done; done; done |
  xargs -P "$jobs" -L 1 bash -c '
    log="'"$out"'/logs/$0.$1.s$2"
    uv run python -m evals.run --task "$0" --strategy "$1" --seed "$2" --backend '"$backend"' \
      --temperature '"$temp"' --runs-dir '"$out"' > "$log.out" 2> "$log.err" \
      && echo "ok   $0 $1 s$2" || echo "FAIL $0 $1 s$2"'
