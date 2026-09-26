"""The harness tool set, shared by the MCP server and the CLI. Every tool returns JSON-serialisable data.

There is deliberately no tool that talks to a PLC: proposals end as files an engineer reviews and imports.
"""
from __future__ import annotations

from pathlib import Path

from .ai import tasks
from .guard import gate
from .lint import lint
from .melsec.gxw3_csv import comments_to_csv_bytes, program_to_csv_bytes
from .melsec.program import Program, format_il, parse_il
from .render import diff_html, diff_programs, program_html, unified_il_diff
from .router.ledger import summary
from .scenarios.runner import load_station_suites, run_suites
from .workspace import Workspace

STATIONS = ("ST10", "ST20", "ST30")


def _station(s: str) -> str:
    s = s.strip().upper()
    if s not in STATIONS:
        raise ValueError(f"unknown station {s!r}; choose one of {', '.join(STATIONS)}")
    return s


class Tools:
    def __init__(self, ws: Workspace):
        self.ws = ws

    # -- helpers ------------------------------------------------------------
    def _program(self, station: str, candidate_path: str | None = None) -> Program:
        if candidate_path:
            return parse_il(self.ws.inside(candidate_path).read_text(encoding="utf-8"), station)
        return self.ws.cell().program(station)

    def _rel(self, p: Path) -> str:
        try:
            return str(p.relative_to(self.ws.root))
        except ValueError:
            return str(p)

    # -- T0: deterministic ---------------------------------------------------
    def ladder_parse(self, station: str, candidate_path: str | None = None) -> dict:
        """Parse a station program (or a candidate file) and summarise it: rungs, instructions, devices."""
        st = _station(station)
        p = self._program(st, candidate_path)
        devices = sorted({str(d) for i in p.instructions() for d in i.devices()})
        return {"station": st, "rungs": len(p.rungs), "instructions": sum(len(r.instructions) for r in p.rungs),
                "devices": devices, "header": p.header, "model_cost_usd": 0.0}

    def ladder_lint(self, station: str, candidate_path: str | None = None) -> dict:
        """Deterministic lint (double coils, FX3→FX5 timer trap, spare I/O, SAFETY rungs, comment coverage). $0."""
        st = _station(station)
        cell = self.ws.cell()
        p = self._program(st, candidate_path)
        comments = cell.legacy_comments(st)
        found = lint(p, cell.iolist, comments)
        return {"station": st, "findings": [{"rule": f.rule, "severity": f.severity, "rung": f.rung,
                                             "devices": list(f.devices), "message": f.message} for f in found],
                "model_cost_usd": 0.0}

    def ladder_simulate(self, station: str, scenario_ids: list[str] | None = None,
                        candidate_path: str | None = None) -> dict:
        """Run the station's factory-acceptance and C&E scenarios on the FX5 simulator + plant twin. $0."""
        st = _station(station)
        p = self._program(st, candidate_path)
        results = run_suites(p, load_station_suites(self.ws.data_dir, st), stop_on_fail=False,
                             ids=set(scenario_ids) if scenario_ids else None)
        return {"station": st, "passed": sum(r.passed for r in results), "failed": sum(not r.passed for r in results),
                "results": [{"id": r.id, "title": r.title, "passed": r.passed,
                             "failures": [f.message for f in r.failures]} for r in results],
                "model_cost_usd": 0.0}

    def ladder_render(self, station: str, candidate_path: str | None = None) -> dict:
        """Draw the program as ladder (SVG in an HTML page) and return the file path."""
        st = _station(station)
        p = self._program(st, candidate_path)
        out = self.ws.out_dir / f"{st.lower()}_{'candidate' if candidate_path else 'program'}.html"
        out.write_text(program_html(p, self.ws.cell().legacy_comments(st), title=f"{st} ladder"), encoding="utf-8")
        return {"station": st, "html_path": self._rel(out), "model_cost_usd": 0.0}

    def ladder_diff(self, station: str, candidate_path: str) -> dict:
        """Compare a candidate with the current program: rung-level changes, IL diff, and a side-by-side page."""
        st = _station(station)
        old, new = self._program(st), self._program(st, candidate_path)
        out = self.ws.out_dir / f"{st.lower()}_diff.html"
        out.write_text(diff_html(old, new, self.ws.cell().legacy_comments(st), title=f"{st}: current vs candidate",
                                 old_label="Current", new_label="Candidate"), encoding="utf-8")
        changes = [c.__dict__ for c in diff_programs(old, new) if c.kind != "equal"]
        return {"station": st, "changes": changes, "unified_diff": unified_il_diff(old, new),
                "html_path": self._rel(out), "model_cost_usd": 0.0}

    # -- T1–T4: routed to a model ------------------------------------------
    def ladder_task(self, task: str, station: str, goal: str = "", targets: list[str] | None = None,
                    profile: str = "routed") -> dict:
        """Run a model task — explain (T1), extract (T2), review (T4) or repair (T3) — on the lane the routing
        table picks. Repair writes a candidate file; it never changes the station program."""
        st = _station(station)
        cell, router = self.ws.cell(), self.ws.router()
        if task == "explain":
            run = tasks.explain(router, cell, st, profile)
        elif task == "extract":
            run = tasks.extract(router, cell, st, profile)
        elif task == "review":
            run = tasks.review(router, cell, st, profile)
        elif task == "repair":
            if not goal:
                raise ValueError("repair needs a goal")
            run = tasks.repair(router, cell, st, goal, set(targets or []), profile)
        else:
            raise ValueError("task must be explain, extract, review or repair")
        out = {"task": task, "station": st, "profile": profile, "ok": run.ok, "result": run.result,
               "notes": run.notes, "attempts": run.attempts,
               "calls": [{"model": c.model, "effort": c.effort, "backend": c.backend, "cost_usd": round(c.cost_usd, 5),
                          "latency_s": round(c.latency_s, 2), "tokens_in": c.usage.input,
                          "tokens_out": c.usage.output + c.usage.thinking} for c in run.calls],
               "model_cost_usd": round(run.cost_usd, 5),
               "replay": run.backends == {"replay"}}
        if task == "repair" and run.ok:
            cand = self.ws.out_dir / f"{st.lower()}_candidate.il"
            cand.write_text(run.result["program_il"].rstrip() + "\n", encoding="utf-8")
            out["candidate_path"] = self._rel(cand)
        return out

    # -- apply gate and hand-off ---------------------------------------------
    def ladder_apply(self, station: str, candidate_path: str, targets: list[str] | None = None) -> dict:
        """Gate a candidate: parse → SAFETY guard → no new lint errors → all scenarios (targets must pass, nothing
        may regress). Only a passing candidate is written, as <station>/proposed.il, for the engineer to sign."""
        st = _station(station)
        cell = self.ws.cell()
        old = cell.program(st)
        suites = load_station_suites(self.ws.data_dir, st)
        known = {r.id for r in run_suites(old, suites) if not r.passed}
        text = self.ws.inside(candidate_path).read_text(encoding="utf-8")
        g = gate(text, old, cell.iolist.safety_devices(), suites, cell.iolist, known_failures=known,
                 targets=set(targets or []))
        out = {"station": st, "allowed": g.allowed, "stage": g.stage, "reasons": g.reasons,
               "scenarios_run": len(g.results), "model_cost_usd": 0.0}
        if g.allowed:
            dest = self.ws.data_dir / st.lower() / "proposed.il"
            dest.write_text(format_il(g.program), encoding="utf-8")
            out["proposed_path"] = self._rel(dest)
            out["next_step"] = "Engineer review and sign-off, then import into GX Works3 (import unverified)."
        return out

    def ladder_export_gxw3(self, station: str, which: str = "proposed") -> dict:
        """Write a GX Works3 listed-instruction CSV (UTF-16LE, tab) + device-comment CSV for a program."""
        st = _station(station)
        src = self.ws.data_dir / st.lower() / f"{which}.il" if which != "current" else None
        p = parse_il(src.read_text(encoding="utf-8"), st) if src else self.ws.cell().program(st)
        prog_out = self.ws.out_dir / f"{st}_{which}_gxw3.csv"
        prog_out.write_bytes(program_to_csv_bytes(p, project=f"{st}_{which}", module_type="FX5U"))
        com_out = self.ws.out_dir / f"{st}_{which}_comments_gxw3.csv"
        com_out.write_bytes(comments_to_csv_bytes(self.ws.cell().legacy_comments(st)))
        return {"station": st, "program_csv": self._rel(prog_out), "comments_csv": self._rel(com_out),
                "note": "Generated in GX Works3 CSV format; import into GX Works3 is unverified.", "model_cost_usd": 0.0}

    def cost_ledger(self, group_by: str = "profile,task_class", run_id: str | None = None) -> dict:
        """Summarise model spend from the ledger: calls, tokens, dollars and latency by the chosen grouping."""
        rows = self.ws.router().ledger.read()
        if run_id:
            rows = [r for r in rows if r.get("run_id") == run_id]
        keys = tuple(k.strip() for k in group_by.split(",") if k.strip())
        groups = summary(rows, keys)
        return {"groups": groups, "total_cost_usd": round(sum(g["cost_usd"] for g in groups), 5),
                "calls": sum(g["calls"] for g in groups),
                "replayed_calls": sum(1 for r in rows if r.get("backend") == "replay")}

    def all(self) -> list:
        return [self.ladder_parse, self.ladder_lint, self.ladder_simulate, self.ladder_render, self.ladder_diff,
                self.ladder_task, self.ladder_apply, self.ladder_export_gxw3, self.cost_ledger]
