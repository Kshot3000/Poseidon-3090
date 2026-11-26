# Bench protocol — how Poseidon proves it

Every performance claim for Poseidon 3090 comes from this protocol, run on a
real RTX 3090. Nothing else counts.

## Setup
- Card: RTX 3090 (sm_86). Record exact model, driver, CUDA version.
- OC: Kyle's profile — CCLK 1600 lock, COFF +200, MCLK 810 floor lock
  (`src/poseidon3090/oc.py`, `KYLE_3090`). Second arm: MCLK 405 lock
  (SRBMiner v3.8.4 supports it for pearlhash) — judged on whole-rig power.
- Pool: same pool, same account/wallet, for every miner in the run.

## Run
1. Apply the OC profile: `scripts/oc-apply.sh --execute` (Linux) or
   `scripts\oc-apply.ps1 -Execute` (Windows) — dry-run without the flag.
   Set the +200 core offset manually (nvidia-settings / Afterburner);
   the tool prints this step and never claims it was set. Reset after
   the run with `scripts/oc-reset.sh --execute` / `oc-reset.ps1 -Execute`.
2. Baseline: SRBMiner-Multi **v3.8.4**, pearlhash, 30+ minutes.
   Record pool-side TH/s, average watts (nvidia-smi, 5 s sampling), temps.
3. Second baseline: OneZeroMiner (current Pearl build, version recorded).
4. Poseidon: same window length, same pool, same OC.
5. Report: pool-side TH/s, avg watts, GH/W, shares accepted/rejected/stale,
   for every miner — Poseidon included, win or lose.

## Rules
- Pool-side numbers are the scoreboard; GPU-side readings are diagnostics.
- Equal windows. No cherry-picked intervals.
- After-fee numbers for Poseidon (the 2% slice is real, so it counts).
- Raw logs/screenshots are attached to the bench report in `docs/benches/`.
- A result that loses is published too, with the next tuning step it implies.
