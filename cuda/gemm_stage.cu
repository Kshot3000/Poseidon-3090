// Poseidon 3090 — GEMM stage host wrapper (CLAUDE-1 skeleton).
// Status: DESIGNED, NOT YET COMPILED OR BENCHMARKED — build with
// scripts/build-kernel.sh on a machine with nvcc (Hermes' 3090 rig);
// correctness is gated by cuda/selftest.cu against the CPU oracle.
#include "gemm_stage.cuh"

#include <cuda_runtime.h>

namespace poseidon {

int gemm_stage_run(const int8_t* A, const int8_t* B, int32_t* C,
                   GemmShape shape, GemmLaunch launch) {
  const size_t a_bytes = sizeof(int8_t) * shape.m * shape.k;
  const size_t b_bytes = sizeof(int8_t) * shape.n * shape.k;
  const size_t c_bytes = sizeof(int32_t) * shape.m * shape.n;
  int8_t *dA = nullptr, *dB = nullptr;
  int32_t* dC = nullptr;
  cudaError_t err = cudaMalloc(&dA, a_bytes);
  if (err != cudaSuccess) return static_cast<int>(err);
  err = cudaMalloc(&dB, b_bytes);
  if (err != cudaSuccess) return static_cast<int>(err);
  err = cudaMalloc(&dC, c_bytes);
  if (err != cudaSuccess) return static_cast<int>(err);

  cudaMemcpy(dA, A, a_bytes, cudaMemcpyHostToDevice);
  cudaMemcpy(dB, B, b_bytes, cudaMemcpyHostToDevice);

  // Reference kernel launch: 16x16 threads per block, grid covers C.
  dim3 block(16, 16);
  dim3 grid((shape.n + block.x - 1) / block.x,
            (shape.m + block.y - 1) / block.y);
  (void)launch;  // tile/blocks_per_sm drive the future MMA path; the
                 // reference kernel ignores them by design.
  gemm_ref_kernel<<<grid, block>>>(dA, dB, dC, shape);
  err = cudaGetLastError();
  if (err == cudaSuccess) {
    cudaMemcpy(C, dC, c_bytes, cudaMemcpyDeviceToHost);
    err = cudaGetLastError();
  }
  cudaFree(dA);
  cudaFree(dB);
  cudaFree(dC);
  return static_cast<int>(err);
}

}  // namespace poseidon
