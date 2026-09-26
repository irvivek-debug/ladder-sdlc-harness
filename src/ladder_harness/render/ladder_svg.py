"""Draw rungs as ladder diagrams (SVG) from the instruction list.

The instruction list is evaluated symbolically — the same stack discipline the simulator uses — into a
series/parallel condition tree per output network. Text is the source of truth; pictures are rendered from it
one way only. Colours come from CSS variables (`--lad-*`) with light defaults, so pages can theme them.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape

from ..melsec.devices import Device
from ..melsec.program import Instruction, Program, Rung

CW, CH, OUTW, LEFT, HEAD, GAP = 104, 60, 200, 16, 26, 10

STYLE = """<style>
.lad-wire{stroke:var(--lad-wire,#6b7280);stroke-width:1.6;fill:none}
.lad-rail{stroke:var(--lad-ink,#1f2933);stroke-width:3}
.lad-sym{stroke:var(--lad-ink,#1f2933);stroke-width:1.8;fill:none}
.lad-box{fill:var(--lad-box,#f4f5f7);stroke:var(--lad-ink,#1f2933);stroke-width:1.2}
.lad-dev{font:600 12px ui-monospace,SFMono-Regular,Menlo,monospace;fill:var(--lad-ink,#1f2933)}
.lad-txt{font:11px ui-monospace,SFMono-Regular,Menlo,monospace;fill:var(--lad-ink,#1f2933)}
.lad-cmt{font:10.5px system-ui,sans-serif;fill:var(--lad-muted,#6b7280)}
.lad-head{font:600 11.5px system-ui,sans-serif;fill:var(--lad-muted,#6b7280)}
.lad-hl{fill:var(--lad-hl,#fff3d6)}
.lad-bg{fill:var(--lad-bg,transparent)}
</style>"""


@dataclass
class Leaf:
    ins: Instruction


@dataclass
class Series:
    items: list


@dataclass
class Parallel:
    items: list


@dataclass
class Not:
    item: object


def _series(a, b):
    return Series((a.items if isinstance(a, Series) else [a]) + (b.items if isinstance(b, Series) else [b]))


def _parallel(a, b):
    return Parallel((a.items if isinstance(a, Parallel) else [a]) + (b.items if isinstance(b, Parallel) else [b]))


def rung_networks(rung: Rung) -> list[tuple[object | None, list[Instruction]]]:
    """Symbolic IL evaluation: [(condition tree, outputs sharing it)], or (None, [MCR/END])."""
    acc, blocks, mps = None, [], []
    nets: list[tuple[object | None, list[Instruction]]] = []
    for ins in rung.instructions:
        k, op = ins.spec.kind, ins.op
        if k == "load":
            if acc is not None:
                blocks.append(acc)
            acc = Leaf(ins)
        elif k == "and":
            acc = _series(acc, Leaf(ins))
        elif k == "or":
            acc = _parallel(acc, Leaf(ins))
        elif op == "ANB":
            acc = _series(blocks.pop(), acc)
        elif op == "ORB":
            acc = _parallel(blocks.pop(), acc)
        elif op == "MPS":
            mps.append(acc)
        elif op == "MRD":
            acc = mps[-1]
        elif op == "MPP":
            acc = mps.pop()
        elif op == "INV":
            acc = Not(acc)
        elif k in ("mcr", "end"):
            nets.append((None, [ins]))
        else:
            if nets and nets[-1][0] is acc:
                nets[-1][1].append(ins)
            else:
                nets.append((acc, [ins]))
    return nets


def _size(n) -> tuple[int, int]:
    if isinstance(n, Leaf):
        return 1, 1
    if isinstance(n, Not):
        c, r = _size(n.item)
        return c + 1, r
    sizes = [_size(i) for i in n.items]
    if isinstance(n, Series):
        return sum(c for c, _ in sizes), max(r for _, r in sizes)
    return max(c for c, _ in sizes), sum(r for _, r in sizes)


def _t(x, y, text, cls, anchor="middle"):
    return f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="{anchor}">{escape(text)}</text>'


def _line(x1, y1, x2, y2, cls="lad-wire"):
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="{cls}"/>'


def _short(text: str, n: int = 17) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def _contact(ins: Instruction, x: float, cy: float, parts: list, comments: dict) -> None:
    cx = x + CW / 2
    s = ins.spec
    if s.cmp:
        a, b = ins.operands
        parts.append(_line(x, cy, x + 8, cy))
        parts.append(_line(x + CW - 8, cy, x + CW, cy))
        parts.append(f'<rect x="{x + 8:.1f}" y="{cy - 11:.1f}" width="{CW - 16}" height="22" rx="3" class="lad-box"/>')
        parts.append(_t(cx, cy + 4, f"{a} {s.cmp} {b}", "lad-txt"))
        dev = next((o for o in ins.operands if isinstance(o, Device)), None)
    else:
        dev = ins.operands[0]
        parts.append(_line(x, cy, cx - 8, cy))
        parts.append(_line(cx + 8, cy, x + CW, cy))
        parts.append(_line(cx - 8, cy - 11, cx - 8, cy + 11, "lad-sym"))
        parts.append(_line(cx + 8, cy - 11, cx + 8, cy + 11, "lad-sym"))
        if s.negate:
            parts.append(_line(cx - 11, cy + 10, cx + 11, cy - 10, "lad-sym"))
        if s.edge:
            parts.append(_t(cx, cy + 4, "↑" if s.edge == "P" else "↓", "lad-dev"))
        parts.append(_t(cx, cy - 16, str(dev), "lad-dev"))
    if dev is not None and comments.get(str(dev)):
        parts.append(_t(cx, cy + 26, _short(comments[str(dev)]), "lad-cmt"))


def _draw(n, x: float, y: float, cols: int, parts: list, comments: dict) -> None:
    c, _ = _size(n)
    cy = y + CH / 2
    if isinstance(n, Leaf):
        _contact(n.ins, x, cy, parts, comments)
    elif isinstance(n, Not):
        _draw(n.item, x, y, c - 1, parts, comments)
        ix = x + (c - 1) * CW
        parts.append(_line(ix, cy, ix + CW, cy))
        parts.append(_line(ix + CW / 2 - 9, cy + 9, ix + CW / 2 + 9, cy - 9, "lad-sym"))
        parts.append(_t(ix + CW / 2, cy - 16, "INV", "lad-dev"))
    elif isinstance(n, Series):
        cx = x
        for item in n.items:
            ic, _ = _size(item)
            _draw(item, cx, y, ic, parts, comments)
            cx += ic * CW
    else:
        yy, centers = y, []
        for item in n.items:
            _, ir = _size(item)
            _draw(item, x, yy, cols, parts, comments)
            centers.append(yy + CH / 2)
            yy += ir * CH
        parts.append(_line(x, centers[0], x, centers[-1]))
        parts.append(_line(x + cols * CW, centers[0], x + cols * CW, centers[-1]))
        return
    if cols > c:
        parts.append(_line(x + c * CW, cy, x + cols * CW, cy))


def _output(ins: Instruction, x: float, cy: float, right: float, parts: list, comments: dict) -> None:
    k, ops = ins.spec.kind, ins.operands
    coil = k in ("out", "set", "rst", "pulse") and isinstance(ops[0], Device) and ops[0].kind in ("Y", "M", "L")
    if coil and len(ops) == 1:
        cx = right - 46
        parts.append(_line(x, cy, cx - 12, cy))
        parts.append(_line(cx + 12, cy, right, cy))
        parts.append(f'<path d="M{cx - 7:.1f},{cy - 12:.1f} Q{cx - 15:.1f},{cy:.1f} {cx - 7:.1f},{cy + 12:.1f}" class="lad-sym"/>')
        parts.append(f'<path d="M{cx + 7:.1f},{cy - 12:.1f} Q{cx + 15:.1f},{cy:.1f} {cx + 7:.1f},{cy + 12:.1f}" class="lad-sym"/>')
        letter = {"set": "S", "rst": "R", "pulse": "P" if ins.op == "PLS" else "F"}.get(k, "")
        if letter:
            parts.append(_t(cx, cy + 4, letter, "lad-dev"))
        parts.append(_t(cx, cy - 16, str(ops[0]), "lad-dev"))
        if comments.get(str(ops[0])):
            parts.append(_t(cx - 60, cy + 26, _short(comments[str(ops[0])], 26), "lad-cmt", "start"))
        return
    label = ins.text()
    if k == "out" and ops[0].kind == "T":
        label = f"{ins.op} {ops[0]} {ops[1]}  ({ins.spec.timer_base_ms} ms)"
    bw = min(OUTW - 20, max(90, 7.2 * len(label) + 16))
    bx = right - 10 - bw
    parts.append(_line(x, cy, bx, cy))
    parts.append(_line(bx + bw, cy, right, cy))
    parts.append(f'<rect x="{bx:.1f}" y="{cy - 12:.1f}" width="{bw:.1f}" height="24" rx="3" class="lad-box"/>')
    parts.append(_t(bx + bw / 2, cy + 4, label, "lad-txt"))
    dev = next((o for o in ops if isinstance(o, Device)), None)
    if dev is not None and comments.get(str(dev)):
        parts.append(_t(bx, cy + 26, _short(comments[str(dev)], 26), "lad-cmt", "start"))


def _rung_parts(rung: Rung, number: int | None, comments: dict, highlight: bool) -> tuple[list[str], float, float]:
    nets = rung_networks(rung)
    cols = max([_size(n)[0] for n, _ in nets if n is not None] or [1])
    width = LEFT * 2 + cols * CW + OUTW
    parts: list[str] = []
    head = " · ".join(filter(None, [f"Rung {number}" if number is not None else "", *rung.statements]))
    y = HEAD
    body: list[str] = []
    for node, outs in nets:
        if node is None:
            body.append(f'<rect x="{LEFT + 20:.1f}" y="{y + 12:.1f}" width="{width - 2 * LEFT - 40:.1f}" '
                        f'height="{CH - 24}" rx="3" class="lad-box"/>')
            body.append(_t(width / 2, y + CH / 2 + 4, outs[0].text(), "lad-dev"))
            y += CH
            continue
        rows = max(_size(node)[1], len(outs))
        _draw(node, LEFT, y, cols, body, comments)
        x_out = LEFT + cols * CW
        for j, ins in enumerate(outs):
            _output(ins, x_out, y + j * CH + CH / 2, width - LEFT, body, comments)
        if len(outs) > 1:
            body.append(_line(x_out, y + CH / 2, x_out, y + (len(outs) - 1) * CH + CH / 2))
        y += rows * CH
    height = y + GAP
    if highlight:
        parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" rx="6" class="lad-hl"/>')
    parts.append(_t(LEFT, 16, head, "lad-head", "start"))
    parts.append(_line(LEFT, HEAD, LEFT, y, "lad-rail"))
    parts.append(_line(width - LEFT, HEAD, width - LEFT, y, "lad-rail"))
    parts.extend(body)
    return parts, width, height


def rung_svg(rung: Rung, comments: dict | None = None, highlight: bool = False, number: int | None = None) -> str:
    parts, w, h = _rung_parts(rung, number, comments or {}, highlight)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" width="{w:.0f}" '
            f'height="{h:.0f}" role="img" aria-label="ladder rung">{STYLE}{"".join(parts)}</svg>')


def program_svg(program: Program, comments: dict | None = None, highlight: set[int] | None = None) -> str:
    comments, highlight = comments or {}, highlight or set()
    groups, width, y = [], 0.0, 0.0
    for i, rung in enumerate(program.rungs):
        parts, w, h = _rung_parts(rung, i + 1, comments, i in highlight)
        groups.append(f'<g transform="translate(0,{y:.0f})">{"".join(parts)}</g>')
        width, y = max(width, w), y + h
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {y:.0f}" width="{width:.0f}" '
            f'height="{y:.0f}" role="img" aria-label="ladder program {escape(program.name)}">{STYLE}{"".join(groups)}</svg>')
