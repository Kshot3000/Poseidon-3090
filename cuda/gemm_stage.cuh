// Poseidon 3090 — main GEMM stage interface (CLAUDE-1 skeleton).
//
// Status: DESIGNED, NOT YET COMPILED OR BENCHMARKED. No hashrate is claimed
// for this code. Kernel status per docs/SPEC.md honesty rules:
// designed != compiled != benchmarked != shipped.
//
// The pearlhash matrix stage multiplies the *prepared* operands produced by
// the cuPOW noising stage. Poseidon carries the Nacre fused sparse
// preparation design (Kyle's Nacre GPU v0.2 research, Oysters4All): with
// stored A (M x K) and B (N x K), dense noise factors LA/LB (M x R, N x R)
// and sparse factors SA/SB (K x R, one +1 and one -1 per row):
//
//   AP = A + LA SA^T        BP = B + LB SB^T
//   U  = A SB               V  = BP SA        (V uses BP, not B)
//   A B^T = AP BP^T - LA V^T - U LB^T
//
// This header is the MAIN GEMM contract: C = AP * BP^T, int8 operands,
// int32 accumulation (exact; no floating point in the correctness path).
// The preparation stage itself lands behind the same style of interface in
// a follow-up task; the CPU oracle in src/poseidon3090/oracle.py pins the
// full identity and this kernel must agree with it bit-for-bit before any
// tensor-core path may replace the reference kernel.
//
// Design notes (starting points to re-tune on Hermes' 3090, not conclusions;
// Sol verifies the design under SOL-1):
//   * sm_86: 82 SMs, compute capability 8.6, 24 GB GDDR6X.
//   * Tile R=64 baseline from the Nacre/OysterRig design notes; autotune
//     candidates live in src/poseidon3090/tune.py (tile 64/128,
//     2-3 blocks/SM) and map onto GemmLaunch below.
#pragma once

#include <cstdint>

namespace poseidon {

// Shapes for C = A * B^T. A is (m x k) int8, B is (n x k) int8,
// C is (m x n) int32. Row-major throughout.
struct GemmShape {
  int m;
  int n;
  int k;
};

// Launch configuration. tile/blocks_per_sm mirror tune.py's Profile fields
// so autotune results map 1:1 onto kernel launches.
struct GemmLaunch {
  int tile;          // square tile edge (64 baseline)
  int blocks_per_sm; // occupancy target used by the host scheduler
};

// Reference (correctness-first) GEMM kernel: one thread per output element.
// Deliberately naive — its only job is to be obviously right against the
// oracle. The tensor-core MMA path lands behind this same interface.
__global__ void gemm_ref_kernel(const int8_t* __restrict__ A,
                                const int8_t* __restrict__ B,
                                int32_t* __restrict__ C, GemmShape shape) {
  int row = blockIdx.y * blockDim.y + threadIdx.y;
  int col = blockIdx.x * blockDim.x + threadIdx.x;
  if (row >= shape.m || col >= shape.n) return;
  int32_t acc = 0;
  for (int t = 0; t < shape.k; ++t) {
    acc += static_cast<int32_t>(A[row * shape.k + t]) *
           static_cast<int32_t>(B[col * shape.k + t]);
  }
  C[row * shape.n + col] = acc;
}

// Tile-local jackpot reduction at the rank-group boundary (CLAUDE-9,
// SOL-1 finding 1). The mining path must NOT materialize the full product:
// Pearl folds the *cumulative* selected tile into a rotating 16-word
// jackpot after every complete group of `rank` dot-product terms, and
// only the final jackpot is hashed. This interface is that boundary: the
// GEMM stage hands over one rank-group partial tile at a time and the
// reducer accumulates it, XOR-reduces the cumulative tile (entries as
// u32 bit patterns, row-major), and folds into word (group % 16) as
// rotl13(previous word) ^ xored_tile. The host reference implementation
// and the known-answer fixture live in src/poseidon3090/jackpot.py and
// tests/test_jackpot.py; a device implementation must match them at
// every group boundary, not just at the end. Full-matrix output stays
// available through gemm_stage_run for the diagnostic path.
// Status: INTERFACE ONLY — declared, not implemented, not compiled.
struct JackpotReducer {
  int32_t tile[16 * 16];  // cumulative tile, row-major, <= 256 entries
  uint32_t words[16];     // the rotating jackpot
  int tile_h;
  int tile_w;
  int groups;             // rank groups folded so far
};

// Reset a reducer for a tile_h x tile_w selected tile.
void jackpot_init(JackpotReducer* red, int tile_h, int tile_w);

// Add one rank-group partial tile (tile_h x tile_w, row-major) into the
// cumulative tile and fold at the group boundary.
void jackpot_add_group(JackpotReducer* red, const int32_t* partial);

// Host entry point implemented in gemm_stage.cu: copies A/B to the device,
// launches the configured kernel, copies C back. Returns 0 on success,
// non-zero CUDA error code otherwise.
int gemm_stage_run(const int8_t* A, const int8_t* B, int32_t* C,
                   GemmShape shape, GemmLaunch launch);

}  // namespace poseidon
