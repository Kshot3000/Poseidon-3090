"""Dev-fee slicer: disclosed 2%, time-based, announced, never blocking.

The standard mechanism used by SRBMiner-Multi, OneZeroMiner, lolMiner and
WildRig: every cycle, the miner switches to the dev pool and mines to the
dev wallet for FEE_FRACTION of the time, then switches back to the user's
pool and wallet. Fee rounds are logged when they start/end, and a round is
skipped if the dev pool is unreachable instead of interrupting user mining.
"""
from __future__ import annotations

FEE_FRACTION = 0.02  # 2% — set by Kyle 2026-11-26
FEE_WALLET = "prl1pvrhfx8g8dpqcj3pp9782ykf8gyff4qwhzz7mfvn4udcelwt858hqsa0l32"  # Poseidon 3090 dev-fee address (Kyle, 2026-11-26) — NOT the donation address, NOT the OysterRig fee address
CYCLE_SECONDS = 100 * 60  # 100-minute cycle -> 120s fee per cycle = 2%


def fee_seconds_in_cycle(elapsed_in_cycle: float) -> float:
    fee_len = CYCLE_SECONDS * FEE_FRACTION
    return max(0.0, min(fee_len, elapsed_in_cycle - (CYCLE_SECONDS - fee_len))) \
        if elapsed_in_cycle > CYCLE_SECONDS - fee_len else 0.0


def is_fee_time(elapsed_total: float, first_round_delay: float = 30 * 60) -> bool:
    if elapsed_total < first_round_delay:
        return False
    return fee_seconds_in_cycle(elapsed_total % CYCLE_SECONDS) > 0 or \
        (elapsed_total % CYCLE_SECONDS) >= CYCLE_SECONDS - CYCLE_SECONDS * FEE_FRACTION


def effective_fee_fraction(observed_user_seconds: float, observed_fee_seconds: float) -> float:
    total = observed_user_seconds + observed_fee_seconds
    return observed_fee_seconds / total if total else 0.0
