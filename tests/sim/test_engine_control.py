from ladder_harness.melsec.program import parse_il
from ladder_harness.sim.engine import Plc

TEXT = """LD X0
MC N0 M100
LD X1
OUT Y0
LD X1
SET Y1
LD X1
OUT T0 K10
MCR N0
LD T0
OUT Y2
END
"""


def test_mc_region_on_behaves_normally():
    p = Plc(parse_il(TEXT))
    p.set_bit("X0", True); p.set_bit("X1", True)
    p.run(1100)
    assert p.bit("M100") and p.bit("Y0") and p.bit("Y1") and p.bit("Y2")


def test_mc_region_off_forces_outputs_off_but_set_holds():
    p = Plc(parse_il(TEXT))
    p.set_bit("X0", True); p.set_bit("X1", True)
    p.run(1100)
    p.set_bit("X0", False); p.scan()
    assert not p.bit("M100") and not p.bit("Y0")
    assert p.bit("Y1")                 # SET holds under MC off
    assert p.word("T0") == 0 and not p.bit("Y2")  # non-retentive timer reset
