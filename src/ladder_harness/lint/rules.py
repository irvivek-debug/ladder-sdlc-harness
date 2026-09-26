"""Deterministic lint rules — the $0 horse. Rung numbers in messages are 1-based."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ..iolist import IoList
from ..melsec.devices import Device
from ..melsec.program import Program

# FX3U/FX3UC timer device ranges and their time base (JY997D16601 p.88).
FX3_TIMER_RANGES = [(0, 200, 100, ""), (200, 246, 10, ""), (246, 250, 1, " retentive"),
                    (250, 256, 100, " retentive"), (256, 512, 1, "")]


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str          # error | warning | info
    message: str
    rung: int | None = None
    line: int = 0
    devices: tuple[str, ...] = ()


def _rungs_text(nums: list[int]) -> str:
    nums = [str(n) for n in nums]
    return nums[0] if len(nums) == 1 else f"{', '.join(nums[:-1])} and {nums[-1]}"


def _fx3_base(n: int) -> tuple[int, str]:
    for lo, hi, base, note in FX3_TIMER_RANGES:
        if lo <= n < hi:
            return base, note
    return 100, ""


def lint(program: Program, iolist: IoList | None = None, comments: dict[str, str] | None = None) -> list[Finding]:
    out: list[Finding] = []
    coil_rungs: dict[Device, list[int]] = defaultdict(list)
    timer_coils: dict[int, list[int]] = defaultdict(list)
    timer_reads: dict[int, list[int]] = defaultdict(list)
    used: set[Device] = set()

    for r_no, rung in enumerate(program.rungs, start=1):
        for ins in rung.instructions:
            used.update(ins.devices())
            k, ops = ins.spec.kind, ins.operands
            if k == "out":
                target = ops[0]
                if target.kind == "T":
                    timer_coils[target.number].append(r_no)
                    base_fx5 = ins.spec.timer_base_ms
                    base_fx3, note = _fx3_base(target.number)
                    preset = getattr(ops[1], "value", None)
                    if target.number >= 200 and base_fx3 != base_fx5 and preset is not None:
                        out.append(Finding(
                            "L002", "warning",
                            f"{ins.text()}: on FX3U, T{target.number} is a {base_fx3} ms{note} timer "
                            f"({preset * base_fx3 / 1000:g} s); on FX5, {ins.op} sets a {base_fx5} ms base "
                            f"({preset * base_fx5 / 1000:g} s). Migration check: confirm the intended time.",
                            r_no, ins.line, (str(target),)))
                elif target.kind != "C":
                    coil_rungs[target].append(r_no)
            for o in ops:
                if isinstance(o, Device) and o.kind == "T" and (k in ("load", "and", "or")):
                    timer_reads[o.number].append(r_no)

    for d, rungs in sorted(coil_rungs.items()):
        distinct = sorted(set(rungs))
        if len(distinct) > 1:
            out.append(Finding("L001", "error",
                               f"{d} is driven by OUT in rungs {_rungs_text(distinct)}; the last rung wins every "
                               f"scan, so the earlier logic has no effect (double coil).",
                               distinct[-1], 0, (str(d),)))
    for n, rungs in sorted(timer_coils.items()):
        if len(rungs) > 1:
            out.append(Finding("L009", "error", f"T{n} has coils in rungs {_rungs_text(rungs)}; drive a timer "
                               f"from one coil only (JY997D55401 p.59).", rungs[-1], 0, (f"T{n}",)))
        first_coil = min(rungs)
        early = sorted({r for r in timer_reads.get(n, []) if r < first_coil})
        if early:
            out.append(Finding("L003", "info", f"T{n} is read in rung {_rungs_text(early)} before its coil in rung "
                               f"{first_coil}; the contact lags by one scan.", early[0], 0, (f"T{n}",)))

    if not program.rungs or program.rungs[-1].instructions[-1].op != "END":
        out.append(Finding("L006", "error", "program does not end with END", None, 0))

    if iolist is not None:
        declared = iolist.io_devices()
        for d in sorted(x for x in used if x.kind in ("X", "Y") and x not in declared):
            out.append(Finding("L004", "warning", f"{d} is used but not in the I/O list", None, 0, (str(d),)))
        for d in sorted(x for x in declared if x.kind in ("X", "Y") and x not in used):
            p = iolist.by_device[d]
            out.append(Finding("L005", "info", f"{d} ({p.tag}) is in the I/O list but never used"
                               + (f" — {p.notes or p.description}" if (p.notes or p.description) else ""),
                               None, 0, (str(d),)))
        safety = iolist.safety_devices()
        for r_no, rung in enumerate(program.rungs, start=1):
            hit = sorted(str(d) for d in rung.writes() & safety)
            if hit:
                out.append(Finding("L007", "info", f"rung {r_no} writes SAFETY device(s) {', '.join(hit)}: "
                                   f"locked against AI edits", r_no, 0, tuple(hit)))

    if comments is not None:
        missing = sorted(str(d) for d in used if str(d) not in comments or not comments[str(d)].strip())
        pct = round(100 * (len(used) - len(missing)) / len(used)) if used else 100
        out.append(Finding("L008", "info", f"{len(missing)} of {len(used)} devices have no comment "
                           f"({pct}% documented)", None, 0, tuple(missing)))
    return out
