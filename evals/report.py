"""Summarize runs into a strategy comparison table.

    uv run python -m evals.report runs/pilot

Costs come from each run's trace (agent turns plus compaction calls), priced three ways:
no cache, provider-reported cache, and ideal cache (the simulated prefix metric).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .metrics import SOURCE_ARG

# $ per million tokens: (input, cache read, output). From OpenRouter endpoint listings.
PRICES: dict[str, tuple[float, float, float]] = {
    "or-qwen3.8-27b": (0.15, 0.0375, 1.875),
}


@dataclass
class RunCost:
    prompt: int = 0
    cached: int = 0
    sim_reused: int = 0
    completion: int = 0
    aux_prompt: int = 0  # summarizer calls; never cached (a fresh prompt each time)
    aux_completion: int = 0
    peak_prompt: int = 0
    rereads: int = 0  # fetches/reads of a source already read earlier in the run

    def dollars(self, price: tuple[float, float, float], mode: str) -> float:
        inp, cache, out = price
        hit = {"none": 0, "real": self.cached, "ideal": self.sim_reused}[mode]
        hit = min(hit, self.prompt)
        tokens_in = (self.prompt - hit) * inp + hit * cache + self.aux_prompt * inp
        return (tokens_in + (self.completion + self.aux_completion) * out) / 1e6


def run_cost(trace_path: Path) -> RunCost:
    c = RunCost()
    seen: set[str] = set()
    for line in trace_path.open():
        e = json.loads(line)
        if e["event"] == "tool_result" and e["tool"] in SOURCE_ARG:
            key = f'{e["tool"]}:{e["arguments"].get(SOURCE_ARG[e["tool"]])}'
            c.rereads += key in seen
            seen.add(key)
        if e["event"] == "turn":
            c.peak_prompt = max(c.peak_prompt, e["usage"]["prompt"])
            c.prompt += e["usage"]["prompt"]
            c.cached += e["usage"]["cached"] or 0
            c.completion += e["usage"]["completion"]
            c.sim_reused += e["sim_prefix"]["reused_tokens"]
        elif e["event"] == "compact_applied":
            c.aux_prompt += e["usage"]["prompt"]
            c.aux_completion += e["usage"]["completion"]
    return c


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs_dir", type=Path, nargs="?", default=Path("runs"))
    args = ap.parse_args()

    groups: dict[tuple[str, str, str], list[tuple[dict, RunCost]]] = defaultdict(list)
    for summary_path in sorted(args.runs_dir.glob("*/summary.json")):
        s = json.loads(summary_path.read_text())
        groups[(s["task"], s["backend"], s["strategy"])].append((s, run_cost(summary_path.parent / "trace.jsonl")))

    order = {"none": 0, "self_forget": 1, "truncate": 2, "compact": 3}
    header = (f"{'task':11} {'backend':16} {'strategy':12} {'n':>2} {'phases ok':>9} {'turns':>5} "
              f"{'prompt':>8} {'peak':>6} {'reread':>6} {'$m none':>8} {'$m real':>8} {'$m ideal':>9}  notes")
    print(header)
    print("-" * len(header))
    for (task, backend, strategy), runs in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1], order.get(kv[0][2], 9))):
        price = PRICES.get(backend)
        n = len(runs)
        ok = sum(sum(s["phase_success"]) for s, _ in runs)
        total = sum(len(s["phase_success"]) for s, _ in runs)
        mean = lambda f: sum(f(s, c) for s, c in runs) / n  # noqa: E731
        costs = (
            [f"{mean(lambda s, c, m=m: c.dollars(price, m)) * 1000:8.2f}" for m in ("none", "real", "ideal")]
            if price else ["       -"] * 3
        )
        notes = []
        for key, label in (("forgets_applied", "forgot"), ("retrievals", "retrieved"),
                           ("truncations", "truncations"), ("compactions", "compactions")):
            v = mean(lambda s, c, k=key: s.get(k, 0))
            if v:
                notes.append(f"{label}={v:g}")
        print(f"{task:11} {backend:16} {strategy:12} {n:>2} {f'{ok}/{total}':>9} {mean(lambda s, c: s['turns']):5.1f} "
              f"{mean(lambda s, c: c.prompt + c.aux_prompt) / 1000:7.1f}k {mean(lambda s, c: c.peak_prompt) / 1000:5.1f}k "
              f"{mean(lambda s, c: c.rereads):6.1f} {costs[0]} {costs[1]} {costs[2]:>9}  {' '.join(notes)}")


if __name__ == "__main__":
    main()
