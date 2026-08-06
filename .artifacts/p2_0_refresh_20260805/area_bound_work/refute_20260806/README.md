# refute 席材料存档（2026-08-06）

来源：codex refute 席对 commit 88c0911 报告的对抗审查（任务书由主线程下发；
原始产物在 flowbound 会话 scratchpad `refute_flowbound/`，本目录为耐久拷贝）。

| 文件 | 内容 |
|---|---|
| `probe_front_state_sharing.py` | **核心引理反例探针**（canonical 位姿 + PortBindingModel + RoutingSubproblem 真模型驱动）：三个 gadget 全 FEASIBLE——splitter 1 产口 2 耗口、merger 2 产口 1 耗口、merger 3 产口 1 耗口，坐实「一个 state ≤1 产口 front + 1 耗口 front」引理 REFUTED |
| `front_state_sharing_receipt.json` | 反例收据（输入 sha 钉死、canonical 几何：planter_buckwheat pose 7793 / crusher_buckwheat 8851 / seed_collector_buckwheat 9086 三机身不重叠共 front (35,35)，绑定 FEASIBLE、残流 1/2+1/2） |
| `front_state_counterexample.py` | 最小独立版反例（合成位姿直驱 routing 模型） |
| `probe_rerun_by_flowbound_stdout.log` | flowbound 线亲手复跑记录（2026-08-06，HEAD eea45ae，VERDICT=REFUTED 复现） |
| `independent_power_ip_probe.py` / `_receipt.json` | K=396 的 SCIP 双档交叉验证（无库存帽/库存帽两档一致，P_min=9 独立复现）——OB4 收据的外部互证件 |

对报告的影响与修正见上级目录 `AREA_BOUND_THEOREM_REPORT.md` §5.4（负结果归档第 3 条）。
