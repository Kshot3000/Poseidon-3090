# SOL-1 — Pearl protocol and RTX 3090 kernel review

Reviewed Poseidon [PR #3](https://github.com/Kshot3000/Poseidon-3090/pull/3)
as merged at `6a35be3` and Pearl's reference at
[`adbfbbac`](https://github.com/pearl-research-labs/pearl/tree/adbfbbac351311859f7f662060f40ef6e57fe109).
This is a source review.

## Findings

1. **Blocking — `cuda/gemm_stage.cuh:17–22,54–65`.** The current
   interface exposes only the final noised GEMM. Pearl feeds the cumulative
   noised tile into a rotating jackpot after **every** complete
   rank-sized group. A full final matrix and the Nacre recovery identity
   cannot reproduce those checkpoints. Keep the recovery test for the
   arithmetic and add a separate reference fixture covering roots, both
   seed modes, patterned tiles, all jackpot words and the final keyed
   digest. The mining path needs a tile-local reduction at the group
   boundary. Keep full-matrix output for the diagnostic path.
   [Reference mining loop](https://github.com/pearl-research-labs/pearl/blob/adbfbbac351311859f7f662060f40ef6e57fe109/zk-pow/src/v2/mine.rs#L86-L122)
2. **Blocking — `docs/SPEC.md:17–23` (reviewed baseline),
   `src/poseidon3090/oracle.py:19–32`.** The old spec skipped
   the job-keyed commitments, fork-specific seeds, verifier shapes and
   jackpot rule. The Nacre oracle limits rank to 64 or 128, accepts a
   prototype `k` up to `2²⁰`, and excludes signal value 64. Pearl's
   verifier caps `k` at `2¹⁶`, imposes other shape constraints, and
   requires rank ≥128 under the penalty rule. The reference generator's
   default signal range includes 64. The oracle's `127 × 2²⁰` argument
   bounds a sum of single factors and leaves the dot-product accumulator
   proof incomplete. An int8-by-int8 dot product up to Pearl's `2¹⁶`
   bound has magnitude at most `128² × 2¹⁶ = 2³⁰`, within int32. Require
   a validated job configuration at the mining boundary.
   [Verifier constraints](https://github.com/pearl-research-labs/pearl/blob/adbfbbac351311859f7f662060f40ef6e57fe109/zk-pow/src/v2/api/sanity_checks.rs#L15-L65) ·
   [Rank rule](https://github.com/pearl-research-labs/pearl/blob/adbfbbac351311859f7f662060f40ef6e57fe109/zk-pow/src/v2/api/sanity_checks.rs#L161-L180) ·
   [Default signal range](https://github.com/pearl-research-labs/pearl/blob/adbfbbac351311859f7f662060f40ef6e57fe109/zk-pow/src/v2/mine.rs#L15-L39)
3. **High — `cuda/gemm_stage.cu:13–43`.** Each invocation allocates
   three device buffers and transfers both operands in and the entire
   product out. Allocation failures after the first allocation leak
   earlier buffers. The code discards the `cudaMemcpy` return values,
   including the blocking copy that can surface an execution error. Use
   checked calls and scoped cleanup in the reference wrapper. For mining,
   reuse device buffers across launches and transfer compact winning tile
   descriptors. Measure preparation, kernel and transfer time independently.
4. **High — `docs/SPEC.md:18–20` (reviewed baseline),
   `src/poseidon3090/gpu.py:17–22`.** The async plan leaves job
   and buffer ownership undefined. The Merkle roots feed the noise seeds
   before GEMM. Opening those trees for a hit can overlap later work if
   the queue owns the committed buffers and tags each hit with its job
   generation. Bound queue depth and work batch duration, check the
   generation before proof building and again before submission, and test
   replacement of a job while the GPU and proof workers both have work.
   [Commitment order](https://github.com/pearl-research-labs/pearl/blob/adbfbbac351311859f7f662060f40ef6e57fe109/zk-pow/src/v2/mine.rs#L45-L62)
5. **Performance risk — `cuda/gemm_stage.cuh:24–29`,
   `cuda/gemm_stage.cu:28–34`.** The 64/128 CUDA tile edges and
   two/three blocks per SM are hypotheses. The skeleton ignores those
   knobs and runs a scalar thread per output. Compare candidate tiles
   with the real rank-boundary reduction enabled: measure registers,
   shared memory, occupancy, spills, and time per batch. Verify that
   fusing sparse preparation saves traffic without increasing register
   pressure enough to erase the gain.

## Verdict

The skeleton is a reasonable correctness reference for dense int8 GEMM.
Matching Pearl's seeded, cumulative jackpot is the first functional
gate. The biggest performance risk is the cost of jackpot reduction and
job/proof handoff around otherwise fast tensor-core math. A reference
jackpot fixture, a real sm_86 compile and self-test, and a device-resident
pipeline need to precede equal-window, pool-side benchmarks against
SRBMiner-Multi v3.8.4 and OneZeroMiner. Whether Poseidon beats either
miner remains an open hardware question.
