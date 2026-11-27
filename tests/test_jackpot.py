"""CLAUDE-9: known-answer fixture for the cumulative Pearl jackpot.

The fixture operands are deterministic patterns (no RNG), so every value
below is reproducible from this file alone. The expected words were frozen
on 2026-11-27 from ``poseidon3090.jackpot``, which is transcribed from the
Pearl reference mining loop (pearl-research-labs/pearl@adbfbbac,
zk-pow/src/v2/mine.rs); before freezing, a second, independent inline
transcription of that loop reproduced all 32 checkpoints exactly. Sol's
verifier lane is asked to cross-check these words against the Rust
reference itself — until then they pin Poseidon's own implementation
against regressions, which is what a fixture is for.

The final keyed-BLAKE3 digest is deliberately NOT pinned here: the repo
is pure-stdlib and stdlib has no BLAKE3. The fixture pins the jackpot
words and their little-endian serialization — the exact 64 bytes the
keyed hash consumes (docs/SPEC.md step 3). Digest + roots + seed modes
are CLAUDE-10.
"""
import unittest

from poseidon3090.jackpot import (
    JACKPOT_SIZE,
    LROT_PER_TILE,
    TileJackpotReducer,
    compute_jackpot,
    xor_reduce_tile,
)

M = N = 4
K, RANK = 1024, 32           # 32 groups: every jackpot word folds twice
A_ROWS, B_COLS = [1, 3], [0, 2]


def fixture_operands():
    ap = [[((i * 31 + l * 7) % 13) - 6 for l in range(K)] for i in range(M)]
    bpt = [[((j * 17 + l * 5) % 11) - 5 for l in range(K)] for j in range(N)]
    return ap, bpt


# Frozen 2026-11-27 (see module docstring for provenance).
CKPT_0 = (0xAF, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
CKPT_1 = (0xAF, 0xF5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
CKPT_15 = (0xAF, 0xF5, 0xEA, 0x65, 0xFFFFFFD5, 0x119, 0xFFFFFFD2, 0x8,
           0x8, 0x92, 0xEF, 0x97, 0x1B, 0xFFFFFFEA, 0x13F, 0xFFFFFF65)
CKPT_16 = (0x15E000, 0xF5, 0xEA, 0x65, 0xFFFFFFD5, 0x119, 0xFFFFFFD2, 0x8,
           0x8, 0x92, 0xEF, 0x97, 0x1B, 0xFFFFFFEA, 0x13F, 0xFFFFFF65)
FINAL = (0x15E000, 0x1EA022, 0x1D4093, 0xFFF35F27, 0xFFFABF47, 0x232059,
         0x5A04E, 0x1011F, 0x100A0, 0x12401C, 0xFFE21FF1, 0x12E089,
         0xFFFC9F06, 0xFFFD5F9C, 0x27E05C, 0x13403C)
FINAL_LE_HEX = ("00e0150022a01e0093401d00275ff3ff47bffaff59202300"
                "4ea005001f010100a00001001c401200f11fe2ff89e01200"
                "069ffcff9c5ffdff5ce027003c401300")


class TestKnownAnswerFixture(unittest.TestCase):
    def setUp(self):
        ap, bpt = fixture_operands()
        self.words, self.ckpts = compute_jackpot(ap, bpt, A_ROWS, B_COLS, RANK)

    def test_checkpoint_count(self):
        self.assertEqual(len(self.ckpts), K // RANK)

    def test_first_group_folds_into_word_zero_only(self):
        self.assertEqual(self.ckpts[0], CKPT_0)

    def test_second_group(self):
        self.assertEqual(self.ckpts[1], CKPT_1)

    def test_all_words_written_after_sixteen_groups(self):
        self.assertEqual(self.ckpts[15], CKPT_15)

    def test_wraparound_revisit_rotates_previous_word(self):
        # Group 17 (index 16) revisits word 0: rotl13(0xAF) = 0x15E000 and
        # this group's cumulative XOR-reduce is 0, so the word is exactly
        # the rotation of its previous value — rotation-on-revisit pinned.
        self.assertEqual(self.ckpts[16], CKPT_16)

    def test_final_words(self):
        self.assertEqual(self.words, FINAL)
        self.assertEqual(self.ckpts[-1], FINAL)

    def test_final_le_serialization(self):
        red = TileJackpotReducer(2, 2)
        ap, bpt = fixture_operands()
        for g in range(K // RANK):
            lo = g * RANK
            red.add_group([[sum(ap[i][l] * bpt[j][l]
                                for l in range(lo, lo + RANK))
                            for j in B_COLS] for i in A_ROWS])
        self.assertEqual(red.words_le_bytes().hex(), FINAL_LE_HEX)


class TestSemantics(unittest.TestCase):
    def test_constants_match_reference(self):
        self.assertEqual((JACKPOT_SIZE, LROT_PER_TILE), (16, 13))

    def test_reducer_matches_compute_jackpot(self):
        ap, bpt = fixture_operands()
        words, ckpts = compute_jackpot(ap, bpt, A_ROWS, B_COLS, RANK)
        red = TileJackpotReducer(len(A_ROWS), len(B_COLS))
        for g in range(K // RANK):
            lo = g * RANK
            red.add_group([[sum(ap[i][l] * bpt[j][l]
                                for l in range(lo, lo + RANK))
                            for j in B_COLS] for i in A_ROWS])
        self.assertEqual(red.words, words)
        self.assertEqual(red.checkpoints, ckpts)
        self.assertEqual(red.groups, K // RANK)

    def test_cumulative_not_per_group(self):
        # Negative control: resetting the tile each group (the bug SOL-1
        # finding 1 warns the final-matrix-only view invites) must give a
        # different jackpot than the cumulative reference.
        ap, bpt = fixture_operands()
        words, _ = compute_jackpot(ap, bpt, A_ROWS, B_COLS, RANK)
        reset_words = [0] * JACKPOT_SIZE
        for g in range(K // RANK):
            lo = g * RANK
            tile = [[sum(ap[i][l] * bpt[j][l] for l in range(lo, lo + RANK))
                     for j in B_COLS] for i in A_ROWS]
            tid = g % JACKPOT_SIZE
            prev = reset_words[tid]
            rot = ((prev << LROT_PER_TILE) |
                   (prev >> (32 - LROT_PER_TILE))) & 0xFFFFFFFF
            reset_words[tid] = rot ^ xor_reduce_tile(tile)
        self.assertNotEqual(tuple(reset_words), words)

    def test_xor_reduce_uses_u32_bit_patterns(self):
        self.assertEqual(xor_reduce_tile([[-1]]), 0xFFFFFFFF)
        self.assertEqual(xor_reduce_tile([[1, 2], [3, 0]]), 0)

    def test_partial_group_rejected(self):
        ap, bpt = fixture_operands()
        with self.assertRaises(ValueError):
            compute_jackpot(ap, bpt, A_ROWS, B_COLS, 48)  # 1024 % 48 != 0

    def test_reducer_shape_checked(self):
        red = TileJackpotReducer(2, 2)
        with self.assertRaises(ValueError):
            red.add_group([[1, 2, 3], [4, 5, 6]])


if __name__ == "__main__":
    unittest.main()
