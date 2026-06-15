**终末地 IndustrialPlanner 精确求解器 — 网格布线子问题面 soundness 审查**

项目快照在本 Project 文件区(来源/Sources):`zmd_snapshot_72ec34a8.zip`,sha256 `72ec34a80bfee3eefcbdc223d5a3a1dcd834118ed04912e3136bbd24e8f9c092`,干净 git 树 HEAD `600f98c`。开工前先校验 sha256,对不上停下报告;文件区其它快照包无视。zip 内 `project/` 为仓库根(`python -m zipfile -e <zip> .` 解包)。依赖 wheels 同在文件区(`zmd_py313_linux_x86_64.zip`,沙盒 Python 3.13 离线装)。`data/preprocessed/candidate_placements.json`(45,773,799 bytes)已随包,不需再生。

70×70 网格 certified-exact 最大空矩形求解器,OR-Tools CP-SAT 9.15 + Benders/LBBD(master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断),宪法 `PROJECT_LOCK.md`,fail-closed 默认姿态。

本面 = 网格布线子问题(grid routing / port adherence / connectivity / 域分析,`src/models/routing_subproblem.py` 为核)。 它有没有 soundness 缺陷,能让求解器在 canonical 数据 + 默认 env 下输出 **false-CERTIFIED**(把预算耗尽/异常/非三态 status 误读成不可行证明、铸出删合法解的 master nogood、或输出 CERTIFIED 而证明前提不成立)?把判读过程和结论写清楚——有问题给可复现触发条件,没问题说明从哪些角度排除。

自验:全量 `python -m pytest -q src/tests` 应 0 failed(沙盒报 randomly seed 错加 `-p no:randomly`)。
