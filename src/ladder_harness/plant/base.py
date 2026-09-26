"""Plant twin contract: read PLC outputs, integrate physics, write plant-driven inputs."""
from __future__ import annotations

from ..sim.engine import Plc


class Plant:
    """Base twin. Subclasses list their fault names and implement `step` and `signals`."""

    FAULTS: frozenset[str] = frozenset()
    ACTIONS = frozenset({"inject", "clear"})

    def __init__(self, **params):
        unknown = set(params) - set(self.defaults())
        if unknown:
            raise ValueError(f"{type(self).__name__}: unknown parameters {sorted(unknown)}")
        self.params = {**self.defaults(), **params}
        self.faults: dict[str, dict] = {}

    @classmethod
    def defaults(cls) -> dict:
        return {}

    def act(self, action: str, args: dict) -> None:
        if action not in self.ACTIONS:
            raise ValueError(f"{type(self).__name__}: action {action!r} is not allowed")
        getattr(self, f"_act_{action}")(**args)

    def _act_inject(self, fault: str, **kw) -> None:
        if fault not in self.FAULTS:
            raise ValueError(f"{type(self).__name__}: unknown fault {fault!r}")
        self.faults[fault] = kw

    def _act_clear(self, fault: str) -> None:
        self.faults.pop(fault, None)

    def step(self, plc: Plc, dt_ms: int, t_ms: int) -> None:
        raise NotImplementedError

    def signals(self) -> dict[str, float | bool]:
        return {}


class NullPlant(Plant):
    """No physics — every input comes from the scenario."""

    def step(self, plc: Plc, dt_ms: int, t_ms: int) -> None:
        return None
