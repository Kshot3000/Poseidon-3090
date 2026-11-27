# Poseidon 3090 — Board

Status key: `queued` · `claimed` · `in progress` · `in review` · `done` · `blocked` · `paused`

| ID | Task | Seat | Status | Notes |
|---|---|---|---|---|
| POSEIDON-1 | Project website: GitHub Pages site in `site/` (scoreboard, fee transparency, honest status) + Pages workflow | Muse | done | 2026-11-26, Kyle's order; live at https://kshot3000.github.io/Poseidon-3090/ |
| CLAUDE-6 | Miner runtime integration: wire stratum client + fee slicer + telemetry into one runnable host loop against the `gpu.py` backend stub, with a fake-pool end-to-end test (local stratum fixture) proving job → work → share flow and the 2% fee switch | Muse | queued | Kyle's constant-improvement order 2026-11-26; builds only on merged main code, independent of PRs #3/#4 |
| CLAUDE-7 | Bench runner: one-command BENCH.md execution — apply OC profile, launch a miner, sample power, capture the pool-side window, emit the bench record in BENCH.md format — so Hermes' rival baselines and every future Poseidon bench are reproducible | Muse | in review | Kyle's constant-improvement order 2026-11-26; must work for SRBMiner/OneZeroMiner command lines as well as Poseidon's |
| CLAUDE-5 | Site v4: uploaded single-file design (underwater canvas, rig simulator, flight-sheet generator) fixed into compliance and shipped | Muse | done | Uploaded by Kyle as a zip 2026-11-26; as-uploaded it failed audit (0.65% fee, fee address missing + fake wallet default, invented 142.8 MH/s / +14.6% / 55 W claims, fake v3.9.2 releases, fake live telemetry, Ada/Blackwell scope). Kyle chose 'fix into compliance and ship as v4'. Fixes: fee 2% + real address section, all numbers converted to the public targets (125 TH/s / 320 W / 0.391 TH/s/W), simulator = target projection (efficiency + power cost; price/profit removed), terminal + configurator labelled SIMULATION/PREVIEW, releases rewritten honest, 3090-only, v3 statue hero + gold flakes + Ocean Floor carried over. Headless QA verified sim math (6 GPUs = 750 TH/s, $4.61/day power) and fee address in DOM; PR #9 merged 2026-11-26, Pages deploy succeeded, live site verified (fee address present, zero banned strings) |
| CLAUDE-4 | Site v3: living-sea redesign — Poseidon digital statue hero (generated art, site/assets/poseidon-statue.webp), animated flowing-water background + drifting gold-flake canvas, Ocean Floor section with oysters and glowing pearls | Muse | done | Kyle's order 2026-11-26 ("more like a live Poseidon digital statue kinda like Athena"); built on Gemini's v2, all v2 claims/fee content preserved; headless QA passed; PR #7 merged 2026-11-26, Pages deploy succeeded, live site + statue asset verified serving v3 |
| GEMINI-2 | Site v2 design: full redesign of `site/index.html` (nav, telemetry hero, rig-scaling estimator, roadmap) | Gemini | done | Delivered by Kyle as a zip 2026-11-26; Muse audit clean (fee address exact, targets labelled, no invented rival numbers, PII clean, estimator math verified); integrated on `gemini/site-v2` with fee-mechanism wording corrected to the standard time-sliced description + kshot.tech footer link; PR #5 merged 2026-11-26, Pages deploy succeeded, live site verified serving v2 |
| POSEIDON-0 | Repo bootstrap: README, SPEC, BENCH, council, OC + fee core, tests | Muse | done | 2026-11-26, founding commit |
| GROK-1 | Rival sweep: current Pearl builds + published 3090 figures for OneZeroMiner, SRBMiner-Multi v3.8.4, lolMiner, PeakMiner, WildRig Multi, PearlVolt — versions, fees, claimed vs pool-accepted numbers, sources | Grok | queued | Packet: `council/feed/GROK_FEED.md` wave 1 |
| SOL-1 | Verify pearlhash/cuPOW spec accuracy in `docs/SPEC.md`; review sm_86 kernel design (tile, launch bounds, async job switch) and flag anything that would not beat the incumbents | Sol | queued | Packet: `council/feed/SOL_FEED.md` |
| CLAUDE-1 | CUDA kernel skeleton: sm_86 build harness (nvcc), GEMM stage interface, CPU math oracle tests ported from Nacre research | Muse | done | PR on `muse/claude-1-kernel-skeleton`: oracle pins the Nacre identity (AP/BP/U/V + recovery, V-from-B negative control); CUDA still DESIGNED, NOT COMPILED — first compile gate is Hermes' 3090 via `scripts/build-kernel.sh` |
| CLAUDE-2 | Stratum client core: Pearl pool messages, failover, share accounting — unit-tested, following the OysterRig pattern | Muse | done | 2026-11-26 framework PR: stratum.py + tune.py + stats.py + gpu.py stub, tests 22/22 |
| CLAUDE-3 | OC tooling: apply/reset scripts for the 3090 profiles (Linux + Windows), from `src/poseidon3090/oc.py` | Muse | done | PR on `muse/claude-3-oc-tooling`: `scripts/poseidon_oc.py` CLI (dry-run default, `--execute` to run) + sh/ps1 wrappers; only named profiles apply, sweep points excluded; core offset is a printed manual step, never claimed set; reset = -rgc/-rmc/-pm 0 |
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
