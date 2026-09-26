#!/usr/bin/env python3
"""Aggregate sweep records into evals/results/summary.json, evals/REPORT.md and (with --write-routing)
config/routing.yaml — the routing table is an output of the evidence, not an assertion.

    python scripts/make_report.py --sweep S1 [--write-routing]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml  # noqa: E402

from ladder_harness.evaluation import aggregate as agg  # noqa: E402
from ladder_harness.evaluation.harness_eval import load_bank  # noqa: E402

GROUP_NAMES = {"T1": "T1 bulk documentation", "T2": "T2 extraction", "T3": "T3 repair until the gate passes",
               "T4": "T4 semantic review", "RT": "Red team"}


def money(x, digits=3):
    return "—" if x is None else f"${x:.{digits}f}"


def rng(r, fmt=lambda v: f"{v}"):
    if not r:
        return "—"
    if r["min"] == r["max"]:
        return fmt(r["median"])
    return f"{fmt(r['median'])} ({fmt(r['min'])}–{fmt(r['max'])})"


def write_routing(summary: dict, bank: dict, sweep: str) -> None:
    path = ROOT / "config" / "routing.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["generated_by"] = f"scripts/make_report.py from sweep {sweep} on {dt.date.today().isoformat()}"
    for g, lane in summary["lanes"].items():
        cfg = bank["configs"][lane["config"]]
        doc["task_classes"][g].update({"model": cfg["model"], "effort": cfg["effort"], "evidence_rule": lane["rule"],
                                       "chosen_config": lane["config"]})
    path.write_text("# Which model runs which task class — GENERATED from evaluation evidence (see evals/REPORT.md).\n"
                    + yaml.safe_dump(doc, sort_keys=False, width=110), encoding="utf-8")


def report(summary: dict, bank: dict, sweep: str, calib: dict | None, mutation: str | None) -> str:
    L = []
    L.append("# Evaluation report — horses for courses on the EV-pack EOL cell\n")
    L.append(f"Sweep `{sweep}` · generated {dt.date.today().isoformat()} · {summary['usable']} scored samples "
             f"({summary['errors']} errored samples reported, not scored). Prices from `config/pricing.yaml` "
             f"(Google Cloud list, read 2026-09-26). Gemini 3.1 Pro is a **preview** model.\n")
    P = summary.get("profiles", {})
    if P:
        L.append("## The four ways to staff the work\n")
        L.append("Workload: onboard and fix ST20 — document (T1), extract (T2), review (T4), and four repairs "
                 "(D1, D3, D4, D5), each proven on the simulator. Median, with min–max over epochs.\n")
        L.append("| Profile | Configs (T1 / T2 / T3 / T4) | Cost per verified change — Flash intro price | "
                 "— Flash 2027 price | Verified changes (of 4) | Defects caught before the plant (of 5) | Wall time |")
        L.append("|---|---|---|---|---|---|---|")
        for name in ("all-pro", "all-flash-high", "all-flash", "routed"):
            if name not in P:
                continue
            p, s = P[name], P[name]["summary"]
            cfgs = " / ".join(p["configs"].get(g, "—") for g in ("T1", "T2", "T3", "T4"))
            L.append(f"| **{name}** | {cfgs} | {rng(s['cost_per_verified_change'], money)} | "
                     f"{rng(s['cost_per_verified_change_list'], money)} | {rng(s['verified_changes'])} | "
                     f"{rng(s['defects_caught'])} | {rng(s['wall_s'], lambda v: f'{v/60:.1f} min')} |")
        L.append("")
        r, simple, prem = (P.get(k, {}).get("summary", {}) for k in ("routed", "all-flash", "all-pro"))
        if r.get("cost_per_verified_change") and simple.get("cost_per_verified_change"):
            rc, sc = r["cost_per_verified_change"]["median"], simple["cost_per_verified_change"]["median"]
            pc = (prem.get("cost_per_verified_change") or {}).get("median")
            L.append("**Honesty clause (milestone M4):** routed costs "
                     + (f"{(1 - rc / pc):.0%} less than the premium model everywhere and " if pc else "")
                     + (f"{(1 - rc / sc):.0%} less than" if rc < sc else "no less than")
                     + " the simplest alternative (Flash medium for everything) per verified change. "
                     + ("" if rc < sc else "Against one well-chosen cheap model, routing's value is catching the same "
                                           "defects with the right effort per task, not a lower bill.") + "\n")
            L.append("Claude Opus 5.5 was not enabled in the project during this sweep, so every lane is Gemini; the "
                     "harness supports Opus on Vertex and the sweep can add it with `--configs opus-low,opus-medium`.\n")
    L.append("## Lanes chosen from the evidence\n")
    for g, lane in summary["lanes"].items():
        L.append(f"- **{GROUP_NAMES[g]} → `{lane['config']}`** ({lane['rule']}).")
    L.append("")
    for g in ("T1", "T2", "T3", "T4", "RT"):
        rows = [r for r in summary["classes"].values() if r["group"] == g]
        if not rows:
            continue
        L.append(f"## {GROUP_NAMES[g]}\n")
        extra = {"T1": ["mean_quality", "mean_coverage"], "T3": ["pass@1", "pass@3", "cost_per_verified_change"],
                 "T4": ["mean_recall", "false_positives_per_review", "injection_flag_rate"],
                 "RT": ["tool_bypasses", "model_compliance_rate"]}.get(g, [])
        L.append("| Config | Model / effort | n | Pass rate | Mean cost | " + "".join(f"{e} | " for e in extra) + "Errors |")
        L.append("|---|---|---|---|---|" + "---|" * len(extra) + "---|")
        for r in sorted(rows, key=lambda r: r.get("mean_cost_usd", 0)):
            if not r.get("n"):
                L.append(f"| {r['config']} | — | 0 | — | — | " + "".join("— | " for _ in extra) + f"{r['errors']} |")
                continue
            vals = [("—" if r.get(k) is None else (money(r[k], 4) if "cost" in k else str(r[k]))) for k in extra]
            L.append(f"| {r['config']} | {r['model']} / {r['effort']} | {r['n']} | {r['pass_rate']:.0%} | "
                     f"{money(r['mean_cost_usd'], 4)} | " + "".join(f"{v} | " for v in vals) + f"{r['errors']} |")
        L.append("")
    if calib:
        L.append("## Judge calibration (T1 accuracy)\n")
        for j, c in calib.items():
            L.append(f"- `{j}`: {c['agreement']:.0%} agreement on {c['n']} author-labelled pairs "
                     + ("— **kept**" if c["agreement"] >= 0.8 else "— **dropped** (below 80%)"))
        L.append("")
    if mutation:
        L.append("## Are the tests strong enough to judge AI output?\n")
        L.append(mutation + "\n")
    L.append("## Method and limits\n")
    L.append("- Every sample is scored against the sealed answer key (`evals/answer_key/`), which no model packet "
             "includes.\n- Repairs pass only through the apply gate: parse → SAFETY guard → no new lint errors → "
             "targets fixed and no scenario regressions.\n- The red team counts model compliance and tool-layer "
             "bypasses separately; the tool layer is deterministic.\n- Costs are token costs of the harness's model "
             "calls. The IDE agent's own tokens (for example AGY's front-desk model) are billed to the seat and are "
             "not included.\n- The data set is one synthetic cell. These results show the method; they are not a "
             "benchmark of the models in general.")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", default="S1")
    ap.add_argument("--write-routing", action="store_true")
    args = ap.parse_args()
    bank = load_bank(ROOT / "evals" / "task_bank.yaml")
    records = agg.load_records([ROOT / "evals" / "results" / "runs" / f"{args.sweep}.jsonl"])
    summary = agg.build_summary(records)
    out = ROOT / "evals" / "results" / "summary.json"
    out.write_text(json.dumps(summary, indent=1, sort_keys=True, default=str), encoding="utf-8")
    calib_path = ROOT / "evals" / "results" / "judge_calibration.json"
    calib = json.loads(calib_path.read_text()) if calib_path.exists() else None
    mut_path = ROOT / "evals" / "results" / "mutation_st20.md"
    mutation = None
    if mut_path.exists():
        line = next((l for l in mut_path.read_text().splitlines() if l.startswith("**Score")), None)
        mutation = f"ST20 scenario suite mutation {line.strip('*') if line else ''} — see `evals/results/mutation_st20.md`."
    (ROOT / "evals" / "REPORT.md").write_text(report(summary, bank, args.sweep, calib, mutation), encoding="utf-8")
    if args.write_routing and all(g in summary["lanes"] for g in ("T1", "T2", "T3", "T4")):
        write_routing(summary, bank, args.sweep)
        print("config/routing.yaml regenerated from evidence")
    print(f"{summary['usable']} scored, {summary['errors']} errored → evals/REPORT.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
