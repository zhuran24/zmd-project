# 批C probe 数据归档(2026-07-13,probe_3~10)

由易失 scratchpad(/tmp,重启即清)抢救归档。判读与完整叙事见 `../01_batch_c_execution_plan_draft.md` §1/§7(F-1~F-6+三 reseal 批)。

- `probe_N/`:发射脚本+probe 日志+cell.json(probe_8/9/10 三个,批C 首批落地)+mem.csv(1s 采样)。
- `probe_7/run.log.gz`:CP-SAT 全日志(F-6 枚举循环定案的证据主体,63M→5.3M)。
- §1b 两臂(6×7/7×6)的原始 CP-SAT 日志(19M/18M gz)不进仓库:本地 `~/zmd_experiment_logs/batch_c_20260713/`(6TB 大盘 2026-07-13 只读挂载未能转存;下次 rw 挂载时迁移)。
- probe_8 的 mem.csv 前段含 14:31 首发夭折期采样;有效段从 14:45 起。
- 内存统计口径:重复 header 行会污染 awk 数值比较(analyze_ptm_burnin.py 同款坑),统计一律先 parse-int 再入表。
