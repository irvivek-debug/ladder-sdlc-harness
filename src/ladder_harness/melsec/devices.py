"""MELSEC FX5 device and operand model.

X/Y are octal on FX5; every other device number is decimal (MELSEC iQ-F FX5 User's Manual
(Application) JY997D55401, §4.1 p.53). Word devices are 16-bit signed and BIN arithmetic wraps.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

OCTAL_KINDS = frozenset({"X", "Y"})
BIT_KINDS = frozenset({"X", "Y", "M", "L", "SM"})
WORD_KINDS = frozenset({"D", "SD"})

# Exclusive upper bounds — FX5U default device assignments (generous where a project may reassign).
LIMITS = {"X": 1024, "Y": 1024, "M": 7680, "L": 7680, "SM": 10000,
          "D": 8000, "SD": 12000, "T": 512, "C": 256}

INT16_MIN, INT16_MAX = -32768, 32767

_OPERAND = re.compile(r"^(SM|SD|X|Y|M|L|T|C|D|K|H|N)(-?[0-9A-F]+)$")


class DeviceError(ValueError):
    """Text that is not a valid FX5 device, constant or nesting level."""


@dataclass(frozen=True, order=True)
class Device:
    kind: str
    number: int

    def __str__(self) -> str:
        if self.kind in OCTAL_KINDS:
            return f"{self.kind}{self.number:o}"
        return f"{self.kind}{self.number}"

    @property
    def is_bit(self) -> bool:
        return self.kind in BIT_KINDS

    @property
    def is_word(self) -> bool:
        return self.kind in WORD_KINDS


@dataclass(frozen=True)
class Constant:
    value: int
    radix: str = "K"

    def __str__(self) -> str:
        if self.radix == "H":
            return f"H{self.value & 0xFFFF:X}"
        return f"K{self.value}"


@dataclass(frozen=True)
class Nesting:
    level: int

    def __str__(self) -> str:
        return f"N{self.level}"


Operand = Device | Constant | Nesting


def wrap16(value: int) -> int:
    """Two's-complement wrap to a 16-bit signed word, as FX5 BIN arithmetic does."""
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def parse_operand(text: str) -> Operand:
    t = text.strip().upper()
    m = _OPERAND.match(t)
    if not m:
        raise DeviceError(f"not a device or constant: {text!r}")
    kind, digits = m.groups()
    if kind == "K":
        value = int(digits, 10) if digits.lstrip("-").isdigit() else None
        if value is None or not INT16_MIN <= value <= INT16_MAX:
            raise DeviceError(f"K constant must be a 16-bit decimal: {text!r}")
        return Constant(value, "K")
    if kind == "H":
        if digits.startswith("-") or int(digits, 16) > 0xFFFF:
            raise DeviceError(f"H constant must be 0..FFFF: {text!r}")
        return Constant(wrap16(int(digits, 16)), "H")
    if digits.startswith("-"):
        raise DeviceError(f"device numbers cannot be negative: {text!r}")
    if kind == "N":
        if not digits.isdigit() or not 0 <= int(digits) <= 14:
            raise DeviceError(f"nesting must be N0..N14: {text!r}")
        return Nesting(int(digits))
    if kind in OCTAL_KINDS:
        if any(c in "89ABCDEF" for c in digits):
            raise DeviceError(f"{text!r}: X/Y device numbers are octal on FX5")
        number = int(digits, 8)
    else:
        if not digits.isdigit():
            raise DeviceError(f"{text!r}: {kind} device numbers are decimal")
        number = int(digits, 10)
    if number >= LIMITS[kind]:
        raise DeviceError(f"{text!r}: {kind} range is {kind}0..{Device(kind, LIMITS[kind] - 1)}")
    return Device(kind, number)


def dev(text: str) -> Device:
    """Parse text that must name a device (not a constant or nesting level)."""
    op = parse_operand(text)
    if not isinstance(op, Device):
        raise DeviceError(f"expected a device, got {text!r}")
    return op
