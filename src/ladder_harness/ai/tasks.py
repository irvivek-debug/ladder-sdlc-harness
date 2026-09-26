"""The model-backed lifecycle tasks (T1–T4). Each call goes through the router; deterministic post-checks and
the apply gate decide what survives. T0 (lint, simulate) and T5 (the SAFETY guard) never call a model."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..cell import Cell
from ..guard import gate
from ..melsec.devices import DeviceError, dev
from ..melsec.program import Program
from ..router.router import Router
from ..router.types import ModelResult
from ..scenarios.runner import load_station_suites, run_suites
from . import prompts, schemas
from .packets import build_packet


@dataclass
class TaskRun:
    task: str
    station: str
    profile: str
    ok: bool
    result: dict
    calls: list[ModelResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    attempts: list[dict] = field(default_factory=list)

    @property
    def cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def backends(self) -> set[str]:
        return {c.backend for c in self.calls}


def _used(program: Program) -> set[str]:
    return {str(d) for i in program.instructions() for d in i.devices()}


def explain(router: Router, cell: Cell, station: str, profile: str = "routed", meta: dict | None = None,
            program: Program | None = None, comments: dict[str, str] | None = None) -> TaskRun:
    program = program or cell.program(station)
    prompt = build_packet(cell, station, ("io_list", "device_comments", "program"), program, comments) + "\n\n" + \
        prompts.EXPLAIN.format(station=station)
    res = router.call("T1", prompts.system_prompt(), prompt, schemas.EXPLAIN, profile, meta={"task": "explain", **(meta or {})})
    used, notes, comments = _used(program), [], {}
    for item in res.data.get("device_comments", []):
        try:
            name = str(dev(item["device"]))
        except DeviceError:
            notes.append(f"dropped comment for non-device {item['device']!r}")
            continue
        if name not in used:
            notes.append(f"dropped comment for {name}: not used in the program (hallucinated)")
            continue
        text = " ".join(item["comment"].split())
        if len(text) > 32:
            notes.append(f"truncated {name} comment to 32 characters")
            text = text[:32]
        comments[name] = text
    n_rungs = len(program.rungs)
    purposes = {p["rung"]: p["purpose"] for p in res.data.get("rung_purposes", []) if 1 <= p["rung"] <= n_rungs}
    result = {"device_comments": comments, "rung_purposes": purposes, "suspicious": res.data.get("suspicious", []),
              "coverage": round(len(comments) / len(used), 3) if used else 1.0}
    return TaskRun("explain", station, profile, True, result, [res], notes)


def extract(router: Router, cell: Cell, station: str, profile: str = "routed", meta: dict | None = None) -> TaskRun:
    prompt = build_packet(cell, station, ("parameters", "narrative", "program")) + "\n\n" + \
        prompts.EXTRACT.format(station=station)
    res = router.call("T2", prompts.system_prompt(), prompt, schemas.EXTRACT, profile, meta={"task": "extract", **(meta or {})})
    return TaskRun("extract", station, profile, True, res.data, [res])


def review(router: Router, cell: Cell, station: str, profile: str = "routed", meta: dict | None = None,
           program: Program | None = None, comments: dict[str, str] | None = None) -> TaskRun:
    program = program or cell.program(station)
    prompt = build_packet(cell, station, ("io_list", "parameters", "cause_effect", "narrative", "device_comments",
                                          "lint", "program"), program=program, comments=comments) + "\n\n" + \
        prompts.REVIEW.format(station=station)
    res = router.call("T4", prompts.system_prompt(), prompt, schemas.REVIEW, profile, meta={"task": "review", **(meta or {})})
    used, notes = _used(program), []
    for f in res.data.get("findings", []):
        ghosts = [d for d in f.get("devices", []) if d.upper() not in used]
        if ghosts:
            notes.append(f"finding {f['title']!r} names devices not in the program: {', '.join(ghosts)}")
    return TaskRun("review", station, profile, True, res.data, [res], notes)


def repair(router: Router, cell: Cell, station: str, goal: str, targets: set[str] | frozenset[str] = frozenset(),
           profile: str = "routed", max_attempts: int = 3, meta: dict | None = None,
           program: Program | None = None, comments: dict[str, str] | None = None) -> TaskRun:
    """Ask for a complete candidate, run the apply gate, feed its reasons back, repeat."""
    program = program or cell.program(station)
    suites = load_station_suites(cell.data_dir, station)
    known = {r.id for r in run_suites(program, suites) if not r.passed}
    safety = cell.iolist.safety_devices()
    base = build_packet(cell, station, ("io_list", "parameters", "cause_effect", "narrative", "device_comments",
                                        "program_il"), program=program, comments=comments) + "\n\n" + \
        prompts.REPAIR.format(station=station, goal=goal)
    prompt, calls, attempts = base, [], []
    for k in range(1, max_attempts + 1):
        res = router.call("T3", prompts.system_prompt(), prompt, schemas.REPAIR, profile,
                          meta={"task": "repair", "attempt": k, **(meta or {})})
        calls.append(res)
        candidate = res.data.get("program_il", "")
        g = gate(candidate, program, safety, suites, cell.iolist, known_failures=known, targets=set(targets))
        attempts.append({"attempt": k, "stage": g.stage, "allowed": g.allowed, "reasons": g.reasons[:10],
                         "change_summary": res.data.get("change_summary", ""), "candidate": candidate})
        if g.allowed:
            return TaskRun("repair", station, profile, True,
                           {"program_il": candidate, "change_summary": res.data.get("change_summary", ""),
                            "pass_at": k}, calls, [], attempts)
        prompt = base + "\n\n" + prompts.FEEDBACK.format(stage=g.stage, reasons="\n".join(f"- {r}" for r in g.reasons[:10]))
    return TaskRun("repair", station, profile, False, {"pass_at": None}, calls, [], attempts)


def request(router: Router, cell: Cell, station: str, text: str, profile: str = "routed",
            meta: dict | None = None) -> TaskRun:
    """An operator request in plain words (used by the red team, e.g. "download this to the PLC")."""
    prompt = build_packet(cell, station, ("io_list",)) + "\n\n" + prompts.REQUEST.format(station=station, request=text)
    res = router.call("T4", prompts.system_prompt(), prompt, schemas.REQUEST, profile,
                      meta={"task": "request", **(meta or {})})
    return TaskRun("request", station, profile, True, res.data, [res])
