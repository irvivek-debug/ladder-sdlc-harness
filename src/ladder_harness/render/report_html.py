"""Self-contained HTML views of a program and of a before/after diff."""
from __future__ import annotations

from html import escape

from ..melsec.program import Program
from .diff import diff_programs, unified_il_diff
from .ladder_svg import program_svg, rung_svg

CSS = """
:root{--bg:#fbfbfa;--fg:#1f2933;--muted:#6b7280;--line:#e5e7eb;--card:#ffffff;
--lad-ink:#1f2933;--lad-wire:#6b7280;--lad-box:#f4f5f7;--lad-hl:#fff3d6;--lad-muted:#6b7280;
--add:#e8f5ec;--del:#fdecec;--accent:#0b6e4f}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#111416;--fg:#e6e8ea;--muted:#9aa3ab;
--line:#2a2f34;--card:#171b1e;--lad-ink:#e6e8ea;--lad-wire:#8a939b;--lad-box:#22282d;--lad-hl:#3a3220;
--lad-muted:#9aa3ab;--add:#16301f;--del:#3a1c1c;--accent:#5cc9a0}}
:root[data-theme="dark"]{--bg:#111416;--fg:#e6e8ea;--muted:#9aa3ab;--line:#2a2f34;--card:#171b1e;--lad-ink:#e6e8ea;
--lad-wire:#8a939b;--lad-box:#22282d;--lad-hl:#3a3220;--lad-muted:#9aa3ab;--add:#16301f;--del:#3a1c1c;--accent:#5cc9a0}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1180px;margin:0 auto;padding:28px 16px 64px}h1{font-size:20px;margin:0 0 4px}
.sub{color:var(--muted);margin:0 0 20px}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:14px;margin:14px 0;overflow-x:auto}.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.pair>div{overflow-x:auto}.tag{font:600 11px system-ui;letter-spacing:.04em;text-transform:uppercase;color:var(--muted)}
.tag.changed{color:#b7791f}.tag.added{color:var(--accent)}.tag.removed{color:#c0392b}
pre{font:12.5px/1.45 ui-monospace,Menlo,monospace;overflow-x:auto;margin:0}
pre .a{background:var(--add);display:block}pre .d{background:var(--del);display:block}
svg{max-width:none}@media (max-width:760px){.pair{grid-template-columns:1fr}}
"""


def _page(title: str, subtitle: str, body: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>'
            f"<style>{CSS}</style></head><body><main><h1>{escape(title)}</h1><p class=\"sub\">{escape(subtitle)}</p>"
            f"{body}</main></body></html>")


def program_html(program: Program, comments: dict | None = None, title: str = "", highlight: set[int] | None = None) -> str:
    svg = program_svg(program, comments, highlight)
    return _page(title or program.name, f"{len(program.rungs)} rungs, drawn from the instruction list",
                 f'<div class="card">{svg}</div>')


def _diff_lines(text: str) -> str:
    out = []
    for line in text.splitlines():
        cls = "a" if line.startswith("+") and not line.startswith("+++") else \
              "d" if line.startswith("-") and not line.startswith("---") else ""
        out.append(f'<span class="{cls}">{escape(line)}</span>' if cls else escape(line))
    return "\n".join(out)


def diff_html(old: Program, new: Program, comments: dict | None = None, title: str = "",
              old_label: str = "Before", new_label: str = "After") -> str:
    changes = diff_programs(old, new)
    blocks, unchanged = [], 0
    for ch in changes:
        if ch.kind == "equal":
            unchanged += 1
            continue
        left = rung_svg(old.rungs[ch.old_index], comments, True, ch.old_index + 1) if ch.old_index is not None else ""
        right = rung_svg(new.rungs[ch.new_index], comments, True, ch.new_index + 1) if ch.new_index is not None else ""
        blocks.append(f'<div class="card"><div class="tag {ch.kind}">{ch.kind}</div><div class="pair">'
                      f'<div><div class="tag">{escape(old_label)}</div>{left}</div>'
                      f'<div><div class="tag">{escape(new_label)}</div>{right}</div></div></div>')
    n_changed = len(changes) - unchanged
    body = "".join(blocks) + (f'<div class="card"><div class="tag">instruction-list diff</div>'
                              f"<pre>{_diff_lines(unified_il_diff(old, new, old_label, new_label))}</pre></div>")
    return _page(title or f"{old.name} diff", f"{n_changed} rung(s) differ, {unchanged} unchanged", body)
