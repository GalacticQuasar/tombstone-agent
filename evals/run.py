"""Run one task × strategy × backend and write a trace.

    uv run python -m evals.run --task toy_bridge --strategy none --backend ollama-glm
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from dotenv import load_dotenv

from tombstone.agent import Agent
from tombstone.client import BACKENDS, OpenAIChatClient
from tombstone.strategies import STRATEGIES, SelfForget, Strategy
from tombstone.tools import ToolRegistry
from tombstone.trace import Trace

from .tasks import TASKS

SYSTEM_PROMPT = (
    "You are a careful research agent. Use the provided tools to gather information. "
    "When you have enough information, reply with your final answer and no tool calls."
)


def make_strategy(args: argparse.Namespace) -> Strategy:
    if args.strategy == SelfForget.name:
        return SelfForget(apply_threshold=args.apply_threshold, show_ledger=not args.no_ledger)
    return STRATEGIES[args.strategy]()


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=sorted(TASKS))
    ap.add_argument("--strategy", default="none", choices=sorted(STRATEGIES))
    ap.add_argument("--backend", default="ollama-glm-flash", choices=sorted(BACKENDS))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-turns", type=int, default=30)
    ap.add_argument("--runs-dir", type=Path, default=Path("runs"))
    ap.add_argument("--apply-threshold", type=int, default=10_000, help="self_forget: batch-apply threshold (tokens)")
    ap.add_argument("--no-ledger", action="store_true", help="self_forget: hide the per-turn block ledger")
    args = ap.parse_args()

    task = TASKS[args.task]
    run_id = f"{time.strftime('%Y%m%d-%H%M%S')}_{task.id}_{args.strategy}_{args.backend}_s{args.seed}"
    run_dir = args.runs_dir / run_id
    trace = Trace(run_dir / "trace.jsonl")

    agent = Agent(
        client=OpenAIChatClient(BACKENDS[args.backend], seed=args.seed),
        tools=ToolRegistry(task.make_tools()),
        system_prompt=SYSTEM_PROMPT,
        strategy=make_strategy(args),
        trace=trace,
        max_turns=args.max_turns,
        run_dir=run_dir,
    )
    try:
        result = agent.run(task.prompt)
    finally:
        trace.close()

    summary = {
        "run_id": run_id,
        "task": task.id,
        "strategy": args.strategy,
        "backend": args.backend,
        "seed": args.seed,
        "success": task.grade(result.answer),
        "stopped": result.stopped,
        "turns": result.turns,
        "prompt_tokens": result.prompt_tokens,
        "cached_tokens": result.cached_tokens,
        "sim_reused_tokens": result.sim_reused_tokens,
        "forgets_requested": sum(e["event"] == "forget_requested" for e in trace.events),
        "forgets_applied": sum(len(e["block_ids"]) for e in trace.events if e["event"] == "forget_applied"),
        "retrievals": sum(e["event"] == "retrieve" for e in trace.events),
        "answer": result.answer,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
