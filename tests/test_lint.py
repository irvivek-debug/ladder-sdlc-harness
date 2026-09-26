from ladder_harness.iolist import IoList
from ladder_harness.lint import lint
from ladder_harness.melsec.program import parse_il


def rules(text, **kw):
    return {f.rule for f in lint(parse_il(text), **kw)}


def test_double_coil():
    assert "L001" in rules("LD X0\nOUT Y0\nLD X1\nOUT Y0\nEND\n")
    assert "L001" not in rules("LD X0\nSET Y0\nLD X1\nRST Y0\nEND\n")


def test_double_coil_names_device_and_rungs():
    f = [x for x in lint(parse_il("LD X0\nOUT Y0\nLD X1\nOUT Y0\nEND\n")) if x.rule == "L001"][0]
    assert f.devices == ("Y0",) and "rungs 1 and 2" in f.message


def test_fx3_timer_trap_message():
    f = [x for x in lint(parse_il("LD X0\nOUT T200 K50\nEND\n")) if x.rule == "L002"][0]
    assert "0.5 s" in f.message and "5 s" in f.message and f.devices == ("T200",)


def test_fx5_native_timer_is_not_flagged():
    assert "L002" not in rules("LD X0\nOUT T24 K5\nEND\n")
    assert "L002" not in rules("LD X0\nOUTH T200 K50\nEND\n")  # FX5 OUTH = 10 ms = FX3 T200 base


def test_missing_end_and_read_before_coil():
    assert "L006" in rules("LD X0\nOUT Y0\n")
    assert "L003" in rules("LD T0\nOUT Y0\nLD X0\nOUT T0 K5\nEND\n")


def test_timer_multiple_coils():
    assert "L009" in rules("LD X0\nOUT T0 K5\nLD X1\nOUT T0 K9\nEND\n")


def test_iolist_rules(tmp_path):
    f = tmp_path / "io.csv"
    f.write_text("tag,device,description,signal,range,units,station,safety,notes\n"
                 "ES,X0,E-stop,DI,,,CELL,SAFETY,\nSP,X24,spare,DI,,,ST20,,\nV,Y0,valve,DO,,,ST20,SAFETY,\n")
    io = IoList.load_csv(f)
    got = rules("LD X0\nAND X7\nOUT Y0\nEND\n", iolist=io)
    assert {"L004", "L005", "L007"} <= got


def test_comment_coverage():
    f = [x for x in lint(parse_il("LD X0\nOUT Y0\nEND\n"), comments={"X0": "start"}) if x.rule == "L008"][0]
    assert "1 of 2" in f.message
