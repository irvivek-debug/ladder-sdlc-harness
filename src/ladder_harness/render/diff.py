"""Rung-level program diff."""
from __future__ import annotations

import difflib
from dataclasses import dataclass

from ..melsec.program import Program, format_il


@dataclass
class RungChange:
    kind: str                 # equal | changed | added | removed
    old_index: int | None
    new_index: int | None


def _keys(p: Program) -> list[tuple[str, ...]]:
    return [tuple(i.text() for i in r.instructions) for r in p.rungs]


def diff_programs(old: Program, new: Program) -> list[RungChange]:
    sm = difflib.SequenceMatcher(a=_keys(old), b=_keys(new), autojunk=False)
    out: list[RungChange] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            out += [RungChange("equal", i1 + k, j1 + k) for k in range(i2 - i1)]
        elif tag == "insert":
            out += [RungChange("added", None, j) for j in range(j1, j2)]
        elif tag == "delete":
            out += [RungChange("removed", i, None) for i in range(i1, i2)]
        else:
            n = min(i2 - i1, j2 - j1)
            out += [RungChange("changed", i1 + k, j1 + k) for k in range(n)]
            out += [RungChange("removed", i, None) for i in range(i1 + n, i2)]
            out += [RungChange("added", None, j) for j in range(j1 + n, j2)]
    return out


def unified_il_diff(old: Program, new: Program, old_name: str = "before", new_name: str = "after") -> str:
    return "\n".join(difflib.unified_diff(format_il(old).splitlines(), format_il(new).splitlines(),
                                          fromfile=old_name, tofile=new_name, lineterm=""))
