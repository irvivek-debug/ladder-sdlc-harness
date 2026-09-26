"""ST30 HV insulation (HiPot) tester as a black box: result 3.0 s after HV enable is held on."""
from __future__ import annotations

from ..sim.engine import Plc
from .base import Plant


class St30Plant(Plant):
    @classmethod
    def defaults(cls) -> dict:
        return {"insulation_ok": True, "test_time_ms": 3000}

    def __init__(self, **params):
        super().__init__(**params)
        self.on_ms = 0

    def step(self, plc: Plc, dt_ms: int, t_ms: int) -> None:
        hv = plc.bit("Y30")
        self.on_ms = self.on_ms + dt_ms if hv else 0
        done = hv and self.on_ms >= self.params["test_time_ms"]
        plc.set_bit("X30", done and self.params["insulation_ok"])
        plc.set_bit("X31", done and not self.params["insulation_ok"])

    def signals(self) -> dict[str, float | bool]:
        return {"hv_on_ms": self.on_ms}
