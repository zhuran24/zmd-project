#!/usr/bin/env bash
set -euo pipefail
cd -- /home/zhuran24/zmd-research-fresh
export PYTHONDONTWRITEBYTECODE=1
exec python3 -B 求解器/内核维护/2026-09-22g/verify/report.py
