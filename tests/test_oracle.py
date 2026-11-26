import random
import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from poseidon3090 import oracle


def gen_case(rng, m, n, k, r, hot=False):
    a = [[rng.randint(-64, 63) for _ in range(k)] for _ in range(m)]
    b = [[rng.randint(-64, 63) for _ in range(k)] for _ in range(n)]
    la = [[rng.randint(-32, 31) for _ in range(r)] for _ in range(m)]
    lb = [[rng.randint(-32, 31) for _ in range(r)] for _ in range(n)]
    pa = [rng.randrange(r) for _ in range(k)]
    na = [(p + rng.randint(1, r - 1)) % r for p in pa]
    pb = [rng.randrange(r) for _ in range(k)]
    nb = [(p + rng.randint(1, r - 1)) % r for p in pb]
    if hot:  # concentrated pattern: worst-case shared-index contention
        pa, pb = [0] * k, [0] * k
        na, nb = [1] * k, [1] * k
    return a, b, la, lb, pa, na, pb, nb


def dense_sparse(pos, neg, k, r):
    s = [[0] * r for _ in range(k)]
    for i in range(k):
        s[i][pos[i]] = 1
        s[i][neg[i]] = -1
    return s


def matmul(a, b):
    return [[sum(x * y for x, y in zip(row, col)) for col in zip(*b)]
            for row in a]


class TestOracleIdentity(unittest.TestCase):
    def test_known_answer_main_gemm(self):
        self.assertEqual(oracle.matmul_t([[1, 2], [3, 4]], [[5, 6], [7, 8]]),
                         [[17, 23], [39, 53]])

    def test_index_form_matches_dense_form(self):
        rng = random.Random(20261007)
        a, b, la, lb, pa, na, pb, nb = gen_case(rng, 7, 11, 31, 64)
        sa = dense_sparse(pa, na, 31, 64)
        sb = dense_sparse(pb, nb, 31, 64)
        ap, bp, u, v = oracle.prepare(a, b, la, lb, pa, na, pb, nb)
        add = lambda x, y: [[p + q for p, q in zip(rx, ry)]
                            for rx, ry in zip(x, y)]
        self.assertEqual(ap, add(a, matmul(la, list(zip(*sa)))))
        self.assertEqual(bp, add(b, matmul(lb, list(zip(*sb)))))
        self.assertEqual(u, matmul(a, sb))
        self.assertEqual(v, matmul(bp, sa))

    def test_full_identity_grid(self):
        # Same grid as the Nacre NumPy oracle (seed 20261007): ranks 64/128,
        # K in {1,31,64,257,1024}, random + concentrated index patterns.
        rng = random.Random(20261007)
        cases = 0
        for r in (64, 128):
            for k in (1, 31, 64, 257, 1024):
                for hot in (False, True):
                    for _ in range(2):
                        case = gen_case(rng, 7, 11, k, r, hot)
                        ap, bp, u, v = oracle.prepare(*case)
                        got = oracle.recover(ap, bp, case[2], case[3], u, v)
                        self.assertEqual(got, oracle.matmul_t(case[0], case[1]))
                        cases += 1
        self.assertEqual(cases, 40)

    def test_v_from_b_instead_of_bp_breaks_identity(self):
        # Negative control for the documented trap: V must use BP, not B.
        rng = random.Random(20261007)
        a, b, la, lb, pa, na, pb, nb = gen_case(rng, 7, 11, 64, 64)
        ap, bp, u, _ = oracle.prepare(a, b, la, lb, pa, na, pb, nb)
        v_wrong = oracle.correction(b, pa, na, 64)
        got = oracle.recover(ap, bp, la, lb, u, v_wrong)
        self.assertNotEqual(got, oracle.matmul_t(a, b))


class TestOracleValidation(unittest.TestCase):
    def setUp(self):
        rng = random.Random(20261007)
        self.case = list(gen_case(rng, 7, 11, 31, 64))

    def test_rejects_out_of_range_operand(self):
        self.case[0][0][0] = 64
        with self.assertRaises(ValueError):
            oracle.prepare(*self.case)

    def test_rejects_out_of_range_noise(self):
        self.case[2][0][0] = 32
        with self.assertRaises(ValueError):
            oracle.prepare(*self.case)

    def test_rejects_bad_rank(self):
        rng = random.Random(1)
        case = list(gen_case(rng, 7, 11, 31, 64))
        case[2] = [[0] * 32 for _ in range(7)]
        case[3] = [[0] * 32 for _ in range(11)]
        with self.assertRaises(ValueError):
            oracle.prepare(*case)

    def test_rejects_coincident_sparse_indices(self):
        self.case[5][0] = self.case[4][0]  # NA[0] = PA[0]
        with self.assertRaises(ValueError):
            oracle.prepare(*self.case)


if __name__ == "__main__":
    unittest.main()
