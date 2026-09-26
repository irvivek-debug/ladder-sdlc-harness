import pytest

from ladder_harness.scenarios.from_ce import generate

ROWS = [{"id": "CE-1", "station": "ST20", "cause": "clamp lost", "effect": "fill closed", "reference": "§4.3"}]
BIND = {"stations": {"ST20": {"plant": "st20", "preamble": [{"at_ms": 0, "set": {"X0": True}}]}},
        "bindings": {"CE-1": {"duration_ms": 1000, "stimuli": [], "expect": [{"never": "Y21"}]}}}


def test_generates_one_scenario_per_row():
    out = generate(ROWS, BIND)
    sc = out["ST20"]["scenarios"][0]
    assert sc["id"] == "CE-1" and sc["trace"] == ["CE-1", "§4.3"]
    assert sc["stimuli"][0]["set"] == {"X0": True}
    assert out["ST20"]["plant"] == "st20"


def test_missing_binding_is_an_error():
    with pytest.raises(ValueError, match="CE-2"):
        generate(ROWS + [{**ROWS[0], "id": "CE-2"}], BIND)


def test_orphan_binding_is_an_error():
    with pytest.raises(ValueError, match="CE-9"):
        generate(ROWS, {**BIND, "bindings": {**BIND["bindings"], "CE-9": {"duration_ms": 1, "expect": []}}})
