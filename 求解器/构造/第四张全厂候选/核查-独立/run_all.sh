#!/bin/bash
# 重算本核查的全部结果（单进程，几十秒）。在任意目录执行均可。
set -e
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1
L=../独立/布局.json
sha256sum "$L"
python3 check_main.py "$L" 编码一结果.json > 编码一输出.txt
python3 check_alt.py "$L" 编码二结果.json > 编码二输出.txt
python3 compare.py 编码一结果.json 编码一结果-进路.json 编码二结果.json 互核.json
python3 obstruct.py "$L" 编码一结果.json 缺路阻断.json > /dev/null
python3 ore_matching.py "$L" 矿路匹配.json
python3 blockers.py "$L" 端口被挡.json > /dev/null
python3 cellcount.py "$L" 运输格下界.json
python3 per_machine.py 编码一结果.json 逐台缺路.json > /dev/null
python3 mutations.py "$L" 变异 变异结果.json > /dev/null
echo 完成
