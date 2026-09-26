"""The SAFETY guard and the apply gate. Deterministic: no model ever decides whether a SAFETY rung changes.

R1  every old rung that writes a SAFETY device must survive unchanged (instruction for instruction);
R2  no new or modified rung may write a SAFETY device;
R3  the multiset of instructions that reference a SAFETY device must not shrink (no dropping E-stop checks).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from ..iolist import IoList
from ..lint import lint
from ..melsec.devices import Device
from ..melsec.program import ParseError, Program, Rung, parse_il
from ..scenarios.model import Suite
from ..scenarios.runner import ScenarioResult, run_suites


@dataclass
class GuardVerdict:
    allowed: bool
    reasons: list[str]


@dataclass
class GateResult:
    allowed: bool
    stage: str              # parse | guard | lint | scenarios | passed
    reasons: list[str]
    results: list[ScenarioResult] = field(default_factory=list)
    program: Program | None = None


def _key(rung: Rung) -> tuple[str, ...]:
    return tuple(i.text() for i in rung.instructions)


def check_patch(old: Program, new: Program, safety: set[Device]) -> GuardVerdict:
    reasons: list[str] = []
    old_locked = [r for r in old.rungs if r.writes() & safety]
    available = Counter(_key(r) for r in new.rungs)
    for r in old_locked:
        k = _key(r)
        if available[k]:
            available[k] -= 1
        else:
            reasons.append(f"locked SAFETY rung changed or removed: {' / '.join(k)}")
    locked_keys = Counter(_key(r) for r in old_locked)
    for r in new.rungs:
        hit = r.writes() & safety
        if not hit:
            continue
        k = _key(r)
        if locked_keys[k]:
            locked_keys[k] -= 1
        else:
            devs = ", ".join(sorted(str(d) for d in hit))
            reasons.append(f"new or modified rung writes SAFETY device(s) {devs}: {' / '.join(k)}")

    def refs(p: Program) -> Counter:
        return Counter(i.text() for i in p.instructions() if set(i.devices()) & safety)

    for text, n in sorted((refs(old) - refs(new)).items()):
        reasons.append(f"removes SAFETY reference `{text}`" + (f" ({n}×)" if n > 1 else ""))
    return GuardVerdict(not reasons, reasons)


def _lint_errors(program: Program, iolist: IoList | None) -> dict[tuple, str]:
    return {(f.rule, f.devices): f"{f.rule}: {f.message}" for f in lint(program, iolist) if f.severity == "error"}


def gate(new_text: str, old: Program, safety: set[Device], suites: list[Suite],
         iolist: IoList | None = None, known_failures: frozenset[str] | set[str] = frozenset(),
         targets: frozenset[str] | set[str] = frozenset()) -> GateResult:
    """Parse → guard → no new lint errors → scenarios. Stops at the first failing stage.

    A candidate passes the scenario stage when every scenario in `targets` passes and nothing fails
    that was not already failing on the old program (`known_failures`): fix what you were asked to,
    break nothing that worked.
    """
    try:
        new = parse_il(new_text, old.name)
    except ParseError as e:
        return GateResult(False, "parse", [str(e)])
    verdict = check_patch(old, new, safety)
    if not verdict.allowed:
        return GateResult(False, "guard", verdict.reasons, program=new)
    old_errors, new_errors = _lint_errors(old, iolist), _lint_errors(new, iolist)
    introduced = [msg for key, msg in new_errors.items() if key not in old_errors]
    if introduced:
        return GateResult(False, "lint", introduced, program=new)
    results = run_suites(new, suites, stop_on_fail=True)
    failed = {r.id: r for r in results if not r.passed}
    regressions = [failed[i].summary() for i in sorted(set(failed) - set(known_failures))]
    unfixed = [failed[i].summary() for i in sorted(set(failed) & set(targets))]
    if regressions or unfixed:
        reasons = [f"REGRESSION {r}" for r in regressions] + [f"TARGET STILL FAILING {r}" for r in unfixed]
        return GateResult(False, "scenarios", reasons, results, new)
    return GateResult(True, "passed", [], results, new)
