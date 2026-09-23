set -euo pipefail
unset RUSTC_BOOTSTRAP RUSTC_WRAPPER RUSTFLAGS
export HEALTH_REPO='/home/zhuran24/zmd-research-fresh/求解器'
export HEALTH_RUN='/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-23-第0批'
export HEALTH_SRC='/tmp/kernel-health-20260923-_5s65pp9/求解器'
export HEALTH_PROFILE=health0isolation1229858
export CARGO_TARGET_DIR='/home/zhuran24/zmd-research-fresh/求解器/target'
export CARGO_BUILD_JOBS=2
export CARGO_PROFILE_DEV_CODEGEN_UNITS=1
export CARGO_PROFILE_TEST_CODEGEN_UNITS=1
export CARGO_PROFILE_RELEASE_CODEGEN_UNITS=1
export RUST_TEST_THREADS=1
export RAYON_NUM_THREADS=1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export UV_THREADPOOL_SIZE=1
export NODE_OPTIONS=--v8-pool-size=1
export PYTHONDONTWRITEBYTECODE=1
export KERNEL_TEST_EVIDENCE_DIR='/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-23-第0批/cargo-test-evidence'
# Use kernel_regression.py with the hash-bound receipt; it applies the four-CPU affinity.
