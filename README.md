# Poseidon 3090

**The best Pearl mining software — built for one coin and one card: Pearl (PRL) on the NVIDIA RTX 3090.**

Poseidon 3090 is a Pearl-only miner, tuned from scratch for Ampere sm_86.
No multi-algo bloat, no ported-from-another-card kernels, no hidden fees.
Every design decision serves one scoreboard: **pool-accepted hashrate per watt
on an RTX 3090, measured back-to-back against the incumbents.**

- **Coin:** Pearl (PRL) only — algorithm: pearlhash (cuPOW, verifiable matrix multiplication)
- **GPU:** NVIDIA RTX 3090 (sm_86, Ampere, 24 GB GDDR6X) — the only target
- **Rivals to beat:** SRBMiner-Multi, OneZeroMiner, lolMiner, WildRig Multi, PeakMiner, PearlVolt
- **Dev fee:** 2% — the standard miner dev-fee mechanism, the same way it
  works in SRBMiner-Multi, OneZeroMiner, lolMiner and WildRig: Poseidon
  periodically switches to the dev pool and mines to the dev wallet for 2% of
  the time, then switches back to your pool and wallet. Announced in the log
  and stats whenever a fee round is active, and skipped (never blocking your
  mining) if the dev pool is unreachable.
  Paid to `prl1pvrhfx8g8dpqcj3pp9782ykf8gyff4qwhzz7mfvn4udcelwt858hqsa0l32`. No hidden fee, ever.

## The bar (public figures, targets — not claims)

| Miner | RTX 3090 pearlhash | Notes |
|---|---|---|
| PeakMiner v2.5.0 | 121.8 TH/s @ 348 W (350 GH/W) | Pool-accepted, default OC |
| PeakMiner v1.0.12 sweep | 126.5 TH/s @ 388 W | Pool-accepted |
| SRBMiner-Multi v3.8.4 | baseline rival build | Named baseline for all A/B benches; skip v3.8.2 (pearlhash flaw, fixed in v3.8.3) |
| OneZeroMiner | to be measured | Rival sweep is board task GROK-1 |

**Poseidon target, on Kyle's OC profile: ≥125 TH/s at ≤320 W → ≥391 GH/W,
pool-side, after fee.** That is a target, not a claim. No hashrate is claimed
for Poseidon until a pool-side A/B run on a real 3090 is published raw —
see [`docs/BENCH.md`](docs/BENCH.md).

Kyle's RTX 3090 profile (production settings): core lock 1600 MHz,
core offset +200 MHz, memory floor lock 810 MHz — with a second bench arm
testing a 405 MHz memory lock, judged pool-side on whole-rig power.

## Status — honest, v0.0 bootstrap (2026-11-26)

- ✅ Repo founded, mission and bench protocol set, team board live ([`council/board.md`](council/board.md))
- ✅ Miner framework: stratum core (with stale-share accounting), autotune selection, telemetry API, GPU backend interface — unit-tested
- ✅ Project website: https://kshot3000.github.io/Poseidon-3090/
- ✅ 3090 OC profiles + efficiency math, unit-tested (`src/poseidon3090/oc.py`)
- 🚧 CUDA pearlhash kernel (sm_86 tensor-core GEMM + fused sparse prep): designed, not yet compiled
- 🚧 Stratum networking (sockets), job loop, CLI: to be built on the framework, to [`docs/SPEC.md`](docs/SPEC.md)
- ⛔ No hashrate claimed. No binary released. The bench decides everything.

## Quick start (core, today)

```bash
python3 -m unittest discover tests   # OC profile + efficiency tests
```

Mining quick start lands with the first CUDA build.

## How this repo is built

A multi-agent team works this repo on scheduled workloads, coordinated on
[`council/board.md`](council/board.md): Muse (lead, kernel architecture,
review and merge), Sol (verification), the Grok swarm (research sweeps,
docs, QA volume), and Gemini (small general tasks). Hardware benches run on
Kyle's 3090. All public-facing work is Kyle's, in his voice. See
[`council/collaboration.md`](council/collaboration.md) for the rules every
seat follows — claim first, one task per PR, never push main, honest claims
only, and a personal-info scan on every bot PR.

Related: [OysterRig](https://github.com/Kshot3000/OysterRig) is Kyle's
Blackwell-first Pearl miner; Poseidon is its Ampere sibling, specialised
purely for the 3090. Pearl research (Nacre kernel work) lives in
[Oysters4All](https://github.com/Kshot3000/Oysters4All).

## Attribution

Built by Kyle Cox — [@kshot9000](https://x.com/kshot9000) ·
GitHub [@Kshot3000](https://github.com/Kshot3000)
Pearl team: [@pearl-research-labs](https://github.com/pearl-research-labs)

Dev fee: **2%**, paid to (PRL):
`prl1pvrhfx8g8dpqcj3pp9782ykf8gyff4qwhzz7mfvn4udcelwt858hqsa0l32`

Tips / donations (PRL):
`prl1p62v09vuzyd8kdz9l23jaf3kph4wwx6jqcmhkkhg8lhr2qlxky8psu3zw9d`

## License

MIT — see [`LICENSE`](LICENSE).
