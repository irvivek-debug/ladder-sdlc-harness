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


def test_gate_accepts_a_targeted_fix_despite_known_failures():
    suite = suite_from_dict({"station": "T", "plant": "none", "scenarios": [
        {"id": "A", "title": "M99 follows X1", "duration_ms": 100,
         "stimuli": [{"at_ms": 0, "set": {"X1": True, "X0": True}}], "expect": [{"eventually": "M99", "by_ms": 50}]},
        {"id": "B", "title": "Y5 on", "duration_ms": 100, "expect": [{"eventually": "Y5", "by_ms": 50}]}]})
    base = "LD X33\nAND X32\nAND X0\nOUT Y30\nLD X1\nAND M0\nORI X0\nOUT M99\nEND\n"
    old = parse_il(base)
    fixed = base.replace("AND M0", "OR M0")
    r = gate(fixed, old, SAFETY, [suite], known_failures={"A", "B"}, targets={"A"})
    assert r.allowed, r.reasons
    r = gate(base, old, SAFETY, [suite], known_failures={"A", "B"}, targets={"A"})
    assert not r.allowed and r.reasons[0].startswith("TARGET STILL FAILING")


def test_gate_rejects_new_lint_errors_only():
    old = parse_il("LD X1\nOUT Y1\nLD X2\nOUT Y1\nLD X0\nOUT M99\nEND\n")      # already has a double coil
    same = "LD X1\nOUT Y1\nLD X2\nOUT Y1\nLD X0\nOR X3\nOUT M99\nEND\n"
    assert gate(same, old, set(), []).allowed
    worse = "LD X1\nOUT Y1\nLD X2\nOUT Y1\nLD X0\nOUT M99\nLD X4\nOUT M99\nEND\n"
    assert gate(worse, old, set(), []).stage == "lint"
