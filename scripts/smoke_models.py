#!/usr/bin/env python3
"""One tiny schema-bound call per model through the router, in record mode. Costs well under a cent.

    LADDER_GCP_PROJECT=<project> python scripts/smoke_models.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ladder_harness.router.router import Router  # noqa: E402
from ladder_harness.router.types import BackendUnavailable  # noqa: E402

SCHEMA = {"type": "object", "properties": {"timer_base_ms": {"type": "integer"}, "why": {"type": "string"}},
          "required": ["timer_base_ms", "why"], "additionalProperties": False}
PROMPT = ("On a MELSEC iQ-F FX5 PLC, what time base in milliseconds does `OUT T200 K50` use? "
          "Answer in one short sentence in `why`.")
LANES = [("gemini-3.8-flash", "low"), ("gemini-3.1-pro-preview", "low"), ("claude-opus-5-5", "low")]


def main() -> int:
    router = Router.from_config(ROOT / "config", ROOT / "logs" / "ledger.jsonl", mode="record",
                                cassette_dir=ROOT / "evals" / "cassettes", run_id="smoke")
    failures = 0
    for model, effort in LANES:
        try:
            r = router.call("T2", "You are a precise PLC assistant. Reply with JSON only.", PROMPT, SCHEMA,
                            model=model, effort=effort, meta={"task": "smoke"})
            ok = r.data.get("timer_base_ms") == 100
            print(f"{'OK ' if ok else 'BAD'} {model:<24} {effort:<6} {r.usage.input:>6} in {r.usage.output + r.usage.thinking:>6} out"
                  f"  ${r.cost_usd:.5f}  {r.latency_s:5.1f}s  → {r.data}")
            failures += 0 if ok else 1
        except BackendUnavailable as e:
            print(f"UNAVAILABLE {model}: {e}")
            return 2
        except Exception as e:  # noqa: BLE001 — report every model, then fail
            print(f"ERROR {model}: {type(e).__name__}: {str(e)[:400]}")
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
