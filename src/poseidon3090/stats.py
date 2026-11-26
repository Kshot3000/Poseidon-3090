"""Telemetry stats for the local HTTP API / HiveOS dashboard."""
from __future__ import annotations
from dataclasses import dataclass, field
from .fee import FEE_FRACTION


@dataclass
class GpuStats:
    name: str
    ths: float = 0.0
    power_w: float = 0.0
    temp_c: float = 0.0
    accepted: int = 0
    rejected: int = 0
    stale: int = 0

    @property
    def gh_per_w(self) -> float:
        return self.ths * 1000 / self.power_w if self.power_w else 0.0

    @property
    def reject_pct(self) -> float:
        total = self.accepted + self.rejected
        return 100 * self.rejected / total if total else 0.0

    @property
    def stale_pct(self) -> float:
        total = self.accepted + self.rejected + self.stale
        return 100 * self.stale / total if total else 0.0


@dataclass
class FleetStats:
    gpus: list[GpuStats] = field(default_factory=list)
    uptime_s: float = 0.0
    fee_active: bool = False

    def total_ths(self) -> float:
        return sum(g.ths for g in self.gpus)

    def to_api(self) -> dict:
        return {"miner": "poseidon-3090", "total_ths": self.total_ths(),
                "uptime_s": self.uptime_s,
                "fee_active": self.fee_active, "fee_fraction": FEE_FRACTION,
                "gpus": [{"name": g.name, "ths": g.ths,
                          "gh_per_w": round(g.gh_per_w, 1),
                          "temp_c": g.temp_c,
                          "reject_pct": round(g.reject_pct, 2),
                          "stale_pct": round(g.stale_pct, 2)}
                         for g in self.gpus]}
