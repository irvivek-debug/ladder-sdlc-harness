"""Scenario suites loaded from YAML.

Suite:  {station, plant, scan_ms?, defaults?: {plant?, stimuli?}, scenarios: [...]}
Scenario: {id, title, trace?, duration_ms, plant?, stimuli?, expect}
Stimulus: {at_ms | when (+ delay_ms), set?: {DEV: value}, plant?: {action: args}}
Expectation (one kind key each): always | never (+ after_ms), eventually (+ by_ms, after_ms), at_end,
response: {trigger, effect} + within_ms.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .expr import Expr, compile_expr

KINDS = ("always", "never", "eventually", "at_end", "response")


@dataclass
class Stimulus:
    at_ms: int | None
    when: Expr | None
    delay_ms: int
    set: dict[str, bool | int]
    plant: dict[str, dict]


@dataclass
class Expectation:
    kind: str
    text: str
    expr: Expr | None = None
    trigger: Expr | None = None
    effect: Expr | None = None
    by_ms: int | None = None
    after_ms: int = 0
    within_ms: int | None = None


@dataclass
class Scenario:
    id: str
    title: str
    duration_ms: int
    trace: list[str] = field(default_factory=list)
    plant: dict = field(default_factory=dict)
    stimuli: list[Stimulus] = field(default_factory=list)
    expect: list[Expectation] = field(default_factory=list)


@dataclass
class Suite:
    station: str
    plant: str
    scan_ms: int
    scenarios: list[Scenario]
    source: str = ""


def _stimulus(d: dict) -> Stimulus:
    if ("at_ms" in d) == ("when" in d):
        raise ValueError(f"stimulus needs exactly one of at_ms / when: {d}")
    return Stimulus(at_ms=d.get("at_ms"), when=compile_expr(d["when"]) if "when" in d else None,
                    delay_ms=int(d.get("delay_ms", 0)), set=dict(d.get("set", {})), plant=dict(d.get("plant", {})))


def _expectation(d: dict) -> Expectation:
    kinds = [k for k in KINDS if k in d]
    if len(kinds) != 1:
        raise ValueError(f"expectation needs exactly one of {KINDS}: {d}")
    kind = kinds[0]
    common = {"by_ms": d.get("by_ms"), "after_ms": int(d.get("after_ms", 0)), "within_ms": d.get("within_ms")}
    if kind == "response":
        r = d["response"]
        if common["within_ms"] is None:
            raise ValueError(f"response expectation needs within_ms: {d}")
        return Expectation(kind, f"response {r['trigger']} -> {r['effect']} within {common['within_ms']} ms",
                           trigger=compile_expr(r["trigger"]), effect=compile_expr(r["effect"]), **common)
    return Expectation(kind, f"{kind} {d[kind]}", expr=compile_expr(d[kind]), **common)


def suite_from_dict(d: dict, source: str = "") -> Suite:
    defaults = d.get("defaults", {})
    scenarios = []
    for s in d.get("scenarios", []):
        scenarios.append(Scenario(
            id=s["id"], title=s.get("title", s["id"]), duration_ms=int(s["duration_ms"]),
            trace=list(s.get("trace", [])), plant={**defaults.get("plant", {}), **s.get("plant", {})},
            stimuli=[_stimulus(x) for x in defaults.get("stimuli", []) + s.get("stimuli", [])],
            expect=[_expectation(x) for x in s.get("expect", [])],
        ))
    ids = [s.id for s in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate scenario ids in {source or 'suite'}")
    return Suite(station=d["station"], plant=d.get("plant", "none"), scan_ms=int(d.get("scan_ms", 10)),
                 scenarios=scenarios, source=source)


def load_suite(path: str | Path) -> Suite:
    with open(path, encoding="utf-8") as f:
        return suite_from_dict(yaml.safe_load(f), source=str(path))
