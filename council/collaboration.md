# Collaboration — how the team works Poseidon 3090

Repo: https://github.com/Kshot3000/Poseidon-3090
Mission: the best Pearl mining software in the field, purely for Pearl on the
RTX 3090 — better than SRBMiner-Multi, OneZeroMiner, lolMiner, PeakMiner, WildRig Multi
and PearlVolt on pool-accepted GH/W, measured by `docs/BENCH.md`.

## Seats and lanes
- **Muse** — lead: kernel architecture, specs, task packets, review and
  merge, the scheduled loop that keeps the board moving.
- **Sol (ChatGPT)** — verifier: pearlhash/cuPOW math and spec accuracy,
  kernel-design review, second pair of eyes on every performance claim.
- **Grok swarm** — volume: rival research sweeps, autotune tables, docs,
  tests/QA, small tools built to spec.
- **Gemini (free tier)** — small general one-offs only: a summary, a short
  draft, a single lookup. Nothing long, nothing load-bearing.
- **Hermes (local seat)** — PAUSED by Kyle's order 2026-11-24 (all local work,
  until he personally resumes her). Do not feed her tasks. Hardware benches
  are Kyle-run until then.
- **Kyle** — owner: hardware, accounts, money/legal, final calls. All
  public-facing work is in his first-person voice, as a solo developer with
  his team behind the scenes.

## Rules every seat follows
1. Claim a task on `council/board.md` before starting it. One task per PR.
2. Branches: `muse/<slug>`, `sol/<slug>`, `grok/<task-id>-<slug>`,
   `gemini/<slug>`. PR titles for the swarm start `Grok:`.
3. Never push directly to main (the founding bootstrap commit is the only
   exception). Everything lands by PR; Muse merges after a clean review.
4. **Honest claims only.** No hashrate/efficiency claim without a BENCH.md
   run behind it. Targets are labelled targets. Never quote a test count no
   tool result in your run actually showed.
5. **Personal-info scan:** every bot PR diff is scanned for Kyle's personal
   information (home address, phone, personal email, IDs) before merge.
   Any hit is a red alert: no merge, flag it on the board.
6. **Money surfaces are character-exact and Kyle-only to change:**
   dev fee **2%** (standard time-sliced dev-pool mechanism, as in SRBMiner/OneZeroMiner/lolMiner/WildRig) to `prl1pvrhfx8g8dpqcj3pp9782ykf8gyff4qwhzz7mfvn4udcelwt858hqsa0l32`.
   Any diff touching the fee fraction or address is held for Kyle.
7. Rebase on latest main before opening a PR. Verify tests on the exact tree
   you submit.
8. Attribution wherever it appears: Kyle Cox — @kshot9000 (X and GitHub).
