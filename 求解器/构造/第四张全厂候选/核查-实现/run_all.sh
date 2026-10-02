#!/bin/sh
# 在项目根目录运行：sh '求解器/构造/第四张全厂候选/核查-实现/run_all.sh'
set -e
D='求解器/构造/第四张全厂候选/核查-实现'
IN='求解器/构造/第四张全厂候选/实现/布局.json'
python3 -B "$D/check_main.py" "$IN" "$D/结果-主.json"
python3 -B "$D/check_alt.py" "$IN" "$D/结果-副.json"
python3 -B "$D/cross.py" "$D/结果-主.json" "$D/结果-副.json" "$D/互核.json"
python3 -B "$D/reach.py" "$IN" "$D/结果-主.json" "$D/结果-可达.json"
python3 -B "$D/per_unit.py" "$D/结果-主.json" "$D/结果-可达.json" "$D/结果-逐台.json"
python3 -B "$D/mutations.py" "$IN" "$D/变异结果.json"
sha256sum "$IN" \
  '求解器/候选约束轮次/第107-109轮/前提快照/《明日方舟：终末地》游戏规则.txt' \
  '求解器/候选约束轮次/第107-109轮/前提快照/求解任务.txt' \
  '求解器/候选约束轮次/第107-109轮/前提快照/求解约束.txt' \
  '求解器/候选约束轮次/第107-109轮/临时规则.md' \
  '求解器/候选约束轮次/第107-109轮/推导107S2B.md' \
  "$D"/*.py
