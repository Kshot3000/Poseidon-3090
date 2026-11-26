#!/usr/bin/env bash
# Apply a reviewed Poseidon 3090 OC profile (default: Kyle's 3090 profile).
# Dry-run by default; pass --execute to actually run nvidia-smi (needs sudo).
#   ./scripts/oc-apply.sh [--profile kyle-3090-mem405] [--device 0] [--execute]
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/poseidon_oc.py apply "$@"
