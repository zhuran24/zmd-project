# P1.3 M4 开工侦察材料（2026-07-08）

M4（F2-F7+F9 逐族阶梯 + 两横切件）开工前的九路侦察报告存档。七路 Fable + 一路 codex（f9，配额耗尽前完成）+ 一路 D2 追加侦察。全部带真实签名 + 行号级硬事实（行号以当日 HEAD 为准，后续 M4 各批 reseal 后会漂移——结论仍有效，行号仅当叙事线索）。

M4 落地结果见 `cc_memory_vnext/cards/p1-3-m4-ladder-landed.md` 与 commits `aad0a7a`→`951b4f2`→`bb952ee`。

## 文件索引

| 文件 | 内容 | 长期价值 |
|---|---|---|
| `f4f2.md` | F4（component_reach）+ F2（cutset）翻译形态侦察 | **owner 拍板材料**：F2 三重死结（吞吐量纲违锁 / 单层图 vs 双层桥未 reconcile / route schema P1.5+）、F4 缺 commodity route registry 的详细论证 |
| `f3f7.md` | F3（port_exposure）+ F7（power_cover）+ 等价回归形态 | **owner 拍板材料**：F3 v1.0 无 active_port_witness → 直译过切的论证；F7 三层等价回归方案（已落地） |
| `f9.md` | F9（density_envelope）被 Phase 1.2 决策绞死的出处 | **owner 拍板材料**：解封条件（PROJECT_LOCK:453-461，需与 F5 同类 replayable proof 升级） |
| `f5.md` | F5 orbit lift 七项规格 + Q1a 五段合同 + R1-R10 红测定位 | D1-D4 实施依据 |
| `f6.md` | F6 baseline packing 契约 + override 来源问题 | M4-B 实施依据；首个点出 F1 anchor 条件性洞交叉信号的报告 |
| `poseMap.md` | pose_id→pose_idx 映射层五个 alias 陷阱 | M4-A 实施依据 |
| `budget.md` | cut 总量预算 + CutStore eviction（要点版；全文两段在会话记录） | 三大纠偏：CutStore 不在生产 attach 路径 / CP-SAT 约束不可删→满即停发是唯一 sound eviction / V82 不是锁条款是 README+checker 结构封堵 |
| `d2_binding_adapter.md` | D2 追加侦察：binding 两种 INFEASIBLE 的提升语义 | **soundness 核心发现**：demand 等式型反单调不可 lift（生产 binding_infeasible 分支全是它），empty-domain 型是唯一 liftable——binding_empty_domain_v1 adapter 的定型依据 |
| `m5_harness.md` | M5 实测入口面侦察 | M5 harness（`../p1_3_m5_convergence_20260708/`）的合法性论证与设计依据：直调路径绕 env 门是设计属性、每 cell 子进程隔离、输出合法性红线 |

## 未接四族的终态处置（等 owner 拍板，不阻塞）

- **F2**：出路 = P2.0 吞吐轴 or owner 拍板连通弱化语义（材料 `f4f2.md`）
- **F3**：出路 = Phase 1.5+ witness 机制 or master 侧窄化版（材料 `f3f7.md`）
- **F9**：解封 = cert 证明机制升级（材料 `f9.md`）
- **F4**：跟 P1.5+ commodity route registry 拍板走（材料 `f4f2.md`）
