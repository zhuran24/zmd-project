#!/bin/sh
# 在本目录下依次复跑核查A的全部程序；只写本目录。
set -e
cd "$(dirname "$0")"
python3 -B check_main.py > /dev/null
python3 -B check_alt.py > /dev/null
python3 -B compare.py
python3 -B reach.py
python3 -B per_machine.py
python3 -B mutations.py
sha256sum ../构造A/未通过候选.json ../../../候选约束轮次/第107-109轮/前提快照/*.txt ../../../候选约束轮次/第107-109轮/临时规则.md ../../../候选约束轮次/第98-100轮/推导98S2.md ../../../候选约束轮次/第107-109轮/推导107S2B.md check_main.py check_alt.py compare.py reach.py per_machine.py mutations.py
