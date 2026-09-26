from ladder_harness.melsec.program import parse_il
from ladder_harness.plant import PLANTS
from ladder_harness.sim.engine import Plc


def drive(plant, text, ms, inputs=None):
    plc = Plc(parse_il(text))
    for d, v in (inputs or {}).items():
        plc.set_bit(d, v)
    while plc.now_ms < ms:
        plant.step(plc, plc.scan_ms, plc.now_ms)
        plc.scan()
    return plc


def test_st20_fill_reaches_threshold_in_about_4_6_s():
    plc = drive(PLANTS["st20"](), "LD SM400\nOUT Y20\nOUT Y21\nEND\n", 4500)
    assert plc.word("D100") < 1450
    plc2 = drive(PLANTS["st20"](), "LD SM400\nOUT Y20\nOUT Y21\nEND\n", 4800)
    assert plc2.word("D100") >= 1450


def test_st20_leak_rates_separate_tight_from_leaking():
    def decay_over_test_window(leak):
        p = PLANTS["st20"](leak_kpa_per_s=leak)
        p.P, p.clamp = 15.0, 1.0
        plc = Plc(parse_il("LD SM400\nOUT Y20\nEND\n"))
        baseline = None
        while plc.now_ms < 15000:          # 5 s stabilise, then a 10 s test window
            if plc.now_ms == 5000:
                baseline = p.signals()["P_kpa"]
            p.step(plc, plc.scan_ms, plc.now_ms)
            plc.scan()
        return baseline - p.signals()["P_kpa"]
    assert decay_over_test_window(0.005) < 0.1     # well inside the 0.30 kPa limit
    assert decay_over_test_window(0.08) > 0.6      # well outside it


def test_st20_vent_empties_pack_in_half_a_second():
    p = PLANTS["st20"]()
    p.P = 15.0
    p.clamp = 1.0
    drive(p, "LD SM400\nOUT Y20\nOUT Y22\nEND\n", 500)
    assert p.signals()["P_kpa"] < 0.2


def test_st20_wire_break_reads_under_range():
    p = PLANTS["st20"]()
    p.act("inject", {"fault": "pt_wire_break"})
    plc = drive(p, "LD SM400\nOUT Y20\nEND\n", 50)
    assert plc.word("D100") == -2500


def test_st20_clamp_travel_and_switches():
    plc = drive(PLANTS["st20"](), "LD SM400\nOUT Y20\nEND\n", 700)
    assert plc.bit("X20") and not plc.bit("X21")


def test_st10_pallet_reaches_stop_and_is_held():
    p = PLANTS["st10"]()
    p.act("spawn_pallet", {})
    plc = drive(p, "LD SM400\nOUT Y10\nEND\n", 8000)
    assert plc.bit("X10")


def test_st10_jam_blocks_entry_eye():
    p = PLANTS["st10"]()
    p.act("inject", {"fault": "jam_at_entry"})
    plc = drive(p, "LD SM400\nOUT Y10\nEND\n", 3000)
    assert plc.bit("X11")


def test_st30_tester_passes_after_3_s():
    plc = drive(PLANTS["st30"](), "LD SM400\nOUT Y30\nEND\n", 3100)
    assert plc.bit("X30") and not plc.bit("X31")


def test_unknown_action_rejected():
    import pytest
    with pytest.raises(ValueError):
        PLANTS["st20"]().act("rm_rf", {})
