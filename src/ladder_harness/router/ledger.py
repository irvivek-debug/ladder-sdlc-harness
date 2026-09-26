"""Append-only JSONL cost ledger: one line per model call."""
from __future__ import annotations

import json
import threading
from collections import defaultdict
from pathlib import Path

_LOCK = threading.Lock()


class Ledger:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(self, entry: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, sort_keys=True) + "\n"
        with _LOCK, self.path.open("a", encoding="utf-8") as f:
            f.write(line)

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]


def summary(rows: list[dict], group_by: tuple[str, ...] = ("profile", "task_class")) -> list[dict]:
    groups: dict[tuple, dict] = defaultdict(lambda: {"calls": 0, "ok": 0, "cost_usd": 0.0, "input": 0,
                                                     "output": 0, "latency_s": 0.0})
    for r in rows:
        g = groups[tuple(r.get(k) for k in group_by)]
        g["calls"] += 1
        g["ok"] += 1 if r.get("ok") else 0
        g["cost_usd"] += float(r.get("cost_usd", 0.0))
        usage = r.get("usage", {})
        g["input"] += int(usage.get("input", 0))
        g["output"] += int(usage.get("output", 0)) + int(usage.get("thinking", 0))
        g["latency_s"] += float(r.get("latency_s", 0.0))
    return [{**dict(zip(group_by, k)), **v} for k, v in sorted(groups.items(), key=lambda kv: tuple(map(str, kv[0])))]
