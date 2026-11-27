#!/usr/bin/env python3
"""Poseidon 3090 bench runner — one-command execution of docs/BENCH.md.

Runs any miner (SRBMiner-Multi, OneZeroMiner, Poseidon itself) under the
bench protocol and emits the bench record BENCH.md requires:

  * optional OC apply/reset via scripts/oc-apply.sh / oc-reset.sh
    (only with --apply-oc; the +200 core offset stays a manual step,
    exactly as the OC tooling states)
  * the miner process for an equal, fixed window (default 30 min)
  * nvidia-smi power/temp sampling every 5 s for the whole window
  * pool-side TH/s entered from the pool dashboard (--pool-side-ths);
    without it the record is emitted with the field marked PENDING —
    pool-side numbers are the scoreboard, so the runner never invents
    or substitutes a GPU-side reading for them
  * share counts parsed best-effort from the miner's own output and
    labelled miner-reported (diagnostics, not the scoreboard)

Output: docs/benches/<YYYY-MM-DD>-<miner-slug>.md plus the raw power
samples CSV next to it, as BENCH.md requires raw evidence attached.

Usage:
  python3 scripts/poseidon_bench.py \
      --miner-name "SRBMiner-Multi v3.8.4" \
      --cmd "./SRBMiner-MULTI --algorithm pearlhash --pool <pool> --wallet <wallet>" \
      --duration-min 30 --apply-oc --pool-side-ths 118.4

  --dry-run prints the plan and launches nothing.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import io
import re
import shlex
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_INTERVAL_S = 5  # BENCH.md: nvidia-smi, 5 s sampling


# ---------------------------------------------------------------- parsing

def parse_smi_line(line: str) -> tuple[float, float] | None:
    """Parse one `nvidia-smi --query-gpu=power.draw,temperature.gpu
    --format=csv,noheader,nounits` line into (watts, temp_c)."""
    parts = [p.strip() for p in line.split(",")]
    if len(parts) != 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None


@dataclass
class SampleSummary:
    count: int = 0
    avg_watts: float | None = None
    max_watts: float | None = None
    avg_temp_c: float | None = None
    max_temp_c: float | None = None


def summarize_samples(samples: list[tuple[float, float]]) -> SampleSummary:
    if not samples:
        return SampleSummary()
    watts = [s[0] for s in samples]
    temps = [s[1] for s in samples]
    return SampleSummary(
        count=len(samples),
        avg_watts=sum(watts) / len(watts),
        max_watts=max(watts),
        avg_temp_c=sum(temps) / len(temps),
        max_temp_c=max(temps),
    )


_SHARE_PATTERNS = {
    "accepted": re.compile(r"accepted[^\d]{0,24}(\d+)", re.IGNORECASE),
    "rejected": re.compile(r"rejected[^\d]{0,24}(\d+)", re.IGNORECASE),
    "stale": re.compile(r"stale[^\d]{0,24}(\d+)", re.IGNORECASE),
}


def parse_share_counts(text: str) -> dict[str, int | None]:
    """Best-effort share totals from miner output: the LAST number seen
    for each class wins (miners print cumulative counters). Returns None
    for a class the output never mentions — unknown, not zero."""
    counts: dict[str, int | None] = {}
    for name, pat in _SHARE_PATTERNS.items():
        found = pat.findall(text)
        counts[name] = int(found[-1]) if found else None
    return counts


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "miner"


# ---------------------------------------------------------------- record

@dataclass
class BenchResult:
    miner_name: str
    command: str
    started: _dt.datetime
    duration_s: float
    pool_side_ths: float | None
    summary: SampleSummary
    shares: dict[str, int | None] = field(
        default_factory=lambda: {"accepted": None, "rejected": None, "stale": None}
    )
    oc_applied: bool = False
    notes: str = ""


def _fmt(value: float | None, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def format_record(r: BenchResult, samples_csv_name: str) -> str:
    pool = (
        f"{r.pool_side_ths:.1f} TH/s"
        if r.pool_side_ths is not None
        else "PENDING — read from the pool dashboard for this exact window and fill in before publishing"
    )
    eff = None
    if r.pool_side_ths is not None and r.summary.avg_watts:
        eff = r.pool_side_ths * 1000.0 / r.summary.avg_watts  # GH/W
    shares = r.shares
    return f"""# Bench record — {r.miner_name}

- Date: {r.started.strftime('%Y-%m-%d %H:%M %Z')}
- Miner: {r.miner_name}
- Command: `{r.command}`
- Window: {r.duration_s / 60.0:.1f} min ({r.duration_s:.0f} s)
- OC profile applied by runner: {"yes (scripts/oc-apply.sh --execute; +200 core offset is manual)" if r.oc_applied else "no"}

## Scoreboard (pool-side is the truth)

- Pool-side hashrate: {pool}
- Average power (nvidia-smi, 5 s sampling, {r.summary.count} samples): {_fmt(r.summary.avg_watts)} W
- Efficiency (pool-side / avg power): {_fmt(eff)} GH/W

