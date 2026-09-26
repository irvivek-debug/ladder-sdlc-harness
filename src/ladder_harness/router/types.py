"""Plain data types shared by the router, backends and tasks."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Usage:
    input: int
    output: int
    thinking: int = 0
    cached: int = 0          # part of `input` served from cache
    cache_write: int = 0     # part of `input` written to cache (Claude: billed at the cache-write rate)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ModelCall:
    task_class: str
    model: str
    effort: str
    system: str
    prompt: str
    schema: dict
    max_output_tokens: int = 32000


@dataclass
class ModelResult:
    data: dict
    text: str
    usage: Usage
    latency_s: float
    model: str
    effort: str
    backend: str                      # vertex | replay | fake
    key: str = ""
    cost_usd: float = 0.0
    cost_by_period: dict = field(default_factory=dict)


class BackendUnavailable(RuntimeError):
    """The backend cannot be reached (credentials, model access, network). Message says how to fix it."""


class ReplayMiss(LookupError):
    """Replay mode was asked for a call that has no recorded cassette."""


class ModelRefused(RuntimeError):
    """The model declined the request (stop_reason == refusal)."""


class BudgetExceeded(RuntimeError):
    """The run's spending cap was reached; the sweep aborts rather than warns."""


class OutputTruncated(RuntimeError):
    """The model hit its output limit (thinking included) before finishing the JSON answer."""
