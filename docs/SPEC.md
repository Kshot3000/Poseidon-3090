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

## Architecture (target)
1. **CUDA kernel, sm_86-first:** tensor-core GEMM for the cuPOW matrix stage,
   with the fused sparse preparation (noising) kernel design carried from
   Kyle's Nacre GPU research (Oysters4All). Per-arch launch bounds and tile
   sizes tuned for Ampere (starting point to re-tune on the bench, not assume:
   3090 SM count 82, 24 GB GDDR6X).
2. **GPU never stalls:** proof/Merkle construction and job switches run async
   on CPU threads while the GPU keeps hashing (the incumbents' best idea is
   table stakes here).
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
