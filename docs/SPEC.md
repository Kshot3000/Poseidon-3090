# Poseidon 3090 — Specification v0.1

## Mission
The best Pearl mining software in the field, focused purely on Pearl mining
with an NVIDIA RTX 3090. Beat SRBMiner-Multi, OneZeroMiner, PeakMiner,
WildRig Multi, lolMiner and PearlVolt on **pool-accepted GH/W on a 3090** — measured,
never marketed.

## Non-goals
- No other coins or algorithms. Pearl / pearlhash only.
- No other GPUs as a design centre. Other cards may run later; nothing is
  tuned for them. The 3090 (sm_86) is the product.
- No hidden fees, no pool lock-in, no closed benchmark modes.

## Pearl protocol contract

Poseidon targets the dense integer path. The reference is Pearl Research Labs'
[node and verifier](https://github.com/pearl-research-labs/pearl/tree/adbfbbac351311859f7f662060f40ef6e57fe109).
Read the certificate rules at the pool job's height. The reference mainnet
parameters require dense proofs from height 91,630, apply the rank penalty
from 96,251, and use the salted-seed V3 certificate from 99,000. FP8/V4 is
unscheduled in this revision.
[Mainnet fork parameters](https://github.com/pearl-research-labs/pearl/blob/adbfbbac351311859f7f662060f40ef6e57fe109/node/chaincfg/params.go#L379-L393)

1. Commit to the serialized incomplete block header and mining configuration
   with BLAKE3 to obtain the job key. The configuration commits to `k`, rank
   `r`, the MMA type, and periodic row and column patterns. Commit the
   BLAKE3 roots of the chunk-padded original matrices using the job key.
   `A` is `m × k` and `B` is `k × n`, stored as `Bᵀ` (`n × k`).
   The V3 seed derivation binds the raw roots to `m` and `n` with separate
   domain salts before the seed chain. Earlier certificates use the raw roots.
   [Proof fields](https://github.com/pearl-research-labs/pearl/blob/adbfbbac351311859f7f662060f40ef6e57fe109/zk-pow/src/v2/api/proof.rs#L53-L105) ·
   [V3 seed derivation](https://github.com/pearl-research-labs/pearl/blob/adbfbbac351311859f7f662060f40ef6e57fe109/zk-pow/src/v2/api/seed.rs#L7-L58)
2. Use those seeds to generate the dense factors `L_A` (`m × r`) and
   `L_B` (`n × r`), with entries in `[-32, 31]`, and the sparse factors
   `S_A` and `S_B` (each `k × r`), with one `+1` and one `−1` per row
   at distinct indices. The noised operands are `AP = A + L_A S_Aᵀ` and
   `BP = Bᵀ + L_B S_Bᵀ`. Each noise value is a difference of two dense
   entries, bounded by `[-63, 63]`. The reference's default generated
   operands are in `[-64, 64]` inclusive, so the prepared values fit signed
   int8. The Nacre oracle exercises a subset of these bounds and separately
   checks recovery of the unnoised product.
   [Reference noise generation](https://github.com/pearl-research-labs/pearl/blob/adbfbbac351311859f7f662060f40ef6e57fe109/zk-pow/src/v2/circuit/pearl_noise.rs#L13-L155) ·
   [CPU mining reference](https://github.com/pearl-research-labs/pearl/blob/adbfbbac351311859f7f662060f40ef6e57fe109/zk-pow/src/v2/mine.rs#L15-L84)
3. For each pattern-selected output tile, accumulate the noised product
   in signed int32 over complete groups of `r` terms. At each group
   boundary, XOR-reduce the cumulative tile and fold the result into a
   cyclic 16-word jackpot with a 13-bit left rotation. Hash the little-endian
   jackpot words with keyed BLAKE3, using the A noise seed. Check the
   little-endian hash against the applicable target. A candidate proof opens
   the selected original A rows and B columns against the job-keyed Merkle
   roots. Pool share acceptance also depends on the pool's job and share
   message contract.
   [Reference mining loop](https://github.com/pearl-research-labs/pearl/blob/adbfbbac351311859f7f662060f40ef6e57fe109/zk-pow/src/v2/mine.rs#L86-L122) ·
   [Jackpot hash](https://github.com/pearl-research-labs/pearl/blob/adbfbbac351311859f7f662060f40ef6e57fe109/zk-pow/src/v2/api/proof_utils.rs#L1510-L1514)

Matrix sizes vary by configuration. The verifier requires `m,n ≤ 2²⁴`,
`max(1024, 16r) ≤ k ≤ min(2¹⁶, 4r²)`, and `k` divisible by 64. The
base rank range is powers of two in `[32, 1024]`. Rank-penalized consensus requires at least 128. The hash tile dimensions are each even,
with 32–256 entries total, and the selected row/column patterns must fit
their matrices. Check the worker input size and all active consensus bounds
in the verifier. The hash tile and noise rank are protocol parameters.
CUDA threadblock tile and launch bounds are hardware tuning knobs.
[Verifier bounds and difficulty](https://github.com/pearl-research-labs/pearl/blob/adbfbbac351311859f7f662060f40ef6e57fe109/zk-pow/src/v2/api/sanity_checks.rs#L15-L65) ·
[Rank penalty](https://github.com/pearl-research-labs/pearl/blob/adbfbbac351311859f7f662060f40ef6e57fe109/zk-pow/src/v2/api/sanity_checks.rs#L161-L200)

## Architecture (target)
1. **CUDA kernel, sm_86-first:** tensor-core GEMM for the cuPOW matrix stage,
   with the fused sparse preparation (noising) kernel design carried from
   Kyle's Nacre GPU research (Oysters4All). Per-arch launch bounds and tile
   sizes tuned for Ampere (starting point to re-tune on the bench, not assume:
   3090 SM count 82, 24 GB GDDR6X).
2. **Overlap GPU work and proof generation:** prepare the job-keyed
   commitments before launching work. Retain the source buffers for any
   outstanding proof, pass proof construction to a bounded host queue, and
   tag each candidate with its job generation. Recheck that generation before
   submitting. Measure stale work and job-switch latency in the pool bench.
3. **Stratum client:** Pearl pool protocol, failover pools, stale/rejected
   share accounting visible in stats — waste is a scoreboard number.
4. **Autotune:** per-card measured profiles picked by efficiency (GH/W),
   sweeping around Kyle's centre profile (see `src/poseidon3090/oc.py`):
   core lock / offset, memory floor lock 810 MHz vs the 405 MHz arm,
   power limit. Saved per card, re-runnable.
5. **Dev fee:** 2%, the standard time-sliced mechanism used by SRBMiner-Multi,
   OneZeroMiner, lolMiner and WildRig: the miner periodically switches to the
   dev pool/wallet for 2% of elapsed time, then returns to the user's pool.
   Announced in log + stats API while a fee round is active, and the round is
   skipped if the dev pool is unreachable — fee mining never blocks user
   mining. Address in README, character-exact.
6. **Telemetry:** local stats API (HiveOS-compatible shape, following the
   OysterRig pattern): hashrate (GPU-side and pool-side), watts, temps,
   shares accepted/rejected/stale, fee state.
7. **Platforms:** Linux first, Windows second, HiveOS flight sheet when the
   binary is real.

## Scoreboard (the only success metric)
- Baseline rival: **SRBMiner-Multi v3.8.4** (skip v3.8.2 entirely — pearlhash
  hashrate/power flaw fixed in v3.8.3). OneZeroMiner's current Pearl build is
  the second baseline (version pinned by GROK-1's rival sweep).
- Public bar: PeakMiner 121.8 TH/s @ 348 W pool-accepted (default OC).
- **Target: ≥125 TH/s @ ≤320 W pool-side, after fee, on Kyle's OC → ≥391 GH/W.**
- Protocol: `docs/BENCH.md`. Equal windows, same pool, same card, same OC,
  raw results published either way.

## Continuous improvement (Kyle's order, 2026-11-26)
The target is a floor, not a ceiling: **higher hashrate, lower power draw,
everything better — improved daily.** Every bench result feeds the next
tuning step (kernel tiles, launch bounds, OC sweep points, stale-share
waste), and the scoreboard in this spec and on the website is updated with
each verified result. A day with a measured improvement beats a day with a
big claim.

## Honesty rules
- No hashrate, efficiency, or "fastest" claim without a BENCH.md run behind it.
- Targets are always labelled targets.
- Kernel status is stated plainly: designed ≠ compiled ≠ benchmarked ≠ shipped.
