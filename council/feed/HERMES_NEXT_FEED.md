# Hermes feed — Poseidon 3090

**RESUMED for Poseidon 3090 only** by Kyle's order 2026-11-26: Hermes is the
project's local hardware/test seat (her machine: i9, RTX 3090, 128 GB DDR4 —
the exact card Poseidon targets). Her other local work (Athena, Midnight
Dapps) remains paused unless Kyle personally resumes it there too.

Start here: `council/feed/HERMES_START_PROMPT.md`.

## HERMES-1 — Rig recon + rival baselines
1. Recon: GPU/VRAM, driver, nvidia-smi, nvcc, OS; presence + versions of
   SRBMiner-Multi v3.8.4 and OneZeroMiner. Report via PR
   (`docs/benches/hermes-recon.md`) on branch `hermes/hermes-1-recon`.
2. Baselines per `docs/BENCH.md`: SRBMiner v3.8.4, then OneZeroMiner —
   Kyle's OC (1600/+200/810), same pool, 30+ min each; pool-side TH/s,
   avg watts, temps, shares. Results in `docs/benches/` via PR.
   Pool/wallet specifics come from Kyle — ask, never invent.
Acceptance: raw numbers with sources/logs attached; no Poseidon claim
(Poseidon has no kernel yet — these are the bars it must beat).

## Queued next — CLAUDE-1 compile gate (after HERMES-1)
The kernel skeleton (PR #3, `muse/claude-1-kernel-skeleton`) is designed but
not yet compiled — the authoring machine has no nvcc. On your rig:
`scripts/build-kernel.sh && ./build/poseidon_selftest`. Report the full
output via PR or a comment on PR #3: PASS lines + `SELFTEST OK` is the
project's first COMPILED gate. A failure is just as valuable — paste it
verbatim, do not fix the kernel yourself (that routes back to Muse).
