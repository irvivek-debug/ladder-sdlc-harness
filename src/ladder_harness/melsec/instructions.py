"""The v1 MELSEC FX5 instruction subset.

Semantics follow the MELSEC iQ-F FX5 Programming Manual (Instructions, Standard Functions/Function
Blocks) JY997D55801: contacts pp.114-121, ANB/ORB p.123, MPS/MRD/MPP p.125, INV p.128, OUT p.130,
OUT T/OUTH/OUTHS p.132, OUT C p.135, SET p.141, RST p.143, PLS p.152, PLF p.154, MC/MCR p.179,
END p.183, 16-bit compares p.189, MOV p.397. Anything not in SPECS is unsupported.
"""
from __future__ import annotations

from dataclasses import dataclass

from .devices import Constant, Device, Nesting


@dataclass(frozen=True)
class Spec:
    op: str
    kind: str
    edge: str = ""
    negate: bool = False
    cmp: str = ""
    timer_base_ms: int = 0
    pulse: bool = False


CONTACT_KINDS = frozenset({"load", "and", "or"})
OUTPUT_KINDS = frozenset({"out", "set", "rst", "pulse", "mc", "mov", "add", "sub"})
STANDALONE_KINDS = frozenset({"mcr", "end"})

CONTACT_DEVICES = frozenset({"X", "Y", "M", "L", "SM", "T", "C"})
COIL_DEVICES = frozenset({"Y", "M", "L"})
WORD_SOURCES = frozenset({"D", "SD", "T", "C"})
CMP_SYMBOLS = ("=", "<>", ">", "<", ">=", "<=")


def _build() -> dict[str, Spec]:
    t: dict[str, Spec] = {}
    for prefix, kind, neg in (("LD", "load", "LDI"), ("AND", "and", "ANI"), ("OR", "or", "ORI")):
        t[prefix] = Spec(prefix, kind)
        t[neg] = Spec(neg, kind, negate=True)
        t[prefix + "P"] = Spec(prefix + "P", kind, edge="P")
        t[prefix + "F"] = Spec(prefix + "F", kind, edge="F")
        for sym in CMP_SYMBOLS:
            t[prefix + sym] = Spec(prefix + sym, kind, cmp=sym)
    for op in ("ANB", "ORB", "MPS", "MRD", "MPP", "INV"):
        t[op] = Spec(op, "stack")
    t["OUT"] = Spec("OUT", "out", timer_base_ms=100)
    t["OUTH"] = Spec("OUTH", "out", timer_base_ms=10)
    t["OUTHS"] = Spec("OUTHS", "out", timer_base_ms=1)
    t["SET"] = Spec("SET", "set")
    t["RST"] = Spec("RST", "rst")
    t["PLS"] = Spec("PLS", "pulse", edge="P")
    t["PLF"] = Spec("PLF", "pulse", edge="F")
    t["MC"] = Spec("MC", "mc")
    t["MCR"] = Spec("MCR", "mcr")
    t["MOV"] = Spec("MOV", "mov")
    t["MOVP"] = Spec("MOVP", "mov", pulse=True)
    t["+"] = Spec("+", "add")
    t["+P"] = Spec("+P", "add", pulse=True)
    t["-"] = Spec("-", "sub")
    t["-P"] = Spec("-P", "sub", pulse=True)
    t["END"] = Spec("END", "end")
    return t


SPECS: dict[str, Spec] = _build()


def _is_dev(o, kinds) -> bool:
    return isinstance(o, Device) and o.kind in kinds


def _is_source(o) -> bool:
    return isinstance(o, Constant) or _is_dev(o, WORD_SOURCES)


def _is_preset(o) -> bool:
    return (isinstance(o, Constant) and 0 <= o.value) or _is_dev(o, {"D"})


def check_operands(spec: Spec, ops: tuple) -> None:
    """Raise ValueError if the operands do not fit the instruction."""
    n, k = len(ops), spec.kind
    if k in CONTACT_KINDS:
        if spec.cmp:
            if n != 2 or not all(_is_source(o) for o in ops):
                raise ValueError("compare needs two word sources (D, SD, T, C or K/H constant)")
        elif n != 1 or not _is_dev(ops[0], CONTACT_DEVICES):
            raise ValueError("contact needs one bit device (X, Y, M, L, SM, T or C)")
    elif k in ("stack", "end"):
        if n:
            raise ValueError("takes no operands")
    elif k == "out":
        if n == 1 and spec.op == "OUT" and _is_dev(ops[0], COIL_DEVICES):
            return
        if n == 2 and _is_dev(ops[0], {"T"}) and _is_preset(ops[1]):
            return
        if n == 2 and spec.op == "OUT" and _is_dev(ops[0], {"C"}) and _is_preset(ops[1]):
            return
        if n == 1 and _is_dev(ops[0], {"T", "C"}):
            raise ValueError(f"OUT {ops[0]} needs a preset (K or D)")
        raise ValueError(f"{', '.join(map(str, ops)) or 'nothing'} cannot be driven by {spec.op}")
    elif k in ("set", "pulse"):
        if n != 1 or not _is_dev(ops[0], COIL_DEVICES):
            raise ValueError("needs one Y, M or L device")
    elif k == "rst":
        if n != 1 or not _is_dev(ops[0], COIL_DEVICES | {"T", "C", "D"}):
            raise ValueError("needs one Y, M, L, T, C or D device")
    elif k == "mc":
        if n != 2 or not isinstance(ops[0], Nesting) or not _is_dev(ops[1], {"M", "Y"}):
            raise ValueError("MC needs a nesting level and an M or Y device, e.g. MC N0 M100")
    elif k == "mcr":
        if n != 1 or not isinstance(ops[0], Nesting):
            raise ValueError("MCR needs a nesting level, e.g. MCR N0")
    elif k == "mov":
        if n != 2 or not _is_source(ops[0]) or not _is_dev(ops[1], {"D"}):
            raise ValueError("needs a word source and a D destination")
    elif k in ("add", "sub"):
        if n not in (2, 3) or not all(_is_source(o) for o in ops[:-1]) or not _is_dev(ops[-1], {"D"}):
            raise ValueError("needs 2 or 3 operands: sources then a D destination")
