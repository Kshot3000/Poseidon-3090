"""Autotune profile selection: pick the best measured profile per GPU.

Profiles are measured (TH/s, watts); selection is by efficiency first with a
hashrate floor, so autotune never trades 20% power for 1% hashrate.
Poseidon tunes for one card only: the RTX 3090 (sm_86, 82 SMs).
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Profile:
    name: str
    tile: int
    blocks_per_sm: int
    power_w: int
    ths: float

    @property
    def gh_per_w(self) -> float:
        return self.ths * 1000 / self.power_w if self.power_w else 0.0


def pick_best(profiles: list[Profile], min_ths_fraction: float = 0.97) -> Profile:
    if not profiles:
        raise ValueError("no profiles measured")
    top_ths = max(p.ths for p in profiles)
    eligible = [p for p in profiles if p.ths >= top_ths * min_ths_fraction]
    return max(eligible, key=lambda p: p.gh_per_w)


# Starting-point candidates for sm_86 (to be measured on Hermes' 3090, not
# assumed — tile 64 is the published Pearl-class baseline we re-tune from).
CANDIDATES = {
    "sm_86": [Profile("amp-default", 64, 2, 350, 0),
              Profile("amp-wide", 128, 2, 350, 0),
              Profile("amp-deep", 64, 3, 350, 0),
              Profile("amp-eco", 64, 2, 320, 0)],
}
