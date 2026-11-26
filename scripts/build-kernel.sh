#!/bin/sh
# Build the Poseidon CUDA kernel skeleton + self-test for sm_86 (RTX 3090).
# Honest failure: on a machine without nvcc this script says so and exits 2 —
# it never fakes a build. Run the self-test on a real 3090 (Hermes' rig):
#   scripts/build-kernel.sh && ./build/poseidon_selftest
set -eu
cd "$(dirname "$0")/.."

if ! command -v nvcc >/dev/null 2>&1; then
  echo "nvcc not found: CUDA toolkit is not installed on this machine." >&2
  echo "Kernel status stays DESIGNED, NOT COMPILED. Build on an sm_86" >&2
  echo "machine (Hermes' RTX 3090 rig) with the CUDA toolkit installed." >&2
  exit 2
fi

mkdir -p build
nvcc -O2 -std=c++17 -gencode arch=compute_86,code=sm_86 \
  -Icuda cuda/gemm_stage.cu cuda/selftest.cu -o build/poseidon_selftest
echo "Built build/poseidon_selftest (sm_86). Run it on the 3090 to execute"
echo "the self-test; a PASS there is the first COMPILED+VERIFIED gate."
