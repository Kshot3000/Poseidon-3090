import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from poseidon3090.oc import (KYLE_3090, KYLE_3090_MEM405, SWEEP_3090,
                             TARGET_3090_THS, TARGET_3090_WATTS, TARGET_3090_GH_PER_W)


class TestOcProfiles(unittest.TestCase):
    def test_kyle_profile_matches_production_settings(self):
        self.assertEqual(KYLE_3090.lock_core_mhz, 1600)
        self.assertEqual(KYLE_3090.core_offset_mhz, 200)
        self.assertEqual(KYLE_3090.lock_mem_mhz, 810)
        self.assertEqual(KYLE_3090.arch, "sm_86")

    def test_mem405_arm_differs_only_in_memory(self):
        self.assertEqual(KYLE_3090_MEM405.lock_mem_mhz, 405)
        self.assertEqual(KYLE_3090_MEM405.lock_core_mhz, KYLE_3090.lock_core_mhz)
        self.assertEqual(KYLE_3090_MEM405.core_offset_mhz, KYLE_3090.core_offset_mhz)

    def test_all_profiles_validate(self):
        for p in [KYLE_3090, KYLE_3090_MEM405, *SWEEP_3090]:
            p.validate()

    def test_sweep_centres_on_kyle_point(self):
        points = [(p.lock_core_mhz, p.core_offset_mhz) for p in SWEEP_3090]
        self.assertIn((1600, 200), points)
        self.assertTrue(all(p.lock_mem_mhz == 810 for p in SWEEP_3090))

    def test_nvidia_smi_commands(self):
        cmds = KYLE_3090.nvidia_smi_linux(0)
        self.assertTrue(any("-lgc 1600,1600" in c for c in cmds))
        self.assertTrue(any("-lmc 810,810" in c for c in cmds))

    def test_efficiency_math(self):
        self.assertAlmostEqual(KYLE_3090.gh_per_w(125.0, 320.0), 390.625)
        self.assertEqual(KYLE_3090.gh_per_w(125.0, 0), 0.0)

    def test_targets_beat_public_bar(self):
        # PeakMiner public bar: 121.8 TH/s @ 348 W = 350 GH/W
        self.assertGreater(TARGET_3090_THS, 121.8)
        self.assertLess(TARGET_3090_WATTS, 348.0)
        self.assertGreater(TARGET_3090_GH_PER_W, 350.0)


if __name__ == "__main__":
    unittest.main()
