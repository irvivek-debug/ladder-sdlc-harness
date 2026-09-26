#!/usr/bin/env python3
"""Mutation score of a station's scenario suite against its reference program.

    python scripts/mutation_score.py ST20 [--processes 8] [--report evals/results/mutation_st20.md]
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ladder_harness.cell import load_cell  # noqa: E402
from ladder_harness.scenarios.mutation import score  # noqa: E402
from ladder_harness.scenarios.runner import load_station_suites  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("station")
    ap.add_argument("--processes", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    cell = load_cell(ROOT / "plant_data" / "ev_pack_eol", ROOT / "evals" / "answer_key")
    suites = load_station_suites(cell.data_dir, args.station)
    t = time.time()
    rep = score(cell.golden(args.station), suites, processes=args.processes)
    print(rep.summary())
    print(f"({time.time() - t:.0f} s, {sum(len(s.scenarios) for s in suites)} scenarios)")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"# Mutation adequacy — {args.station}", "",
                 f"Reference program mutated one defect at a time; a mutant is killed when any scenario fails.", "",
                 f"**Score: {rep.killed}/{rep.total} = {rep.score:.1%}** (invalid mutants skipped: {rep.invalid})", "",
                 "| Survivor | Operator | Mutation | Analysis |", "|---|---|---|---|"]
        lines += [f"| {m.id} | {m.operator} | {m.description} | |" for m in rep.survivors]
        args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
