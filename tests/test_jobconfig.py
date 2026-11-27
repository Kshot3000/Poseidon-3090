"""CLAUDE-8: verifier-bound job configuration validation (SOL-1 finding 2)."""
import unittest

from poseidon3090 import jobconfig
from poseidon3090.jobconfig import JobConfig, validate_job_config


def valid(**over):
    cfg = dict(m=4096, n=4096, k=2048, rank=128, tile_h=16, tile_w=16)
    cfg.update(over)
    return cfg


class TestValidConfigs(unittest.TestCase):
    def test_penalized_rank_128(self):
        cfg = validate_job_config(**valid(rank_penalized=True))
        self.assertIsInstance(cfg, JobConfig)

    def test_signal_value_64_is_valid(self):
        # SOL-1: the reference generator's default range includes 64,
        # which the prototype oracle rejects for A/B entries.
        validate_job_config(**valid(signal_min=-64, signal_max=64))

    def test_rank_bounds(self):
        validate_job_config(**valid(rank=32, k=1024))
        validate_job_config(**valid(rank=1024, k=16384))
        validate_job_config(**valid(rank=256, k=4096))

    def test_k_at_verifier_cap(self):
        validate_job_config(**valid(rank=128, k=65536))

    def test_tile_entry_bounds(self):
        validate_job_config(**valid(tile_h=4, tile_w=8))     # 32 entries
        validate_job_config(**valid(tile_h=16, tile_w=16))   # 256 entries

    def test_dot_product_bound_fits_int32(self):
        self.assertEqual(jobconfig.dot_product_bound(1 << 16), 1 << 30)
        self.assertLess(jobconfig.dot_product_bound(1 << 16),
                        jobconfig.INT32_LIMIT)


class TestRejectedConfigs(unittest.TestCase):
    def assert_bad(self, **over):
        with self.assertRaises(ValueError):
            validate_job_config(**valid(**over))

    def test_k_above_verifier_cap(self):
        # The prototype oracle accepts k up to 2^20; the verifier caps 2^16.
        self.assert_bad(rank=1024, k=1 << 17)

    def test_k_not_divisible_by_64(self):
        self.assert_bad(k=2112 - 32)

    def test_k_below_floor(self):
        self.assert_bad(k=1024)            # rank 128 floor is 16*r = 2048
        self.assert_bad(rank=32, k=512)    # absolute floor is 1024

    def test_k_above_rank_cap(self):
        self.assert_bad(rank=32, k=8192)   # 4*r^2 = 4096

    def test_rank_not_power_of_two(self):
        self.assert_bad(rank=96, k=1536)

    def test_rank_out_of_range(self):
        self.assert_bad(rank=16, k=1024)
        self.assert_bad(rank=2048, k=16384)

    def test_penalized_rank_below_128(self):
        self.assert_bad(rank=64, k=1024, rank_penalized=True)

    def test_dim_above_cap(self):
        self.assert_bad(m=(1 << 24) + 1)
        self.assert_bad(n=0)

    def test_tile_odd_dimension(self):
        self.assert_bad(tile_h=15)

    def test_tile_entry_count(self):
        self.assert_bad(tile_h=4, tile_w=4)     # 16 < 32
        self.assert_bad(tile_h=32, tile_w=16)   # 512 > 256

    def test_tile_must_fit_matrices(self):
        self.assert_bad(m=8, tile_h=16)

    def test_signal_range_outside_generated_range(self):
        self.assert_bad(signal_max=65)
        self.assert_bad(signal_min=-65)
        self.assert_bad(signal_min=10, signal_max=-10)


if __name__ == "__main__":
    unittest.main()
