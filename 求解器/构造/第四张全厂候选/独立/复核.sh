#!/usr/bin/env bash
set -euo pipefail
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python -B "$root/代码/check_static.py" "$root/布局.json" "$root/静态检查结果.json"
python -B "$root/代码/check_metrics.py"
python -B "$root/代码/check_mutations.py"
