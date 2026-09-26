import itertools

import pytest

from ladder_harness.melsec.program import parse_il
from ladder_harness.sim.engine import Plc


def plc(text, scan_ms=10):
    return Plc(parse_il(text), scan_ms=scan_ms)


def test_seal_in():
    p = plc("LD X0\nOR Y0\nANI X1\nOUT Y0\nEND\n")
    p.scan()
    assert p.bit("Y0") is False
    p.set_bit("X0", True); p.scan(); assert p.bit("Y0")
    p.set_bit("X0", False); p.scan(); assert p.bit("Y0")
    p.set_bit("X1", True); p.scan(); assert not p.bit("Y0")


def test_anb_orb_truth_table():
    p = plc("LD X0\nOR X1\nLD X2\nOR X3\nANB\nOUT Y0\nLD X0\nAND X1\nLD X2\nAND X3\nORB\nOUT Y1\nEND\n")
    for bits in itertools.product([False, True], repeat=4):
        for i, b in enumerate(bits):
            p.set_bit(f"X{i}", b)
        p.scan()
        a, b, c, d = bits
        assert p.bit("Y0") == ((a or b) and (c or d))
        assert p.bit("Y1") == ((a and b) or (c and d))


def test_mps_branches():
    p = plc("LD X0\nMPS\nAND X1\nOUT Y0\nMRD\nAND X2\nOUT Y1\nMPP\nANI X3\nOUT Y2\nEND\n")
    for bits in itertools.product([False, True], repeat=4):
        for i, b in enumerate(bits):
            p.set_bit(f"X{i}", b)
        p.scan()
        x0, x1, x2, x3 = bits
        assert (p.bit("Y0"), p.bit("Y1"), p.bit("Y2")) == (x0 and x1, x0 and x2, x0 and not x3)


def test_continuous_output_uses_retained_result():
    p = plc("LD X0\nOUT Y0\nAND X1\nOUT Y1\nEND\n")
    p.set_bit("X0", True); p.scan()
    assert p.bit("Y0") and not p.bit("Y1")
    p.set_bit("X1", True); p.scan()
    assert p.bit("Y1")


def test_set_rst_latch():
    p = plc("LD X0\nSET M0\nLD X1\nRST M0\nLD M0\nOUT Y0\nEND\n")
    p.set_bit("X0", True); p.scan(); p.set_bit("X0", False); p.scan()
    assert p.bit("Y0")
    p.set_bit("X1", True); p.scan()
    assert not p.bit("Y0")


def test_ldp_and_ldf_fire_once_per_edge():
    p = plc("LDP X0\nOUT Y0\nLDF X0\nOUT Y1\nEND\n")
    seen_p, seen_f = [], []
    for x in [False, True, True, True, False, False, True]:
        p.set_bit("X0", x); p.scan()
        seen_p.append(p.bit("Y0")); seen_f.append(p.bit("Y1"))
    assert seen_p == [False, True, False, False, False, False, True]
    assert seen_f == [False, False, False, False, True, False, False]


def test_pls_is_one_scan():
    p = plc("LD X0\nPLS M0\nLD M0\nOUT Y0\nEND\n")
    trace = []
    for x in [False, True, True, True]:
        p.set_bit("X0", x); p.scan(); trace.append(p.bit("Y0"))
    assert trace == [False, True, False, False]


def test_special_relays():
    p = plc("LD SM402\nSET M0\nLD SM400\nOUT Y0\nLD SM401\nOUT Y1\nLD SM403\nOUT Y2\nEND\n")
    p.scan()
    assert p.bit("M0") and p.bit("Y0") and not p.bit("Y1") and not p.bit("Y2")
    p.scan()
    assert p.bit("Y2")


def test_compare_mov_arith_and_wrap():
    p = plc("LD SM400\nMOV K30 D100\n- D100 K5 D101\nLD> D101 K20\nOUT Y0\n"
            "LD SM400\nMOV K32767 D0\n+ K1 D0\nEND\n")
    p.scan()
    assert p.word("D101") == 25 and p.bit("Y0")
    assert p.word("D0") == -32768


def test_pulse_data_executes_once_per_rising_edge():
    p = plc("LD X0\n+P K1 D2\nEND\n")
    for x in [True, True, False, True, True]:
        p.set_bit("X0", x); p.scan()
    assert p.word("D2") == 2


def test_set_word_rejects_out_of_range():
    p = plc("LD X0\nOUT Y0\nEND\n")
    with pytest.raises(ValueError):
        p.set_word("D100", 40000)


def test_set_bit_rejects_word_device():
    p = plc("LD X0\nOUT Y0\nEND\n")
    with pytest.raises(ValueError):
        p.set_bit("D0", True)
