import os
import subprocess
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from poseidon3090.oc import KYLE_3090, KYLE_3090_MEM405, PROFILES, SWEEP_3090  # noqa: E402
import poseidon_oc  # noqa: E402


class TestResetCommands(unittest.TestCase):
    def test_reset_releases_both_locks_and_persistence(self):
        cmds = KYLE_3090.reset_nvidia_smi(0)
        self.assertTrue(any(c.endswith("-rgc") for c in cmds))
        self.assertTrue(any(c.endswith("-rmc") for c in cmds))
        self.assertTrue(any("-pm 0" in c for c in cmds))

    def test_reset_targets_the_requested_device(self):
        self.assertTrue(all("-i 2" in c for c in KYLE_3090.reset_nvidia_smi(2)))


class TestProfileRegistry(unittest.TestCase):
    def test_only_reviewed_profiles_are_applicable(self):
        self.assertEqual(set(PROFILES), {KYLE_3090.name, KYLE_3090_MEM405.name})

    def test_sweep_points_are_not_applicable_by_name(self):
        for p in SWEEP_3090:
            self.assertNotIn(p.name, PROFILES)


class TestToolingCli(unittest.TestCase):
    def run_cli(self, *argv):
        return subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "poseidon_oc.py"), *argv],
            capture_output=True, text=True)

    def test_apply_is_dry_run_by_default_and_matches_profile(self):
        r = self.run_cli("apply")
        self.assertEqual(r.returncode, 0)
        self.assertIn("DRY  nvidia-smi -i 0 -lgc 1600,1600", r.stdout)
        self.assertIn("DRY  nvidia-smi -i 0 -lmc 810,810", r.stdout)
        self.assertIn("Dry run only", r.stdout)

    def test_apply_never_claims_the_offset_was_set(self):
        r = self.run_cli("apply")
        self.assertIn("MANUAL STEP: core offset +200 MHz is not set", r.stdout)

    def test_mem405_arm_applies_405_lock(self):
        r = self.run_cli("apply", "--profile", "kyle-3090-mem405")
        self.assertIn("-lmc 405,405", r.stdout)

    def test_unknown_profile_is_rejected(self):
        r = self.run_cli("apply", "--profile", "sweep-c1600o200")
        self.assertNotEqual(r.returncode, 0)

    def test_reset_is_dry_run_by_default(self):
        r = self.run_cli("reset")
        self.assertEqual(r.returncode, 0)
        self.assertIn("-rgc", r.stdout)
        self.assertIn("-rmc", r.stdout)

    def test_list_names_both_arms(self):
        r = self.run_cli("list")
        self.assertIn("kyle-3090-efficiency", r.stdout)
        self.assertIn("kyle-3090-mem405", r.stdout)


class TestWrappers(unittest.TestCase):
    def test_all_four_wrappers_exist_and_delegate_to_the_cli(self):
        for name in ("oc-apply.sh", "oc-reset.sh", "oc-apply.ps1", "oc-reset.ps1"):
            path = os.path.join(ROOT, "scripts", name)
            self.assertTrue(os.path.isfile(path), name)
            with open(path) as f:
                self.assertIn("poseidon_oc.py", f.read(), name)

    def test_apply_commands_match_profile_on_both_platforms(self):
        self.assertEqual(poseidon_oc.apply_commands(KYLE_3090.name, 0, "linux"),
                         KYLE_3090.nvidia_smi_linux(0))
        self.assertEqual(poseidon_oc.apply_commands(KYLE_3090.name, 0, "win32"),
                         KYLE_3090.nvidia_smi_windows(0))


if __name__ == "__main__":
    unittest.main()
