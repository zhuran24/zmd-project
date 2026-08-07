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
| `followup_g_ledger_probe.py` / `_stdout.log` | **二轮 followup 探针**（本线复跑存档）：①dense_hyperedge——四口 merger 一个 state 吃下 4 口（ports−matching=3 vs 实际 1），击穿 G1 的普通匹配形式，坐实必须用超边 packing（w=\|e\|−1）；②四场景 L1 共置判定——splitter+垂直 L1、merger+垂直 L1、直带+平行 L1 全 INFEASIBLE、仅直带+垂直 L1 可行，钉死 G1×OB6 局部互斥 SOUND。**复跑注意：探针不自注根路径，须 `PYTHONPATH=/home/zhuran24/zmd-pj`（从仓库根裸跑实测 ModuleNotFoundError）** |
| `canonical_mixed_source_hyperedge.py` / `.log` / `_rerun_by_flowbound.log` | **三轮探针**：canonical 局部反例——grinder_fine_buckwheat pose 3961 + molding_bottle pose 8581 两机身不交、同 front (35,35) 的两个**异商品**产口，binding FEASIBLE、残流 1/2+1/2=1 合容量 ⇒ 超边定义的「同商品」全局要素被驳倒（source-only 超边须允许跨商品，依据 canonical `mixed_commodity_flow`；sink front 仍须纯流）。脚本自注根路径、无需 PYTHONPATH。**四轮起耐久副本由本线补真实 PortBindingModel 自证段**（原探针只验口存在性/互斥/容量，binding FEASIBLE 当时由 refute 席独立复验；原始输出见 `.log`，自证版输出见 `_rerun_by_flowbound.log`：status=FEASIBLE、两异商品 out spec 同现 front） |
| `hypergraph_packing_audit.py` | **三轮探针**：G1「普通 cover 等价」审计——重叠 cover 反例（**全部 singleton 边** + {a,b,c} + {c,d,e}：普通 cover=2、最小精确分割=packing 公式=3），坐实端口 exact-one 下正确对象是增广族 E⁺ 的精确覆盖/超边分割 |

对报告的影响与修正见上级目录 `AREA_BOUND_THEOREM_REPORT.md` §5.4（负结果归档）、
§5 G1/G1×OB6（二轮修正后的正确形式）与修订记录。
