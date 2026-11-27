"""Validated Pearl job configuration at the mining boundary (CLAUDE-8).

Implements SOL-1 finding 2 (docs/SOL-1.md, PR #16): the Nacre CPU oracle in
``oracle.py`` is a *prototype* — it limits rank to {64, 128}, accepts a
prototype ``k`` up to 2^20, and rejects the signal value 64. Pearl's
verifier is different, and a job that the verifier would reject must never
reach the kernel. This module is that boundary check: every job
configuration is validated against the verifier's bounds before mining.

Verifier bounds (Pearl reference, zk-pow v2 sanity checks, as pinned by
SOL-1 against pearl-research-labs/pearl@adbfbbac):

- ``m, n <= 2^24``
- rank ``r`` is a power of two in [32, 1024]; under the rank-penalty rule
  (mainnet from height 96,251 per SOL-1's SPEC update) ``r >= 128``
- ``max(1024, 16*r) <= k <= min(2^16, 4*r^2)`` and ``k`` divisible by 64
- the hash tile's dimensions are each even, with 32..256 entries total,
  and the tile must fit inside the matrices it selects from
- generated operand (signal) values lie in [-64, 64] inclusive — 64 is
  valid here even though the prototype oracle rejects it for A/B entries

Accumulator safety follows from the ``k`` cap, not from the oracle's
``127 * 2^20`` argument (which bounds a sum of single factors, not a dot
product): an int8-by-int8 dot product over at most 2^16 terms has
magnitude at most ``128 * 128 * 2^16 = 2^30``, inside signed int32.
``dot_product_bound`` makes that check explicit.

This module validates configuration only. It mines nothing and claims no
hashrate.
"""
from __future__ import annotations

from dataclasses import dataclass

MAX_DIM = 1 << 24            # verifier cap on m and n
MAX_K = 1 << 16              # verifier cap on k
K_DIVISOR = 64               # k must be divisible by 64
MIN_RANK, MAX_RANK = 32, 1024
PENALIZED_MIN_RANK = 128     # rank-penalty rule floor
SIGNAL_MIN, SIGNAL_MAX = -64, 64
TILE_MIN_ENTRIES, TILE_MAX_ENTRIES = 32, 256
INT32_LIMIT = 1 << 31


def _is_power_of_two(v: int) -> bool:
    return v > 0 and (v & (v - 1)) == 0


def dot_product_bound(k: int, entry_bound: int = 128) -> int:
    """Worst-case |dot product| of two int8-range vectors of length k."""
    return entry_bound * entry_bound * k


@dataclass(frozen=True)
class JobConfig:
    """One Pearl job's shape, as committed to by the job key (SOL-1)."""

    m: int
    n: int
    k: int
    rank: int
    tile_h: int
    tile_w: int
    rank_penalized: bool = False
    signal_min: int = SIGNAL_MIN
    signal_max: int = SIGNAL_MAX

    def validate(self) -> "JobConfig":
        """Raise ValueError on any verifier-bound violation; return self."""
        for name, dim in (("m", self.m), ("n", self.n)):
            if not 1 <= dim <= MAX_DIM:
                raise ValueError(f"{name}={dim} outside [1, 2^24]")
        r = self.rank
        if not _is_power_of_two(r) or not MIN_RANK <= r <= MAX_RANK:
            raise ValueError(
                f"rank r={r} must be a power of two in [32, 1024]")
        if self.rank_penalized and r < PENALIZED_MIN_RANK:
            raise ValueError(
                f"rank r={r} below the rank-penalty floor of 128")
        k_lo = max(1024, 16 * r)
        k_hi = min(MAX_K, 4 * r * r)
        if self.k % K_DIVISOR:
            raise ValueError(f"k={self.k} not divisible by 64")
        if not k_lo <= self.k <= k_hi:
            raise ValueError(
                f"k={self.k} outside [{k_lo}, {k_hi}] for rank {r}")
        if dot_product_bound(self.k) >= INT32_LIMIT:
            raise ValueError(
                f"k={self.k} dot-product bound reaches int32 limit")
        for name, dim in (("tile_h", self.tile_h), ("tile_w", self.tile_w)):
            if dim <= 0 or dim % 2:
                raise ValueError(f"{name}={dim} must be positive and even")
        entries = self.tile_h * self.tile_w
        if not TILE_MIN_ENTRIES <= entries <= TILE_MAX_ENTRIES:
            raise ValueError(
                f"hash tile has {entries} entries, outside [32, 256]")
        if self.tile_h > self.m or self.tile_w > self.n:
            raise ValueError("hash tile must fit inside its matrices")
        if not (SIGNAL_MIN <= self.signal_min <= self.signal_max
                <= SIGNAL_MAX):
            raise ValueError(
                f"signal range [{self.signal_min}, {self.signal_max}] "
                "outside the generated-operand range [-64, 64]")
        return self


def validate_job_config(**kwargs) -> JobConfig:
    """Build and validate a JobConfig in one call (mining-boundary entry)."""
    return JobConfig(**kwargs).validate()
