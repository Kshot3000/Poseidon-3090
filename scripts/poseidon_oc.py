#!/usr/bin/env python3
"""Poseidon 3090 OC tooling — apply/reset the reviewed profiles in oc.py.

Usage:
    python3 scripts/poseidon_oc.py apply [--profile NAME] [--device N] [--execute]
    python3 scripts/poseidon_oc.py reset [--device N] [--execute]
    python3 scripts/poseidon_oc.py list

Safety rules:
- DRY RUN by default. Commands are printed, never run, unless --execute
  is passed. Applying clock locks needs root/admin on both OSes.
- Only named profiles from poseidon3090.oc.PROFILES can be applied.
  The autotune sweep points are bench data, not apply targets.
- The core OFFSET (+200 on Kyle's profile) is NOT applied by nvidia-smi
  on any OS: Linux needs nvidia-settings/NVML, Windows needs MSI
  Afterburner / NVIDIA App. This tool prints the offset as a required
  manual step and never pretends it was set.
- Reset releases the clock locks (-rgc/-rmc) and persistence mode.
  It does not restore a power limit (no profile here sets one).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from poseidon3090.oc import PROFILES, KYLE_3090  # noqa: E402


def apply_commands(profile_name: str, device: int, platform: str) -> list[str]:
    profile = PROFILES[profile_name]
    profile.validate()
    if platform.startswith("win"):
        return profile.nvidia_smi_windows(device)
    return profile.nvidia_smi_linux(device)


def reset_commands(device: int) -> list[str]:
    # Reset is profile-independent: every profile locks via the same flags.
    return KYLE_3090.reset_nvidia_smi(device)


def offset_note(profile_name: str) -> str:
    profile = PROFILES[profile_name]
    return (
        f"MANUAL STEP: core offset {profile.core_offset_mhz:+d} MHz is not set "
        "by nvidia-smi. Linux: nvidia-settings/NVML. Windows: MSI Afterburner "
        "/ NVIDIA App. Bench numbers are only comparable once it is set."
    )


def run(cmds: list[str], execute: bool) -> int:
    for cmd in cmds:
        print(("RUN  " if execute else "DRY  ") + cmd)
        if execute:
            rc = subprocess.run(cmd, shell=True).returncode
            if rc != 0:
                print(f"FAILED ({rc}): {cmd}", file=sys.stderr)
                return rc
    if not execute:
        print("Dry run only — re-run with --execute to apply (needs root/admin).")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="action", required=True)
    p_apply = sub.add_parser("apply")
    p_apply.add_argument("--profile", default=KYLE_3090.name, choices=sorted(PROFILES))
    p_apply.add_argument("--device", type=int, default=0)
    p_apply.add_argument("--execute", action="store_true")
    p_reset = sub.add_parser("reset")
    p_reset.add_argument("--device", type=int, default=0)
    p_reset.add_argument("--execute", action="store_true")
    sub.add_parser("list")
    args = ap.parse_args(argv)

    if args.action == "list":
        for name, p in sorted(PROFILES.items()):
            print(f"{name}: CCLK {p.lock_core_mhz} lock, COFF {p.core_offset_mhz:+d}, "
                  f"MCLK {p.lock_mem_mhz} lock, PL {p.power_limit_w or 'unset'}")
        return 0
    if args.action == "apply":
        print(offset_note(args.profile))
        return run(apply_commands(args.profile, args.device, sys.platform), args.execute)
    return run(reset_commands(args.device), args.execute)


if __name__ == "__main__":
    raise SystemExit(main())
