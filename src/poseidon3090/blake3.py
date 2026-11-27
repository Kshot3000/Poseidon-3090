"""Pure-Python BLAKE3 — vendored, verified against the official test vectors.

Why this exists (CLAUDE-10, the BLAKE3 source decision): the Pearl jackpot's
final keyed digest and the job commitment roots are BLAKE3 constructions, but
this repo is pure-stdlib and the stdlib has no BLAKE3. The board rule for
CLAUDE-10 was: do not hand-roll a hash without published test vectors pinned
in the same PR. So this module is a from-spec implementation of BLAKE3
(compression function, chunk/parent tree, keyed-hash and derive-key modes,
XOF output) and ``tests/test_blake3.py`` pins it against the complete
official BLAKE3 test vector set published by the BLAKE3 team
(https://github.com/BLAKE3-team/BLAKE3/blob/master/test_vectors/test_vectors.json):
all 35 input lengths, all three modes, full 131-byte extended outputs for the
boundary lengths and 32-byte digests for the rest.

This is a *reference* implementation for host-side fixtures and verification
— it is not fast and it is not the mining kernel. It exists so the jackpot
digest and root fixtures (the rest of CLAUDE-10, which builds on CLAUDE-9's
jackpot reference once that lands) can be pinned byte-for-byte on the host
before any CUDA code is trusted with them.

API:
    hash(data, out_len=32)                  -> bytes
    keyed_hash(key32, data, out_len=32)     -> bytes
    derive_key(context, material, out_len)  -> bytes
    Hasher / Hasher.new_keyed / Hasher.new_derive_key for streaming input.
"""

from __future__ import annotations

import struct

__all__ = ["Hasher", "hash", "keyed_hash", "derive_key", "OUT_LEN", "KEY_LEN"]

OUT_LEN = 32
KEY_LEN = 32
CHUNK_LEN = 1024
BLOCK_LEN = 64

_IV = (
    0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A,
    0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19,
)
_MSG_PERMUTATION = (2, 6, 3, 10, 7, 0, 4, 13, 1, 11, 12, 5, 9, 14, 15, 8)

_FLAG_CHUNK_START = 1 << 0
_FLAG_CHUNK_END = 1 << 1
_FLAG_PARENT = 1 << 2
_FLAG_ROOT = 1 << 3
_FLAG_KEYED_HASH = 1 << 4
_FLAG_DERIVE_KEY_CONTEXT = 1 << 5
_FLAG_DERIVE_KEY_MATERIAL = 1 << 6

_MASK = 0xFFFFFFFF


def _rotr(x: int, n: int) -> int:
    return ((x >> n) | (x << (32 - n))) & _MASK


def _g(state: list, a: int, b: int, c: int, d: int, mx: int, my: int) -> None:
    state[a] = (state[a] + state[b] + mx) & _MASK
    state[d] = _rotr(state[d] ^ state[a], 16)
    state[c] = (state[c] + state[d]) & _MASK
    state[b] = _rotr(state[b] ^ state[c], 12)
    state[a] = (state[a] + state[b] + my) & _MASK
    state[d] = _rotr(state[d] ^ state[a], 8)
    state[c] = (state[c] + state[d]) & _MASK
    state[b] = _rotr(state[b] ^ state[c], 7)


def _round(state: list, m: list) -> None:
    _g(state, 0, 4, 8, 12, m[0], m[1])
    _g(state, 1, 5, 9, 13, m[2], m[3])
    _g(state, 2, 6, 10, 14, m[4], m[5])
    _g(state, 3, 7, 11, 15, m[6], m[7])
    _g(state, 0, 5, 10, 15, m[8], m[9])
    _g(state, 1, 6, 11, 12, m[10], m[11])
    _g(state, 2, 7, 8, 13, m[12], m[13])
    _g(state, 3, 4, 9, 14, m[14], m[15])


def _compress(cv, block_words, counter: int, block_len: int, flags: int) -> list:
    state = list(cv) + list(_IV)
    state[12] = counter & _MASK
    state[13] = (counter >> 32) & _MASK
    state[14] = block_len
    state[15] = flags
    m = list(block_words)
    _round(state, m)
    for _ in range(6):
        m = [m[_MSG_PERMUTATION[i]] for i in range(16)]
        _round(state, m)
    for i in range(8):
        state[i] ^= state[i + 8]
        state[i + 8] ^= cv[i]
    return state


def _words_from_block(block: bytes) -> list:
    if len(block) < BLOCK_LEN:
        block = block + b"\x00" * (BLOCK_LEN - len(block))
    return list(struct.unpack("<16I", block))


def _words_from_key(key: bytes) -> list:
    return list(struct.unpack("<8I", key))


class _Output:
    __slots__ = ("input_cv", "block_words", "counter", "block_len", "flags")

    def __init__(self, input_cv, block_words, counter, block_len, flags):
        self.input_cv = input_cv
        self.block_words = block_words
        self.counter = counter
        self.block_len = block_len
        self.flags = flags

    def chaining_value(self) -> list:
        return _compress(
            self.input_cv, self.block_words, self.counter, self.block_len, self.flags
        )[:8]

    def root_bytes(self, out_len: int) -> bytes:
        out = bytearray()
        counter = 0
        while len(out) < out_len:
            words = _compress(
                self.input_cv,
                self.block_words,
                counter,
                self.block_len,
                self.flags | _FLAG_ROOT,
            )
            out += struct.pack("<16I", *words)
            counter += 1
        return bytes(out[:out_len])


