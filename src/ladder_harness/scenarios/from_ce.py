"""Generate scenario suites from the cause-and-effect matrix plus engineer-authored bindings.

The C&E matrix says *what* must happen; each binding (written and signed by the controls engineer) says
*how to provoke the cause* and *how to observe the effect*. Every C&E row needs a binding and every binding a
row, so the matrix and the tests cannot drift apart silently.
"""
from __future__ import annotations


def generate(ce_rows: list[dict], bindings: dict) -> dict[str, dict]:
    rows = {r["id"]: r for r in ce_rows}
    binds = bindings.get("bindings", {})
    missing = sorted(set(rows) - set(binds))
    orphan = sorted(set(binds) - set(rows))
    if missing:
        raise ValueError(f"C&E rows without a test binding: {', '.join(missing)}")
    if orphan:
        raise ValueError(f"test bindings without a C&E row: {', '.join(orphan)}")
    out: dict[str, dict] = {}
    for ce_id in sorted(rows):
        row, b = rows[ce_id], binds[ce_id]
        station = row["station"]
        cfg = bindings["stations"][station]
        suite = out.setdefault(station, {
            "station": station, "plant": cfg["plant"], "scan_ms": cfg.get("scan_ms", 10),
            "generated_from": "cause_effect.csv + scenarios/ce_bindings.yaml", "scenarios": [],
        })
        scenario = {
            "id": ce_id,
            "title": f"{row['cause']} → {row['effect']}",
            "trace": [ce_id, row.get("reference", "")],
            "duration_ms": b["duration_ms"],
            "stimuli": list(cfg.get("preamble", [])) + list(b.get("stimuli", [])),
            "expect": list(cfg.get("invariants", [])) + list(b["expect"]),
        }
        if b.get("plant"):
            scenario["plant"] = dict(b["plant"])
        suite["scenarios"].append(scenario)
    return out
