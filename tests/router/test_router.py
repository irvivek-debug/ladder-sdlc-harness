from pathlib import Path

import pytest

from ladder_harness.router.router import Router
from ladder_harness.router.types import ReplayMiss

from .fakes import fake_backends

ROOT = Path(__file__).resolve().parents[2]


def router(tmp_path, mode="live", answers=None):
    fb, backends = fake_backends(answers)
    r = Router.from_config(ROOT / "config", tmp_path / "ledger.jsonl", mode=mode, backends=backends,
                           cassette_dir=tmp_path / "cassettes")
    return r, fb


def test_lanes_per_profile(tmp_path):
    r, _ = router(tmp_path)
    assert r.lane("T1") == ("gemini-3.8-flash", "low")
    assert r.lane("T4") == ("claude-opus-5-5", "medium")
    assert r.lane("T1", "all-opus-low") == ("claude-opus-5-5", "low")
    assert r.lane("T4", "all-flash") == ("gemini-3.8-flash", "medium")
    with pytest.raises(ValueError, match="deterministic"):
        r.lane("T0")


def test_call_is_priced_and_logged(tmp_path):
    r, fb = router(tmp_path, answers=[{"x": 1}])
    res = r.call("T4", "sys", "prompt", {"type": "object"}, meta={"task_id": "t-1"})
    assert res.data == {"x": 1} and fb.calls[0].model == "claude-opus-5-5"
    assert res.cost_usd > 0 and set(res.cost_by_period) == {"list"}
    line = r.ledger.read()[0]
    assert line["task_id"] == "t-1" and line["backend"] == "fake" and line["ok"]


def test_record_then_replay_round_trip(tmp_path):
    rec, _ = router(tmp_path, mode="record", answers=[{"answer": 42}])
    a = rec.call("T1", "s", "p", {"type": "object"})
    rep, fb = router(tmp_path, mode="replay")
    b = rep.call("T1", "s", "p", {"type": "object"})
    assert b.data == a.data == {"answer": 42} and b.backend == "replay" and not fb.calls


def test_replay_miss_raises(tmp_path):
    rep, _ = router(tmp_path, mode="replay")
    with pytest.raises(ReplayMiss):
        rep.call("T1", "s", "never recorded", {"type": "object"})


def test_auto_prefers_cassette_then_live(tmp_path):
    rec, _ = router(tmp_path, mode="record", answers=[{"v": "recorded"}])
    rec.call("T2", "s", "p", {"type": "object"})
    auto, fb = router(tmp_path, mode="auto", answers=[{"v": "live"}])
    assert auto.call("T2", "s", "p", {"type": "object"}).data == {"v": "recorded"}
    assert auto.call("T2", "s", "other", {"type": "object"}).data == {"v": "live"}
    assert len(fb.calls) == 1


def test_failed_call_is_logged_and_raised(tmp_path):
    def boom(c):
        raise RuntimeError("500 from model")
    r, _ = router(tmp_path, answers=[boom])
    with pytest.raises(RuntimeError):
        r.call("T1", "s", "p", {"type": "object"})
    assert r.ledger.read()[0]["ok"] is False
