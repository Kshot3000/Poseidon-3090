#!/usr/bin/env bash
# Release the Poseidon 3090 clock locks and persistence mode.
# Dry-run by default; pass --execute to actually run nvidia-smi (needs sudo).
#   ./scripts/oc-reset.sh [--device 0] [--execute]
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/poseidon_oc.py reset "$@"
