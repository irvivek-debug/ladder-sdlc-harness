#!/usr/bin/env python3
"""Local server for the alpha front end: serves demo/app and exposes the harness tool set over HTTP.

    python demo/app/server.py            # http://127.0.0.1:8765

It adds no behaviour to the harness. Every /api/tool call goes to the same `Tools` class the CLI and the MCP server
use, so what the page shows is what `ladder` would print. The only code here that the CLI does not have is the pack
trace, which drives the same FX5 simulator and ST20 plant twin as `scripts/build_demo_pages.py` and samples them so
the page can draw the pressure curve. Model tasks follow LADDER_MODE (default: replay, the pinned recorded runs).
Binds to 127.0.0.1 only. Nothing here talks to a PLC.
"""
from __future__ import annotations

import json
import mimetypes
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP = Path(__file__).resolve().parent
ROOT = APP.parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("LADDER_MODE", "replay")

from ladder_harness.melsec.program import parse_il  # noqa: E402
from ladder_harness.plant import PLANTS  # noqa: E402
from ladder_harness.sim.engine import Plc  # noqa: E402
from ladder_harness.tools import Tools  # noqa: E402
from ladder_harness.workspace import Workspace  # noqa: E402

TOOL_NAMES = {"ladder_parse", "ladder_lint", "ladder_simulate", "ladder_render", "ladder_diff", "ladder_task",
              "ladder_apply", "ladder_export_gxw3", "cost_ledger"}

# Leak rates (kPa/s at 15 kPa) for the packs the Line screen sends through ST20: good packs around 0.005,
# one leaking pack at 0.08, the same leaking pack `scripts/build_demo_pages.py` uses for the story.
GOOD_LEAK, BAD_LEAK = 0.005, 0.08
LINE_PACKS = [0.004, 0.006, 0.005, BAD_LEAK, 0.005, 0.007, 0.004, 0.006]
STEPS = {"M201": "CLAMP", "M202": "FILL", "M203": "STABILISE", "M204": "TEST", "M205": "VENT", "M206": "UNCLAMP"}


def workspace() -> Workspace:
    return Workspace.discover(ROOT)


def st20_program(which: str):
    """running = the legacy program on the controller; candidate = the AI's last proven-able fix;
    signed = the proposal the gate wrote for the engineer."""
    ws = workspace()
    paths = {"running": ws.data_dir / "st20" / "legacy.il", "candidate": ws.out_dir / "st20_candidate.il",
             "signed": ws.data_dir / "st20" / "proposed.il"}
    if which not in paths:
        raise ValueError("program must be running, candidate or signed")
    if not paths[which].exists():
        return None
    return parse_il(paths[which].read_text(encoding="utf-8"), "ST20")


def pack_trace(which: str = "running", leak: float = BAD_LEAK, sample_ms: int = 100, trace: bool = True) -> dict:
    program = st20_program(which)
    if program is None:
        return {"program": which, "available": False}
    plant, plc = PLANTS["st20"](leak_kpa_per_s=float(leak)), Plc(program)
    points, events, step, done_at, alarm = [], [], None, None, False
    last = {"D110": plc.word("D110"), "D111": plc.word("D111")}
    while plc.now_ms < 40000 and done_at is None:
        plc.set_bit("X0", True), plc.set_bit("X2", True), plc.set_bit("X23", plc.now_ms >= 100)
        plant.step(plc, plc.scan_ms, plc.now_ms)
        plc.scan()
        t = plc.now_ms - 100
        alarm = alarm or plc.bit("Y25")
        now_step = next((name for dev, name in STEPS.items() if plc.bit(dev)), None)
        if now_step != step and now_step:
            events.append({"t_s": round(t / 1000, 2), "kind": "step", "label": now_step})
            step = now_step
        for reg, label in (("D110", "baseline sampled"), ("D111", "final sampled")):
            v = plc.word(reg)
            if v != last[reg]:
                events.append({"t_s": round(t / 1000, 2), "kind": reg, "label": label, "kpa": v / 100})
                last[reg] = v
        if trace and t % sample_ms == 0:
            points.append([round(t / 1000, 2), round(plant.P, 3)])
        if plc.bit("M207"):
            done_at = t - plc.scan_ms
    return {"program": which, "available": True, "leak_kpa_per_s": leak, "leaking": leak >= BAD_LEAK / 2,
            "decay_kpa": plc.word("D112") / 100, "limit_kpa": plc.word("D120") / 100,
            "result": "PASS" if plc.bit("M210") else "FAIL" if plc.bit("M211") else "NONE",
            "cycle_s": round(done_at / 1000, 1) if done_at else None, "budget_s": 23.0, "alarm": alarm,
            "points": points, "events": events}


