"""Load a plant-cell data set (plant_data/<cell>/) and, for evals and tests only, its sealed answer key."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .iolist import IoList
from .melsec.program import Program, parse_il

STATIONS = ("ST10", "ST20", "ST30")


def read_comments_csv(path: str | Path) -> dict[str, str]:
    with open(path, newline="", encoding="utf-8") as f:
        return {r["Device Name"].strip(): r["Comment"].strip() for r in csv.DictReader(f) if r["Device Name"].strip()}


def write_comments_csv(path: str | Path, comments: dict[str, str]) -> None:
    from .melsec.devices import dev
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Device Name", "Comment"])
        for d in sorted(comments, key=dev):
            w.writerow([d, comments[d]])


@dataclass
class Cell:
    data_dir: Path
    key_dir: Path | None
    iolist: IoList
    defects: dict = field(default_factory=dict)
    realism: dict = field(default_factory=dict)

    def _station_dir(self, station: str) -> Path:
        return self.data_dir / station.lower()

    def legacy_path(self, station: str) -> Path:
        return self._station_dir(station) / "legacy.il"

    def program(self, station: str) -> Program:
        """What an engineer (or a model packet) sees: the legacy program, or the station program."""
        path = self.legacy_path(station)
        if not path.exists():
            path = self._station_dir(station) / "program.il"
        return parse_il(path.read_text(encoding="utf-8"), station)

    def legacy(self, station: str) -> Program:
        return parse_il(self.legacy_path(station).read_text(encoding="utf-8"), station)

    def golden(self, station: str) -> Program:
        if self.key_dir is not None:
            path = self.key_dir / f"{station.lower()}_golden.il"
            if path.exists():
                return parse_il(path.read_text(encoding="utf-8"), station)
        return parse_il((self._station_dir(station) / "program.il").read_text(encoding="utf-8"), station)

    def legacy_comments(self, station: str) -> dict[str, str]:
        return read_comments_csv(self._station_dir(station) / "device_comments.csv")

    @property
    def golden_comments(self) -> dict[str, str]:
        if self.key_dir is None:
            raise FileNotFoundError("the answer key is not loaded")
        return read_comments_csv(self.key_dir / "golden_comments.csv")

    def narrative(self) -> str:
        return (self.data_dir / "narrative.md").read_text(encoding="utf-8")


def load_cell(data_dir: str | Path, key_dir: str | Path | None = None) -> Cell:
    data_dir = Path(data_dir)
    key = Path(key_dir) if key_dir is not None else None
    defects, realism = {}, {}
    if key is not None:
        defects = yaml.safe_load((key / "defects.yaml").read_text(encoding="utf-8"))
        realism = yaml.safe_load((key / "realism.yaml").read_text(encoding="utf-8"))
    return Cell(data_dir, key, IoList.load_csv(data_dir / "io_list.csv"), defects, realism)
