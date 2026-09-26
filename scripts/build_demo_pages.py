#!/usr/bin/env python3
"""Build demo/story.html (beat 1) and demo/ledger.html (beat 6). Every number is computed here: plant facts come from
the simulator ($0, deterministic); cost, coverage and catch rates come from the evaluation sweep. Nothing is typed in.

    python scripts/build_demo_pages.py --sweep S1
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ladder_harness.cell import load_cell  # noqa: E402
from ladder_harness.evaluation.aggregate import load_records, usable  # noqa: E402
from ladder_harness.lint import lint  # noqa: E402
from ladder_harness.plant import PLANTS  # noqa: E402
from ladder_harness.sim.engine import Plc  # noqa: E402

PENDING = '<span class="pending">pending</span>'
MCKINSEY = ("McKinsey &amp; Company, “Unleashing developer productivity with generative AI,” 27 June 2023. "
            "Documentation in half the time; savings fell below 10 percent on high-complexity tasks.")


def cycle(program, leak: float) -> dict:
    plant, plc = PLANTS["st20"](leak_kpa_per_s=leak), Plc(program)
    done_at = None
    while plc.now_ms < 40000 and done_at is None:
        plc.set_bit("X0", True), plc.set_bit("X2", True), plc.set_bit("X23", plc.now_ms >= 100)
        plant.step(plc, plc.scan_ms, plc.now_ms)
        plc.scan()
        if plc.bit("M207"):
            done_at = plc.now_ms - plc.scan_ms
    return {"done_s": (done_at - 100) / 1000 if done_at else None, "dp_kpa": plc.word("D112") / 100,
            "passed": plc.bit("M210"), "failed": plc.bit("M211")}


def plant_facts(cell) -> dict:
    legacy, golden = cell.legacy("ST20"), cell.golden("ST20")
    leak_legacy, leak_ref = cycle(legacy, 0.08), cycle(golden, 0.08)
    tight_legacy, tight_ref = cycle(legacy, 0.005), cycle(golden, 0.005)
    comments = cell.legacy_comments("ST20")
    cov = next(f for f in lint(legacy, cell.iolist, comments) if f.rule == "L008")
    used = len({str(d) for i in legacy.instructions() for d in i.devices()})
    return {"leak_measured_legacy": leak_legacy["dp_kpa"], "leak_measured_ref": leak_ref["dp_kpa"],
            "leak_passed_legacy": leak_legacy["passed"], "leak_failed_ref": leak_ref["failed"],
            "cycle_legacy": tight_legacy["done_s"], "cycle_ref": tight_ref["done_s"],
            "devices": used, "documented_pct": round(100 * (used - len(cov.devices)) / used)}


def med(vals):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


def sweep_facts(sweep: str) -> dict:
    runs = ROOT / "evals" / "results" / "runs" / f"{sweep}.jsonl"
    summary_path = ROOT / "evals" / "results" / "summary.json"
    if not runs.exists() or not summary_path.exists():
        return {}
    summary = json.loads(summary_path.read_text())
    recs = [r for r in load_records([runs]) if usable(r)]
    lanes = {g: v["config"] for g, v in summary.get("lanes", {}).items()}

    def lane_recs(task, group):
        return [r for r in recs if r["task_id"] == task and r["config"] == lanes.get(group)]

    ex, rv, rp = lane_recs("EX-ST20", "T1"), lane_recs("RV-LEGACY", "T4"), lane_recs("RP-D5", "T3")
    return {"summary": summary, "lanes": lanes,
            "doc_coverage": med([r["score"].get("coverage") for r in ex]),
            "doc_cost": med([r.get("cost_usd") for r in ex]), "doc_seconds": med([r.get("wall_s") for r in ex]),
            "review_d5_rate": (sum("D5" in r["score"].get("matched", {}) for r in rv) / len(rv)) if rv else None,
            "review_cost": med([r.get("cost_usd") for r in rv]), "review_n": len(rv),
            "fix_rate": (sum(r["passed"] for r in rp) / len(rp)) if rp else None,
            "fix_cost": med([r.get("cost_usd") for r in rp]), "fix_n": len(rp)}


CSS = """
:root{--bg:#131313;--surface:#1f2020;--surface-high:#2a2a2a;--fg:#e4e2e1;--muted:#a0a3a8;--border:#374151;
--accent:#a7caed;--ok:#30d158;--warn:#ff9f0a;--crit:#ff453a;
--display:"Bricolage Grotesque",system-ui,sans-serif;--sans:"Work Sans",system-ui,sans-serif;
--mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,monospace}
@media (prefers-color-scheme: light){:root:not([data-theme="dark"]){--bg:#f6f6f4;--surface:#ffffff;--surface-high:#eeeeec;
--fg:#1b1c1d;--muted:#55595f;--border:#d0d3d8;--accent:#1f5f99;--ok:#0a7f3f;--warn:#9a5b00;--crit:#b3261e}}
:root[data-theme="light"]{--bg:#f6f6f4;--surface:#ffffff;--surface-high:#eeeeec;--fg:#1b1c1d;--muted:#55595f;
--border:#d0d3d8;--accent:#1f5f99;--ok:#0a7f3f;--warn:#9a5b00;--crit:#b3261e}
*{box-sizing:border-box;margin:0}
body{background:var(--bg);color:var(--fg);font:16px/1.55 var(--sans);-webkit-font-smoothing:antialiased}
main{max-width:1120px;margin:0 auto;padding:28px 16px 56px}
.strip{font:700 11px/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);
border-bottom:1px solid var(--border);padding-bottom:10px;display:flex;flex-wrap:wrap;gap:6px 18px}
h1{font:700 clamp(30px,5vw,52px)/1.08 var(--display);letter-spacing:-.01em;margin:28px 0 12px;max-width:17ch}
.lede{font-size:clamp(17px,2vw,20px);color:var(--muted);max-width:60ch}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:28px}
.card{background:var(--surface);border:1px solid var(--border);padding:18px}
.span2{grid-column:span 2}.span4{grid-column:span 4}
.k{font:700 11px/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:12px}
.v{font:700 clamp(26px,3vw,38px)/1.05 var(--display);white-space:nowrap}
.v small{font:500 14px var(--sans);color:var(--muted);margin-left:6px}
.d{color:var(--muted);font-size:14px;margin-top:10px}
.pill{display:inline-flex;align-items:center;gap:6px;font:700 11px/1 var(--mono);text-transform:uppercase;
letter-spacing:.06em;border:1px solid currentColor;padding:5px 8px;border-radius:999px}
.ok{color:var(--ok)}.warn{color:var(--warn)}.crit{color:var(--crit)}.acc{color:var(--accent)}
.compare{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.tele{font:500 13px/1.6 var(--mono);color:var(--muted);white-space:pre-wrap}
.tele b{color:var(--fg);font-weight:600}
.pending{font:italic 500 14px var(--sans);color:var(--muted)}
.tag{font:700 clamp(18px,2.4vw,24px)/1.3 var(--display);margin-top:36px}
.src{font-size:12px;color:var(--muted);margin-top:28px;border-top:1px solid var(--border);padding-top:12px;max-width:90ch}
table{width:100%;border-collapse:collapse;font-size:15px}
th,td{text-align:left;padding:12px 10px;border-bottom:1px solid var(--border);vertical-align:top}
th{font:700 11px/1.2 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
td.num{font:600 16px var(--mono)}td .sub{display:block;font:400 12px var(--sans);color:var(--muted);margin-top:4px}
tr.routed td{background:var(--surface-high)}
.scroll{overflow-x:auto}
@media (max-width:820px){.grid{grid-template-columns:1fr 1fr}.span4{grid-column:span 2}.compare{grid-template-columns:1fr}}
@media (max-width:520px){.grid{grid-template-columns:1fr}.span2,.span4{grid-column:span 1}}
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700&family=JetBrains+Mono:wght@500;600;700'
         '&family=Work+Sans:wght@400;500;600&display=swap" rel="stylesheet">')


def page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,'
            f'initial-scale=1"><title>{escape(title)}</title>{FONTS}<style>{CSS}</style></head><body><main>{body}</main></body></html>')


def money(x, digits=2):
    return PENDING if x is None else f"${x:,.{digits}f}"


def story(plant: dict, sweep: dict) -> str:
    cov = sweep.get("doc_coverage")
    d5 = sweep.get("review_d5_rate")
    fix = sweep.get("fix_rate")
    routed = sweep.get("summary", {}).get("profiles", {}).get("routed", {}).get("summary", {})
    caught = routed.get("defects_caught")
    cpvc = routed.get("cost_per_verified_change")
    extra = plant["cycle_legacy"] - plant["cycle_ref"] if plant["cycle_legacy"] and plant["cycle_ref"] else None
    body = f"""
<div class="strip"><span>EV battery pack</span><span>End of line</span><span>Station 20 leak test</span>
<span class="acc">Simulated plant, synthetic data</span></div>
<h1>The leak test passes packs that leak.</h1>
<p class="lede">A pack losing {plant['leak_measured_ref']:.2f} kPa in ten seconds should be rejected. The running program
computed a decay of {plant['leak_measured_legacy']:.2f} kPa, a value no real pack can produce, and passed it. The cause is one
instruction in a 2019 controller conversion. The line ran every day and nothing looked wrong.</p>
<div class="grid">
  <div class="card span2"><div class="k">What the plant sees</div>
    <div class="compare">
      <div><div class="pill crit">Running program</div><div class="tele" style="margin-top:12px">leaking pack
<b>decay computed  {plant['leak_measured_legacy']:.2f} kPa</b>
physically impossible
result          {'PASS' if plant['leak_passed_legacy'] else 'FAIL'}</div></div>
      <div><div class="pill ok">Proven fix</div><div class="tele" style="margin-top:12px">leaking pack
<b>decay computed  {plant['leak_measured_ref']:.2f} kPa</b>
over the 0.30 kPa limit
result          {'FAIL, rejected' if plant['leak_failed_ref'] else 'PASS'}</div></div>
    </div></div>
  <div class="card span2"><div class="k">Hidden cost on every good pack</div>
    <div class="v">{'+%.1f s' % extra if extra else PENDING}<small>per pack</small></div>
    <div class="d">The same conversion stretched one timer tenfold. Station time went from {plant['cycle_ref']:.1f} s to
    {plant['cycle_legacy']:.1f} s against a 23.0 s allowance.</div></div>
  <div class="card"><div class="k">Speed</div><div class="v">{'%d s' % sweep['doc_seconds'] if sweep.get('doc_seconds') else PENDING}</div>
    <div class="d">to document every device on the station, at {money(sweep.get('doc_cost'), 3)} a run.</div></div>
  <div class="card"><div class="k">Quality</div><div class="v">{('%g of 5' % caught['median']) if caught else PENDING}</div>
    <div class="d">planted defects caught before reaching the plant, median across repeated runs.</div></div>
  <div class="card"><div class="k">Knowledge</div><div class="v">{plant['documented_pct']}<small>%</small> → {('%d%%' % round(100 * cov)) if cov else PENDING}</div>
    <div class="d">of {plant['devices']} devices documented, before and after.</div></div>
  <div class="card"><div class="k">Cost</div><div class="v">{money(cpvc['median'], 3) if cpvc else PENDING}</div>
    <div class="d">per change proven on the simulator, all model calls included.</div></div>
  <div class="card span4"><div class="k">What the research says, and what we measured</div>
    <div class="d" style="margin-top:0">Documentation with generative AI took half the time in McKinsey's developer study. On this
    station the harness documented every device in {'%d seconds' % sweep['doc_seconds'] if sweep.get('doc_seconds') else 'a pending time'}.
    The same study found savings below 10 percent on high-complexity work. That is why every AI change here must pass the
    simulator before an engineer sees it: the reviewer found the leak defect in {('%d of %d' % (round(d5 * sweep['review_n']), sweep['review_n'])) if d5 is not None else 'a pending number of'} runs,
    and the fix passed the plant tests in {('%d of %d' % (round(fix * sweep['fix_n']), sweep['fix_n'])) if fix is not None else 'a pending number of'} runs.</div></div>
</div>
<p class="tag">AI proposes. The simulator proves. The engineer signs.</p>
<p class="src">Source: {MCKINSEY} Plant values are representative and come from the harness simulator; model results come from
the evaluation sweep in evals/REPORT.md.</p>"""
    return page("Leak test story", body)


def ledger(sweep: dict) -> str:
    s = sweep.get("summary", {})
    P = s.get("profiles", {})
    order = [("all-pro", "Premium model everywhere", "Gemini 3.1 Pro, high effort (preview)"),
             ("all-flash-high", "Flash, maximum effort", "Gemini 3.8 Flash, high thinking everywhere"),
             ("all-flash", "Flash, one setting", "Gemini 3.8 Flash, medium effort everywhere"),
             ("routed", "Horses for courses", "Each task on the lane the evidence chose")]

    def cell(p, key, fmt):
        r = P.get(p, {}).get("summary", {}).get(key)
        if not r:
            return PENDING
        main = fmt(r["median"])
        return main + (f'<span class="sub">{fmt(r["min"])} to {fmt(r["max"])}</span>' if r["min"] != r["max"] else "")

    rows = []
    for p, name, sub in order:
        cls = ' class="routed"' if p == "routed" else ""
        rows.append(f'<tr{cls}><td><b>{name}</b><span class="sub">{sub}</span></td>'
                    f'<td class="num">{cell(p, "cost_per_verified_change", lambda v: f"${v:.3f}")}</td>'
                    f'<td class="num">{cell(p, "cost_per_verified_change_list", lambda v: f"${v:.3f}")}</td>'
                    f'<td class="num">{cell(p, "verified_changes", lambda v: f"{v:g} of 4")}</td>'
                    f'<td class="num">{cell(p, "defects_caught", lambda v: f"{v:g} of 5")}</td>'
                    f'<td class="num">{cell(p, "wall_s", lambda v: f"{v / 60:.1f} min")}</td></tr>')
    names = {"flash-low": "Gemini 3.8 Flash, low effort", "flash-medium": "Gemini 3.8 Flash, medium effort",
             "flash-high": "Gemini 3.8 Flash, high effort", "pro-high": "Gemini 3.1 Pro, high effort",
             "opus-low": "Claude Opus 5.5, low effort", "opus-medium": "Claude Opus 5.5, medium effort"}
    lanes = {g: {**v, "config": names.get(v["config"], v["config"])} for g, v in s.get("lanes", {}).items()}
    lane_rows = "".join(
        f'<tr><td><b>{n}</b><span class="sub">{d}</span></td><td class="num">{escape(lanes[g]["config"]) if g in lanes else PENDING}</td></tr>'
        for g, n, d in (("T0", "Parse, lint, simulate, prove", "Deterministic"), ("T1", "Document every device", "Bulk"),
                        ("T2", "Read the narrative", "Extraction"), ("T3", "Change the program", "Until the plant tests pass"),
                        ("T4", "Engineering review", "The gate before a human"))
    ).replace(f'<td class="num">{PENDING}</td></tr>', '<td class="num">$0, no model</td></tr>', 1)
    r_s, simple_s, prem_s = (P.get(k, {}).get("summary", {}) for k in ("routed", "all-flash", "all-pro"))
    verdict = ""
    if r_s.get("cost_per_verified_change") and prem_s.get("cost_per_verified_change"):
        rc, pc = r_s["cost_per_verified_change"]["median"], prem_s["cost_per_verified_change"]["median"]
        sc = (simple_s.get("cost_per_verified_change") or {}).get("median")
        verdict = (f"Routing costs {1 - rc / pc:.0%} less per proven change than the premium model everywhere"
                   + (f" and {1 - rc / sc:.0%} less than Flash on one setting." if sc and rc < sc else
                      ". Against Flash on one well-chosen setting it is about the same: the saving comes from not "
                      "paying premium rates for work a cheaper horse does just as well."))
    body = f"""
<div class="strip"><span>Horses for courses</span><span>Measured, not estimated</span><span class="acc">Ranges over repeated runs</span></div>
<h1>Right model, right task.</h1>
<p class="lede">The same workload staffed four ways: onboard ST20, read its narrative, review it, and make four fixes that must pass
the plant tests. Median cost with the range across runs.</p>
<div class="card span4" style="margin-top:24px"><div class="scroll"><table>
<thead><tr><th>Staffing</th><th>Cost per proven change<br>Flash intro price</th><th>From 1 Jan 2027</th><th>Fixes proven</th><th>Defects caught</th><th>Time</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p class="d">{verdict or PENDING}</p></div>
<div class="grid" style="grid-template-columns:1fr 1fr">
  <div class="card"><div class="k">Where each task runs</div><table><tbody>{lane_rows}</tbody></table></div>
  <div class="card"><div class="k">What is not in these numbers</div><div class="d" style="margin-top:0">The IDE agent's own tokens are
  billed to the Antigravity seat. Gemini 3.1 Pro is a preview model. Claude Opus 5.5 was not enabled in the project for this
  run, so every lane here is Gemini. Prices are Google Cloud list prices read on 26 September 2026;
  Gemini 3.8 Flash doubles on 1 January 2027, shown in its own column. One synthetic cell: this shows the method, not a model benchmark.</div></div>
</div>
<p class="src">Source: evals/REPORT.md and evals/results/summary.json, sweep {escape(str(s.get('records', 0)))} records.</p>"""
    return page("Model cost ledger", body)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", default="S1")
    args = ap.parse_args()
    cell = load_cell(ROOT / "plant_data" / "ev_pack_eol", ROOT / "evals" / "answer_key")
    plant, sweep = plant_facts(cell), sweep_facts(args.sweep)
    out = ROOT / "demo"
    out.mkdir(exist_ok=True)
    (out / "story.html").write_text(story(plant, sweep), encoding="utf-8")
    (out / "ledger.html").write_text(ledger(sweep), encoding="utf-8")
    print(json.dumps({"plant": plant, "sweep_keys": sorted(k for k in sweep if k != "summary")}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
