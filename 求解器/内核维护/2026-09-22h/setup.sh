#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
cp ../2026-09-22g/guard.py guard.py
cp ../2026-09-22g/run.sh run.sh
cp ../2026-09-22g/safe-suite.sh safe-suite.sh
bash run.sh init
