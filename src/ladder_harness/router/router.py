"""Horses for courses: pick the lane for a task class, call it, price it, log it."""
from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

import yaml

from .ledger import Ledger
from .pricing import Pricing
from .replay import Recorder, ReplayBackend, call_key
from .types import BackendUnavailable, ModelCall, ModelResult, ReplayMiss

MODES = ("live", "record", "replay", "auto")


class Router:
    def __init__(self, routing: dict, pricing: Pricing, ledger: Ledger, mode: str = "auto",
                 backends: dict | None = None, cassette_dir: str | Path = "evals/cassettes",
                 run_id: str | None = None):
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        self.routing, self.pricing, self.ledger, self.mode = routing, pricing, ledger, mode
        self._backends = backends
        self.replay = ReplayBackend(cassette_dir)
        self.cassette_dir = Path(cassette_dir)
        self.run_id = run_id or dt.datetime.now().strftime("%Y%m%dT%H%M%S")

    @classmethod
    def from_config(cls, config_dir: str | Path, ledger_path: str | Path, **kw) -> "Router":
        config_dir = Path(config_dir)
        routing = yaml.safe_load((config_dir / "routing.yaml").read_text(encoding="utf-8"))
        return cls(routing, Pricing.load(config_dir / "pricing.yaml"), Ledger(ledger_path), **kw)

    def lane(self, task_class: str, profile: str = "routed") -> tuple[str, str]:
        prof = self.routing["profiles"][profile]
        if prof == "lanes":
            tc = self.routing["task_classes"][task_class]
            if tc.get("model") in (None, "none"):
                raise ValueError(f"{task_class} is deterministic — it never calls a model")
            return tc["model"], tc["effort"]
        return prof["model"], prof["effort"]

    def _live_backend(self, model: str):
        if self._backends is None:
            from .backends import default_backends
            self._backends = default_backends()
        provider = self.pricing.models[model]["provider"]
        return self._backends[provider]

    def call(self, task_class: str, system: str, prompt: str, schema: dict, profile: str = "routed",
             meta: dict | None = None, model: str | None = None, effort: str | None = None) -> ModelResult:
        if model is None or effort is None:
            model, effort = self.lane(task_class, profile)
        c = ModelCall(task_class, model, effort, system, prompt, schema)
        t0 = time.monotonic()
        ok, error = True, None
        try:
            if self.mode == "replay" or (self.mode == "auto" and self.replay.has(c)):
                result = self.replay.call(c)
            elif self.mode in ("live", "auto"):
                result = self._live_backend(model).call(c)
            else:
                result = Recorder(self._live_backend(model), self.cassette_dir).call(c)
        except (BackendUnavailable, ReplayMiss):
            raise
        except Exception as e:  # noqa: BLE001 — logged, then re-raised
            ok, error = False, f"{type(e).__name__}: {e}"
            self.ledger.append({"run_id": self.run_id, "ts": dt.datetime.now().isoformat(timespec="seconds"),
                                "task_class": task_class, "profile": profile, "model": model, "effort": effort,
                                "ok": False, "error": error[:300], "latency_s": round(time.monotonic() - t0, 3),
                                **(meta or {})})
            raise
        result.key = result.key or call_key(c)
        result.cost_usd = self.pricing.price(model, result.usage)
        result.cost_by_period = self.pricing.price_both(model, result.usage)
        self.ledger.append({"run_id": self.run_id, "ts": dt.datetime.now().isoformat(timespec="seconds"),
                            "task_class": task_class, "profile": profile, "model": model, "effort": effort,
                            "backend": result.backend, "key": result.key, "usage": result.usage.to_dict(),
                            "cost_usd": round(result.cost_usd, 6),
                            "cost_by_period": {k: round(v, 6) for k, v in result.cost_by_period.items()},
                            "latency_s": round(result.latency_s, 3), "ok": ok, **(meta or {})})
        return result
