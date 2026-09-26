"""GX Works3 ladder CSV ("listed instructions") and device-comment CSV.

Layout per GX Works3 Operating Manual SH(NA)-081215ENG-AN §6.3 (pp.300-306): row 1 the project
name; row 2 'Module Type Information:' and the module; row 3 a 7-column header; export is UTF-16LE
with BOM, tab-delimited, every item double-quoted, CRLF. Import accepts tab or comma and ignores
columns 8+; multi-operand instructions may use any of four layouts (p.302). We write all operands in
the I/O (Device) column, one of those accepted layouts — which layout GX Works3 itself exports is
UNVERIFIED. 'Step No.' is written as a sequence number, not FX5 program steps. The module-type text
for FX5U and the device-comment CSV preamble/encoding (§6.8) are UNVERIFIED; comment files use
'Device Name' + 'Comment' headers, which GX Works3 matches by name. Nothing produced here has yet
been imported into a real GX Works3 — label outputs accordingly.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

from .devices import dev
from .program import ParseError, Program, parse_il

HEADER = ["Step No.", "Line Statement", "Instruction", "I/O (Device)", "Blank", "P/I Statement", "Note"]


def _encode(rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    csv.writer(buf, delimiter="\t", quoting=csv.QUOTE_ALL, lineterminator="\r\n").writerows(rows)
    return b"\xff\xfe" + buf.getvalue().encode("utf-16-le")


def _decode(data: bytes) -> list[list[str]]:
    if data.startswith(b"\xff\xfe"):
        text = data[2:].decode("utf-16-le")
    elif data.startswith(b"\xfe\xff"):
        text = data[2:].decode("utf-16-be")
    elif data.startswith(b"\xef\xbb\xbf"):
        text = data[3:].decode("utf-8")
    else:
        text = data.decode("utf-8")
    delimiter = "\t" if "\t" in text else ","
    return list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))


def program_to_csv_bytes(program: Program, project: str = "LadderHarness", module_type: str = "FX5U") -> bytes:
    rows = [[project], ["Module Type Information:", module_type], HEADER]
    step = 0
    for rung in program.rungs:
        for statement in rung.statements:
            rows.append([str(step), statement, "", "", "", "", ""])
        for ins in rung.instructions:
            rows.append([str(step), "", ins.op, " ".join(map(str, ins.operands)), "", "", ins.comment])
            step += 1
    return _encode(rows)


def program_from_csv_bytes(data: bytes, name: str = "program") -> Program:
    rows = _decode(data)
    start = next((i + 1 for i, r in enumerate(rows) if r and r[0].strip() == "Step No."), 3)
    entries: list[list[str]] = []  # [kind, text, note]
    for rowno, row in enumerate(rows[start:], start=start + 1):
        _, stmt, instr, io_, _, _, note = [c.strip() for c in (row + [""] * 7)[:7]]
        if stmt:
            entries.append(["#", stmt.lstrip("*").strip(), ""])
        if instr.startswith(";"):
            entries.append(["#", instr[1:].strip(), ""])
        elif instr:
            entries.append(["i", f"{instr} {io_}".strip(), note])
        elif io_ or note:
            if not entries or entries[-1][0] != "i":
                raise ParseError(rowno, "CSV row has operands or a note but no instruction before it")
            if io_:
                entries[-1][1] += f" {io_}"
            if note:
                entries[-1][2] = f"{entries[-1][2]} {note}".strip()
    lines = [f"# {t}" if k == "#" else (f"{t} ; {n}" if n else t) for k, t, n in entries]
    return parse_il("\n".join(lines) + "\n", name)


def comments_to_csv_bytes(comments: dict[str, str]) -> bytes:
    rows = [["Device Name", "Comment"]]
    rows += [[str(dev(d)), c] for d, c in sorted(comments.items(), key=lambda kv: dev(kv[0]))]
    return _encode(rows)


def comments_from_csv_bytes(data: bytes) -> dict[str, str]:
    rows = _decode(data)
    hdr = next(i for i, r in enumerate(rows) if r and r[0].strip() == "Device Name")
    names = [c.strip() for c in rows[hdr]]
    col = names.index("Comment") if "Comment" in names else 1
    out: dict[str, str] = {}
    for row in rows[hdr + 1:]:
        if row and row[0].strip():
            out[str(dev(row[0]))] = row[col].strip() if col < len(row) else ""
    return out


def write_program_csv(program: Program, path: str | Path, **kw) -> None:
    Path(path).write_bytes(program_to_csv_bytes(program, **kw))


def read_program_csv(path: str | Path) -> Program:
    p = Path(path)
    return program_from_csv_bytes(p.read_bytes(), name=p.stem)
