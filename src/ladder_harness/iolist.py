"""The plant I/O list: tags, devices, descriptions and SAFETY classification."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .melsec.devices import Device, dev


@dataclass(frozen=True)
class IoPoint:
    tag: str
    device: Device
    description: str
    signal: str
    range: str
    units: str
    station: str
    safety: bool
    notes: str


class IoList:
    def __init__(self, points: list[IoPoint]):
        self.points = points
        self.by_device = {p.device: p for p in points}

    def safety_devices(self) -> set[Device]:
        return {p.device for p in self.points if p.safety}

    def io_devices(self) -> set[Device]:
        return set(self.by_device)

    def station_points(self, station: str) -> list[IoPoint]:
        return [p for p in self.points if p.station in (station, "CELL")]

    @classmethod
    def load_csv(cls, path: str | Path) -> "IoList":
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        return cls([IoPoint(
            tag=r["tag"].strip(), device=dev(r["device"]), description=r["description"].strip(),
            signal=r["signal"].strip(), range=r.get("range", "").strip(), units=r.get("units", "").strip(),
            station=r["station"].strip(), safety=r.get("safety", "").strip().upper() == "SAFETY",
            notes=r.get("notes", "").strip(),
        ) for r in rows])
