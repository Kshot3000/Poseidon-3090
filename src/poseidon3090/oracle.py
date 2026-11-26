"""CPU math oracle for the pearlhash matrix stage (CLAUDE-1).

Pure-stdlib port of the Nacre GPU v0.2 dense oracle (Kyle's Nacre research,
Oysters4All `research/nacre-gpu/`; CPU equivalence verified 100/100 cases at
intake). This is the correctness reference every Poseidon kernel must match
bit-for-bit before it may claim anything. It is NOT a miner and makes no
performance claim.

The math (stored A is M x K, stored B is N x K; dense noise factors LA/LB
are M x R and N x R; sparse factors SA/SB are K x R with exactly one +1 and
one -1 per row):

    AP = A + LA SA^T
    BP = B + LB SB^T
    U  = A SB
    V  = BP SA            <-- V uses BP, not B; using B loses a cross term
    A B^T = AP BP^T - LA V^T - U LB^T

Bounds carried from the Nacre prototype: R in {64, 128}, A/B entries in
[-64, 63], LA/LB entries in [-32, 31], AP/BP stay in int8 range, and
K <= 2^20 keeps the correction accumulator inside int32
(127 * 2^20 < 2^31). Exact integer arithmetic throughout (Python ints);
range validation enforces the prototype's bounds so a kernel-side int8 /
int32 implementation cannot silently diverge.
"""
from __future__ import annotations

RANKS = (64, 128)
X_MIN, X_MAX = -64, 63        # stored operands A / B
L_MIN, L_MAX = -32, 31        # dense noise factors LA / LB
I8_MIN, I8_MAX = -128, 127    # prepared operands AP / BP
MAX_K = 1 << 20


def _check_matrix(mat, lo, hi, name):
    if not mat or not mat[0]:
        raise ValueError(f"{name}: empty matrix")
    width = len(mat[0])
    for row in mat:
        if len(row) != width:
            raise ValueError(f"{name}: ragged matrix")
        for v in row:
            if not lo <= v <= hi:
                raise ValueError(f"{name}: entry {v} outside [{lo}, {hi}]")
    return len(mat), width


def _check_indices(idx, k, r, name):
    if len(idx) != k:
        raise ValueError(f"{name}: expected {k} indices, got {len(idx)}")
    for v in idx:
        if not 0 <= v < r:
            raise ValueError(f"{name}: index {v} outside [0, {r})")


def matmul_t(a, b):
    """A (M x K) times B^T (B is N x K) -> M x N, exact integer math."""
    return [[sum(x * y for x, y in zip(ra, rb)) for rb in b] for ra in a]


def noise_operand(x, l, pos, neg):
    """Y = X + L SA^T in index form: Y[i][k] = X[i][k] + L[i][pos[k]] - L[i][neg[k]]."""
    return [[v + lrow[pos[k]] - lrow[neg[k]] for k, v in enumerate(row)]
            for row, lrow in zip(x, l)]


def correction(x, pos, neg, r):
    """G = X S in index form: G[i][pos[k]] += X[i][k]; G[i][neg[k]] -= X[i][k]."""
    g = [[0] * r for _ in x]
    for i, row in enumerate(x):
        for k, v in enumerate(row):
            g[i][pos[k]] += v
            g[i][neg[k]] -= v
    return g


def prepare(a, b, la, lb, pa, na, pb, nb):
    """Full Nacre preparation. Returns (AP, BP, U, V), all range-checked.

    pa/na are the +1/-1 column indices of SA per k; pb/nb the same for SB.
    """
    m, k = _check_matrix(a, X_MIN, X_MAX, "A")
    n, kb = _check_matrix(b, X_MIN, X_MAX, "B")
    if kb != k:
        raise ValueError("A and B disagree on K")
    if k > MAX_K:
        raise ValueError(f"K={k} exceeds the 2^20 accumulator bound")
    m2, r = _check_matrix(la, L_MIN, L_MAX, "LA")
    n2, r2 = _check_matrix(lb, L_MIN, L_MAX, "LB")
    if (m2, n2) != (m, n) or r2 != r:
        raise ValueError("noise factor shapes disagree with A/B")
    if r not in RANKS:
        raise ValueError(f"rank R={r} not in {RANKS}")
    for name, idx in (("PA", pa), ("NA", na), ("PB", pb), ("NB", nb)):
        _check_indices(idx, k, r, name)
    for k_i in range(k):
        if pa[k_i] == na[k_i] or pb[k_i] == nb[k_i]:
            raise ValueError("sparse row must hold one +1 and one -1 in "
                             "distinct columns")
    ap = noise_operand(a, la, pa, na)
    bp = noise_operand(b, lb, pb, nb)
    _check_matrix(ap, I8_MIN, I8_MAX, "AP")
    _check_matrix(bp, I8_MIN, I8_MAX, "BP")
    u = correction(a, pb, nb, r)
    v = correction(bp, pa, na, r)  # V uses BP, not B — see module docstring.
    return ap, bp, u, v


def recover(ap, bp, la, lb, u, v):
    """A B^T from the prepared operands: AP BP^T - LA V^T - U LB^T."""
    main = matmul_t(ap, bp)
    lav = matmul_t(la, v)
    ulb = matmul_t(u, lb)
    return [[main[i][j] - lav[i][j] - ulb[i][j]
             for j in range(len(main[0]))] for i in range(len(main))]
