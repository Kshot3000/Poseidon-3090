"""GPU backend stub — honest placeholder.

The production backend is CUDA for sm_86 only: tensor-core MMA GEMM + the
Nacre fused sparse preparation kernel design (Oysters4All research).
It is built and benchmarked on Hermes' RTX 3090 (board HERMES-1 /
CLAUDE-1) — this build environment has no GPU, so nothing here claims
a hashrate. This stub exists so the rest of the miner can be developed
and tested against a stable interface.
"""
from __future__ import annotations


class GpuUnavailable(RuntimeError):
    pass


def list_devices() -> list[str]:
    raise GpuUnavailable("CUDA backend not built: compile gpu/cuda with nvcc (sm_86) on a 3090 host")


def mine_once(*args, **kwargs):
    raise GpuUnavailable("CUDA backend not built")
