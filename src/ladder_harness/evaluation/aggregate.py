"""Turn sweep records into evidence: per-class results, lanes chosen by the M4 rule, and the four baselines.

Lane rule: per class, the cheapest config whose pass rate is not significantly below the best config's
(one-sided Fisher exact test, alpha 0.05). T4 (review) takes the best config by mean recall, cost aside.
Profiles are views over the same matrix: all-pro = Gemini 3.1 Pro high everywhere (the premium horse),
all-flash-high = Flash high everywhere, all-flash = Flash medium everywhere, routed = the chosen lanes.
"""
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

WORKLOAD = {"T1": ["EX-ST20"], "T2": ["XT-ST20"], "T4": ["RV-LEGACY"], "T3": ["RP-D1", "RP-D3", "RP-D4", "RP-D5"]}
PROFILES = {"all-pro": "pro-high", "all-flash-high": "flash-high", "all-flash": "flash-medium"}
LINT_CAUGHT = {"D1", "D3"}      # the $0 linter finds these on the legacy program every time (tested)


def load_records(paths: list[Path]) -> list[dict]:
    latest: dict[tuple, dict] = {}
    for p in paths:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                latest[(r["task_id"], r["config"], r["epoch"])] = r
    return list(latest.values())


def usable(r: dict) -> bool:
    """Errored samples and explain samples still waiting for their judge are reported, never scored."""
    if r.get("error"):
        return False
    judge_pending = str(r["score"].get("judge", "done")).startswith("pending")
    return not (r["kind"] == "explain" and r["group"] != "RT" and judge_pending)


def fisher_one_sided(a_succ: int, a_n: int, b_succ: int, b_n: int) -> float:
    """P(observing b's successes this low or lower if a and b share one rate) — hypergeometric lower tail."""
    total_s, n = a_succ + b_succ, a_n + b_n
    def p(k):
        return math.comb(total_s, k) * math.comb(n - total_s, b_n - k) / math.comb(n, b_n)
    lo = max(0, b_n - (n - total_s))
    return min(1.0, sum(p(k) for k in range(lo, b_succ + 1)))


def pass_at_k(n: int, c: int, k: int) -> float:
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def class_table(records: list[dict]) -> dict:
    by: dict[tuple, list[dict]] = defaultdict(list)
    for r in records:
        if usable(r):
            by[(r["group"], r["config"])].append(r)
    table: dict = {}
    for (group, config), rs in sorted(by.items()):
        n, succ = len(rs), sum(r["passed"] for r in rs)
        row = {"group": group, "config": config, "model": rs[0]["model"], "effort": rs[0]["effort"], "n": n,
               "passed": succ, "pass_rate": round(succ / n, 3),
               "mean_cost_usd": round(statistics.mean(r.get("cost_usd", 0.0) for r in rs), 5),
               "mean_cost_list_usd": round(statistics.mean(r.get("cost_by_period", {}).get("list", r.get("cost_usd", 0.0))
                                                           for r in rs), 5),
               "median_wall_s": round(statistics.median(r.get("wall_s") or 0 for r in rs), 1),
               "errors": 0}
        if group == "T3":
            per_task = defaultdict(list)
            for r in rs:
                per_task[r["task_id"]].append(r["passed"])
            row["pass@1"] = round(statistics.mean(pass_at_k(len(v), sum(v), 1) for v in per_task.values()), 3)
            row["pass@3"] = round(statistics.mean(pass_at_k(len(v), sum(v), 3) for v in per_task.values()
                                                  if len(v) >= 3), 3) if any(len(v) >= 3 for v in per_task.values()) else None
            costs = [r["cost_usd"] for r in rs]
            row["cost_per_verified_change"] = round(sum(costs) / succ, 4) if succ else None
        if group == "T4":
            row["mean_recall"] = round(statistics.mean(r["score"].get("recall", 0.0) for r in rs), 3)
            row["false_positives_per_review"] = round(statistics.mean(r["score"].get("false_positives", 0) for r in rs), 2)
            row["injection_flag_rate"] = round(statistics.mean(bool(r["score"].get("injection_flagged")) for r in rs), 3)
        if group == "T1":
            row["mean_quality"] = round(statistics.mean(r["score"].get("quality", 0.0) for r in rs), 3)
            row["mean_coverage"] = round(statistics.mean(r["score"].get("coverage", 0.0) for r in rs), 3)
        if group == "RT":
            row["tool_bypasses"] = sum(bool(r["score"].get("tool_bypass")) for r in rs)
            row["model_compliance_rate"] = round(statistics.mean(bool(r["score"].get("model_complied")) for r in rs), 3)
        table[f"{group}/{config}"] = row
    errors = defaultdict(int)
    for r in records:
        if r.get("error"):
            errors[f"{r['group']}/{r['config']}"] += 1
    for k, v in errors.items():
        if k in table:
            table[k]["errors"] = v
        else:
            group, config = k.split("/")
            table[k] = {"group": group, "config": config, "n": 0, "errors": v}
    return table


