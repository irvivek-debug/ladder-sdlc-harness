"""The harness workspace: one plant cell, config, ledger, cassettes and an output folder.

Surfaces (MCP server, CLI, skills) never load the sealed answer key — only evals and tests do.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .cell import Cell, load_cell
from .router.router import Router


class WorkspaceError(ValueError):
    pass


@dataclass
class Workspace:
    root: Path
    cell_name: str = "ev_pack_eol"

    @classmethod
    def discover(cls, start: str | Path | None = None) -> "Workspace":
        env = os.environ.get("LADDER_ROOT")
        here = Path(env or start or Path.cwd()).resolve()
        for d in (here, *here.parents):
            if (d / "config" / "routing.yaml").exists() and (d / "plant_data").is_dir():
                return cls(d, os.environ.get("LADDER_CELL", "ev_pack_eol"))
        pkg_root = Path(__file__).resolve().parents[2]
        if (pkg_root / "config" / "routing.yaml").exists():
            return cls(pkg_root, os.environ.get("LADDER_CELL", "ev_pack_eol"))
        raise WorkspaceError("no harness workspace found (looked for config/routing.yaml and plant_data/)")

    @property
    def data_dir(self) -> Path:
        return self.root / "plant_data" / self.cell_name

    @property
    def out_dir(self) -> Path:
        d = self.root / "demo" / "out"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def ledger_path(self) -> Path:
        return self.root / "logs" / "ledger.jsonl"

    def cell(self) -> Cell:
        return load_cell(self.data_dir)          # no answer key, by design

    def router(self, mode: str | None = None) -> Router:
        return Router.from_config(self.root / "config", self.ledger_path,
                                  mode=mode or os.environ.get("LADDER_MODE", "auto"),
                                  cassette_dir=self.root / "evals" / "cassettes")

    def inside(self, path: str | Path) -> Path:
        """Resolve a user-supplied path and refuse anything outside the workspace or inside the answer key."""
        p = Path(path)
        p = (p if p.is_absolute() else self.root / p).resolve()
        if self.root.resolve() not in (p, *p.parents):
            raise WorkspaceError(f"{path} is outside the workspace")
        if (self.root / "evals" / "answer_key").resolve() in (p, *p.parents):
            raise WorkspaceError("the answer key is sealed; tools do not read it")
        return p
