# Poseidon CUDA — kernel skeleton (CLAUDE-1)

Status, plainly (per `docs/SPEC.md` honesty rules): **designed, not yet
compiled, not yet benchmarked, not shipped.** No hashrate is claimed for
anything in this directory.

## What is here
- `gemm_stage.cuh` / `gemm_stage.cu` — the main GEMM stage contract for the
  pearlhash matrix stage: `C = AP * BP^T`, int8 operands, int32 exact
  accumulation, sm_86-first. Ships a deliberately naive reference kernel;
  the tensor-core MMA path lands behind the same interface once the
  reference agrees with the CPU oracle on real hardware.
- `selftest.cu` — GPU self-test: known-answer GEMM vectors plus the full
  Nacre preparation/recovery identity with the GPU doing the main GEMM.
- `src/poseidon3090/oracle.py` — the CPU math oracle (pure stdlib port of
  the Nacre GPU v0.2 dense oracle from Kyle's Nacre research). The identity
  it pins:

  ```
  AP = A + LA SA^T    BP = B + LB SB^T
  U  = A SB           V  = BP SA        (V uses BP, not B)
  A B^T = AP BP^T - LA V^T - U LB^T
  ```

## Build & run (needs nvcc + an RTX 3090)
```sh
scripts/build-kernel.sh
./build/poseidon_selftest   # expect: PASS lines + SELFTEST OK
```

The build harness targets `sm_86` only — the 3090 is the product. On a
machine without nvcc the script exits 2 and says so; it never fakes a build.

## Next gates (in order)
1. Hermes compiles + runs the self-test on her 3090 (first COMPILED gate).
2. Sol verifies this interface against the pearlhash/cuPOW spec (SOL-1) —
   in particular the preparation bounds and the correction epilogue.
3. Fused sparse preparation kernel behind this interface (the Nacre
   design), then the tensor-core GEMM path, each gated on the oracle.
4. Only then: a `docs/BENCH.md` run — the first moment any number may be
   called a Poseidon hashrate.
