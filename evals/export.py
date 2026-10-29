"""Export a runs directory to one committed JSONL file (summary + trace-derived costs per run).

    uv run python -m evals.export runs/matrix results/matrix.jsonl

Traces and archives stay in runs/ (git-ignored); this keeps the numbers behind PLAN.md.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .report import run_cost


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs_dir", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with args.out.open("w") as fh:
        for summary_path in sorted(args.runs_dir.glob("*/summary.json")):
            s = json.loads(summary_path.read_text())
            s["cost"] = asdict(run_cost(summary_path.parent / "trace.jsonl"))
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")
            n += 1
    print(f"wrote {n} runs to {args.out}")


if __name__ == "__main__":
    main()
