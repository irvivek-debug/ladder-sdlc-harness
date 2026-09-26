#!/usr/bin/env python3
"""Run the evaluation sweep with Inspect AI (the harness makes the model calls).

    python scripts/run_evals.py --dry-run                                   # cost estimate only
    python scripts/run_evals.py --sweep S1 --groups T3,T4 --configs flash-medium,flash-high,pro-high
    python scripts/run_evals.py --sweep S1 --mode replay                    # re-score from cassettes, $0

Results append to evals/results/runs/<sweep>.jsonl; Inspect logs go to logs/inspect/ (`inspect view`).
The shared budget guard aborts the whole sweep at --budget USD.
"""
from __future__ import annotations

import argparse
import copy
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml  # noqa: E402
from inspect_ai import eval as inspect_eval  # noqa: E402

from ladder_harness.cell import load_cell  # noqa: E402
from ladder_harness.evaluation import harness_eval  # noqa: E402
from ladder_harness.router.ledger import Ledger  # noqa: E402
from ladder_harness.router.pricing import Pricing  # noqa: E402
from ladder_harness.router.router import BudgetGuard, Router  # noqa: E402

# Rough per-call token profiles (input, output incl. thinking) by kind and effort, for the dry-run estimate.
PROFILE = {"explain": (7000, {"low": 2500, "medium": 4000, "high": 7000}),
           "extract": (6500, {"low": 2500, "medium": 4000, "high": 7000}),
           "review": (10000, {"low": 3500, "medium": 6000, "high": 10000}),
           "repair": (10000, {"low": 5000, "medium": 7000, "high": 11000}),
           "request": (3000, {"low": 600, "medium": 900, "high": 1500})}
REPAIR_ATTEMPTS = 1.8


def estimate(bank: dict, groups: list[str], configs: dict, epochs: int, pricing: Pricing) -> float:
    from ladder_harness.router.types import Usage
    total = 0.0
    for t in bank["tasks"]:
        if t["group"] not in groups:
            continue
        for name in configs.get(t["group"], []):
            cfg = bank["configs"][name]
            tin, touts = PROFILE[t["kind"]]
            calls = REPAIR_ATTEMPTS if t["kind"] == "repair" else 1
            cost = pricing.price(cfg["model"], Usage(tin, touts[cfg["effort"]], 0, 0)) * calls
            if t["kind"] == "explain":   # the cross-family judge
                judge = ("claude-opus-5-5" if cfg["model"].startswith("gemini") else "gemini-3.8-flash")
                cost += pricing.price(judge, Usage(2500, 2500, 0, 0))
            total += cost * epochs
    return total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", default="S1")
    ap.add_argument("--groups", default="T1,T2,T3,T4,RT")
    ap.add_argument("--configs", default="", help="comma list; default = every config the group allows")
    ap.add_argument("--ids", default="", help="comma list of task ids")
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--mode", default="record", choices=["record", "replay", "live", "auto"])
    ap.add_argument("--budget", type=float, default=150.0)
    ap.add_argument("--max-tasks", type=int, default=4)
    ap.add_argument("--max-samples", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    bank = harness_eval.load_bank(ROOT / "evals" / "task_bank.yaml")
    pricing = Pricing.load(ROOT / "config" / "pricing.yaml")
    groups = [g.strip() for g in args.groups.split(",") if g.strip()]
    wanted = {c.strip() for c in args.configs.split(",") if c.strip()}
    plan = {g: [c for c in bank["groups"][g] if not wanted or c in wanted] for g in groups}
    ids = {i.strip() for i in args.ids.split(",") if i.strip()} or None
    est = estimate(bank if not ids else {**bank, "tasks": [t for t in bank["tasks"] if t["id"] in ids]},
                   groups, plan, args.epochs, pricing)
    n_samples = sum(len(plan[t["group"]]) for t in bank["tasks"] if t["group"] in groups and (not ids or t["id"] in ids))
    print(f"sweep {args.sweep}: {n_samples} task×config samples × {args.epochs} epochs; "
          f"estimated live cost ≈ ${est:.2f} (budget cap ${args.budget:.2f})")
    for g, cs in plan.items():
        print(f"  {g}: {', '.join(cs)}")
    if args.dry_run:
        return 0
    if args.mode in ("record", "live") and not os.environ.get("LADDER_GCP_PROJECT"):
        print("set LADDER_GCP_PROJECT for live calls")
        return 2

    routing = yaml.safe_load((ROOT / "config" / "routing.yaml").read_text(encoding="utf-8"))
    ledger = Ledger(ROOT / "logs" / "ledger.jsonl")
    guard = BudgetGuard(args.budget)
    routers: dict[str, Router] = {}

    def make_router(config: str) -> Router:
        if config not in routers:
            doc = copy.deepcopy(routing)
            doc["profiles"]["cfg"] = dict(bank["configs"][config])
            routers[config] = Router(doc, pricing, ledger, mode=args.mode, cassette_dir=ROOT / "evals" / "cassettes",
                                     run_id=args.sweep, budget=guard)
        return routers[config]

    harness_eval.CTX = harness_eval.EvalContext(
        cell=load_cell(ROOT / "plant_data" / "ev_pack_eol", ROOT / "evals" / "answer_key"), bank=bank,
        make_router=make_router, sink=ROOT / "evals" / "results" / "runs" / f"{args.sweep}.jsonl")
    tasks = [harness_eval.build_task(g, c, bank, args.epochs, ids) for g, cs in plan.items() for c in cs]
    tasks = [t for t in tasks if len(t.dataset)]
    inspect_eval(tasks, model="mockllm/model", log_dir=str(ROOT / "logs" / "inspect"), display="plain",
                 max_tasks=args.max_tasks, max_samples=args.max_samples, fail_on_error=False)
    print(f"spent ${guard.spent_usd:.2f} live" + (f" — STOPPED: {harness_eval.CTX.stopped}" if harness_eval.CTX.stopped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
