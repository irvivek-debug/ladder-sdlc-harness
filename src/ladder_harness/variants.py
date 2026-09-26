"""Build program variants: golden + chosen seeded defects, documentation stripped the way legacy is.

Used by scripts/build_data.py (the legacy programs) and by the evals (single- and multi-defect variants), so
every variant a model sees looks like the legacy it would meet in the plant.
"""
from __future__ import annotations

from .cell import Cell
from .melsec.devices import dev
from .melsec.program import Instruction, Program, format_il, parse_il
from .patching import apply_patches


def used_devices(program: Program) -> list[str]:
    return sorted({str(d) for i in program.instructions() for d in i.devices()}, key=dev)


def legacy_comments(station: str, program: Program, golden: dict[str, str], realism: dict) -> dict[str, str]:
    keep = realism["comment_keep"]
    used = used_devices(program)
    chosen = {d for i, d in enumerate(used) if i % 5 in (0, 2)} | set(keep["forced"].get(station, []))
    out = {}
    for d in used:
        if d in chosen:
            text = realism["legacy_comment_overrides"].get(d, golden.get(d, ""))
            if text:
                out[d] = text
    rt = realism["red_team"]
    if rt["station"] == station and rt["device"] in used:
        out[rt["device"]] = " ".join(rt["text"].split())
    return out


def strip_documentation(program: Program, comments: dict[str, str], header: list[str]) -> Program:
    for rung in program.rungs:
        rung.statements = []
        rung.instructions = [Instruction(i.op, i.operands,
                                         comments.get(str(i.devices()[0]), "") if i.devices() else "", i.line)
                             for i in rung.instructions]
    program.header = list(header)
    return parse_il(format_il(program), program.name)


def make_variant(cell: Cell, station: str, defect_ids: list[str] | tuple[str, ...]) -> tuple[Program, dict[str, str]]:
    """Golden + defects, stripped like legacy. Returns (program, device comments). Needs the answer key."""
    golden = cell.golden(station)
    patched = golden
    for d in defect_ids:
        if cell.defects[d]["station"] != station:
            raise ValueError(f"{d} belongs to {cell.defects[d]['station']}, not {station}")
        patched = apply_patches(patched, cell.defects[d]["patches"])
    comments = legacy_comments(station, patched, cell.golden_comments, cell.realism)
    header = cell.realism["legacy_header"].get(station, [f"{station} (FX5U)"])
    return strip_documentation(patched, comments, header), comments
