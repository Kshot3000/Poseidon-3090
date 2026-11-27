"""Cumulative Pearl jackpot — CPU reference implementation (CLAUDE-9).

Implements SOL-1 finding 1 (docs/SOL-1.md, PR #16): the Nacre recovery
identity in ``oracle.py`` covers the final noised GEMM only. Pearl's mining
loop does more — after **every** complete rank-sized group of the dot
product it folds the *cumulative* tile into a rotating jackpot, and only
the final jackpot is hashed. A kernel that produces the right final matrix
but the wrong intermediate checkpoints produces proofs the verifier
rejects. This module is the reference those checkpoints are pinned
against.

Transcribed from the Pearl reference CPU mining loop
(pearl-research-labs/pearl@adbfbbac, zk-pow/src/v2/mine.rs, the
``try_mine_one`` tile loop; constants from zk-pow/src/v2/circuit/
pearl_program.rs):

- the selected tile accumulates in signed int32 and is **never reset**
  between groups — group ``g`` covers dot-product terms
  ``[g*r, (g+1)*r)`` and the fold sees the sum over all terms so far;
- at each group boundary the cumulative tile is XOR-reduced: every entry
  is taken as its two's-complement ``u32`` bit pattern and XOR-folded in
  row-major order;
- the reduced word folds into jackpot word ``tid = g % 16`` as
  ``jackpot[tid] = rotl13(jackpot[tid]) ^ xored_tile`` — the rotation is
  applied to the *previous* word value, including on the first visit
  (rotating zero, a no-op) and on every wrap-around revisit;
- after the last group, the 16 jackpot words serialized little-endian are
  the input to keyed BLAKE3 under the A noise seed (docs/SPEC.md step 3).

Scope, stated plainly: this module pins the jackpot **words** and their
little-endian serialization. The final keyed-BLAKE3 digest is NOT computed
here — the repo is pure-stdlib and Python's stdlib has no BLAKE3; adding a
dependency or a hand-rolled BLAKE3 is its own task (CLAUDE-10, together
with the roots / seed-mode fixture). Roots and seed derivation are
likewise CLAUDE-10. Nothing here mines, and no hashrate is claimed.

``TileJackpotReducer`` is the tile-local reduction interface the kernel
skeleton exposes at the group boundary (cuda/gemm_stage.cuh): a kernel
feeds it one rank-group partial tile at a time and reads back the running
jackpot, instead of materializing the full matrix on the mining path.
"""
from __future__ import annotations

JACKPOT_SIZE = 16        # u32 words in the jackpot (pearl_program.rs)
LROT_PER_TILE = 13       # left rotation per fold (pearl_program.rs)
_U32 = 0xFFFFFFFF


def _u32(value: int) -> int:
    """Bit pattern of a signed int32 value as an unsigned 32-bit word."""
    return value & _U32


def _rotl32(value: int, shift: int) -> int:
    return ((value << shift) | (value >> (32 - shift))) & _U32


def xor_reduce_tile(tile) -> int:
    """XOR-fold every entry of a tile (row-major) as u32 bit patterns."""
    acc = 0
    for row in tile:
        for v in row:
            acc ^= _u32(v)
    return acc


class TileJackpotReducer:
    """Stateful group-boundary reduction for one selected tile.

    Feed exactly one partial tile per rank group, in dot-product order,
    via :meth:`add_group`. The partial is added into the cumulative tile
    (signed int32 wraparound, matching the reference's ``i32`` adds) and
    the cumulative tile is folded into the jackpot. ``checkpoints``
    records a snapshot of the 16 jackpot words after every group — the
    known-answer surface the fixture pins.
    """

    def __init__(self, tile_h: int, tile_w: int):
        if tile_h <= 0 or tile_w <= 0:
            raise ValueError("tile dimensions must be positive")
        self.tile_h = tile_h
        self.tile_w = tile_w
        self._tile = [[0] * tile_w for _ in range(tile_h)]
        self._words = [0] * JACKPOT_SIZE
        self._groups = 0
        self.checkpoints: list[tuple[int, ...]] = []

    def add_group(self, partial) -> tuple[int, ...]:
        """Add one rank-group partial tile and fold at the boundary."""
        if len(partial) != self.tile_h or any(
                len(row) != self.tile_w for row in partial):
            raise ValueError("partial tile shape does not match the tile")
        for u in range(self.tile_h):
            for v in range(self.tile_w):
                # i32 wraparound: Python ints are unbounded, the reference
                # accumulates in i32; wrap to the same bit pattern.
                s = (self._tile[u][v] + partial[u][v]) & _U32
                self._tile[u][v] = s - (1 << 32) if s >= (1 << 31) else s
        tid = self._groups % JACKPOT_SIZE
        self._words[tid] = _rotl32(self._words[tid], LROT_PER_TILE) ^ \
            xor_reduce_tile(self._tile)
        self._groups += 1
        snap = tuple(self._words)
        self.checkpoints.append(snap)
        return snap

    @property
    def words(self) -> tuple[int, ...]:
        return tuple(self._words)

    @property
    def groups(self) -> int:
        return self._groups

    @property
    def cumulative_tile(self) -> list[list[int]]:
        return [row[:] for row in self._tile]

    def words_le_bytes(self) -> bytes:
        """The 64 little-endian bytes keyed BLAKE3 hashes (SPEC step 3)."""
        return b"".join(w.to_bytes(4, "little") for w in self._words)


def compute_jackpot(ap, bpt, a_rows, b_cols, rank: int):
    """Full reference jackpot for one pattern-selected tile.

    ``ap`` is the noised A operand (m x k), ``bpt`` the noised B^T operand
    (n x k); ``a_rows`` / ``b_cols`` select the tile. ``k`` must be a
    multiple of ``rank`` — the reference loop steps ``rank..=k`` by
    ``rank`` and folds only at complete-group boundaries, so a trailing
    partial group would silently never fold; reject it instead.

    Returns ``(words, checkpoints)``: the final 16 jackpot words and the
    snapshot after every group boundary.
    """
    if rank <= 0:
        raise ValueError("rank must be positive")
    if not a_rows or not b_cols:
        raise ValueError("tile selection must be non-empty")
    k = len(ap[0]) if ap else 0
    if k == 0 or any(len(row) != k for row in ap):
        raise ValueError("AP is empty or ragged")
    if any(len(row) != k for row in bpt):
        raise ValueError("BPt rows disagree with AP on k")
    if k % rank != 0:
        raise ValueError(
            f"k={k} is not a multiple of rank={rank}: the reference loop "
            "folds only at complete rank-group boundaries")
    for i in a_rows:
        if not 0 <= i < len(ap):
            raise ValueError(f"a_rows index {i} outside AP")
    for j in b_cols:
        if not 0 <= j < len(bpt):
            raise ValueError(f"b_cols index {j} outside BPt")

    reducer = TileJackpotReducer(len(a_rows), len(b_cols))
    for g in range(k // rank):
        lo = g * rank
        partial = [[sum(ap[i][l] * bpt[j][l] for l in range(lo, lo + rank))
                    for j in b_cols] for i in a_rows]
        reducer.add_group(partial)
    return reducer.words, reducer.checkpoints
