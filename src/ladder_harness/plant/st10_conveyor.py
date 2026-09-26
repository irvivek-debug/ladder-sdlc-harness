"""ST10 pallet conveyor twin: 0.5 m pallets at 0.2 m/s, entry eye at 0.2 m, stopper at 1.0 m."""
from __future__ import annotations

from ..sim.engine import Plc
from .base import Plant

SPEED, LENGTH, ENTRY_EYE, STOP, EXIT = 0.2, 0.5, 0.2, 1.0, 1.6


class St10Plant(Plant):
    FAULTS = frozenset({"jam_at_entry", "overload"})
    ACTIONS = frozenset({"inject", "clear", "spawn_pallet"})

    def __init__(self, **params):
        super().__init__(**params)
        self.pallets: list[float] = []   # front positions, leading pallet first
        self.jammed: float | None = None

    def _act_spawn_pallet(self) -> None:
        rear_of_last = self.pallets[-1] - LENGTH if self.pallets else EXIT
        if rear_of_last >= 0.0:
            self.pallets.append(0.0)

    def _act_inject(self, fault: str, **kw) -> None:
        super()._act_inject(fault, **kw)
        if fault == "jam_at_entry":
            self.jammed = ENTRY_EYE + LENGTH / 2

    def step(self, plc: Plc, dt_ms: int, t_ms: int) -> None:
        running = plc.bit("Y10") and "overload" not in self.faults
        released = plc.bit("Y11")
        if running:
            moved = []
            for i, front in enumerate(self.pallets):
                limit = EXIT + 1.0 if i == 0 else moved[i - 1] - LENGTH
                if not released and front <= STOP + 1e-9:
                    limit = min(limit, STOP)
                if self.jammed is not None:
                    limit = min(limit, self.jammed - LENGTH if front < self.jammed else limit)
                moved.append(max(front, min(front + SPEED * dt_ms / 1000.0, limit)))
            self.pallets = [f for f in moved if f <= EXIT]
        occupied = self.pallets + ([self.jammed] if self.jammed is not None else [])
        plc.set_bit("X10", any(0.98 <= f <= 1.10 for f in self.pallets))
        plc.set_bit("X11", any(f - LENGTH <= ENTRY_EYE <= f for f in occupied))
        plc.set_bit("X13", "overload" not in self.faults)

    def signals(self) -> dict[str, float | bool]:
        return {"pallets": len(self.pallets), "lead_pallet_m": round(self.pallets[0], 3) if self.pallets else -1.0}
