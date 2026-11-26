import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from poseidon3090 import stratum, tune, stats, gpu


class TestStratum(unittest.TestCase):
    def test_roundtrip_request(self):
        line = stratum.build_request(1, "mining.subscribe", ["poseidon/0.0.1"])
        msg = stratum.parse_message(line)
        self.assertEqual(msg["method"], "mining.subscribe")

    def test_parse_rejects_garbage(self):
        with self.assertRaises(ValueError):
            stratum.parse_message('{"foo": 1}')

    def test_wallet_validation(self):
        self.assertTrue(stratum.validate_prl_wallet(
            "prl1pvrhfx8g8dpqcj3pp9782ykf8gyff4qwhzz7mfvn4udcelwt858hqsa0l32"))
        with self.assertRaises(ValueError):
            stratum.validate_prl_wallet("bc1qnotapearlwallet")

    def test_job_from_notify(self):
        job = stratum.Job.from_notify(["abc123", "deadbeef", True], difficulty=8.0)
        self.assertEqual(job.job_id, "abc123")
        self.assertEqual(job.difficulty, 8.0)
        with self.assertRaises(ValueError):
            stratum.Job.from_notify([])

    def test_share_tracker_counts_stale_separately(self):
        tr = stratum.ShareTracker()
        tr.on_new_job("j1")
        self.assertEqual(tr.record_submit("j1", True), "accepted")
        tr.on_new_job("j2")
        self.assertEqual(tr.record_submit("j1", True), "stale")
        self.assertEqual(tr.record_submit("j2", False), "rejected")
        self.assertEqual((tr.accepted, tr.stale, tr.rejected), (1, 1, 1))
        self.assertAlmostEqual(tr.stale_pct, 100 / 3)

    def test_pool_failover_wraps(self):
        pools = stratum.PoolSet(["a:1", "b:2"])
        self.assertEqual(pools.failover(), "b:2")
        self.assertEqual(pools.failover(), "a:1")


class TestTune(unittest.TestCase):
    def test_pick_best_prefers_efficiency_within_floor(self):
        profiles = [tune.Profile("fast-hungry", 64, 2, 390, 126.0),
                    tune.Profile("fast-eco", 64, 2, 320, 124.0),
                    tune.Profile("slow-eco", 64, 2, 250, 100.0)]
        # slow-eco is most efficient per watt but below the 97% TH/s floor.
        self.assertEqual(tune.pick_best(profiles).name, "fast-eco")

    def test_candidates_are_sm86_only(self):
        self.assertEqual(list(tune.CANDIDATES.keys()), ["sm_86"])

    def test_pick_best_empty_raises(self):
        with self.assertRaises(ValueError):
            tune.pick_best([])


class TestStats(unittest.TestCase):
    def test_api_shape_and_fee(self):
        fleet = stats.FleetStats(gpus=[stats.GpuStats(
            name="RTX 3090", ths=100.0, power_w=300.0, temp_c=62.0,
            accepted=97, rejected=2, stale=1)], uptime_s=60, fee_active=True)
        api = fleet.to_api()
        self.assertEqual(api["miner"], "poseidon-3090")
        self.assertEqual(api["fee_fraction"], 0.02)
        self.assertEqual(api["gpus"][0]["gh_per_w"], 333.3)
        self.assertEqual(api["gpus"][0]["stale_pct"], 1.0)


class TestGpuStub(unittest.TestCase):
    def test_stub_is_honest(self):
        with self.assertRaises(gpu.GpuUnavailable):
            gpu.list_devices()


if __name__ == "__main__":
    unittest.main()
