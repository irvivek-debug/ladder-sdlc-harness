"""`.il` programs: parse, segment into rungs, validate structure, print canonically.

Format: one instruction per line; `;` starts an inline comment (a whole-line `;` comment is a header
line before the first instruction, a rung statement after it); `#` lines are rung statements (GX Works3
line statements); blank lines are ignored. Rungs are inferred: MCR and END stand alone; a load after an
output starts a new rung unless the MPS stack is open or a later ANB/ORB consumes the prior result.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

from .devices import Device, DeviceError, Operand, parse_operand
from .instructions import (
    CONTACT_KINDS, OUTPUT_KINDS, SPECS, STANDALONE_KINDS, Spec, check_operands,
)


class ParseError(ValueError):
    def __init__(self, line: int, message: str):
        super().__init__(f"line {line}: {message}")
        self.line = line
        self.message = message


class UnsupportedInstruction(ParseError):
    """An instruction outside the supported FX5 subset. Never silently skipped."""


@dataclass(frozen=True)
class Instruction:
    op: str
    operands: tuple[Operand, ...] = ()
    comment: str = field(default="", compare=False)
    line: int = field(default=0, compare=False)

    @property
    def spec(self) -> Spec:
        return SPECS[self.op]

    def text(self) -> str:
        return " ".join([self.op, *map(str, self.operands)])

    def devices(self) -> list[Device]:
        return [o for o in self.operands if isinstance(o, Device)]

    def __str__(self) -> str:
        return self.text()


@dataclass
class Rung:
    instructions: list[Instruction]
    statements: list[str] = field(default_factory=list)

    def writes(self) -> set[Device]:
        out: set[Device] = set()
        for ins in self.instructions:
            k, devs = ins.spec.kind, ins.devices()
            if k in ("out", "set", "rst", "pulse", "mc") and devs:
                out.add(devs[0] if k != "mc" else devs[-1])
            elif k in ("mov", "add", "sub"):
                out.add(devs[-1])
        return out

    def reads(self) -> set[Device]:
        out: set[Device] = set()
        for ins in self.instructions:
            k, devs = ins.spec.kind, ins.devices()
            if k in CONTACT_KINDS:
                out.update(devs)
            elif k in ("mov", "add", "sub"):
                srcs = ins.operands[:-1]
                if k != "mov" and len(ins.operands) == 2:
                    srcs = ins.operands  # "+ S D" reads D as well
                out.update(o for o in srcs if isinstance(o, Device))
            elif k == "out" and len(devs) == 2:
                out.add(devs[1])  # D register preset
        return out


@dataclass
class Program:
    name: str
    rungs: list[Rung]
    header: list[str] = field(default_factory=list)

    def instructions(self) -> Iterator[Instruction]:
        for rung in self.rungs:
            yield from rung.instructions


def _consumes_prior(items: list[tuple[Instruction, list[str]]], idx: int) -> bool:
    """True if the load at idx is later ANB/ORB-combined with the result before it."""
    depth = 1
    for ins, _ in items[idx + 1:]:
        k = ins.spec.kind
        if k == "load":
            depth += 1
        elif ins.op in ("ANB", "ORB"):
            depth -= 1
            if depth == 0:
                return True
        elif k in OUTPUT_KINDS or k in STANDALONE_KINDS:
            return False
    return False


def _segment(items: list[tuple[Instruction, list[str]]]) -> list[Rung]:
    rungs: list[Rung] = []
    cur: list[Instruction] = []
    statements: list[str] = []
    has_output, mps = False, 0

    def close() -> None:
        nonlocal cur, statements, has_output, mps
        if cur:
            rungs.append(Rung(cur, statements))
        cur, statements, has_output, mps = [], [], False, 0

    for idx, (ins, pending) in enumerate(items):
        k = ins.spec.kind
        if k in STANDALONE_KINDS:
            close()
        elif k == "load" and cur and has_output and mps == 0 and not _consumes_prior(items, idx):
            close()
        statements.extend(pending)
        cur.append(ins)
        if k in OUTPUT_KINDS:
            has_output = True
        if ins.op == "MPS":
            mps += 1
        elif ins.op == "MPP":
            mps -= 1
        if k in STANDALONE_KINDS:
            close()
    close()
    return rungs


def _validate_rung(rung: Rung) -> None:
    depth, mps, outputs = 0, 0, 0
    open_branch: Instruction | None = None      # MPS/MRD/MPP not yet followed by an output
    for ins in rung.instructions:
        k, op, line = ins.spec.kind, ins.op, ins.line
        if k == "load":
            depth += 1
        elif k in ("and", "or") or op in ("MPS", "INV"):
            if depth < 1:
                raise ParseError(line, f"{op} has no operation result to work on")
            if op == "MPS":
                mps += 1
                open_branch = ins
                if mps > 16:
                    raise ParseError(line, "MPS nested deeper than 16")
        elif op in ("ANB", "ORB"):
            if depth < 2:
                raise ParseError(line, f"{op} needs two logic blocks")
            depth -= 1
        elif op in ("MRD", "MPP"):
            if mps < 1:
                raise ParseError(line, f"{op} without a preceding MPS")
            if op == "MPP":
                mps -= 1
            open_branch = ins
        elif k in OUTPUT_KINDS:
            if depth == 0:
                raise ParseError(line, f"{ins.text()} has no operation result to work on")
            if depth > 1:
                raise ParseError(line, f"unconsumed LD block before {ins.text()} (missing ANB/ORB)")
            outputs += 1
            open_branch = None
    last = rung.instructions[-1]
    if mps:
        raise ParseError(last.line, "MPS without a matching MPP in this rung")
    if open_branch is not None:
        raise ParseError(open_branch.line, f"{open_branch.op} branch has no output after it")
    if not outputs and last.spec.kind not in STANDALONE_KINDS:
        raise ParseError(last.line, "rung has no output instruction")


def parse_instruction(text: str, line: int = 0) -> Instruction:
    """Parse one instruction line (`OP operands ; comment`) without rung-structure checks."""
    code, _, comment = text.strip().partition(";")
    tokens = code.split()
    if not tokens:
        raise ParseError(line, "empty instruction")
    op = tokens[0].upper()
    if op not in SPECS:
        raise UnsupportedInstruction(line, f"{tokens[0]!r} is not in the supported FX5 subset")
    try:
        operands = tuple(parse_operand(t) for t in tokens[1:])
        check_operands(SPECS[op], operands)
    except (DeviceError, ValueError) as e:
        raise ParseError(line, f"{op}: {e}") from None
    return Instruction(op, operands, comment.strip(), line)


def parse_il(text: str, name: str = "program") -> Program:
    header: list[str] = []
    pending: list[str] = []
    items: list[tuple[Instruction, list[str]]] = []
    ended = False
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            pending.append(line[1:].strip())
            continue
        if line.startswith(";"):
            (pending if items or pending else header).append(line[1:].strip())
            continue
        if ended:
            raise ParseError(lineno, f"{line.split()[0].upper()} appears after END")
        ins = parse_instruction(line, lineno)
        items.append((ins, pending))
        pending = []
        ended = ins.op == "END"
    rungs = _segment(items)
    for rung in rungs:
        _validate_rung(rung)
    return Program(name, rungs, header)


def format_instruction(ins: Instruction) -> str:
    body = f"{ins.op:<6} {' '.join(map(str, ins.operands))}".rstrip()
    return f"{body:<24}; {ins.comment}" if ins.comment else body


def format_il(program: Program) -> str:
    out = [f"; {h}".rstrip() for h in program.header]
    if out:
        out.append("")
    for i, rung in enumerate(program.rungs):
        if i:
            out.append("")
        out += [f"# {s}".rstrip() for s in rung.statements]
        out += [format_instruction(x) for x in rung.instructions]
    return "\n".join(out) + "\n"
