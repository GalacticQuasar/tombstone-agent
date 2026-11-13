#!/usr/bin/env bash
# Run a matrix: tasks × strategies × seeds, N runs in parallel.
#   evals/matrix.sh runs/matrix or-qwen3.8-27b 0.7
#   TASKS="rot_1 queue_1" SEEDS="0 1 2 3 4" evals/matrix.sh runs/v2 purdue-qwen3.8-27b 0.7
# Env: JOBS (parallel runs, default 8), TASKS (default: the original 6-task suite),
#      STRATEGIES (default: all 4), SEEDS (default "0 1 2"), EXTRA (more evals.run flags).
#
# Resumable: a combination that already has a finished run (summary.json) in <out> is skipped,
# and unfinished run dirs (crashed or interrupted) are moved to <out>-unfinished/ first.
# Rerun the same command after an interruption. Don't run two instances on the same <out>:
# the second would move the first's in-progress runs aside.
set -u
out=${1:-runs/matrix}; backend=${2:-or-qwen3.8-27b}; temp=${3:-0.7}; jobs=${JOBS:-8}
tasks=${TASKS:-"dossier_1 dossier_2 chain_1 chain_2 repo_1 repo_2"}
strategies=${STRATEGIES:-"none self_forget truncate compact"}
seeds=${SEEDS:-"0 1 2"}
extra=${EXTRA:-}
mkdir -p "$out/logs"

# Run dirs are named <timestamp>_<task>_<strategy>_<backend>_s<seed>.
moved=0
for d in "$out"/*_s*/; do
  [ -d "$d" ] && [ ! -f "$d/summary.json" ] || continue
  mkdir -p "$out-unfinished" && mv "$d" "$out-unfinished/" && moved=$((moved + 1))
done
[ "$moved" -gt 0 ] && echo "moved $moved unfinished run(s) to $out-unfinished/"

todo=(); skipped=0
for t in $tasks; do for s in $strategies; do for seed in $seeds; do
  if compgen -G "$out/*_${t}_${s}_${backend}_s${seed}/summary.json" > /dev/null; then
    skipped=$((skipped + 1))
  else
    todo+=("$t $s $seed")
  fi
done; done; done
echo "skipping $skipped finished, running ${#todo[@]}"
[ "${#todo[@]}" -eq 0 ] && exit 0

printf '%s\n' "${todo[@]}" |
  xargs -P "$jobs" -L 1 bash -c '
    log="'"$out"'/logs/$0.$1.s$2"
    uv run python -m evals.run --task "$0" --strategy "$1" --seed "$2" --backend '"$backend"' \
      --temperature '"$temp"' --runs-dir '"$out"' '"$extra"' > "$log.out" 2> "$log.err" \
      && echo "ok   $0 $1 s$2" || echo "FAIL $0 $1 s$2"'
