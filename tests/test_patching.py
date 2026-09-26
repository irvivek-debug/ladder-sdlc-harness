import pytest

from ladder_harness.melsec.program import format_il, parse_il
from ladder_harness.patching import PatchError, apply_patches

BASE = "# A\nLD X0\nAND X1\nOUT Y0\n# B\nLD X2\nOUT T0 K5\nLD T0\nOUT Y1\nEND\n"


def test_replace_and_remove():
    p = apply_patches(parse_il(BASE), [
        {"op": "replace", "find": "OUT T0 K5", "with": "OUT T200 K50"},
        {"op": "remove", "find": "AND X1", "in_rung": "A"},
    ])
    text = format_il(p)
    assert "OUT    T200 K50" in text and "AND    X1" not in text


def test_expect_count_enforced():
    with pytest.raises(PatchError, match="expected 1"):
        apply_patches(parse_il(BASE), [{"op": "replace", "find": "LD X9", "with": "LD X1"}])


def test_rung_ops():
    p = apply_patches(parse_il(BASE), [
        {"op": "replace_rung", "statement": "A", "il": "# A2\nLD X0\nOUT Y0\n"},
        {"op": "insert_rung_before", "statement": "B", "il": "# M\nLD X3\nOUT Y3\n"},
        {"op": "remove_rung", "contains": "OUT Y1"},
    ])
    assert [r.statements for r in p.rungs][:3] == [["A2"], ["M"], ["B"]]
    assert all("OUT Y1" not in [i.text() for i in r.instructions] for r in p.rungs)


def test_patched_program_is_revalidated():
    with pytest.raises(PatchError):
        apply_patches(parse_il(BASE), [{"op": "remove", "find": "OUT Y0"}])  # leaves a rung with no output
