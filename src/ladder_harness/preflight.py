"""Preflight: run 10 minutes before going on stage. Decides live or replay, and says exactly why."""
from __future__ import annotations

import datetime as dt
import os
import subprocess
from dataclasses import dataclass

import yaml

from .router.types import ModelCall
from .workspace import Workspace

TINY_SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"],
               "additionalProperties": False}


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def run_preflight(ws: Workspace, call_models: bool = True) -> tuple[list[Check], str]:
    checks: list[Check] = []
    project = os.environ.get("LADDER_GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    checks.append(Check("project", bool(project), project or "set LADDER_GCP_PROJECT"))
    try:
        subprocess.run(["gcloud", "auth", "application-default", "print-access-token"], check=True,
                       capture_output=True, timeout=30)
        checks.append(Check("login (ADC)", True, "application-default credentials valid"))
        adc = True
    except Exception:  # noqa: BLE001
        checks.append(Check("login (ADC)", False, "run: gcloud auth application-default login"))
        adc = False

    pricing = yaml.safe_load((ws.root / "config" / "pricing.yaml").read_text())
    age = (dt.date.today() - dt.date.fromisoformat(str(pricing["read_on"]))).days
    checks.append(Check("prices fresh", age <= 14, f"read {age} days ago ({pricing['read_on']})"))

    routing = yaml.safe_load((ws.root / "config" / "routing.yaml").read_text())
    lanes = {(tc["model"], tc["effort"]) for tc in routing["task_classes"].values() if tc.get("model") not in (None, "none")}
    router = ws.router(mode="live")
    live_ok = adc and bool(project)
    for model, effort in sorted(lanes):
        if not (call_models and live_ok):
            checks.append(Check(f"model {model}/{effort}", False, "not checked (no login/project)"))
            live_ok = False
            continue
        try:
            router._live_backend(model).call(ModelCall("PREFLIGHT", model, "low", "Reply with JSON.",
                                                       'Return {"ok": true}.', TINY_SCHEMA, 2000))
            checks.append(Check(f"model {model}/{effort}", True, "reachable"))
        except Exception as e:  # noqa: BLE001
            checks.append(Check(f"model {model}/{effort}", False, f"{type(e).__name__}: {str(e)[:120]}"))
            live_ok = False

    pinned = ws.root / "evals" / "cassettes" / "demo_pins.yaml"
    n_pins = len(yaml.safe_load(pinned.read_text()).get("pins", [])) if pinned.exists() else 0
    checks.append(Check("demo cassettes", n_pins > 0, f"{n_pins} recorded demo runs pinned for replay"))
    mode = "live" if live_ok else ("replay" if n_pins else "offline-only")
    return checks, mode


def format_preflight(checks: list[Check], mode: str) -> str:
    lines = [f"{'OK ' if c.ok else 'NO '} {c.name:<34} {c.detail}" for c in checks]
    lines.append(f"\nRecommended mode: {mode.upper()}"
                 + ("  →  export LADDER_MODE=replay  (every replayed answer is labelled REPLAY)" if mode == "replay" else
                    "  →  export LADDER_MODE=auto  (pinned demo runs replay; anything new goes live)" if mode == "live" else
                    "  →  deterministic tools only (lint, simulate, diff, apply)"))
    return "\n".join(lines)
