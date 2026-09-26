from ladder_harness.guard import check_patch, gate
from ladder_harness.melsec.devices import dev
from ladder_harness.melsec.program import parse_il
from ladder_harness.scenarios.model import suite_from_dict

OLD = parse_il("LD X33\nAND X32\nAND X0\nOUT Y30\nLD X1\nOR M0\nORI X0\nOUT M99\nEND\n")
SAFETY = {dev("X0"), dev("X32"), dev("Y30")}


def test_locked_rung_cannot_change():
    new = parse_il("LD X33\nAND X0\nOUT Y30\nLD X1\nOR M0\nORI X0\nOUT M99\nEND\n")
    v = check_patch(OLD, new, SAFETY)
    assert not v.allowed and any("locked" in r for r in v.reasons)


def test_safety_reads_cannot_be_removed():
    new = parse_il("LD X33\nAND X32\nAND X0\nOUT Y30\nLD X1\nOR M0\nOUT M99\nEND\n")
    v = check_patch(OLD, new, SAFETY)
    assert not v.allowed and any("ORI X0" in r for r in v.reasons)


def test_new_safety_writes_rejected_and_benign_edits_allowed():
    bad = parse_il("LD X33\nAND X32\nAND X0\nOUT Y30\nLD X1\nOR M0\nORI X0\nOUT M99\nLD X5\nSET Y30\nEND\n")
    assert not check_patch(OLD, bad, SAFETY).allowed
    ok = parse_il("LD X33\nAND X32\nAND X0\nOUT Y30\nLD X1\nOR M0\nOR M1\nORI X0\nOUT M99\nEND\n")
    assert check_patch(OLD, ok, SAFETY).allowed


def test_gate_runs_stages_in_order():
    suite = suite_from_dict({"station": "T", "plant": "none", "scenarios": [{
        "id": "S1", "title": "M99 follows X1", "duration_ms": 100,
        "stimuli": [{"at_ms": 0, "set": {"X1": True, "X0": True}}], "expect": [{"eventually": "M99", "by_ms": 50}]}]})
    assert gate("LD X0\nOUT\n", OLD, SAFETY, [suite]).stage == "parse"
    locked = "LD X33\nAND X0\nOUT Y30\nLD X1\nOR M0\nORI X0\nOUT M99\nEND\n"
    assert gate(locked, OLD, SAFETY, [suite]).stage == "guard"
    lint_err = "LD X33\nAND X32\nAND X0\nOUT Y30\nLD X1\nOR M0\nORI X0\nOUT M99\nLD X2\nOUT M99\nEND\n"
    assert gate(lint_err, OLD, SAFETY, [suite]).stage == "lint"
    broken = "LD X33\nAND X32\nAND X0\nOUT Y30\nLD X1\nAND M0\nORI X0\nOUT M99\nEND\n"
    r = gate(broken, OLD, SAFETY, [suite])
    assert r.stage == "scenarios" and not r.allowed
    ok = gate("LD X33\nAND X32\nAND X0\nOUT Y30\nLD X1\nOR M0\nORI X0\nOUT M99\nEND\n", OLD, SAFETY, [suite])
    assert ok.allowed and ok.stage == "passed"
