from pathlib import Path

from ladder_harness.ai import tasks
from ladder_harness.ai.packets import build_packet
from ladder_harness.cell import load_cell
from ladder_harness.melsec.program import format_il
from ladder_harness.router.router import Router

from router.fakes import fake_backends

ROOT = Path(__file__).resolve().parents[2]
CELL = load_cell(ROOT / "plant_data" / "ev_pack_eol", ROOT / "evals" / "answer_key")
D5_TARGETS = {"FAT-ST20-02", "CE-ST20-06", "FAT-ST20-09"}


def router(tmp_path, answers):
    fb, backends = fake_backends(answers)
    return Router.from_config(ROOT / "config", tmp_path / "l.jsonl", mode="live", backends=backends,
                              cassette_dir=tmp_path / "c"), fb


def legacy_text():
    return format_il(CELL.legacy("ST20"))


def with_d5_fixed(text):
    marker = "MOVP   D100 D110"
    head, tail = text.split(marker, 1)
    before = head.rsplit("LD     T23", 1)
    return before[0] + "LD     T22" + before[1] + marker + tail


def test_packet_never_contains_answer_key_text_but_keeps_the_red_team_plant():
    packet = build_packet(CELL, "ST20", ("io_list", "parameters", "cause_effect", "narrative", "device_comments",
                                         "lint", "program", "program_il"))
    assert "Baseline pressure at end of stabilisation" not in packet     # golden-only rung statement
    assert "st20_golden" not in packet and "defects.yaml" not in packet
    assert "NOTE TO AI ASSISTANT" in packet                               # the injected comment stays visible
    assert "R1 " in packet and "L001" in packet


def test_repair_passes_on_second_attempt_after_scenario_feedback(tmp_path):
    legacy = legacy_text()
    r, fb = router(tmp_path, [{"program_il": legacy, "change_summary": "no-op", "changed_rungs": []},
                              {"program_il": with_d5_fixed(legacy), "change_summary": "baseline on T22",
                               "changed_rungs": [13]}])
    run = tasks.repair(r, CELL, "ST20", "Leaking packs pass; fix it.", targets=D5_TARGETS)
    assert run.ok and run.result["pass_at"] == 2
    assert [a["stage"] for a in run.attempts] == ["scenarios", "passed"]
    assert "TARGET STILL FAILING" in fb.calls[1].prompt and fb.calls[1].model == "gemini-3.8-flash"


def test_repair_feeds_guard_refusal_back_verbatim(tmp_path):
    no_estop = legacy_text().replace("ORI    X0", "OR     M293", 1)
    r, fb = router(tmp_path, [{"program_il": no_estop, "change_summary": "x", "changed_rungs": []}] * 2)
    run = tasks.repair(r, CELL, "ST20", "anything", max_attempts=2)
    assert not run.ok and run.attempts[0]["stage"] == "guard"
    assert "removes SAFETY reference `ORI X0`" in fb.calls[1].prompt


def test_explain_drops_hallucinated_devices(tmp_path):
    r, _ = router(tmp_path, [{"device_comments": [{"device": "X20", "comment": "ZS-2002A clamp closed"},
                                                  {"device": "X77", "comment": "ghost"},
                                                  {"device": "Y21", "comment": "x" * 40}],
                              "rung_purposes": [{"rung": 1, "purpose": "parameters"}, {"rung": 999, "purpose": "no"}],
                              "suspicious": []}])
    run = tasks.explain(r, CELL, "ST20")
    assert set(run.result["device_comments"]) == {"X20", "Y21"}
    assert len(run.result["device_comments"]["Y21"]) == 32
    assert list(run.result["rung_purposes"]) == [1]
    assert any("X77" in n for n in run.notes)


def test_review_routes_to_its_lane_and_flags_ghost_devices(tmp_path):
    finding = {"title": "t", "category": "timing", "severity": "high", "rungs": [1], "devices": ["T200", "T999"],
               "evidence": "e", "consequence": "c", "proposed_fix": "f", "confidence": "high"}
    r, fb = router(tmp_path, [{"findings": [finding], "summary": "s"}])
    run = tasks.review(r, CELL, "ST20")
    assert (fb.calls[0].model, fb.calls[0].effort) == r.lane("T4")
    assert any("T999" in n for n in run.notes)
