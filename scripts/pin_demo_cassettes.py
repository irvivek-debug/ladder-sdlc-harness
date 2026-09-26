#!/usr/bin/env python3
"""Pin real recorded sweep runs as the demo's replay answers.

For each demo task, pick one epoch recorded on the routed lane and copy its epoch-tagged cassettes to untagged keys, so
`LADDER_MODE=auto|replay` on stage returns exactly what that recorded run returned (labelled REPLAY).
RP-D5 prefers a run whose first attempt the gate rejected — the "simulator says no" moment.

    python scripts/pin_demo_cassettes.py --sweep S1
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml  # noqa: E402

from ladder_harness.evaluation.aggregate import load_records, usable  # noqa: E402
from ladder_harness.router.ledger import Ledger  # noqa: E402

DEMO = ["EX-ST20", "XT-ST20", "RV-LEGACY", "RP-D5", "RP-D1", "RP-D3", "RP-D4", "RT-DOWNLOAD"]


def preference(task_id: str, r: dict) -> tuple:
    s = r["score"]
    if task_id == "RP-D5":
        return (r["passed"], s.get("pass_at") == 2, -(s.get("pass_at") or 9))
    if task_id == "RV-LEGACY":
        return ("D5" in s.get("matched", {}), s.get("recall", 0), -s.get("false_positives", 9))
    if task_id == "EX-ST20":
        return (s.get("quality", 0), s.get("injection_flagged", False))
    return (r["passed"],)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", default="S1")
    args = ap.parse_args()
    routing = yaml.safe_load((ROOT / "config" / "routing.yaml").read_text())
    bank = yaml.safe_load((ROOT / "evals" / "task_bank.yaml").read_text())
    records = [r for r in load_records([ROOT / "evals" / "results" / "runs" / f"{args.sweep}.jsonl"]) if usable(r)]
    ledger = Ledger(ROOT / "logs" / "ledger.jsonl").read() or Ledger(ROOT / "evals" / "results" / f"ledger_{args.sweep}.jsonl").read()
    cdir = ROOT / "evals" / "cassettes"
    pins = []
    for task_id in DEMO:
        spec = next(t for t in bank["tasks"] if t["id"] == task_id)
        group = spec["group"] if spec["group"] != "RT" else "T4"
        lane = routing["task_classes"][group]
        config = next((c for c, v in bank["configs"].items()
                       if v["model"] == lane["model"] and v["effort"] == lane["effort"]), None)
        cands = [r for r in records if r["task_id"] == task_id and r["config"] == config]
        if not cands:
            print(f"skip {task_id}: no usable record on the routed lane {config}")
            continue
        best = max(cands, key=lambda r: preference(task_id, r))
        rows = [x for x in ledger if x.get("run_id") == args.sweep and x.get("task_id") == task_id
                and x.get("config") == config and x.get("epoch") == best["epoch"] and x.get("task") != "judge"
                and x.get("backend") == "vertex"]
        copied = 0
        for row in rows:
            key = row["key"]
            src = cdir / f"{key}.json"
            if src.exists():
                shutil.copyfile(src, cdir / f"{key.split('.')[0]}.json")
                copied += 1
        pins.append({"task_id": task_id, "config": config, "epoch": best["epoch"], "cassettes": copied,
                     "passed": best["passed"], "cost_usd": best.get("cost_usd"),
                     "note": json.dumps({k: v for k, v in best["score"].items() if k in ("pass_at", "stages", "recall",
                                         "matched", "quality", "decision", "drift_detected")})})
        print(f"pinned {task_id} on {config} epoch {best['epoch']} ({copied} cassettes)")
    (cdir / "demo_pins.yaml").write_text(yaml.safe_dump({"sweep": args.sweep, "pins": pins}, sort_keys=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
