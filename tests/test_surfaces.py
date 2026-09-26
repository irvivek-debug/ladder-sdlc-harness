import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ladder_harness.tools import Tools
from ladder_harness.workspace import Workspace, WorkspaceError

ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "LADDER_ROOT": str(ROOT), "LADDER_MODE": "replay"}


@pytest.fixture()
def tools(tmp_path, monkeypatch):
    ws = Workspace(ROOT)
    monkeypatch.setattr(Workspace, "out_dir", property(lambda self: tmp_path))
    return Tools(ws)


def test_lint_and_parse_are_free_and_find_the_seeded_issues(tools):
    lint = tools.ladder_lint("st20")
    rules = {(f["rule"], tuple(f["devices"])) for f in lint["findings"]}
    assert ("L001", ("Y22",)) in rules and ("L002", ("T200",)) in rules and lint["model_cost_usd"] == 0.0
    assert tools.ladder_parse("ST20")["rungs"] > 20


def test_simulate_reports_the_legacy_failures(tools):
    sim = tools.ladder_simulate("ST20", ["FAT-ST20-02", "FAT-ST20-01"])
    by_id = {r["id"]: r["passed"] for r in sim["results"]}
    assert by_id == {"FAT-ST20-01": False, "FAT-ST20-02": False}


def test_workspace_refuses_answer_key_and_outside_paths(tools):
    with pytest.raises(WorkspaceError, match="sealed"):
        tools.ladder_parse("ST20", "evals/answer_key/st20_golden.il")
    with pytest.raises(WorkspaceError, match="outside"):
        tools.ladder_parse("ST20", "/etc/hosts")


def test_unknown_station_rejected(tools):
    with pytest.raises(ValueError, match="unknown station"):
        tools.ladder_lint("ST99")


def test_render_and_diff_write_html(tools, tmp_path):
    assert tools.ladder_render("ST30")["html_path"]
    cand = ROOT / "demo" / "out" / "_test_candidate.il"
    cand.parent.mkdir(parents=True, exist_ok=True)
    cand.write_text((ROOT / "plant_data/ev_pack_eol/st30/program.il").read_text())
    try:
        d = tools.ladder_diff("ST30", str(cand))
        assert d["changes"] == []
    finally:
        cand.unlink()


def test_cli_lint_runs():
    out = subprocess.run([sys.executable, "-m", "ladder_harness.cli", "lint", "ST20"], env=ENV,
                         capture_output=True, text=True, check=True).stdout
    assert "L001" in out and "$0.00" in out


def test_mcp_server_lists_tools_over_stdio():
    proc = subprocess.Popen([sys.executable, "-m", "ladder_harness.mcp_server"], env=ENV, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    def send(msg):
        proc.stdin.write(json.dumps(msg) + "\n"); proc.stdin.flush()
    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}})
        init = json.loads(proc.stdout.readline())
        assert init["result"]["serverInfo"]["name"] == "ladder-harness"
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        listed = json.loads(proc.stdout.readline())
        names = {t["name"] for t in listed["result"]["tools"]}
        assert {"ladder_lint", "ladder_simulate", "ladder_task", "ladder_apply", "cost_ledger"} <= names
        assert not any("plc" in n or "download" in n for n in names)
    finally:
        proc.kill()
