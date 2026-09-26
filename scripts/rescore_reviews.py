#!/usr/bin/env python3
"""Re-score review (T4) records from their recorded findings against the current answer key — seeded defects plus
simulator-confirmed latent issues. No model calls. Appends updated records.

    python scripts/rescore_reviews.py --sweep S1
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ladder_harness.cell import load_cell  # noqa: E402
from ladder_harness.evaluation import scoring  # noqa: E402
from ladder_harness.evaluation.aggregate import load_records  # noqa: E402
from ladder_harness.evaluation.harness_eval import load_bank, resolve_program  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", default="S1")
    args = ap.parse_args()
    runs = ROOT / "evals" / "results" / "runs" / f"{args.sweep}.jsonl"
    bank = {t["id"]: t for t in load_bank(ROOT / "evals" / "task_bank.yaml")["tasks"]}
    cell = load_cell(ROOT / "plant_data" / "ev_pack_eol", ROOT / "evals" / "answer_key")
    ledger = [json.loads(l) for l in (ROOT / "logs" / "ledger.jsonl").read_text().splitlines() if l.strip()]
    index = {(x.get("task_id"), x.get("config"), x.get("epoch")): x for x in ledger
             if x.get("run_id") == args.sweep and x.get("task") == "review"}
    out, missing = [], 0
    for r in load_records([runs]):
        if r["group"] != "T4" or r.get("error"):
            continue
        row = index.get((r["task_id"], r["config"], r["epoch"]))
        path = ROOT / "evals" / "cassettes" / f"{row['key']}.json" if row else None
        if not path or not path.exists():
            missing += 1
            continue
        findings = json.loads(path.read_text())["data"].get("findings", [])
        spec = bank[r["task_id"]]
        program, _ = resolve_program(cell, spec)
        score = scoring.score_review(findings, program, spec.get("present", []), cell.defects, cell.latent, spec["station"])
        out.append({**r, "score": {**score, "rescored": "seeded + simulator-confirmed latent issues"}, "passed": score["passed"]})
    with runs.open("a", encoding="utf-8") as f:
        for rec in out:
            f.write(json.dumps(rec, sort_keys=True, default=str) + "\n")
    print(f"re-scored {len(out)} reviews ({missing} without a recorded answer)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
