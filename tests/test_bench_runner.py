"""Tests for scripts/poseidon_bench.py — the BENCH.md bench runner.

CPU-only: parsing, summary math, share extraction, record format, and
the CLI dry-run (which must launch nothing).
"""

import datetime as dt
import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
spec = importlib.util.spec_from_file_location("poseidon_bench", SCRIPTS / "poseidon_bench.py")
bench = importlib.util.module_from_spec(spec)
sys.modules["poseidon_bench"] = bench
spec.loader.exec_module(bench)


class TestSmiParsing(unittest.TestCase):
    def test_parses_watts_and_temp(self):
        self.assertEqual(bench.parse_smi_line("318.42, 67"), (318.42, 67.0))

    def test_rejects_garbage(self):
        self.assertIsNone(bench.parse_smi_line("N/A"))
        self.assertIsNone(bench.parse_smi_line(""))
        self.assertIsNone(bench.parse_smi_line("only-one-field"))


class TestSummary(unittest.TestCase):
    def test_empty_is_all_none(self):
        s = bench.summarize_samples([])
        self.assertEqual(s.count, 0)
        self.assertIsNone(s.avg_watts)

    def test_averages_and_maxes(self):
        s = bench.summarize_samples([(300.0, 60.0), (320.0, 70.0), (310.0, 65.0)])
        self.assertEqual(s.count, 3)
        self.assertAlmostEqual(s.avg_watts, 310.0)
        self.assertEqual(s.max_watts, 320.0)
        self.assertAlmostEqual(s.avg_temp_c, 65.0)
        self.assertEqual(s.max_temp_c, 70.0)


class TestShareParsing(unittest.TestCase):
    def test_last_cumulative_count_wins(self):
        text = (
            "Shares: accepted 12 rejected 1\n"
            "some other line\n"
            "Shares: accepted 47 rejected 2 stale 3\n"
        )
        counts = bench.parse_share_counts(text)
        self.assertEqual(counts["accepted"], 47)
        self.assertEqual(counts["rejected"], 2)
        self.assertEqual(counts["stale"], 3)

    def test_unmentioned_class_is_none_not_zero(self):
        counts = bench.parse_share_counts("accepted: 5")
        self.assertEqual(counts["accepted"], 5)
        self.assertIsNone(counts["rejected"])
        self.assertIsNone(counts["stale"])


class TestRecordFormat(unittest.TestCase):
    def _result(self, pool_side):
        return bench.BenchResult(
            miner_name="SRBMiner-Multi v3.8.4",
            command="./SRBMiner-MULTI --algorithm pearlhash",
            started=dt.datetime(2026, 11, 26, 12, 0, tzinfo=dt.timezone.utc),
            duration_s=1800.0,
            pool_side_ths=pool_side,
            summary=bench.summarize_samples([(320.0, 65.0)] * 10),
            shares={"accepted": 100, "rejected": 1, "stale": 2},
            oc_applied=True,
        )

    def test_record_has_scoreboard_fields(self):
        rec = bench.format_record(self._result(125.0), "samples.csv")
        self.assertIn("Pool-side hashrate: 125.0 TH/s", rec)
        self.assertIn("Average power", rec)
        # 125 TH/s over 320 W = 390.6 GH/W
        self.assertIn("390.6 GH/W", rec)
        self.assertIn("samples.csv", rec)

    def test_missing_pool_side_is_pending_never_invented(self):
        rec = bench.format_record(self._result(None), "samples.csv")
        self.assertIn("PENDING", rec)
        self.assertIn("Efficiency (pool-side / avg power): n/a", rec)


class TestDryRun(unittest.TestCase):
    def test_dry_run_launches_nothing(self):
        rc = bench.main([
            "--miner-name", "Poseidon 3090",
            "--cmd", "echo should-not-run-and-would-fail-anyway --definitely-not-a-flag",
            "--duration-min", "30",
            "--dry-run",
        ])
        self.assertEqual(rc, 0)

    def test_slugify(self):
        self.assertEqual(bench.slugify("SRBMiner-Multi v3.8.4"), "srbminer-multi-v3-8-4")
        self.assertEqual(bench.slugify("  "), "miner")


if __name__ == "__main__":
    unittest.main()
