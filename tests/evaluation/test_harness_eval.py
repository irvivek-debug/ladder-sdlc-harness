import copy
import json
from pathlib import Path

import yaml
from inspect_ai import eval as inspect_eval

from ladder_harness.cell import load_cell
from ladder_harness.evaluation import harness_eval, scoring
from ladder_harness.router.ledger import Ledger
from ladder_harness.router.pricing import Pricing
from ladder_harness.router.router import Router
from ladder_harness.variants import make_variant
from router.fakes import FakeBackend

ROOT = Path(__file__).resolve().parents[2]
CELL = load_cell(ROOT / "plant_data" / "ev_pack_eol", ROOT / "evals" / "answer_key")


def test_inspect_runs_the_harness_and_scores_against_the_key(tmp_path):
    bank = harness_eval.load_bank(ROOT / "evals" / "task_bank.yaml")
    program, _ = make_variant(CELL, "ST20", ["D5"])
    rung = min(scoring.anchor_rungs(program, ["MOVP D100 D110"]))
    finding = {"title": "baseline sampled at test end", "category": "semantic_logic", "severity": "critical",
               "rungs": [rung], "devices": ["D110", "T23"], "evidence": "e", "consequence": "c",
               "proposed_fix": "use T22", "confidence": "high"}
    fb = FakeBackend([{"findings": [finding], "summary": "s"}] * 4)
    routing = yaml.safe_load((ROOT / "config" / "routing.yaml").read_text())

    def make_router(config):
        doc = copy.deepcopy(routing)
        doc["profiles"]["cfg"] = dict(bank["configs"][config])
        return Router(doc, Pricing.load(ROOT / "config" / "pricing.yaml"), Ledger(tmp_path / "l.jsonl"),
                      mode="live", backends={"vertex-gemini": fb, "vertex-claude": fb}, cassette_dir=tmp_path / "c",
                      run_id="test")

    sink = tmp_path / "runs.jsonl"
    harness_eval.CTX = harness_eval.EvalContext(CELL, bank, make_router, sink)
    task = harness_eval.build_task("T4", "flash-high", bank, epochs=2, ids={"RV-D5"})
    logs = inspect_eval(task, model="mockllm/model", log_dir=str(tmp_path / "logs"), display="none")
    assert logs[0].status == "success"
    recs = [json.loads(line) for line in sink.read_text().splitlines()]
    assert len(recs) == 2 and all(r["passed"] and r["score"]["matched"] == {"D5": finding["title"]} for r in recs)
    assert {r["epoch"] for r in recs} == {1, 2} and all(r["model"] == "gemini-3.8-flash" for r in recs)
    assert fb.calls[0].effort == "high"
