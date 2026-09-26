from ladder_harness.melsec.program import parse_il
from ladder_harness.scenarios.model import suite_from_dict
from ladder_harness.scenarios.runner import run_scenario

PROG = parse_il("LD X0\nOUT T0 K10\nLD T0\nOUT Y0\nLD X1\nOUT Y1\nEND\n")


def run(expect, stimuli=None, duration=2000):
    s = suite_from_dict({"station": "T", "plant": "none", "scenarios": [{
        "id": "S", "title": "t", "duration_ms": duration,
        "stimuli": stimuli or [{"at_ms": 0, "set": {"X0": True}}], "expect": expect}]})
    return run_scenario(PROG, s.scenarios[0], s.plant, stop_on_fail=False)


def test_eventually_pass_and_fail():
    assert run([{"eventually": "Y0", "by_ms": 1100}]).passed
    r = run([{"eventually": "Y0", "by_ms": 900}])
    assert not r.passed and "by 900 ms" in r.failures[0].message


def test_never_and_always():
    assert run([{"never": "Y1"}]).passed
    assert not run([{"always": "not Y0"}]).passed


def test_after_ms_limits_always_and_never():
    assert run([{"always": "Y0", "after_ms": 1000}]).passed
    assert not run([{"always": "Y0", "after_ms": 500}]).passed


def test_at_end():
    assert run([{"at_end": "Y0"}]).passed
    assert not run([{"at_end": "Y1"}]).passed


def test_response_within():
    stim = [{"at_ms": 0, "set": {"X0": True}}, {"at_ms": 500, "set": {"X1": True}}]
    assert run([{"response": {"trigger": "X1", "effect": "Y1"}, "within_ms": 20}], stimuli=stim).passed
    assert not run([{"response": {"trigger": "X1", "effect": "Y0"}, "within_ms": 20}], stimuli=stim).passed


def test_when_stimulus_fires_after_condition():
    stim = [{"at_ms": 0, "set": {"X0": True}}, {"when": "Y0", "delay_ms": 100, "set": {"X1": True}}]
    r = run([{"eventually": "Y1", "by_ms": 1150}, {"never": "Y1 and not Y0"}], stimuli=stim)
    assert r.passed


def test_failure_message_shows_values():
    r = run([{"always": "not Y0"}])
    assert "Y0=True" in r.failures[0].message


def test_stop_on_fail_ends_early():
    s = suite_from_dict({"station": "T", "plant": "none", "scenarios": [{
        "id": "S", "title": "t", "duration_ms": 5000,
        "stimuli": [{"at_ms": 0, "set": {"X1": True}}], "expect": [{"never": "Y1"}]}]})
    r = run_scenario(PROG, s.scenarios[0], s.plant, stop_on_fail=True)
    assert not r.passed and r.end_ms < 100
