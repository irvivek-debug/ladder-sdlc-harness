"""Deterministic FX5 scan simulator on a virtual clock.

Each scan executes the program rung by rung at time `now_ms`, then advances the clock by `scan_ms`.
Inputs written between scans stand in for the input refresh; outputs read after a scan stand in for
the output refresh. Timer semantics follow JY997D55801 p.132-133 and JY997D55401 p.58-59: the base
comes from the instruction and the current value only updates when the OUT T coil executes, so a
contact read before its coil lags by one scan. MC/MCR follow JY997D55801 p.179.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..melsec.devices import Constant, Device, Operand, dev, parse_operand, wrap16
from ..melsec.program import Instruction, Program, Rung


class SimulationError(RuntimeError):
    """The program did something the simulator cannot represent."""


@dataclass
class TimerState:
    base_ms: int = 100
    acc_ms: int = 0
    last_ms: int = 0
    active: bool = False
    done: bool = False


@dataclass
class CounterState:
    value: int = 0
    done: bool = False


_CMP = {"=": lambda a, b: a == b, "<>": lambda a, b: a != b, ">": lambda a, b: a > b,
        "<": lambda a, b: a < b, ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b}


def _as_device(ref: str | Device) -> Device:
    return ref if isinstance(ref, Device) else dev(ref)


class Plc:
    def __init__(self, program: Program, scan_ms: int = 10):
        if scan_ms <= 0:
            raise ValueError("scan_ms must be positive")
        self.program = program
        self.scan_ms = scan_ms
        self.now_ms = 0
        self.scan_count = 0
        self.bits: dict[Device, bool] = {}
        self.words: dict[Device, int] = {}
        self.timers: dict[int, TimerState] = {}
        self.counters: dict[int, CounterState] = {}
        self._edge: dict[tuple[int, int], bool] = {}
        self._mc: dict[int, bool] = {}

    # ---- device access -------------------------------------------------
    def bit(self, ref: str | Device) -> bool:
        d = _as_device(ref)
        if d.kind == "T":
            return self.timers.get(d.number, TimerState()).done
        if d.kind == "C":
            return self.counters.get(d.number, CounterState()).done
        if d.kind == "SM":
            special = {400: True, 401: False, 402: self.scan_count == 0, 403: self.scan_count > 0}
            if d.number in special:
                return special[d.number]
        if not d.is_bit:
            raise ValueError(f"{d} is not a bit device")
        return self.bits.get(d, False)

    def word(self, ref: str | Operand) -> int:
        o = parse_operand(ref) if isinstance(ref, str) else ref
        if isinstance(o, Constant):
            return o.value
        if o.kind == "T":
            t = self.timers.get(o.number, TimerState())
            return min(t.acc_ms // t.base_ms, 32767)
        if o.kind == "C":
            return self.counters.get(o.number, CounterState()).value
        if not o.is_word:
            raise ValueError(f"{o} is not a word device")
        return self.words.get(o, 0)

    def set_bit(self, ref: str | Device, value: bool) -> None:
        d = _as_device(ref)
        if not d.is_bit or d.kind == "SM":
            raise ValueError(f"{d} cannot be written as an input bit")
        self.bits[d] = bool(value)

    def set_word(self, ref: str | Device, value: int) -> None:
        d = _as_device(ref)
        if not d.is_word:
            raise ValueError(f"{d} is not a word device")
        if not -32768 <= value <= 32767:
            raise ValueError(f"{value} does not fit a 16-bit word ({d})")
        self.words[d] = int(value)

    def snapshot(self) -> dict[str, bool | int]:
        snap: dict[str, bool | int] = {str(d): v for d, v in self.bits.items()}
        snap.update({str(d): v for d, v in self.words.items()})
        for n, t in self.timers.items():
            snap[f"T{n}"] = t.done
            snap[f"T{n}.value"] = min(t.acc_ms // t.base_ms, 32767)
        for n, c in self.counters.items():
            snap[f"C{n}"] = c.done
            snap[f"C{n}.value"] = c.value
        return dict(sorted(snap.items()))

    # ---- execution -----------------------------------------------------
    def scan(self) -> None:
        self._mc = {}
        for r_idx, rung in enumerate(self.program.rungs):
            self._exec_rung(r_idx, rung)
        self.scan_count += 1
        self.now_ms += self.scan_ms

    def run(self, ms: int) -> None:
        end = self.now_ms + ms
        while self.now_ms < end:
            self.scan()

    def _gate(self) -> bool:
        return all(self._mc.values())

    def _exec_rung(self, r_idx: int, rung: Rung) -> None:
        acc: bool | None = None
        blocks: list[bool] = []
        mps: list[bool] = []
        for i_idx, ins in enumerate(rung.instructions):
            key, k = (r_idx, i_idx), ins.spec.kind
            if k in ("load", "and", "or"):
                v = self._contact(key, ins)
                if k == "load":
                    if acc is not None:
                        blocks.append(acc)
                    acc = v
                elif k == "and":
                    acc = bool(acc) and v
                else:
                    acc = bool(acc) or v
            elif ins.op == "ANB":
                acc = blocks.pop() and bool(acc)
            elif ins.op == "ORB":
                acc = blocks.pop() or bool(acc)
            elif ins.op == "MPS":
                mps.append(bool(acc))
            elif ins.op == "MRD":
                acc = mps[-1]
            elif ins.op == "MPP":
                acc = mps.pop()
            elif ins.op == "INV":
                acc = not acc
            elif k == "mc":
                level, coil = ins.operands
                on = bool(acc) and self._gate()
                self._mc[level.level] = on
                self.bits[coil] = on
            elif k == "mcr":
                level = ins.operands[0].level
                self._mc = {n: v for n, v in self._mc.items() if n < level}
            elif k == "end":
                return
            else:
                self._output(key, ins, bool(acc) and self._gate())

    def _contact(self, key: tuple[int, int], ins: Instruction) -> bool:
        s = ins.spec
        if s.cmp:
            a, b = (self.word(o) for o in ins.operands)
            return _CMP[s.cmp](a, b)
        cur = self.bit(ins.operands[0])
        if s.edge:
            prev = self._edge.get(key, False)
            self._edge[key] = cur
            return (cur and not prev) if s.edge == "P" else (prev and not cur)
        return not cur if s.negate else cur

    def _rising(self, key: tuple[int, int], cond: bool) -> bool:
        prev = self._edge.get(key, False)
        self._edge[key] = cond
        return cond and not prev

    def _output(self, key: tuple[int, int], ins: Instruction, cond: bool) -> None:
        s, ops, k = ins.spec, ins.operands, ins.spec.kind
        if k == "out":
            target = ops[0]
            if target.kind == "T":
                self._timer(target.number, ops[1], s.timer_base_ms, cond)
            elif target.kind == "C":
                self._counter(key, target.number, ops[1], cond)
            else:
                self.bits[target] = cond
        elif k == "set":
            if cond:
                self.bits[ops[0]] = True
        elif k == "rst":
            if cond:
                self._reset(ops[0])
        elif k == "pulse":
            prev = self._edge.get(key, False)
            self._edge[key] = cond
            self.bits[ops[0]] = (cond and not prev) if s.edge == "P" else (prev and not cond)
        elif k in ("mov", "add", "sub"):
            if s.pulse:
                if not self._rising(key, cond):
                    return
            elif not cond:
                return
            if k == "mov":
                self._store(ops[1], self.word(ops[0]))
                return
            a, b, dst = (ops[1], ops[0], ops[1]) if len(ops) == 2 else ops
            x, y = self.word(a), self.word(b)
            self._store(dst, x + y if k == "add" else x - y)
        else:
            raise SimulationError(f"no execution rule for {ins.text()}")

    def _timer(self, n: int, preset_op: Operand, base_ms: int, cond: bool) -> None:
        t = self.timers.setdefault(n, TimerState(base_ms=base_ms))
        t.base_ms = base_ms
        if not cond:
            t.active, t.acc_ms, t.done = False, 0, False
            return
        if not t.active:
            t.active, t.acc_ms, t.last_ms = True, 0, self.now_ms
        else:
            t.acc_ms = min(t.acc_ms + self.now_ms - t.last_ms, 32767 * base_ms)
            t.last_ms = self.now_ms
        t.done = t.acc_ms >= self.word(preset_op) * base_ms

    def _counter(self, key: tuple[int, int], n: int, preset_op: Operand, cond: bool) -> None:
        c = self.counters.setdefault(n, CounterState())
        preset = self.word(preset_op)
        if self._rising(key, cond) and c.value < preset:
            c.value += 1
        c.done = c.value >= preset

    def _reset(self, d: Device) -> None:
        if d.kind == "T":
            base = self.timers.get(d.number, TimerState()).base_ms
            self.timers[d.number] = TimerState(base_ms=base)
        elif d.kind == "C":
            self.counters[d.number] = CounterState()
        elif d.kind == "D":
            self.words[d] = 0
        else:
            self.bits[d] = False

    def _store(self, d: Device, value: int) -> None:
        self.words[d] = wrap16(value)
