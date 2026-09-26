"""Record-and-replay cassettes: the demo keeps working without credentials or Wi-Fi, visibly labelled REPLAY."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .types import ModelCall, ModelResult, ReplayMiss, Usage


def call_key(c: ModelCall) -> str:
    canonical = json.dumps({"task_class": c.task_class, "model": c.model, "effort": c.effort,
                            "system": c.system, "prompt": c.prompt, "schema": c.schema},
                           sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


class ReplayBackend:
    def __init__(self, cassette_dir: str | Path):
        self.dir = Path(cassette_dir)

    def has(self, c: ModelCall) -> bool:
        return (self.dir / f"{call_key(c)}.json").exists()

    def call(self, c: ModelCall) -> ModelResult:
        path = self.dir / f"{call_key(c)}.json"
        if not path.exists():
            raise ReplayMiss(f"no recorded answer for {c.task_class} on {c.model}/{c.effort} (key {call_key(c)})")
        rec = json.loads(path.read_text(encoding="utf-8"))
        return ModelResult(rec["data"], rec["text"], Usage(**rec["usage"]), rec["latency_s"], c.model, c.effort,
                           "replay", call_key(c))


class Recorder:
    """Wrap a live backend and save every answer as a cassette (no auth material is ever written)."""

    def __init__(self, inner, cassette_dir: str | Path):
        self.inner, self.dir = inner, Path(cassette_dir)

    def call(self, c: ModelCall) -> ModelResult:
        result = self.inner.call(c)
        self.dir.mkdir(parents=True, exist_ok=True)
        key = call_key(c)
        record = {"key": key, "task_class": c.task_class, "model": c.model, "effort": c.effort,
                  "data": result.data, "text": result.text, "usage": result.usage.to_dict(),
                  "latency_s": round(result.latency_s, 3), "recorded_backend": result.backend}
        (self.dir / f"{key}.json").write_text(json.dumps(record, indent=1, sort_keys=True, ensure_ascii=False),
                                              encoding="utf-8")
        result.key = key
        return result
