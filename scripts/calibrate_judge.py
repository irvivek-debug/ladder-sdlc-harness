#!/usr/bin/env python3
"""Measure each T1 judge against the author-labelled calibration pairs. A judge is kept only at >= 80% agreement.

    python scripts/calibrate_judge.py gemini-3.8-flash:high claude-opus-5-5:low
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml  # noqa: E402

from ladder_harness.evaluation.scoring import JUDGE_SCHEMA, JUDGE_SYSTEM  # noqa: E402
from ladder_harness.router.router import Router  # noqa: E402


def main() -> int:
    pairs = yaml.safe_load((ROOT / "evals" / "judge_calibration.yaml").read_text())["pairs"]
    router = Router.from_config(ROOT / "config", ROOT / "logs" / "ledger.jsonl", mode="record",
                                cassette_dir=ROOT / "evals" / "cassettes", run_id="calibration")
    out_path = ROOT / "evals" / "results" / "judge_calibration.json"
    results = json.loads(out_path.read_text()) if out_path.exists() else {}
    for spec in sys.argv[1:]:
        model, effort = spec.split(":")
        # Same prompt shape as scoring.judge_pairs; devices are indexed so repeated devices stay distinct.
        lines = "\n".join(f"- device {p['device']}#{i}: REFERENCE \"{p['reference']}\" | CANDIDATE \"{p['candidate']}\""
                          for i, p in enumerate(pairs))
        res = router.call("JUDGE", JUDGE_SYSTEM, f"Pairs:\n{lines}\n\nReturn one verdict per device (keep the #index).",
                          JUDGE_SCHEMA, model=model, effort=effort, meta={"task": "judge-calibration"})
        verdicts = {v["device"].upper(): bool(v["match"]) for v in res.data.get("verdicts", [])}
        agree, disagreements = 0, []
        for i, p in enumerate(pairs):
            got = verdicts.get(f"{p['device']}#{i}".upper())
            if got == p["label"]:
                agree += 1
            else:
                disagreements.append({"device": p["device"], "candidate": p["candidate"], "label": p["label"], "judge": got})
        results[spec] = {"n": len(pairs), "agreement": round(agree / len(pairs), 3), "cost_usd": round(res.cost_usd, 5),
                         "disagreements": disagreements}
        print(f"{spec}: {agree}/{len(pairs)} = {agree / len(pairs):.0%}  (${res.cost_usd:.4f})")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
