#!/usr/bin/env python3
"""Record demo/app/data/snapshot.js: every call the alpha front end makes, answered by the real harness.

    python scripts/build_app_snapshot.py

The page uses the snapshot when it is opened without the local server (a file, a static host, a laptop with no
Python). Each entry is the harness's own answer to the same call, recorded here in replay mode, so the recorded
page and the live page show the same things. Figures for the economics screen come from the evaluation sweep, as
`scripts/build_demo_pages.py` computes them. Nothing is typed in.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["LADDER_MODE"] = "replay"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "demo" / "app"))
sys.path.insert(0, str(ROOT / "scripts"))

import server  # noqa: E402
from build_demo_pages import plant_facts, sweep_facts  # noqa: E402
from ladder_harness.cell import load_cell  # noqa: E402

CAND = "demo/out/st20_candidate.il"
LEGACY = "plant_data/ev_pack_eol/st20/legacy.il"
TOOL_CALLS = [
    *[("ladder_parse", {"station": s}) for s in ("ST10", "ST20", "ST30")],
    *[("ladder_lint", {"station": s}) for s in ("ST10", "ST20", "ST30")],
    *[("ladder_simulate", {"station": s}) for s in ("ST10", "ST20", "ST30")],
    ("ladder_task", {"task": "explain", "station": "ST20"}),
    ("ladder_task", {"task": "extract", "station": "ST20"}),
    ("ladder_task", {"task": "review", "station": "ST20"}),
    ("ladder_apply", {"station": "ST20", "candidate_path": LEGACY, "targets": ["FAT-ST20-02"]}),
    ("ladder_task", {"task": "repair", "station": "ST20", "bank_task": "RP-D5"}),
    ("ladder_diff", {"station": "ST20", "candidate_path": CAND}),
    ("ladder_simulate", {"station": "ST20", "candidate_path": CAND}),
    ("ladder_apply", {"station": "ST30", "candidate_path": "demo/playground/st30_no_guard.il"}),
    ("ladder_apply", {"station": "ST20", "candidate_path": CAND,
                      "targets": ["FAT-ST20-02", "CE-ST20-06", "FAT-ST20-09"]}),
    ("ladder_export_gxw3", {"station": "ST20", "which": "proposed"}),
]


def key(path: str, args: dict) -> str:
    return path + "|" + json.dumps(args, sort_keys=True, separators=(",", ":"))


def main() -> int:
    server.reset()
    calls: dict[str, object] = {"/api/status|{}": {**server.status(), "live": False}}
    for name, args in TOOL_CALLS:
        try:
            out = server.call(f"/api/tool/{name}", dict(args))
        except Exception as e:  # recorded as the page would receive it
            out = {"error": str(e)}
        calls[key(f"/api/tool/{name}", args)] = out
        print(f"  {name:20s} {json.dumps(args)[:70]}")
    for which in ("running", "candidate", "signed"):
        for leak in (server.GOOD_LEAK, server.BAD_LEAK):
            args = {"program": which, "leak": leak}
            calls[key("/api/pack", args)] = server.call("/api/pack", args)
        calls[key("/api/line", {"program": which})] = server.call("/api/line", {"program": which})
    files = {f"/out/{p.name}": p.read_text(encoding="utf-8") for p in (ROOT / "demo" / "out").glob("*.html")}

    cell = load_cell(ROOT / "plant_data" / "ev_pack_eol", ROOT / "evals" / "answer_key")
    sweep = sweep_facts("S1")
    s = sweep.pop("summary", {})
    facts = {"plant": plant_facts(cell), "sweep": sweep,
             "profiles": {k: v.get("summary", {}) for k, v in s.get("profiles", {}).items()},
             "profile_configs": {k: v.get("configs", {}) for k, v in s.get("profiles", {}).items()},
             "lanes": s.get("lanes", {}), "classes": s.get("classes", {}), "records": s.get("records"),
             "built": date.today().isoformat()}
    mut = re.search(r"Score: (\d+)/(\d+) = ([\d.]+%)", (ROOT / "evals" / "results" / "mutation_st20.md").read_text())
    if mut:
        facts["mutation"] = f"{mut.group(3)} ({mut.group(1)} of {mut.group(2)} mutants)"
    judge = json.loads((ROOT / "evals" / "results" / "judge_calibration.json").read_text())
    j = judge.get("gemini-3.8-flash:high") or next(iter(judge.values()), None)
    if j:
        facts["judge"] = f"{round(j['agreement'] * j['n'])} / {j['n']} agreed"
    # A script, not JSON, so the page also works opened straight from disk (file:// cannot fetch JSON).
    out = ROOT / "demo" / "app" / "data" / "snapshot.js"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("window.LADDER_SNAPSHOT = " + json.dumps({"calls": calls, "files": files, "facts": facts},
                                                          default=str) + ";\n", encoding="utf-8")
    server.reset()
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB, {len(calls)} calls)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
