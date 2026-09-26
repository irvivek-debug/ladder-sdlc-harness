"""Mutation testing of a scenario suite: are the tests strong enough to judge a changed program?

Each mutant is the reference program with one small, plausible defect. A mutant is *killed* when at least one
scenario fails. A high kill rate is the evidence that "all scenarios pass" means something when an AI proposes
a change. Survivors are either equivalent (no observable difference) or a missing test.
"""
from __future__ import annotations

import copy
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field

from ..melsec.devices import Constant, Device
from ..melsec.program import Instruction, ParseError, Program, format_il, parse_il, parse_instruction
from .model import Suite
from .runner import run_suites

NEG = {"LD": "LDI", "LDI": "LD", "AND": "ANI", "ANI": "AND", "OR": "ORI", "ORI": "OR"}
CMP_SWAP = {">": ">=", ">=": ">", "<": "<=", "<=": "<", "=": "<>", "<>": "="}
EDGE_DROP = {"LDP": "LD", "LDF": "LD", "ANDP": "AND", "ANDF": "AND", "ORP": "OR", "ORF": "OR"}


@dataclass
class Mutant:
    id: str
    operator: str
    description: str
    program: Program


@dataclass
class MutationReport:
    total: int
    killed: int
    invalid: int
    survivors: list[Mutant] = field(default_factory=list)
    killed_by: dict[str, str] = field(default_factory=dict)

    @property
    def score(self) -> float:
        return self.killed / self.total if self.total else 1.0

    def summary(self) -> str:
        lines = [f"mutation score {self.killed}/{self.total} = {self.score:.1%} (invalid mutants skipped: {self.invalid})"]
        lines += [f"  survivor {m.id}: {m.description}" for m in self.survivors]
        return "\n".join(lines)


def _with(program: Program, r: int, i: int, new: Instruction | None) -> Program:
    p = copy.deepcopy(program)
    if new is None:
        del p.rungs[r].instructions[i]
    else:
        p.rungs[r].instructions[i] = new
    return p


def _replace(ins: Instruction, text: str) -> Instruction:
    n = parse_instruction(text)
    return Instruction(n.op, n.operands, ins.comment, ins.line)


def _candidates(program: Program):
    timers = sorted({o.number for x in program.instructions() for o in x.operands
                     if isinstance(o, Device) and o.kind == "T"})
    for r, rung in enumerate(program.rungs):
        for i, ins in enumerate(rung.instructions):
            op, ops, k = ins.op, ins.operands, ins.spec.kind
            loc = f"rung {r + 1} `{ins.text()}`"
            if op in NEG:
                yield "NEG", f"{loc} -> {NEG[op]}", _with(program, r, i, Instruction(NEG[op], ops, ins.comment, ins.line))
            if k in ("and", "or") and i > 0:
                yield "DROP", f"{loc} removed", _with(program, r, i, None)
            if op in EDGE_DROP:
                yield "EDGE", f"{loc} -> {EDGE_DROP[op]}", _with(program, r, i, Instruction(EDGE_DROP[op], ops, ins.comment, ins.line))
            if ins.spec.cmp:
                prefix = op[: -len(ins.spec.cmp)]
                new_op = prefix + CMP_SWAP[ins.spec.cmp]
                yield "CMP", f"{loc} -> {new_op}", _with(program, r, i, Instruction(new_op, ops, ins.comment, ins.line))
            if op in ("SET", "RST") and ops[0].kind in ("Y", "M", "L"):
                other = "RST" if op == "SET" else "SET"
                yield "SETRST", f"{loc} -> {other}", _with(program, r, i, Instruction(other, ops, ins.comment, ins.line))
            if k == "out" and len(ops) == 2 and isinstance(ops[1], Constant) and ops[1].value > 1:
                for factor, label in ((2, "x2"), (0.5, "/2")):
                    v = max(1, int(ops[1].value * factor))
                    yield "PRESET", f"{loc} preset {label}", _with(
                        program, r, i, _replace(ins, f"{op} {ops[0]} K{v}"))
            if k in ("load", "and", "or") and ops and isinstance(ops[0], Device) and ops[0].kind == "T" and len(timers) > 1:
                n = ops[0].number
                other = timers[(timers.index(n) + 1) % len(timers)]
                yield "TIMER", f"{loc} -> T{other}", _with(program, r, i, _replace(ins, f"{op} T{other}"))


def mutants(program: Program) -> tuple[list[Mutant], int]:
    out, invalid = [], 0
    for n, (operator, desc, mutated) in enumerate(_candidates(program)):
        try:
            valid = parse_il(format_il(mutated), program.name)
        except ParseError:
            invalid += 1
            continue
        out.append(Mutant(f"M{n:03d}", operator, desc, valid))
    return out, invalid


def _kill(args) -> tuple[str, str | None]:
    mutant, suites = args
    for result in run_suites(mutant.program, suites, stop_on_fail=True):
        if not result.passed:
            return mutant.id, result.id
    return mutant.id, None


def score(program: Program, suites: list[Suite], processes: int = 1) -> MutationReport:
    muts, invalid = mutants(program)
    jobs = [(m, suites) for m in muts]
    outcomes = None
    if processes > 1:
        try:
            with ProcessPoolExecutor(max_workers=processes) as pool:
                outcomes = list(pool.map(_kill, jobs, chunksize=4))
        except PermissionError:   # sandboxes that forbid POSIX semaphores: fall back to serial
            outcomes = None
    if outcomes is None:
        outcomes = [_kill(j) for j in jobs]
    by_id = {m.id: m for m in muts}
    killed_by = {mid: sid for mid, sid in outcomes if sid}
    survivors = [by_id[mid] for mid, sid in outcomes if not sid]
    return MutationReport(len(muts), len(killed_by), invalid, survivors, killed_by)
