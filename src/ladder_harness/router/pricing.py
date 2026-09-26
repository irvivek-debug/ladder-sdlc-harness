"""Token prices from config/pricing.yaml (every row carries its source URL and read date)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import yaml

from .types import Usage


class Pricing:
    def __init__(self, doc: dict):
        self.doc = doc
        self.models: dict = doc["models"]
        self.read_on = doc.get("read_on")

    @classmethod
    def load(cls, path: str | Path) -> "Pricing":
        return cls(yaml.safe_load(Path(path).read_text(encoding="utf-8")))

    def _period(self, model: str, on: dt.date) -> dict:
        periods = self.models[model]["periods"]
        for p in periods:
            start = dt.date.fromisoformat(str(p["from"])) if "from" in p else dt.date.min
            end = dt.date.fromisoformat(str(p["until"])) if "until" in p else dt.date.max
            if start <= on <= end:
                return p
        raise KeyError(f"no price period for {model} on {on}")

    @staticmethod
    def _cost(p: dict, u: Usage) -> float:
        fresh = max(0, u.input - u.cached - u.cache_write)
        return (fresh * p["input"] + u.cached * p.get("cached_input", p["input"])
                + u.cache_write * p.get("cache_write", p["input"])
                + (u.output + u.thinking) * p["output"]) / 1_000_000

    def price(self, model: str, usage: Usage, on: dt.date | None = None) -> float:
        return self._cost(self._period(model, on or dt.date.today()), usage)

    def price_both(self, model: str, usage: Usage) -> dict[str, float]:
        return {p.get("label", str(i)): self._cost(p, usage) for i, p in enumerate(self.models[model]["periods"])}
