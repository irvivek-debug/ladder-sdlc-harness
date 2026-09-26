import pytest

from ladder_harness.melsec.program import (
    ParseError, UnsupportedInstruction, format_il, parse_il,
)

SEAL = """; Seal-in motor starter
# Motor run with seal-in
LD    X0          ; start PB
OR    Y0
ANI   X1          ; stop PB
OUT   Y0          ; motor contactor
# Run timer
LD    Y0
OUT   T0 K50
LD    T0
OUT   Y1
END
"""


def test_parse_segments_rungs():
    p = parse_il(SEAL)
    assert [len(r.instructions) for r in p.rungs] == [4, 2, 2, 1]
    assert p.rungs[0].statements == ["Motor run with seal-in"]
    assert p.rungs[1].statements == ["Run timer"]
    assert p.header == ["Seal-in motor starter"]
    assert p.rungs[0].instructions[0].comment == "start PB"


def test_round_trip_text_is_canonical():
    t = format_il(parse_il(SEAL))
    assert format_il(parse_il(t)) == t
    assert parse_il(t) == parse_il(SEAL)


def test_continuous_output_stays_in_rung():
    p = parse_il("LD X0\nOUT Y0\nAND X1\nOUT Y1\nEND\n")
    assert len(p.rungs) == 2


def test_block_after_mpp_stays_in_rung():
    text = "LD X0\nMPS\nAND X1\nOUT Y0\nMPP\nLD X2\nOR X3\nANB\nOUT Y1\nEND\n"
    assert len(parse_il(text).rungs) == 2


def test_mcr_and_end_are_standalone_rungs():
    p = parse_il("LD X0\nMC N0 M100\nLD X1\nOUT Y0\nMCR N0\nEND\n")
    assert [r.instructions[0].op for r in p.rungs] == ["LD", "LD", "MCR", "END"]


@pytest.mark.parametrize("text,msg", [
    ("LD X0\nANB\nOUT Y0\n", "ANB"),
    ("LD X0\nLD X1\nOUT Y0\n", "unconsumed"),
    ("LD X0\nMPS\nOUT Y0\n", "MPS"),
    ("AND X0\nOUT Y0\n", "no operation result"),
    ("LD X0\nOUT T0\n", "OUT"),
    ("LD X0\nOUT X1\n", "OUT"),
    ("LD X0\nOUT Y0\nEND\nLD X1\nOUT Y1\n", "after END"),
    ("LD X0\nAND X1\n", "no output"),
])
def test_malformed_programs_raise(text, msg):
    with pytest.raises(ParseError, match=msg):
        parse_il(text)


def test_unsupported_instruction_is_loud():
    with pytest.raises(UnsupportedInstruction, match="ZRST"):
        parse_il("LD X0\nZRST D0 D10\nEND\n")


def test_error_carries_line_number():
    with pytest.raises(ParseError) as e:
        parse_il("LD X0\nOUT Y0\nLD X9\nOUT Y1\n")
    assert e.value.line == 3


def test_reads_and_writes():
    p = parse_il("LD X0\nAND T0\nLD> D100 K30\nORB\nOUT Y0\nMOV D100 D110\nEND\n")
    r = p.rungs[0]
    assert {str(d) for d in r.reads()} == {"X0", "T0", "D100"}
    assert {str(d) for d in r.writes()} == {"Y0", "D110"}


def test_timer_and_arith_operands():
    p = parse_il("LD X0\nOUTH T3 K25\n+ K1 D0\n- D1 D2 D3\nEND\n")
    ops = [i.op for i in p.instructions()]
    assert ops == ["LD", "OUTH", "+", "-", "END"]


def test_branch_without_output_is_rejected():
    with pytest.raises(ParseError, match="MPP branch has no output"):
        parse_il("LD X0\nMPS\nAND X1\nOUT Y1\nMPP\nLD X2\nOUT Y2\nEND\n")
