// Poseidon 3090 — kernel self-test (CLAUDE-1 skeleton).
// Status: NOT YET RUN — needs nvcc + an sm_86 GPU (Hermes' 3090 rig).
// Build/run via scripts/build-kernel.sh.
//
// Checks:
//   1. gemm_stage_run against fixed known-answer A * B^T vectors.
//   2. The full Nacre preparation identity on host-generated factors:
//      AP/BP built with the index form of the sparse factors, the main
//      GEMM run on the GPU over AP/BP, then host recovery
//      A B^T = AP BP^T - LA V^T - U LB^T compared against a direct host
//      A B^T. The Python CPU oracle (src/poseidon3090/oracle.py,
//      tests/test_oracle.py) pins the same identity without a GPU.
#include <cstdint>
#include <cstdio>
#include <random>
#include <vector>

#include "gemm_stage.cuh"

using poseidon::GemmLaunch;
using poseidon::GemmShape;

static void host_gemm_t(const std::vector<int8_t>& A,
                        const std::vector<int8_t>& B, std::vector<int32_t>& C,
                        GemmShape s) {
  for (int i = 0; i < s.m; ++i)
    for (int j = 0; j < s.n; ++j) {
      int32_t acc = 0;
      for (int t = 0; t < s.k; ++t)
        acc += static_cast<int32_t>(A[i * s.k + t]) *
               static_cast<int32_t>(B[j * s.k + t]);
      C[i * s.n + j] = acc;
    }
}

static int check_gemm(const char* name, GemmShape s,
                      const std::vector<int8_t>& A,
                      const std::vector<int8_t>& B,
                      const std::vector<int32_t>& want) {
  std::vector<int32_t> got(s.m * s.n, 0);
  int rc = poseidon::gemm_stage_run(A.data(), B.data(), got.data(), s,
                                    GemmLaunch{64, 2});
  if (rc != 0) {
    std::printf("FAIL %s: gemm_stage_run rc=%d\n", name, rc);
    return 1;
  }
  if (got != want) {
    std::printf("FAIL %s: result mismatch\n", name);
    return 1;
  }
  std::printf("PASS %s\n", name);
  return 0;
}

int main() {
  int fails = 0;
  // Known-answer: [[1,2],[3,4]] * [[5,6],[7,8]]^T = [[17,23],[39,53]]
  fails += check_gemm("known-answer-2x2", {2, 2, 2}, {1, 2, 3, 4},
                      {5, 6, 7, 8}, {17, 23, 39, 53});

  // Nacre identity, R=64, K=31, M=7, N=11 (mirrors the oracle's grid).
  {
    const int M = 7, N = 11, K = 31, R = 64;
    std::mt19937 rng(20261007);
    std::uniform_int_distribution<int> dx(-64, 63), dl(-32, 31),
        dr(0, R - 1), dshift(1, R - 1);
    std::vector<int8_t> A(M * K), B(N * K), LA(M * R), LB(N * R);
    for (auto& v : A) v = static_cast<int8_t>(dx(rng));
    for (auto& v : B) v = static_cast<int8_t>(dx(rng));
    for (auto& v : LA) v = static_cast<int8_t>(dl(rng));
    for (auto& v : LB) v = static_cast<int8_t>(dl(rng));
    std::vector<int> PA(K), NA(K), PB(K), NB(K);
    for (int k = 0; k < K; ++k) {
      PA[k] = dr(rng); NA[k] = (PA[k] + dshift(rng)) % R;
      PB[k] = dr(rng); NB[k] = (PB[k] + dshift(rng)) % R;
    }
    // Index-form preparation (same formulas as oracle.py).
    std::vector<int8_t> AP = A, BP = B;
    for (int i = 0; i < M; ++i)
      for (int k = 0; k < K; ++k)
        AP[i * K + k] = static_cast<int8_t>(A[i * K + k] + LA[i * R + PA[k]] -
                                            LA[i * R + NA[k]]);
    for (int j = 0; j < N; ++j)
      for (int k = 0; k < K; ++k)
        BP[j * K + k] = static_cast<int8_t>(B[j * K + k] + LB[j * R + PB[k]] -
                                            LB[j * R + NB[k]]);
    std::vector<int32_t> U(M * R, 0), V(N * R, 0);
    for (int k = 0; k < K; ++k) {
      for (int i = 0; i < M; ++i) {
        U[i * R + PB[k]] += A[i * K + k];
        U[i * R + NB[k]] -= A[i * K + k];
      }
      for (int j = 0; j < N; ++j) {
        V[j * R + PA[k]] += BP[j * K + k];  // V uses BP, not B
        V[j * R + NA[k]] -= BP[j * K + k];
      }
    }
    // GPU main GEMM over the prepared operands.
    std::vector<int32_t> APBP(M * N, 0);
    int rc = poseidon::gemm_stage_run(AP.data(), BP.data(), APBP.data(),
                                      GemmShape{M, N, K}, GemmLaunch{64, 2});
    if (rc != 0) {
      std::printf("FAIL nacre-identity: gemm_stage_run rc=%d\n", rc);
      ++fails;
    } else {
      // Host recovery and direct product.
      std::vector<int32_t> rec(M * N, 0), direct(M * N, 0);
      for (int i = 0; i < M; ++i)
        for (int j = 0; j < N; ++j) {
          int32_t lav = 0, ulb = 0;
          for (int r = 0; r < R; ++r) {
            lav += static_cast<int32_t>(LA[i * R + r]) * V[j * R + r];
            ulb += U[i * R + r] * static_cast<int32_t>(LB[j * R + r]);
          }
          rec[i * N + j] = APBP[i * N + j] - lav - ulb;
        }
      host_gemm_t(A, B, direct, GemmShape{M, N, K});
      if (rec == direct) {
        std::printf("PASS nacre-identity-r64-k31\n");
      } else {
        std::printf("FAIL nacre-identity: recovery mismatch\n");
        ++fails;
      }
    }
  }
  std::printf(fails ? "SELFTEST FAILED (%d)\n" : "SELFTEST OK\n", fails);
  return fails ? 1 : 0;
}