def line_run(which: str = "running") -> dict:
    packs = [pack_trace(which, leak, trace=False) for leak in LINE_PACKS]
    if not packs[0]["available"]:
        return {"program": which, "available": False}
    for p in packs:
        p.pop("points", None)
        p.pop("events", None)
    return {"program": which, "available": True, "packs": packs}


def reset() -> dict:
    ws = workspace()
    removed = []
    for p in ws.data_dir.glob("st*/proposed.il"):
        p.unlink()
        removed.append(str(p.relative_to(ws.root)))
    for p in ws.out_dir.glob("*"):
        if p.is_file():
            p.unlink()
    return {"reset": True, "removed": removed}


def status() -> dict:
    ws = workspace()
    return {"live": True, "mode": os.environ.get("LADDER_MODE", "auto"), "cell": ws.cell_name,
            "stations": ["ST10", "ST20", "ST30"], "signed": (ws.data_dir / "st20" / "proposed.il").exists(),
            "candidate": (ws.out_dir / "st20_candidate.il").exists()}


def call(path: str, body: dict):
    if path == "/api/status":
        return status()
    if path == "/api/reset":
        return reset()
    if path == "/api/pack":
        return pack_trace(body.get("program", "running"), float(body.get("leak", BAD_LEAK)))
    if path == "/api/line":
        return line_run(body.get("program", "running"))
    if path.startswith("/api/tool/"):
        name = path.rsplit("/", 1)[1]
        if name not in TOOL_NAMES:
            raise ValueError(f"unknown tool {name}")
        return getattr(Tools(workspace()), name)(**body)
    raise FileNotFoundError(path)


class Handler(BaseHTTPRequestHandler):
    server_version = "LadderAlpha/1"

    def _send(self, code: int, payload: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, code: int, obj):
        self._send(code, json.dumps(obj, default=str).encode(), "application/json")

    def _api(self, body: dict):
        try:
            self._json(200, call(self.path.split("?")[0], body))
        except FileNotFoundError as e:
            self._json(404, {"error": str(e)})
        except Exception as e:  # the page shows the harness's own error text
            traceback.print_exc()
            self._json(400, {"error": str(e)})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._json(400, {"error": "body must be JSON"})
        self._api(body if isinstance(body, dict) else {})

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("/api/"):
            return self._api({})
        if path.startswith("/out/"):
            base, rel = workspace().out_dir, path[len("/out/"):]
        else:
            base, rel = APP, (path.lstrip("/") or "index.html")
        f = (base / rel).resolve()
        if base.resolve() not in f.parents or not f.is_file() or f.suffix == ".py":
            return self._json(404, {"error": "not found"})
        self._send(200, f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream")

    def log_message(self, fmt, *args):
        if "/api/" in str(args[0] if args else ""):
            sys.stderr.write("  " + (fmt % args) + "\n")


def main() -> int:
    port = int(os.environ.get("LADDER_APP_PORT", "8765"))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Ladder alpha on http://127.0.0.1:{port}  (LADDER_MODE={os.environ['LADDER_MODE']})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
