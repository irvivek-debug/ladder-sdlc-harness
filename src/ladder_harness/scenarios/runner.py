"""Run scenarios: program + plant twin + stimuli, checked scan by scan against expectations."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..melsec.devices import DeviceError, dev
from ..melsec.program import Program
from ..plant import PLANTS
from ..sim.engine import Plc
from .expr import Expr, ExprError, evaluate
from .model import Expectation, Scenario, Suite, load_suite


@dataclass
class Failure:
    expectation: str
    message: str
    at_ms: int


@dataclass
class ScenarioResult:
    id: str
    title: str
    passed: bool
    failures: list[Failure] = field(default_factory=list)
    end_ms: int = 0
    trace: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.passed:
            return f"PASS {self.id} {self.title}"
        return f"FAIL {self.id} {self.title}: " + "; ".join(f.message for f in self.failures)


class Env:
    def __init__(self, plc: Plc, signals: dict):
        self.plc, self.signals = plc, signals

    def resolve(self, name: str):
        if name in self.signals:
            return self.signals[name]
        try:
            if name.endswith("_value"):
                return self.plc.word(name[: -len("_value")])
            d = dev(name)
        except DeviceError:
            raise ExprError(f"unknown name {name!r} (not a device, *_value, or plant signal)") from None
        return self.plc.word(d) if d.is_word else self.plc.bit(d)

    def value(self, expr: Expr):
        return evaluate(expr, self.resolve)

    def show(self, *exprs: Expr | None) -> str:
        names = sorted({n for e in exprs if e is not None for n in e.names})
        return ", ".join(f"{n}={self.resolve(n)}" for n in names)


class _Check:
    def __init__(self, exp: Expectation):
        self.exp = exp
        self.failure: Failure | None = None
        self.satisfied = False
        self.pending: list[int] = []      # response trigger times awaiting effect
        self.prev_trigger = False

    def fail(self, t: int, message: str) -> None:
        if self.failure is None:
            self.failure = Failure(self.exp.text, message, t)

    def observe(self, t: int, env: Env) -> None:
        e = self.exp
        if self.failure is not None:
            return
        if e.kind in ("always", "never"):
            if t < e.after_ms:
                return
            v = bool(env.value(e.expr))
            if v != (e.kind == "always"):
                self.fail(t, f"expected {e.kind} `{e.expr.text}` but it was {v} at t={t} ms ({env.show(e.expr)})")
        elif e.kind == "eventually":
            if not self.satisfied and t >= e.after_ms and bool(env.value(e.expr)):
                self.satisfied = True
            if not self.satisfied and e.by_ms is not None and t > e.by_ms:
                self.fail(t, f"expected `{e.expr.text}` by {e.by_ms} ms; still false at t={t} ms ({env.show(e.expr)})")
        elif e.kind == "response":
            trig = bool(env.value(e.trigger))
            if trig and not self.prev_trigger:
                self.pending.append(t)
            self.prev_trigger = trig
            if self.pending and bool(env.value(e.effect)):
                self.pending.clear()
            if self.pending and t > self.pending[0] + e.within_ms:
                self.fail(t, f"after `{e.trigger.text}` at t={self.pending[0]} ms, `{e.effect.text}` was not true "
                             f"within {e.within_ms} ms ({env.show(e.trigger, e.effect)})")

    def finish(self, t: int, env: Env) -> None:
        e = self.exp
        if self.failure is not None:
            return
        if e.kind == "eventually" and not self.satisfied:
            by = f"by {e.by_ms} ms" if e.by_ms is not None else "before the end"
            self.fail(t, f"expected `{e.expr.text}` {by}; never true ({env.show(e.expr)})")
        elif e.kind == "at_end" and not bool(env.value(e.expr)):
            self.fail(t, f"expected at end `{e.expr.text}` ({env.show(e.expr)})")
        elif e.kind == "response" and self.pending:
            self.fail(t, f"after `{e.trigger.text}` at t={self.pending[0]} ms, `{e.effect.text}` never became true")


def _apply_set(plc: Plc, values: dict) -> None:
    for name, value in values.items():
        d = dev(name)
        if d.is_word:
            plc.set_word(d, int(value))
        else:
            plc.set_bit(d, bool(value))


def run_scenario(program: Program, scenario: Scenario, plant: str, scan_ms: int = 10,
                 stop_on_fail: bool = True) -> ScenarioResult:
    twin = PLANTS[plant](**scenario.plant)
    plc = Plc(program, scan_ms=scan_ms)
    checks = [_Check(e) for e in scenario.expect]
    overrides: dict[str, bool | int] = {}
    pending = list(enumerate(scenario.stimuli))
    armed: dict[int, int] = {}
    env: Env | None = None
    t = 0
    while plc.now_ms <= scenario.duration_ms:
        t = plc.now_ms
        for idx, s in list(pending):
            if s.at_ms is not None:
                due = t >= s.at_ms
            else:
                if idx not in armed and env is not None and bool(env.value(s.when)):
                    armed[idx] = t
                due = idx in armed and t >= armed[idx] + s.delay_ms
            if due:
                overrides.update(s.set)
                for action, args in s.plant.items():
                    twin.act(action, dict(args or {}))
                pending.remove((idx, s))
        twin.step(plc, scan_ms, t)
        _apply_set(plc, overrides)
        plc.scan()
        env = Env(plc, twin.signals())
        for c in checks:
            c.observe(t, env)
        if stop_on_fail and any(c.failure for c in checks):
            break
    env = env or Env(plc, twin.signals())
    if not (stop_on_fail and any(c.failure for c in checks)):
        for c in checks:
            c.finish(t, env)
    failures = [c.failure for c in checks if c.failure]
    return ScenarioResult(scenario.id, scenario.title, not failures, failures, t, list(scenario.trace))


def load_station_suites(data_dir: str | Path, station: str) -> list[Suite]:
    suites = [load_suite(p) for p in sorted(Path(data_dir, "scenarios").glob("*.yaml"))
              if not p.name.startswith("ce_bindings")]
    return [s for s in suites if s.station == station]


def run_suites(program: Program, suites: list[Suite], stop_on_fail: bool = True,
               ids: set[str] | None = None) -> list[ScenarioResult]:
    results = []
    for suite in suites:
        for sc in suite.scenarios:
            if ids is None or sc.id in ids:
                results.append(run_scenario(program, sc, suite.plant, suite.scan_ms, stop_on_fail))
    return results
