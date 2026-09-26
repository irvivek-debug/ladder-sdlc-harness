#!/usr/bin/env bash
# Run once Claude Opus 5.5 is enabled for the project in Model Garden. Completes sweep S1 and refreshes every artefact.
#   LADDER_GCP_PROJECT=<project> scripts/finish_opus_half.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
: "${LADDER_GCP_PROJECT:?set LADDER_GCP_PROJECT}"
$PY - <<'PY'
import os
from anthropic import AnthropicVertex
AnthropicVertex(project_id=os.environ["LADDER_GCP_PROJECT"], region="global").messages.create(
    model="claude-opus-5-5", max_tokens=32, output_config={"effort": "low"}, messages=[{"role": "user", "content": "OK"}])
print("Opus 5.5 reachable")
PY
$PY scripts/calibrate_judge.py claude-opus-5-5:low                 # the judge for Gemini documentation
$PY scripts/run_evals.py --sweep S1 --configs opus-low,opus-medium --epochs 5 --budget 150 --max-tasks 8 --max-samples 6
$PY scripts/run_evals.py --sweep S1 --fill-gaps --workers 6 --budget 150   # transient errors, every config
$PY scripts/rejudge.py --sweep S1                                    # Gemini documentation judged by Opus
$PY scripts/rescore_reviews.py --sweep S1
$PY scripts/rescore_redteam.py --sweep S1
$PY scripts/make_report.py --sweep S1 --write-routing
$PY scripts/pin_demo_cassettes.py --sweep S1
$PY scripts/build_demo_pages.py --sweep S1
$PY - <<'PY'
import json
rows = [l for l in open("logs/ledger.jsonl") if l.strip() and json.loads(l).get("run_id") in ("S1", "calibration", "smoke")]
open("evals/results/ledger_S1.jsonl", "w").writelines(rows)
PY
echo "done: see evals/REPORT.md, config/routing.yaml, demo/story.html, demo/ledger.html"
