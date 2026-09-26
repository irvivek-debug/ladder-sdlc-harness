import pytest

from ladder_harness.melsec.gxw3_csv import (
    HEADER, comments_from_csv_bytes, comments_to_csv_bytes,
    program_from_csv_bytes, program_to_csv_bytes,
)
from ladder_harness.melsec.program import format_il, parse_il

PROG = """# [Title]Seal-in
LD    X0          ; start PB
OR    Y0
ANI   X1
OUT   Y0          ; motor; contactor K1
LD    Y0
OUT   T0 K50
MOV   K30 D100
END
"""


def test_export_encoding_and_preamble():
    data = program_to_csv_bytes(parse_il(PROG), project="ST20", module_type="FX5U")
    assert data[:2] == b"\xff\xfe"
    text = data[2:].decode("utf-16-le")
    lines = text.split("\r\n")
    assert lines[0] == '"ST20"'
    assert lines[1] == '"Module Type Information:"\t"FX5U"'
    assert lines[2] == "\t".join(f'"{h}"' for h in HEADER)
    assert '"OUT"\t"T0 K50"' in text
    assert text.rstrip("\r\n").endswith('"END"\t""\t""\t""\t""')


def test_program_round_trip():
    p = parse_il(PROG)
    back = program_from_csv_bytes(program_to_csv_bytes(p))
    assert format_il(back) == format_il(p)


PRE = ("P\nModule Type Information:,FX5U\n"
       "Step No.,Line Statement,Instruction,I/O (Device),Blank,P/I Statement,Note\n")


@pytest.mark.parametrize("body", [
    "0,,LD,X0,,,\n1,,MOV,D0,,,\n2,,,D1,,,\n3,,END,,,,\n",
    "0,,LD X0,,,,\n1,,MOV D0 D1,,,,\n2,,END,,,,\n",
    "0,,LD,X0,,,\n1,,MOV,D0 D1,,,\n2,,END,,,,\n",
    "0,,LD,X0,,,\n1,,MOV D0,D1,,,\n2,,END,,,,\n",
])
def test_import_accepts_all_four_manual_layouts(body):
    p = program_from_csv_bytes((PRE + body).encode("utf-8"))
    assert [i.text() for i in p.instructions()] == ["LD X0", "MOV D0 D1", "END"]


def test_note_on_continuation_row_attaches_to_instruction():
    body = "0,,LD,X0,,,\n1,,OUT,Y0,,,\n2,,,,,,motor run\n3,,END,,,,\n"
    p = program_from_csv_bytes((PRE + body).encode("utf-8"))
    assert p.rungs[0].instructions[1].comment == "motor run"


def test_comment_csv_round_trip():
    comments = {"X20": "PB-2001 cycle start", "D100": "PT-2001 pressure kPa x100", "Y21": "XV-2003 fill"}
    data = comments_to_csv_bytes(comments)
    assert data[:2] == b"\xff\xfe"
    assert comments_from_csv_bytes(data) == comments