def choose_lanes(table: dict, alpha: float = 0.05) -> dict:
    lanes = {}
    for group in ("T1", "T2", "T3", "T4"):
        rows = [r for r in table.values() if r["group"] == group and r.get("n")]
        if not rows:
            continue
        if group == "T4":
            best = max(rows, key=lambda r: (r["mean_recall"], r["pass_rate"], -r["mean_cost_usd"]))
            lanes[group] = {"config": best["config"], "rule": "best mean recall (review gate; cost aside)",
                            "evidence": {r["config"]: {"mean_recall": r["mean_recall"], "pass_rate": r["pass_rate"],
                                                       "n": r["n"], "mean_cost_usd": r["mean_cost_usd"]} for r in rows}}
            continue
        best = max(rows, key=lambda r: (r["pass_rate"], -r["mean_cost_usd"]))
        evidence, eligible = {}, []
        for r in rows:
            pval = fisher_one_sided(best["passed"], best["n"], r["passed"], r["n"]) if r is not best else 1.0
            evidence[r["config"]] = {"pass_rate": r["pass_rate"], "n": r["n"], "p_vs_best": round(pval, 4),
                                     "mean_cost_usd": r["mean_cost_usd"]}
            if pval >= alpha:
                eligible.append(r)
        chosen = min(eligible, key=lambda r: r["mean_cost_usd"])
        lanes[group] = {"config": chosen["config"], "best": best["config"],
                        "rule": f"cheapest config not significantly below the best (one-sided Fisher, alpha={alpha})",
                        "evidence": evidence}
    return lanes


def profile_workloads(records: list[dict], lanes: dict) -> dict:
    idx = {(r["task_id"], r["config"], r["epoch"]): r for r in records if usable(r)}
    epochs = sorted({r["epoch"] for r in records})
    profiles = {**{p: {g: c for g in WORKLOAD} for p, c in PROFILES.items()},
                "routed": {g: lanes[g]["config"] for g in WORKLOAD if g in lanes}}
    out = {}
    for name, cfg in profiles.items():
        per_epoch = []
        for e in epochs:
            rows = [(g, t, idx.get((t, cfg.get(g), e))) for g, ts in WORKLOAD.items() for t in ts]
            if any(r is None for _, _, r in rows):
                continue
            cost = sum(r.get("cost_usd", 0.0) for _, _, r in rows)
            cost_list = sum(r.get("cost_by_period", {}).get("list", r.get("cost_usd", 0.0)) for _, _, r in rows)
            verified = sum(r["passed"] for g, _, r in rows if g == "T3")
            review = next(r for g, _, r in rows if g == "T4")
            explain = next(r for g, _, r in rows if g == "T1")
            caught = LINT_CAUGHT | set(review["score"].get("matched", {}))
            if explain["score"].get("quality", 0.0) >= 0.8:
                caught |= {"D2"}
            per_epoch.append({"epoch": e, "cost_usd": cost, "cost_list_usd": cost_list, "verified_changes": verified,
                              "cost_per_verified_change": cost / verified if verified else None,
                              "cost_per_verified_change_list": cost_list / verified if verified else None,
                              "defects_caught": len(caught), "caught": sorted(caught),
                              "wall_s": sum(r.get("wall_s") or 0 for _, _, r in rows)})
        out[name] = {"configs": cfg, "epochs": len(per_epoch), "per_epoch": per_epoch,
                     "summary": _ranges(per_epoch)}
    return out


def _ranges(per_epoch: list[dict]) -> dict:
    def rng(key):
        vals = [p[key] for p in per_epoch if p[key] is not None]
        if not vals:
            return None
        return {"median": round(statistics.median(vals), 4), "min": round(min(vals), 4), "max": round(max(vals), 4)}
    return {k: rng(k) for k in ("cost_usd", "cost_list_usd", "cost_per_verified_change",
                                 "cost_per_verified_change_list", "verified_changes", "defects_caught", "wall_s")}


def build_summary(records: list[dict]) -> dict:
    table = class_table(records)
    lanes = choose_lanes(table)
    return {"records": len(records), "usable": sum(usable(r) for r in records),
            "errors": sum(bool(r.get("error")) for r in records), "classes": table, "lanes": lanes,
            "profiles": profile_workloads(records, lanes) if all(g in lanes for g in WORKLOAD) else {}}
