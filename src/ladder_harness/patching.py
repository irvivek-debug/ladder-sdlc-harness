"""Instruction- and rung-level patches on programs.

Used to derive the legacy programs (golden + seeded defects), eval variants, and to apply model
proposals expressed as patches. Every result is re-validated by printing and re-parsing.
"""
from __future__ import annotations

import copy

from .melsec.program import (
    Instruction, ParseError, Program, Rung, format_il, parse_il, parse_instruction,
)


class PatchError(ValueError):
    """A patch that does not apply exactly as written, or leaves an invalid program."""


def _norm(text: str) -> str:
    return " ".join(text.split()).upper()


def _rungs_by_statement(program: Program, statement: str) -> list[int]:
    return [i for i, r in enumerate(program.rungs) if statement in r.statements]


def _one(indices: list[int], what: str) -> int:
    if len(indices) != 1:
        raise PatchError(f"{what}: expected 1 match, found {len(indices)}")
    return indices[0]


def _parse_rungs(il: str) -> list[Rung]:
    try:
        return parse_il(il).rungs
    except ParseError as e:
        raise PatchError(f"patch IL does not parse: {e}") from None


def _apply_one(program: Program, patch: dict) -> None:
    op = patch["op"]
    if op in ("replace", "remove"):
        find = _norm(patch["find"])
        scope = range(len(program.rungs))
        if "in_rung" in patch:
            scope = [_one(_rungs_by_statement(program, patch["in_rung"]), f"rung {patch['in_rung']!r}")]
        hits = [(ri, ii) for ri in scope for ii, ins in enumerate(program.rungs[ri].instructions)
                if _norm(ins.text()) == find]
        expected = patch.get("expect_count", 1)
        if len(hits) != expected:
            raise PatchError(f"{op} {patch['find']!r}: expected {expected} match(es), found {len(hits)}")
        for ri, ii in reversed(hits):
            rung = program.rungs[ri]
            if op == "remove":
                del rung.instructions[ii]
            else:
                old = rung.instructions[ii]
                try:
                    new = parse_instruction(patch["with"])
                except ParseError as e:
                    raise PatchError(f"replacement {patch['with']!r} does not parse: {e}") from None
                rung.instructions[ii] = Instruction(new.op, new.operands, patch.get("comment", old.comment), old.line)
    elif op == "remove_rung":
        find = _norm(patch["contains"])
        hits = [i for i, r in enumerate(program.rungs) if any(_norm(x.text()) == find for x in r.instructions)]
        _one(hits, f"remove_rung containing {patch['contains']!r}")
        del program.rungs[hits[0]]
    elif op == "replace_rung":
        idx = _one(_rungs_by_statement(program, patch["statement"]), f"rung {patch['statement']!r}")
        program.rungs[idx:idx + 1] = _parse_rungs(patch["il"])
    elif op == "insert_rung_before":
        idx = _one(_rungs_by_statement(program, patch["statement"]), f"rung {patch['statement']!r}")
        program.rungs[idx:idx] = _parse_rungs(patch["il"])
    else:
        raise PatchError(f"unknown patch op {op!r}")


def apply_patches(program: Program, patches: list[dict]) -> Program:
    result = copy.deepcopy(program)
    for patch in patches:
        _apply_one(result, patch)
    result.rungs = [r for r in result.rungs if r.instructions]
    try:
        return parse_il(format_il(result), result.name)
    except ParseError as e:
        raise PatchError(f"patched program is invalid: {e}") from None
