# Sol feed — Poseidon 3090

You are the verifier seat. Rules are in `council/collaboration.md`.

## SOL-1 — Spec + kernel-design verification
- Verify `docs/SPEC.md` against the Pearl protocol: pearlhash / cuPOW stages,
  matrix dimensions and noising as actually specified by Pearl — flag any
  inaccuracy with the correct source.
- Review the sm_86 kernel plan (tensor-core GEMM stage, fused sparse prep,
  async proof/Merkle + job switch): would this beat SRBMiner-Multi and
  OneZeroMiner on a 3090, and where is it weakest?
- Verdict format: findings first (file/line), then a one-paragraph verdict.
  No performance claim without a bench behind it.
