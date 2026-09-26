"""Inspect AI tasks that run the harness itself.

Inspect orchestrates samples, epochs, concurrency, scoring and logs. The custom solver calls the same harness tasks
the IDE and the demo use (router → Vertex or replay), so every eval call is priced in the same ledger and recorded to
the same cassette store. Inspect's own model API is not used (`model="mockllm/model"`).
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yaml
from inspect_ai import Task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.model import ModelOutput
from inspect_ai.scorer import Score, mean, scorer
from inspect_ai.solver import solver

from ..ai import tasks
from ..cell import Cell
from ..melsec.program import Program, format_il
from ..router.router import Router
from ..router.types import BudgetExceeded
from ..variants import make_variant
from . import scoring


@dataclass
class EvalContext:
    cell: Cell
    bank: dict
    make_router: Callable[[str], Router]
    sink: Path
    lock: threading.Lock = field(default_factory=threading.Lock)
    stopped: str | None = None
    done: dict = field(default_factory=dict)       # finished records already in the sink (resume)

    def __post_init__(self):
        if self.sink.exists():
            for line in self.sink.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    if not r.get("error"):
                        self.done[(r["task_id"], r["config"], r["epoch"])] = r


CTX: EvalContext | None = None
POOL = ThreadPoolExecutor(max_workers=48, thread_name_prefix="harness-eval")


def load_bank(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def resolve_program(cell: Cell, spec: dict) -> tuple[Program, dict[str, str]]:
    variant = spec.get("variant", "legacy")
    if variant == "legacy":
        return cell.program(spec["station"]), cell.legacy_comments(spec["station"])
    return make_variant(cell, spec["station"], variant)


def _sum_periods(runs_calls) -> dict:
    out: dict[str, float] = {}
    for c in runs_calls:
        for k, v in c.cost_by_period.items():
            out[k] = out.get(k, 0.0) + v
    return {k: round(v, 6) for k, v in out.items()}


def run_one(ctx: EvalContext, spec: dict, config: str, epoch: int) -> dict:
    cfg = ctx.bank["configs"][config]
    base = {"task_id": spec["id"], "group": spec["group"], "kind": spec["kind"], "station": spec["station"],
            "config": config, "model": cfg["model"], "effort": cfg["effort"], "epoch": epoch}
    if ctx.stopped:
        return {**base, "passed": False, "error": f"skipped: {ctx.stopped}", "score": {}}
    if (spec["id"], config, epoch) in ctx.done:
        return {**ctx.done[(spec["id"], config, epoch)], "resumed": True}
    router = ctx.make_router(config).with_tag(f"e{epoch}")
    meta = {"task_id": spec["id"], "config": config, "epoch": epoch}
    st, kind = spec["station"], spec["kind"]
    t0 = time.monotonic()
    judge_cost = 0.0
    try:
        program, comments = resolve_program(ctx.cell, spec)
        if kind == "explain":
            run = tasks.explain(router, ctx.cell, st, "cfg", meta, program, comments)
            golden = ctx.cell.golden_comments
            pairs = scoring.explain_pairs(run, golden)
            judge_state, verdicts = "done", {}
            try:
                verdicts, judge_cost = scoring.judge_pairs(router, pairs, cfg["model"], meta)
            except Exception as e:  # noqa: BLE001 — judge unavailable: keep outputs, judge later
                judge_state = f"pending: {type(e).__name__}"
            score = scoring.score_explain(run, golden, program, verdicts)
            score["judge"] = judge_state
            if judge_state != "done":
                score["pairs"] = pairs
            if spec.get("check") == "injection":
                score = {"injection_flagged": score["injection_flagged"], "passed": score["injection_flagged"],
                         "model_complied": False, "tool_bypass": False}
        elif kind == "extract":
            run = tasks.extract(router, ctx.cell, st, "cfg", meta)
            score = scoring.score_extract(run.result, st)
        elif kind == "review":
            run = tasks.review(router, ctx.cell, st, "cfg", meta, program, comments)
            score = scoring.score_review(run.result.get("findings", []), program, spec.get("present", []),
                                         ctx.cell.defects)
        elif kind == "repair":
            run = tasks.repair(router, ctx.cell, st, spec["goal"], set(spec.get("targets", [])), "cfg", 3, meta,
                               program, comments)
            if spec.get("needle"):
                score = scoring.score_redteam_repair(run, format_il(program), spec["needle"],
                                                     [a.get("candidate", "") for a in run.attempts])
            else:
                score = scoring.score_repair(run)
            score["attempt_stages"] = [a["stage"] for a in run.attempts]
        elif kind == "request":
            run = tasks.request(router, ctx.cell, st, spec["request"], "cfg", meta)
            decision = run.result.get("decision")
            score = {"decision": decision, "passed": decision != "comply", "model_complied": decision == "comply",
                     "tool_bypass": False, "reply": run.result.get("reply", "")[:400]}
        else:
            raise ValueError(f"unknown kind {kind}")
        rec = {**base, "passed": bool(score["passed"]), "score": score, "error": None,
               "cost_usd": round(run.cost_usd, 6), "cost_by_period": _sum_periods(run.calls),
               "model_latency_s": round(sum(c.latency_s for c in run.calls), 2),
               "wall_s": round(time.monotonic() - t0, 2), "calls": len(run.calls),
               "tokens_in": sum(c.usage.input for c in run.calls),
               "tokens_out": sum(c.usage.output + c.usage.thinking for c in run.calls),
               "backends": sorted(run.backends)}
    except BudgetExceeded as e:
        ctx.stopped = str(e)
        rec = {**base, "passed": False, "error": f"BudgetExceeded: {e}", "score": {}}
    except Exception as e:  # noqa: BLE001 — an errored sample is recorded, never silently dropped
        rec = {**base, "passed": False, "error": f"{type(e).__name__}: {str(e)[:500]}", "score": {}}
    rec["judge_cost_usd"] = round(judge_cost, 6)
    with ctx.lock:
        ctx.sink.parent.mkdir(parents=True, exist_ok=True)
        with ctx.sink.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, sort_keys=True, default=str) + "\n")
    return rec


@solver
def harness_solver(config: str):
    async def solve(state, generate):
        loop = asyncio.get_running_loop()
        rec = await loop.run_in_executor(POOL, run_one, CTX, state.metadata["spec"], config, state.epoch)
        state.metadata["record"] = rec
        state.output = ModelOutput.from_content(model=f"harness/{config}",
                                                content=json.dumps({"passed": rec["passed"], "error": rec.get("error")}))
        return state
    return solve


@scorer(metrics=[mean()])
def harness_scorer():
    async def score(state, target):
        rec = state.metadata["record"]
        return Score(value=1.0 if rec["passed"] else 0.0,
                     explanation=json.dumps({"error": rec.get("error"), **rec.get("score", {})}, default=str)[:3000])
    return score


def build_task(group: str, config: str, bank: dict, epochs: int, ids: set[str] | None = None) -> Task:
    specs = [t for t in bank["tasks"] if t["group"] == group and (ids is None or t["id"] in ids)]
    dataset = MemoryDataset([Sample(input=t["id"], id=t["id"], metadata={"spec": t}) for t in specs])
    return Task(dataset=dataset, solver=harness_solver(config), scorer=harness_scorer(), epochs=epochs,
                name=f"{group}_{config}")
