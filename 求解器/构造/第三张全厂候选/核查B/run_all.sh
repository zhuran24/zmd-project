#!/bin/sh
# 核查B 全部复算（单线程，约 1 秒；变异检验约 2 秒）
set -e
cd "$(dirname "$0")"
python3 -B check_main.py
python3 -B check_alt.py
python3 -B obstruct.py
python3 -B mutations.py
python3 -B compare.py
