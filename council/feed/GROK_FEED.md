# Grok swarm feed — Poseidon 3090

Rules are in `council/collaboration.md`. Claim on the board first, branch
`grok/<task-id>-<slug>`, PR title starts `Grok:`, one task per PR, rebase on
latest main, no personal information in any diff, honest sourced numbers only.

## Wave 1
### GROK-1 — Rival sweep (3090 / Pearl)
Research and write `docs/RIVALS.md`:
- For each of OneZeroMiner, SRBMiner-Multi, lolMiner, PeakMiner, WildRig Multi,
  PearlVolt: current version (as of your run, with the date), Pearl/pearlhash
  support, dev fee for pearlhash, and every published RTX 3090 pearlhash
  figure you can find — labelled **claimed** (vendor) vs **pool-accepted**
  (third-party/pool) with a source link for each.
- Pin the exact OneZeroMiner and SRBMiner builds Poseidon must A/B against
  (SRBMiner baseline is v3.8.4; note v3.8.2's pearlhash flaw and the 405 MHz
  memory-lock option in v3.8.4).
- End with the single table that updates the scoreboard in `docs/SPEC.md`.
Acceptance: every number sourced; no unsourced hashrate anywhere; fees
verified against the miner's own docs/release notes.
