import pytest

from ladder_harness.evaluation import aggregate as agg


def rec(task, group, config, epoch, passed, cost, model="m", **score):
    kind = {"T1": "explain", "T2": "extract", "T3": "repair", "T4": "review", "RT": "repair"}[group]
    return {"task_id": task, "group": group, "kind": kind, "station": "ST20", "config": config, "model": model,
            "effort": "x", "epoch": epoch, "passed": passed, "cost_usd": cost, "cost_by_period": {"list": cost * 2},
            "wall_s": 10, "score": {"judge": "done", **score}, "error": None}


def test_fisher_one_sided_behaves():
    assert agg.fisher_one_sided(10, 10, 10, 10) == pytest.approx(1.0)
    assert agg.fisher_one_sided(10, 10, 0, 10) < 0.001
    assert agg.fisher_one_sided(9, 10, 8, 10) > 0.05


def test_pass_at_k_unbiased():
    assert agg.pass_at_k(5, 0, 1) == 0.0 and agg.pass_at_k(5, 5, 3) == 1.0
    assert agg.pass_at_k(5, 1, 1) == pytest.approx(0.2)


def test_lane_rule_picks_cheapest_indistinguishable_config():
    rs = []
    for e in range(1, 6):
        for t in ("A", "B", "C", "D"):
            rs.append(rec(t, "T3", "cheap", e, True, 0.01))
            rs.append(rec(t, "T3", "pricey", e, True, 0.30))
            rs.append(rec(t, "T3", "bad", e, e == 1, 0.001))
    lanes = agg.choose_lanes(agg.class_table(rs))
    assert lanes["T3"]["config"] == "cheap"
    assert lanes["T3"]["evidence"]["bad"]["p_vs_best"] < 0.05


def test_review_lane_is_best_recall_even_if_pricier():
    rs = [rec("R", "T4", "cheap", e, False, 0.01, recall=0.5) for e in range(1, 6)]
    rs += [rec("R", "T4", "opus", e, True, 0.5, recall=1.0) for e in range(1, 6)]
    assert agg.choose_lanes(agg.class_table(rs))["T4"]["config"] == "opus"


def test_errors_and_pending_judges_are_not_scored():
    rs = [rec("EX", "T1", "c", 1, False, 0.01), {**rec("EX", "T1", "c", 2, False, 0.01), "error": "boom"}]
    rs[0]["score"]["judge"] = "pending: NotFound"
    table = agg.class_table(rs)
    assert table["T1/c"]["n"] == 0 and table["T1/c"]["errors"] == 1


def test_profile_workload_ranges():
    rs = []
    for e in range(1, 4):
        for cfg, ok, cost in (("flash-medium", e != 3, 0.05), ("opus-medium", True, 0.5), ("opus-low", True, 0.3)):
            rs.append(rec("EX-ST20", "T1", cfg, e, True, cost / 10, quality=0.9))
            rs.append(rec("XT-ST20", "T2", cfg, e, True, cost / 10))
            rs.append(rec("RV-LEGACY", "T4", cfg, e, ok, cost, recall=1.0 if ok else 0.5,
                          matched={"D4": "x", "D5": "y"} if ok else {"D4": "x"}))
            for t in ("RP-D1", "RP-D3", "RP-D4", "RP-D5"):
                rs.append(rec(t, "T3", cfg, e, ok or t != "RP-D5", cost))
    summary = agg.build_summary(rs)
    flash = summary["profiles"]["all-flash"]["summary"]
    assert flash["defects_caught"]["max"] == 5 and flash["defects_caught"]["min"] == 4
    assert summary["profiles"]["routed"]["epochs"] == 3
