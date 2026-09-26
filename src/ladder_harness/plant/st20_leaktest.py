"""ST20 pressure-decay leak-test twin (representative values, not any OEM's specification).

Pack pressure P (kPa gauge) integrates, per scan:
  fill valve open (Y21 or stuck-open fault):  (supply - P) / tau_fill
  vent valve open (Y22):                       -P / tau_vent
  enclosure leak (always):                     -(leak_kpa_per_s / 15) * P      (rate quoted at 15 kPa)
  thermal settle while isolated:               -thermal * (P / 15) * exp(-t_isolated / tau_thermal)
Clamp travels in clamp_travel_s; X20 closed at >= 0.99, X21 open at <= 0.01. PT-2001 is scaled
0..10000 = 0..100.00 kPa into D100; a wire break reads -2500.
"""
from __future__ import annotations

import math

from ..sim.engine import Plc
from .base import Plant


class St20Plant(Plant):
    FAULTS = frozenset({"clamp_slip", "pt_wire_break", "regulator_fail", "fill_valve_stuck_open", "supply_air_low"})

    @classmethod
    def defaults(cls) -> dict:
        return {"leak_kpa_per_s": 0.005, "supply_kpa": 15.2, "tau_fill_s": 1.5, "tau_vent_s": 0.1,
                "thermal_kpa_per_s": 0.05, "tau_thermal_s": 2.0, "clamp_travel_s": 0.6}

    def __init__(self, **params):
        super().__init__(**params)
        self.P = 0.0
        self.clamp = 0.0
        self.isolated_ms: int | None = None
        self.unclamped_pressurized = False

    def _supply(self) -> float:
        if "supply_air_low" in self.faults:
            return 0.0
        if "regulator_fail" in self.faults:
            return float(self.faults["regulator_fail"].get("supply_kpa", 30.0))
        return self.params["supply_kpa"]

    def step(self, plc: Plc, dt_ms: int, t_ms: int) -> None:
        p, dt = self.params, dt_ms / 1000.0
        if "clamp_slip" in self.faults:
            self.clamp = 0.5
        else:
            rate = dt / p["clamp_travel_s"]
            self.clamp = min(1.0, self.clamp + rate) if plc.bit("Y20") else max(0.0, self.clamp - rate)

        fill = plc.bit("Y21") or "fill_valve_stuck_open" in self.faults
        vent = plc.bit("Y22")
        dP = -(p["leak_kpa_per_s"] / 15.0) * self.P
        if fill:
            dP += (self._supply() - self.P) / p["tau_fill_s"]
        if vent:
            dP += -self.P / p["tau_vent_s"]
        if not fill and not vent:
            if self.isolated_ms is None:
                self.isolated_ms = t_ms
            age_s = (t_ms - self.isolated_ms) / 1000.0
            dP += -p["thermal_kpa_per_s"] * (self.P / 15.0) * math.exp(-age_s / p["tau_thermal_s"])
        else:
            self.isolated_ms = None
        self.P = max(0.0, self.P + dP * dt)
        if self.clamp < 0.99 and self.P > 2.0:
            self.unclamped_pressurized = True

        plc.set_bit("X20", self.clamp >= 0.99)
        plc.set_bit("X21", self.clamp <= 0.01)
        plc.set_bit("X22", "supply_air_low" not in self.faults)
        raw = -2500 if "pt_wire_break" in self.faults else max(-2500, min(10000, round(self.P * 100)))
        plc.set_word("D100", raw)

    def signals(self) -> dict[str, float | bool]:
        return {"P_kpa": round(self.P, 4), "clamp_pos": round(self.clamp, 4),
                "unclamped_pressurized": self.unclamped_pressurized}
