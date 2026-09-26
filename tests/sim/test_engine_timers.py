from ladder_harness.melsec.program import parse_il
from ladder_harness.sim.engine import Plc


def first_on(p, device, max_ms):
    """Scan until device is on; return the time of the scan in which it turned on."""
    while p.now_ms <= max_ms:
        p.scan()
        if p.bit(device):
            return p.now_ms - p.scan_ms
    return None


def make(text, **kw):
    p = Plc(parse_il(text), **kw)
    p.set_bit("X0", True)
    return p


def test_out_timer_is_100ms_base():
    assert first_on(make("LD X0\nOUT T0 K50\nLD T0\nOUT Y0\nEND\n"), "Y0", 6000) == 5000


def test_outh_and_ouths_bases():
    assert first_on(make("LD X0\nOUTH T0 K50\nLD T0\nOUT Y0\nEND\n"), "Y0", 1000) == 500
    assert first_on(make("LD X0\nOUTHS T0 K50\nLD T0\nOUT Y0\nEND\n", scan_ms=1), "Y0", 100) == 50


def test_contact_read_before_coil_lags_one_scan():
    assert first_on(make("LD T0\nOUT Y0\nLD X0\nOUT T0 K50\nEND\n"), "Y0", 6000) == 5010


def test_fx3_device_range_does_not_change_fx5_base():
    # On an FX3U, T200 is a 10 ms timer (0.5 s here). On FX5 the instruction sets the base: 5.0 s.
    assert first_on(make("LD X0\nOUT T200 K50\nLD T200\nOUT Y0\nEND\n"), "Y0", 6000) == 5000


def test_timer_is_non_retentive():
    p = make("LD X0\nOUT T0 K50\nLD T0\nOUT Y0\nEND\n")
    p.run(3000)
    p.set_bit("X0", False); p.scan()
    assert p.word("T0") == 0
    p.set_bit("X0", True)
    start = p.now_ms
    assert first_on(p, "Y0", start + 6000) == start + 5000


def test_timer_current_value_compare_and_rst():
    p = make("LD X0\nOUT T0 K50\nLD>= T0 K30\nOUT Y0\nLD X1\nRST T0\nEND\n")
    assert first_on(p, "Y0", 4000) == 3000
    p.set_bit("X1", True); p.scan()
    assert p.word("T0") == 0 and not p.bit("T0")


def test_counter_counts_rising_edges_to_preset():
    p = Plc(parse_il("LD X0\nOUT C0 K3\nLD C0\nOUT Y0\nLD X1\nRST C0\nEND\n"))
    for _ in range(5):
        p.set_bit("X0", True); p.scan()
        p.set_bit("X0", False); p.scan()
    assert p.word("C0") == 3 and p.bit("Y0")
    p.set_bit("X1", True); p.scan()
    assert p.word("C0") == 0
    p.scan()  # Y0 was computed before RST in the previous scan; it follows the counter one scan later
    assert not p.bit("Y0")
