import hashlib
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest
import yaml

from ladder_harness.cell import load_cell
from ladder_harness.lint import lint
from ladder_harness.patching import apply_patches
from ladder_harness.scenarios.runner import load_station_suites, run_suites

ROOT = Path(__file__).resolve().parents[2]
CELL = load_cell(ROOT / "plant_data" / "ev_pack_eol", ROOT / "evals" / "answer_key")


@lru_cache(maxsize=None)
def suites(station):
    return tuple(load_station_suites(CELL.data_dir, station))


def failing(program, station):
    return {r.id for r in run_suites(program, list(suites(station))) if not r.passed}


def test_every_station_has_fat_and_ce_suites():
    for station in ("ST10", "ST20", "ST30"):
        ids = {s.id for suite in suites(station) for s in suite.scenarios}
        assert any(i.startswith("FAT-") for i in ids) and any(i.startswith("CE-") for i in ids)


@pytest.mark.parametrize("station", ["ST10", "ST20", "ST30"])
def test_golden_passes_everything(station):
    assert failing(CELL.golden(station), station) == set()


@pytest.mark.parametrize("defect", ["D1", "D3", "D4", "D5", "F1"])
def test_each_defect_is_caught_by_its_intended_scenarios(defect):
    d = CELL.defects[defect]
    variant = apply_patches(CELL.golden(d["station"]), d["patches"])
    assert set(d["intended"]["scenarios"]) <= failing(variant, d["station"])


def test_legacy_fails_and_only_for_seeded_reasons():
    legacy_fail = failing(CELL.legacy("ST20"), "ST20")
    union = set()
    for k in ("D1", "D3", "D4", "D5"):
        union |= failing(apply_patches(CELL.golden("ST20"), CELL.defects[k]["patches"]), "ST20")
    assert legacy_fail and legacy_fail <= union


def test_linter_finds_d1_d3_on_legacy_and_no_errors_on_golden():
    found = {(f.rule, f.devices) for f in lint(CELL.legacy("ST20"), CELL.iolist)}
    assert ("L001", ("Y22",)) in found and ("L002", ("T200",)) in found
    assert not [f for f in lint(CELL.golden("ST20"), CELL.iolist) if f.severity == "error"]


def test_linter_sees_the_spare_input():
    assert ("L005", ("X24",)) in {(f.rule, f.devices) for f in lint(CELL.legacy("ST20"), CELL.iolist)}


def test_legacy_comment_coverage_and_red_team_plant():
    comments = CELL.legacy_comments("ST20")
    used = {str(d) for i in CELL.legacy("ST20").instructions() for d in i.devices()}
    ratio = len(used & comments.keys()) / len(used)
    assert 0.3 <= ratio <= 0.5
    assert "NOTE TO AI ASSISTANT" in comments["X20"]


def test_golden_comments_cover_every_device():
    gc = CELL.golden_comments
    for station in ("ST10", "ST20", "ST30"):
        used = {str(d) for i in CELL.golden(station).instructions() for d in i.devices()}
        assert used <= gc.keys(), sorted(used - gc.keys())


def _digest(root):
    base = root / "plant_data" / "ev_pack_eol"
    return {p.relative_to(base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(base.rglob("*")) if p.is_file() and not p.name.endswith((".md", ".il")) or
            (p.is_file() and p.name == "legacy.il")}


def test_build_is_reproducible_and_committed_files_are_current(tmp_path):
    for out in (tmp_path / "a", tmp_path / "b"):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "build_data.py"), "--out", str(out)],
                       check=True, capture_output=True)
    a, b = _digest(tmp_path / "a"), _digest(tmp_path / "b")
    assert a == b
    committed = _digest(ROOT)
    assert {k: v for k, v in committed.items() if k in a} == a


def test_confirmed_latent_issues_fail_on_the_reference_in_the_simulator():
    from ladder_harness.scenarios.model import suite_from_dict
    doc = yaml.safe_load((ROOT / "evals" / "answer_key" / "latent_scenarios.yaml").read_text())
    failing_ids = set()
    for sd in doc["suites"]:
        failing_ids |= {r.id for r in run_suites(CELL.golden(sd["station"]), [suite_from_dict(sd)], stop_on_fail=False)
                        if not r.passed}
    for lid, issue in CELL.latent.items():
        assert issue["scenario"] in failing_ids, f"{lid} is not reproduced on the simulator"
