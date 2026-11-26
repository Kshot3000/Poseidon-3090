"""Overclock / clock-lock profiles for the RTX 3090 — efficiency is the product.

Pearl (pearlhash) is tensor-core bound, not memory bound. The winning move on
Ampere is: lock the core at its efficiency sweet spot, push the core offset,
and lock memory DOWN to the floor — GDDR6X at full clock burns watts the
GEMM never uses.

Kyle's RTX 3090 profile (his production settings, 2026-10-13):
  CCLK 1600  — core locked at 1600 MHz
  COFF +200  — core clock offset +200 MHz (VF curve shift: same clock, less volts)
  MCLK 810   — memory locked at 810 MHz (floor lock, the efficiency trick)

A second bench arm tests MCLK 405 (SRBMiner v3.8.4's pearlhash memory lock)
against the 810 floor, judged pool-side on whole-rig power.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class OcProfile:
    name: str
    gpu: str
    arch: str
    lock_core_mhz: int
    core_offset_mhz: int
    lock_mem_mhz: int
    power_limit_w: int | None = None

    def validate(self) -> None:
        assert 800 <= self.lock_core_mhz <= 2200, "core lock out of sane range"
        assert -500 <= self.core_offset_mhz <= 300, "core offset out of sane range"
        assert 400 <= self.lock_mem_mhz <= 1200, "mem lock should be a floor lock (GDDR6X idle-class)"
        if self.power_limit_w is not None:
            assert 150 <= self.power_limit_w <= 500

    def nvidia_smi_linux(self, device: int = 0) -> list[str]:
        """Commands for Linux. Core OFFSET is not in nvidia-smi — it needs
        nvidia-settings (X) or NVML; emitted as a comment line by callers."""
        cmds = [
            f"nvidia-smi -i {device} -pm 1",
            f"nvidia-smi -i {device} -lgc {self.lock_core_mhz},{self.lock_core_mhz}",
            f"nvidia-smi -i {device} -lmc {self.lock_mem_mhz},{self.lock_mem_mhz}",
        ]
        if self.power_limit_w:
            cmds.append(f"nvidia-smi -i {device} -pl {self.power_limit_w}")
        return cmds

    def nvidia_smi_windows(self, device: int = 0) -> list[str]:
        """Windows nvidia-smi supports -lgc/-lmc; core offset needs MSI
        Afterburner / NVIDIA App (documented by callers)."""
        return self.nvidia_smi_linux(device)

    def reset_nvidia_smi(self, device: int = 0) -> list[str]:
        """Commands that undo nvidia_smi_linux(): release the core and
        memory clock locks and drop persistence mode. A power limit set by
        the profile is NOT reset here — nvidia-smi has no 'default PL'
        flag that is safe across cards; callers must say so out loud."""
        return [
            f"nvidia-smi -i {device} -rgc",
            f"nvidia-smi -i {device} -rmc",
            f"nvidia-smi -i {device} -pm 0",
        ]

    def gh_per_w(self, ths: float, watts: float) -> float:
        return ths * 1000 / watts if watts else 0.0


KYLE_3090 = OcProfile(
    name="kyle-3090-efficiency", gpu="RTX 3090", arch="sm_86",
    lock_core_mhz=1600, core_offset_mhz=200, lock_mem_mhz=810,
    power_limit_w=None,  # Kyle did not specify a PL — clocks do the capping
)
KYLE_3090.validate()

# Second bench arm: same core point, memory locked at 405 MHz.
KYLE_3090_MEM405 = OcProfile(
    name="kyle-3090-mem405", gpu="RTX 3090", arch="sm_86",
    lock_core_mhz=1600, core_offset_mhz=200, lock_mem_mhz=405,
    power_limit_w=None,
)
KYLE_3090_MEM405.validate()

# Autotune sweep AROUND Kyle's profile: his point is the centre, not gospel.
# Memory stays floor-locked (compute-bound algo); core lock/offset vary.
SWEEP_3090 = [
    OcProfile(f"sweep-c{c}o{o}", "RTX 3090", "sm_86", c, o, 810)
    for c, o in [(1500, 200), (1600, 150), (1600, 200), (1600, 250),
                 (1700, 200), (1800, 200)]
]
for _p in SWEEP_3090:
    _p.validate()

# Name -> profile registry for the OC tooling (scripts/poseidon_oc.py).
# Sweep points are bench-only and deliberately NOT applicable by name:
# the tooling applies a named, reviewed profile or nothing.
PROFILES = {p.name: p for p in (KYLE_3090, KYLE_3090_MEM405)}

# The bar on a 3090 (public figures, Oct–Nov 2026):
#   PeakMiner v2.5.0: 121.8 TH/s @ 348 W = 350 GH/W (v1.0.12 sweep: 126.5 @ 388 W)
#   SRBMiner-Multi v3.8.4 is the named baseline rival (skip v3.8.2: pearlhash flaw).
# Poseidon targets on Kyle's OC — TARGETS, not claims:
TARGET_3090_THS = 125.0      # beat 121.8 with margin
TARGET_3090_WATTS = 320.0    # under PeakMiner's 348 W via the 810 mem lock + 1600 core lock
TARGET_3090_GH_PER_W = TARGET_3090_THS * 1000 / TARGET_3090_WATTS  # ≈391 GH/W