## Diagnostics (miner/GPU-side, not the scoreboard)

- Max power: {_fmt(r.summary.max_watts)} W
- GPU temp avg / max: {_fmt(r.summary.avg_temp_c)} °C / {_fmt(r.summary.max_temp_c)} °C
- Shares, miner-reported — accepted: {shares['accepted'] if shares['accepted'] is not None else 'n/a'}, rejected: {shares['rejected'] if shares['rejected'] is not None else 'n/a'}, stale: {shares['stale'] if shares['stale'] is not None else 'n/a'}

## Evidence

- Raw power samples: `{samples_csv_name}`
{r.notes}
"""


# ---------------------------------------------------------------- runner

class PowerSampler:
    """Samples nvidia-smi on an interval from a daemon thread. Missing
    nvidia-smi yields zero samples — the record then says n/a rather
    than guessing."""

    def __init__(self, interval_s: int = SAMPLE_INTERVAL_S):
        self.interval_s = interval_s
        self.samples: list[tuple[float, float]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _sample_once(self) -> None:
        try:
            out = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=power.draw,temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return
        for line in out.stdout.splitlines():
            parsed = parse_smi_line(line)
            if parsed is not None:
                self.samples.append(parsed)
                break  # single-GPU bench card

    def start(self) -> None:
        def loop() -> None:
            while not self._stop.is_set():
                self._sample_once()
                self._stop.wait(self.interval_s)

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=15)


def _run_oc_script(name: str) -> bool:
    script = REPO_ROOT / "scripts" / name
    if not script.exists():
        print(f"warning: {script} not found; OC step skipped", file=sys.stderr)
        return False
    proc = subprocess.run(["bash", str(script), "--execute"])
    return proc.returncode == 0


def run_bench(args: argparse.Namespace) -> int:
    started = _dt.datetime.now().astimezone()
    duration_s = args.duration_min * 60

    if args.dry_run:
        print("DRY RUN — plan only, nothing launched:")
        print(f"  miner:    {args.miner_name}")
        print(f"  command:  {args.cmd}")
        print(f"  window:   {args.duration_min} min")
        print(f"  OC apply: {'yes' if args.apply_oc else 'no'}")
        print(f"  record:   docs/benches/{started.strftime('%Y-%m-%d')}-{slugify(args.miner_name)}.md")
        return 0

    oc_applied = False
    if args.apply_oc:
        oc_applied = _run_oc_script("oc-apply.sh")

    sampler = PowerSampler()
    output = io.StringIO()
    proc: subprocess.Popen | None = None
    t0 = time.monotonic()
    try:
        sampler.start()
        proc = subprocess.Popen(
            shlex.split(args.cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert proc.stdout is not None
        # Read until the window ends; the miner is then terminated.
        deadline = t0 + duration_s
        for line in proc.stdout:
            output.write(line)
            sys.stdout.write(line)
            if time.monotonic() >= deadline:
                break
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
        sampler.stop()
        if oc_applied:
            _run_oc_script("oc-reset.sh")

    elapsed = time.monotonic() - t0
    summary = summarize_samples(sampler.samples)
    result = BenchResult(
        miner_name=args.miner_name,
        command=args.cmd,
        started=started,
        duration_s=elapsed,
        pool_side_ths=args.pool_side_ths,
        summary=summary,
        shares=parse_share_counts(output.getvalue()),
        oc_applied=oc_applied,
    )

    out_dir = REPO_ROOT / "docs" / "benches"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{started.strftime('%Y-%m-%d')}-{slugify(args.miner_name)}"
    csv_name = f"{stem}-power.csv"
    with open(out_dir / csv_name, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["watts", "temp_c"])
        writer.writerows(sampler.samples)
    record_path = out_dir / f"{stem}.md"
    record_path.write_text(format_record(result, csv_name))
    print(f"\nBench record written: {record_path}")
    if args.pool_side_ths is None:
        print("Pool-side TH/s is PENDING in the record — fill it from the pool "
              "dashboard for this exact window before publishing, per BENCH.md.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Poseidon 3090 bench runner (docs/BENCH.md)")
    ap.add_argument("--miner-name", required=True, help='e.g. "SRBMiner-Multi v3.8.4"')
    ap.add_argument("--cmd", required=True, help="full miner command line")
    ap.add_argument("--duration-min", type=float, default=30.0,
                    help="bench window in minutes (BENCH.md: 30+; default 30)")
    ap.add_argument("--apply-oc", action="store_true",
                    help="apply the bench OC profile before, reset after")
    ap.add_argument("--pool-side-ths", type=float, default=None,
                    help="pool-side TH/s for the window, read from the pool dashboard")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, launch nothing")
    args = ap.parse_args(argv)
    if args.duration_min <= 0:
        ap.error("--duration-min must be positive")
    return run_bench(args)


if __name__ == "__main__":
    raise SystemExit(main())
