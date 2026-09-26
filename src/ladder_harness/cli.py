"""`ladder` — the harness from any terminal. Mirrors the MCP tools; add --json for machine-readable output."""
from __future__ import annotations

import argparse
import json
import sys

from .tools import Tools
from .workspace import Workspace


def _print(data: dict, as_json: bool, cmd: str) -> None:
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    if cmd == "lint":
        for f in data["findings"]:
            where = f"rung {f['rung']}" if f["rung"] else "program"
            print(f"{f['rule']} {f['severity']:<7} {where:<9} {f['message']}")
        print(f"model cost: $0.00 (deterministic)")
    elif cmd == "simulate":
        for r in data["results"]:
            print(f"{'PASS' if r['passed'] else 'FAIL'} {r['id']:<12} {r['title']}")
            for msg in r["failures"]:
                print(f"     └ {msg}")
        print(f"{data['passed']} passed, {data['failed']} failed — model cost: $0.00 (simulator)")
    elif cmd == "ledger":
        for g in data["groups"]:
            label = " / ".join(str(v) for k, v in g.items() if k not in ("calls", "ok", "cost_usd", "input", "output", "latency_s"))
            print(f"{label:<40} {g['calls']:>4} calls  ${g['cost_usd']:.4f}  {g['input']:>9} in  {g['output']:>8} out")
        print(f"total ${data['total_cost_usd']:.4f} over {data['calls']} calls ({data['replayed_calls']} replayed)")
    elif cmd == "task":
        print(json.dumps(data["result"], indent=2, ensure_ascii=False)[:6000])
        for c in data["calls"]:
            tag = "REPLAY " if c["backend"] == "replay" else ""
            print(f"{tag}{c['model']}/{c['effort']}: ${c['cost_usd']:.4f}, {c['tokens_in']} in / {c['tokens_out']} out, {c['latency_s']} s")
        for a in data["attempts"]:
            print(f"attempt {a['attempt']}: {a['stage']}" + (f" — {a['reasons'][0][:160]}" if a["reasons"] else ""))
        for n in data["notes"]:
            print(f"note: {n}")
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ladder", description="AI proposes, the simulator proves, the engineer signs.")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("parse", "lint", "render"):
        p = sub.add_parser(name)
        p.add_argument("station")
        p.add_argument("--candidate")
    p = sub.add_parser("simulate")
    p.add_argument("station")
    p.add_argument("--candidate")
    p.add_argument("--only", nargs="*", help="scenario ids")
    p = sub.add_parser("diff")
    p.add_argument("station")
    p.add_argument("candidate")
    p = sub.add_parser("task")
    p.add_argument("task", choices=["explain", "extract", "review", "repair"])
    p.add_argument("station")
    p.add_argument("--goal", default="")
    p.add_argument("--targets", nargs="*")
    p.add_argument("--profile", default="routed")
    p.add_argument("--bank-task", default="", help="take goal/targets from evals/task_bank.yaml (e.g. RP-D5)")
    p = sub.add_parser("apply")
    p.add_argument("station")
    p.add_argument("candidate")
    p.add_argument("--targets", nargs="*")
    p = sub.add_parser("export")
    p.add_argument("station")
    p.add_argument("--which", default="proposed")
    p = sub.add_parser("ledger")
    p.add_argument("--by", default="profile,task_class")
    p.add_argument("--run")
    p = sub.add_parser("preflight", help="run before going on stage: decides live or replay")
    p.add_argument("--no-model-calls", action="store_true")
    args = ap.parse_args(argv)

    if args.cmd == "preflight":
        from .preflight import format_preflight, run_preflight
        checks, mode = run_preflight(Workspace.discover(), call_models=not args.no_model_calls)
        print(format_preflight(checks, mode))
        return 0 if mode != "offline-only" else 1

    t = Tools(Workspace.discover())
    if args.cmd == "parse":
        data = t.ladder_parse(args.station, args.candidate)
    elif args.cmd == "lint":
        data = t.ladder_lint(args.station, args.candidate)
    elif args.cmd == "render":
        data = t.ladder_render(args.station, args.candidate)
    elif args.cmd == "simulate":
        data = t.ladder_simulate(args.station, args.only, args.candidate)
    elif args.cmd == "diff":
        data = t.ladder_diff(args.station, args.candidate)
    elif args.cmd == "task":
        data = t.ladder_task(args.task, args.station, args.goal, args.targets, args.profile, args.bank_task)
    elif args.cmd == "apply":
        data = t.ladder_apply(args.station, args.candidate, args.targets)
    elif args.cmd == "export":
        data = t.ladder_export_gxw3(args.station, args.which)
    else:
        data = t.cost_ledger(args.by, args.run)
    _print(data, args.json, args.cmd)
    return 0 if data.get("ok", data.get("allowed", True)) is not False else 1


if __name__ == "__main__":
    sys.exit(main())
