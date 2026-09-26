import pytest

from ladder_harness.scenarios.expr import ExprError, compile_expr, evaluate


def test_evaluates_bools_and_compares():
    e = compile_expr("Y21 and not X20 or P_kpa > 20.5")
    vals = {"Y21": True, "X20": True, "P_kpa": 21.0}
    assert evaluate(e, vals.__getitem__) is True
    assert e.names == ("P_kpa", "X20", "Y21")


def test_arithmetic_and_negative_constants():
    e = compile_expr("D110 - D111 > 30 and D100 > -500")
    assert evaluate(e, {"D110": 1500, "D111": 1460, "D100": 1400}.__getitem__) is True


@pytest.mark.parametrize("bad", ["__import__('os')", "a.b", "f(x)", "[1]", "'s'", "x if y else z", "lambda: 1"])
def test_rejects_unsafe_syntax(bad):
    with pytest.raises(ExprError):
        compile_expr(bad)
