# refute 席材料存档（2026-08-06）

来源：codex refute 席对 commit 88c0911 报告的对抗审查（任务书由主线程下发；
原始产物在 flowbound 会话 scratchpad `refute_flowbound/`，本目录为耐久拷贝）。

| 文件 | 内容 |
|---|---|
| `probe_front_state_sharing.py` | **核心引理反例探针**（canonical 位姿 + PortBindingModel + RoutingSubproblem 真模型驱动）：三个 gadget 全 FEASIBLE——splitter 1 产口 2 耗口、merger 2 产口 1 耗口、merger 3 产口 1 耗口，坐实「一个 state ≤1 产口 front + 1 耗口 front」引理 REFUTED |
| `front_state_sharing_receipt.json` | 反例收据（输入 sha 钉死、canonical 几何：planter_buckwheat pose 7793 / crusher_buckwheat 8851 / seed_collector_buckwheat 9086 三机身不重叠共 front (35,35)，绑定 FEASIBLE、残流 1/2+1/2） |
| `front_state_counterexample.py` | 最小独立版反例（合成位姿直驱 routing 模型） |
| `probe_rerun_by_flowbound_stdout.log` | flowbound 线亲手复跑记录（2026-08-06，HEAD eea45ae，VERDICT=REFUTED 复现） |
| `independent_power_ip_probe.py` / `_receipt.json` | K=396 的 SCIP 双档交叉验证（无库存帽/库存帽两档一致，P_min=9 独立复现）——OB4 收据的外部互证件。**收据已于二轮复核后重跑刷新**（`_rerun2_stdout.log`）：一轮原收据 pin 的是修正前 OB4 收据哈希（3c7e9c99…），刷新后 pin 当前哈希（d6c44dff…），数学结论逐字不变、仅 provenance 闭合 |
| `independent_power_ip_probe_rerun2_stdout.log` | 上述二轮刷新跑的 stdout（K=396 双档复现） |
| `followup_g_ledger_probe.py` / `_stdout.log` | **二轮 followup 探针**（本线复跑存档）：①dense_hyperedge——四口 merger 一个 state 吃下 4 口（ports−matching=3 vs 实际 1），击穿 G1 的普通匹配形式，坐实必须用超边 packing（w=\|e\|−1）；②四场景 L1 共置判定——splitter+垂直 L1、merger+垂直 L1、直带+平行 L1 全 INFEASIBLE、仅直带+垂直 L1 可行，钉死 G1×OB6 局部互斥 SOUND |

对报告的影响与修正见上级目录 `AREA_BOUND_THEOREM_REPORT.md` §5.4（负结果归档）、
§5 G1/G1×OB6（二轮修正后的正确形式）与修订记录。
