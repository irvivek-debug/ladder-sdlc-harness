#!/usr/bin/env python3
"""Score explain samples whose judge was unavailable during the sweep (their comment pairs were stored).
Appends updated records; aggregation keeps the latest record per (task, config, epoch).

    python scripts/rejudge.py --sweep S1
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ladder_harness.evaluation import aggregate  # noqa: E402
from ladder_harness.evaluation.scoring import judge_pairs  # noqa: E402
from ladder_harness.router.router import Router  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", default="S1")
    args = ap.parse_args()
    runs = ROOT / "evals" / "results" / "runs" / f"{args.sweep}.jsonl"
    router = Router.from_config(ROOT / "config", ROOT / "logs" / "ledger.jsonl", mode="record",
                                cassette_dir=ROOT / "evals" / "cassettes", run_id=args.sweep)
    pending = [r for r in aggregate.load_records([runs])
               if r["kind"] == "explain" and str(r["score"].get("judge", "")).startswith("pending") and r["score"].get("pairs")]
    print(f"{len(pending)} explain samples waiting for a judge")
    with runs.open("a", encoding="utf-8") as f:
        for r in pending:
            s = r["score"]
            verdicts, cost = judge_pairs(router.with_tag(f"e{r['epoch']}"), s["pairs"], r["model"],
                                         {"task_id": r["task_id"], "config": r["config"], "epoch": r["epoch"]})
            judged = [p["device"] for p in s["pairs"]]
            correct = [d for d in judged if verdicts.get(d.upper())]
            accuracy = len(correct) / len(judged) if judged else 0.0
            quality = s["coverage"] * accuracy
            new = {**r, "passed": quality >= 0.8, "judge_cost_usd": round(cost, 6),
                   "score": {**{k: v for k, v in s.items() if k != "pairs"}, "accuracy": round(accuracy, 3),
                             "quality": round(quality, 3), "judge": "done (rejudged)",
                             "wrong": [d for d in judged if not verdicts.get(d.upper())][:15]}}
            f.write(json.dumps(new, sort_keys=True, default=str) + "\n")
            print(f"{r['task_id']} {r['config']} e{r['epoch']}: quality {quality:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
