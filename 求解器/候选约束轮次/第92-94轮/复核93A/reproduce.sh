#!/usr/bin/env bash
set -euo pipefail
review_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export TMPDIR="$review_dir"
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
python "$review_dir/arithmetic_matrix.py"
python "$review_dir/arithmetic_batches.py"
python "$review_dir/dense_cells.py"
python "$review_dir/dense_countdown.py"
python "$review_dir/dense_geometry.py"
g++ -std=c++17 -O2 -Wall -Wextra -pedantic "$review_dir/polling_exhaustive.cpp" -o "$review_dir/polling_exhaustive"
"$review_dir/polling_exhaustive" "$review_dir/polling_exhaustive.json"
python "$review_dir/additional_checks.py"
python "$review_dir/cache_balance.py"
python "$review_dir/build_payload.py"
python "$review_dir/validate_delivery.py"
