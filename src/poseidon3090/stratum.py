"""Stratum V1 message handling for Pearl pools (pure logic, no sockets here).

Poseidon is Pearl-only: mining.subscribe / authorize / notify /
set_difficulty / submit, with share accounting that keeps accepted,
rejected and stale shares as separate scoreboard numbers.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field


def parse_message(line: str) -> dict:
    msg = json.loads(line)
    if not isinstance(msg, dict) or "method" not in msg and "id" not in msg:
        raise ValueError("not a stratum message")
    return msg


def build_request(req_id: int, method: str, params: list) -> str:
    return json.dumps({"id": req_id, "method": method, "params": params}) + "\n"


def validate_prl_wallet(wallet: str) -> str:
    """Pearl wallets are bech32 'prl1...' strings. Reject anything else early,
    at config time, instead of after a pool disconnect loop."""
    w = wallet.strip()
    if not w.startswith("prl1") or len(w) < 20 or " " in w:
        raise ValueError("wallet does not look like a Pearl (prl1...) address")
    return w


@dataclass
class Job:
    job_id: str
    prevhash: str = ""
    clean: bool = True
    difficulty: float = 1.0
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_notify(cls, params: list, difficulty: float = 1.0) -> "Job":
        if not params or not str(params[0]):
            raise ValueError("notify missing job_id")
        return cls(job_id=str(params[0]),
                   prevhash=str(params[1]) if len(params) > 1 else "",
                   clean=bool(params[-1]) if len(params) > 2 else True,
                   difficulty=difficulty)


@dataclass
class ShareTracker:
    """Accepted / rejected / stale accounting. A share submitted for a job
    that is no longer current is stale — that waste is a scoreboard number
    (docs/BENCH.md), so it is counted, never lumped into rejected."""
    accepted: int = 0
    rejected: int = 0
    stale: int = 0
    current_job_id: str | None = None

    def on_new_job(self, job_id: str) -> None:
        self.current_job_id = job_id

    def record_submit(self, job_id: str, accepted: bool) -> str:
        if self.current_job_id is not None and job_id != self.current_job_id:
            self.stale += 1
            return "stale"
        if accepted:
            self.accepted += 1
            return "accepted"
        self.rejected += 1
        return "rejected"

    @property
    def reject_pct(self) -> float:
        total = self.accepted + self.rejected
        return 100 * self.rejected / total if total else 0.0

    @property
    def stale_pct(self) -> float:
        total = self.accepted + self.rejected + self.stale
        return 100 * self.stale / total if total else 0.0


@dataclass
class PoolSet:
    """Ordered failover pools; first healthy pool wins."""
    pools: list[str]
    index: int = 0

    def current(self) -> str:
        return self.pools[self.index]

    def failover(self) -> str:
        self.index = (self.index + 1) % len(self.pools)
        return self.current()
