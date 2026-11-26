# Poseidon 3090 — Board

Status key: `queued` · `claimed` · `in progress` · `in review` · `done` · `blocked` · `paused`

| ID | Task | Seat | Status | Notes |
|---|---|---|---|---|
| POSEIDON-1 | Project website: GitHub Pages site in `site/` (scoreboard, fee transparency, honest status) + Pages workflow | Muse | done | 2026-11-26, Kyle's order; live at https://kshot3000.github.io/Poseidon-3090/ once Pages deploys |
| POSEIDON-0 | Repo bootstrap: README, SPEC, BENCH, council, OC + fee core, tests | Muse | done | 2026-11-26, founding commit |
| GROK-1 | Rival sweep: current Pearl builds + published 3090 figures for OneZeroMiner, SRBMiner-Multi v3.8.4, lolMiner, PeakMiner, WildRig Multi, PearlVolt — versions, fees, claimed vs pool-accepted numbers, sources | Grok | queued | Packet: `council/feed/GROK_FEED.md` wave 1 |
| SOL-1 | Verify pearlhash/cuPOW spec accuracy in `docs/SPEC.md`; review sm_86 kernel design (tile, launch bounds, async job switch) and flag anything that would not beat the incumbents | Sol | queued | Packet: `council/feed/SOL_FEED.md` |
| CLAUDE-1 | CUDA kernel skeleton: sm_86 build harness (nvcc), GEMM stage interface, CPU math oracle tests ported from Nacre research | Muse | queued | No hashrate claim; compile + oracle correctness only |
| CLAUDE-2 | Stratum client core: Pearl pool messages, failover, share accounting — unit-tested, following the OysterRig pattern | Muse | done | 2026-11-26 framework PR: stratum.py + tune.py + stats.py + gpu.py stub, tests 22/22 |
| CLAUDE-3 | OC tooling: apply/reset scripts for the 3090 profiles (Linux + Windows), from `src/poseidon3090/oc.py` | Muse | in review | PR on `muse/claude-3-oc-tooling`: `scripts/poseidon_oc.py` CLI (dry-run default, `--execute` to run) + sh/ps1 wrappers; only named profiles apply, sweep points excluded; core offset is a printed manual step, never claimed set; reset = -rgc/-rmc/-pm 0 |
| GEMINI-1 | Short summary of `docs/AUDIT` material in OysterRig relevant to 3090-only design (one page max) | Gemini | queued | Small one-off, free-tier sized |
| HERMES-1 | Rig recon + first hardware benches: SRBMiner v3.8.4 + OneZeroMiner baselines per `docs/BENCH.md` on her 3090 | Hermes | queued | Kyle resumed Hermes for Poseidon on 2026-11-26; packet: `council/feed/HERMES_NEXT_FEED.md`, start prompt: `council/feed/HERMES_START_PROMPT.md` |

## Standing order — daily improvement (Kyle, 2026-11-26)
Higher hashrate, lower power draw, everything better, improved daily. The
target below is a floor, not a ceiling; every verified bench updates the
scoreboard and names the next tuning step.

## Scoreboard
- Target: ≥125 TH/s @ ≤320 W pool-side, after the 2% fee, on Kyle's OC (≥391 GH/W).
- Verified Poseidon hashrate: **none yet — no claim.**
- Baselines measured: none yet (HERMES-1).
