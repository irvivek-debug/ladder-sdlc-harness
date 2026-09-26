"""Model packets: the plant data a model sees, built from plant_data/ only — never the sealed answer key."""
from __future__ import annotations

import csv
import io
from pathlib import Path

from ..cell import Cell
from ..lint import lint
from ..melsec.program import Program, format_il, format_instruction

ORDER = ("io_list", "parameters", "cause_effect", "narrative", "device_comments", "lint", "program", "program_il")


def numbered_listing(program: Program) -> str:
    lines = []
    for i, rung in enumerate(program.rungs, start=1):
        for s in rung.statements:
            lines.append(f"      # {s}")
        for j, ins in enumerate(rung.instructions):
            tag = f"R{i:<3} " if j == 0 else "     "
            lines.append(f"{tag} {format_instruction(ins)}")
    return "\n".join(lines)


def _csv_rows(path: Path, keep) -> str:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), lineterminator="\n")
    w.writeheader()
    w.writerows(r for r in rows if keep(r))
    return buf.getvalue().strip()


def build_packet(cell: Cell, station: str, parts: tuple[str, ...], program: Program | None = None,
                 comments: dict[str, str] | None = None) -> str:
    """Tagged data blocks in a fixed order (stable prefix → cache-friendly)."""
    data_dir = cell.data_dir
    if cell.key_dir is not None and data_dir.resolve() == cell.key_dir.resolve():
        raise ValueError("refusing to build a packet from the answer key")
    program = program or cell.program(station)
    blocks = []
    for part in ORDER:
        if part not in parts:
            continue
        if part == "io_list":
            body = _csv_rows(data_dir / "io_list.csv", lambda r: r["station"] in (station, "CELL"))
        elif part == "parameters":
            body = _csv_rows(data_dir / "parameters.csv", lambda r: r["station"] == station)
        elif part == "cause_effect":
            body = _csv_rows(data_dir / "cause_effect.csv", lambda r: r["station"] == station)
        elif part == "narrative":
            body = (data_dir / "narrative.md").read_text(encoding="utf-8").strip()
        elif part == "device_comments":
            shown = comments if comments is not None else cell.legacy_comments(station)
            body = "\n".join(f"{d},{c}" for d, c in shown.items()) or "(none)"
        elif part == "lint":
            body = "\n".join(f"{f.rule} {f.severity} rung {f.rung or '-'}: {f.message}"
                             for f in lint(program, cell.iolist) if f.rule != "L008") or "(no findings)"
        elif part == "program":
            body = numbered_listing(program)
        else:
            body = format_il(program).strip()
        blocks.append(f'<{part} station="{station}">\n{body}\n</{part}>')
    return "\n\n".join(blocks)
