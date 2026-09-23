#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
bash run.sh run cargo-build cargo build --workspace -j 4
bash run.sh run cargo-check-final cargo check --workspace -j 4
bash run.sh run cargo-clippy-final cargo clippy --workspace -j 4
bash run.sh run kernel-lib-final cargo test -p kernel --lib -j 4 -- --test-threads=1
bash run.sh run kernel-reference-final cargo test -p kernel --test reference -j 4 -- --test-threads=1
bash run.sh run topology-validation-final cargo test -p topology --test validation -j 4 -- --test-threads=1
bash task.sh positive.py