class _ChunkState:
    __slots__ = ("cv", "chunk_counter", "buf", "blocks_compressed", "flags")

    def __init__(self, key_words, chunk_counter: int, flags: int):
        self.cv = list(key_words)
        self.chunk_counter = chunk_counter
        self.buf = bytearray()
        self.blocks_compressed = 0
        self.flags = flags

    def length(self) -> int:
        return BLOCK_LEN * self.blocks_compressed + len(self.buf)

    def _start_flag(self) -> int:
        return _FLAG_CHUNK_START if self.blocks_compressed == 0 else 0

    def update(self, data: bytes) -> None:
        while data:
            if len(self.buf) == BLOCK_LEN:
                self.cv = _compress(
                    self.cv,
                    _words_from_block(bytes(self.buf)),
                    self.chunk_counter,
                    BLOCK_LEN,
                    self.flags | self._start_flag(),
                )[:8]
                self.blocks_compressed += 1
                self.buf = bytearray()
            want = BLOCK_LEN - len(self.buf)
            take = min(want, len(data))
            self.buf += data[:take]
            data = data[take:]

    def output(self) -> _Output:
        return _Output(
            self.cv,
            _words_from_block(bytes(self.buf)),
            self.chunk_counter,
            len(self.buf),
            self.flags | self._start_flag() | _FLAG_CHUNK_END,
        )


def _parent_output(left_cv, right_cv, key_words, flags: int) -> _Output:
    block = struct.pack("<8I", *left_cv) + struct.pack("<8I", *right_cv)
    return _Output(key_words, _words_from_block(block), 0, BLOCK_LEN, flags | _FLAG_PARENT)


class Hasher:
    """Streaming BLAKE3 hasher (hash, keyed_hash, and derive_key modes)."""

    def __init__(self, key_words, flags: int):
        self._key_words = list(key_words)
        self._flags = flags
        self._chunk = _ChunkState(self._key_words, 0, flags)
        self._cv_stack: list = []

    @classmethod
    def new(cls) -> "Hasher":
        return cls(_IV, 0)

    @classmethod
    def new_keyed(cls, key: bytes) -> "Hasher":
        if len(key) != KEY_LEN:
            raise ValueError(f"keyed_hash key must be {KEY_LEN} bytes, got {len(key)}")
        return cls(_words_from_key(key), _FLAG_KEYED_HASH)

    @classmethod
    def new_derive_key(cls, context: str) -> "Hasher":
        context_hasher = cls(_IV, _FLAG_DERIVE_KEY_CONTEXT)
        context_hasher.update(context.encode("utf-8"))
        context_key = context_hasher.finalize(OUT_LEN)
        return cls(_words_from_key(context_key), _FLAG_DERIVE_KEY_MATERIAL)

    def _push_cv(self, cv, total_chunks: int) -> None:
        while total_chunks & 1 == 0:
            cv = _parent_output(
                self._cv_stack.pop(), cv, self._key_words, self._flags
            ).chaining_value()
            total_chunks >>= 1
        self._cv_stack.append(cv)

    def update(self, data: bytes) -> "Hasher":
        data = bytes(data)
        while data:
            if self._chunk.length() == CHUNK_LEN:
                cv = self._chunk.output().chaining_value()
                total_chunks = self._chunk.chunk_counter + 1
                self._push_cv(cv, total_chunks)
                self._chunk = _ChunkState(self._key_words, total_chunks, self._flags)
            want = CHUNK_LEN - self._chunk.length()
            take = min(want, len(data))
            self._chunk.update(data[:take])
            data = data[take:]
        return self

    def finalize(self, out_len: int = OUT_LEN) -> bytes:
        output = self._chunk.output()
        remaining = len(self._cv_stack)
        while remaining > 0:
            remaining -= 1
            output = _parent_output(
                self._cv_stack[remaining],
                output.chaining_value(),
                self._key_words,
                self._flags,
            )
        return output.root_bytes(out_len)


def hash(data: bytes, out_len: int = OUT_LEN) -> bytes:  # noqa: A001 - mirrors the BLAKE3 mode name
    """One-shot BLAKE3 hash (XOF: ``out_len`` may exceed 32)."""
    return Hasher.new().update(data).finalize(out_len)


def keyed_hash(key: bytes, data: bytes, out_len: int = OUT_LEN) -> bytes:
    """One-shot BLAKE3 keyed hash (MAC mode) with a 32-byte key."""
    return Hasher.new_keyed(key).update(data).finalize(out_len)


def derive_key(context: str, material: bytes, out_len: int = OUT_LEN) -> bytes:
    """One-shot BLAKE3 key derivation for ``context`` over ``material``."""
    return Hasher.new_derive_key(context).update(material).finalize(out_len)
