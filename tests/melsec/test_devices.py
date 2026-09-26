import pytest

from ladder_harness.melsec.devices import (
    Constant, Device, DeviceError, Nesting, dev, parse_operand, wrap16,
)


def test_x_and_y_are_octal():
    assert parse_operand("X17") == Device("X", 15)
    assert str(Device("Y", 8)) == "Y10"


def test_octal_digit_rejected():
    with pytest.raises(DeviceError, match="octal"):
        parse_operand("X8")


def test_decimal_devices():
    assert parse_operand("M100") == Device("M", 100)
    assert parse_operand("d7999") == Device("D", 7999)
    assert parse_operand("SM400") == Device("SM", 400)


def test_range_limits():
    with pytest.raises(DeviceError, match="range"):
        parse_operand("T512")
    with pytest.raises(DeviceError, match="range"):
        parse_operand("D8000")


def test_constants():
    assert parse_operand("K50") == Constant(50, "K")
    assert parse_operand("K-5") == Constant(-5, "K")
    assert parse_operand("HFFFF") == Constant(-1, "H")
    assert str(Constant(-1, "H")) == "HFFFF"
    with pytest.raises(DeviceError):
        parse_operand("K40000")


def test_nesting():
    assert parse_operand("N0") == Nesting(0)
    with pytest.raises(DeviceError):
        parse_operand("N15")


def test_dev_rejects_constants():
    with pytest.raises(DeviceError, match="expected a device"):
        dev("K1")


def test_garbage_rejected():
    for bad in ("", "Q0", "X", "M-1", "DA"):
        with pytest.raises(DeviceError):
            parse_operand(bad)


def test_wrap16():
    assert wrap16(32767 + 1) == -32768
    assert wrap16(-32768 - 1) == 32767
    assert wrap16(-1) == -1
