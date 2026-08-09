# Round 4/5 bespoke coordinate master 修正语义重验（2026-07-19）

> 承 `01_historical_rejudgment_addendum.md` 的 RND-06/RND-07 重验义务，以及 `04`、`05` 号文档的 rounds 第 3 梯队。本轮只新增研究 harness 和未跟踪原始输出；未修改 `src/`、`rules/`、`data/`、`PROJECT_LOCK.md`，未 reseal、未写强状态。

## 0. 一句话结论

修正后的 identity-front、82,829 新池、628 个 routing-visible 实体口下，bespoke front-clear coordinate master 仍保持紧凑：三个锚点均为 **10,816 variables / 16,513 constraints / 4,083,135-byte Proto**，独立语义与 Proto 拓扑 oracle 全绿。六条固定臂（600s + 1,200s）全部 clean 完成，但三锚点仍全为 `UNKNOWN`。

因此：

- **RND-06 的重验动作已完成**：旧模型结果不再承载结论；当前哈希闭合的新模型重新确认“模型小、当前固定 profile 在 1,200s 内证不动”。
- **没有产出上界证书**：无一臂为 `INFEASIBLE`；`UNKNOWN` 对锚点可行性没有结论。
- **RND-07 的 corrected-front baseline 已完成，广义条目仍需重验**：307,092 个 front→body rectangle references 在新语义下重新算实，但旧记载的 18–20 GiB 内存墙没有在当前模型/profile 复现，本轮峰值仅 1.443 GiB；“结构墙、solver 攻法用尽”仍维持撤回。能说的只有本轮固定 strict-lean profile 在这两个时限内仍不收敛。

## 1. Campaign 身份与输入闭合

原始输出根：

`.artifacts/front_offset_incident_20260718/round45_bespoke_coordinate_master/r45-6120809f5de8b4f5/`

| 项 | 钉值 |
| --- | --- |
| campaign id | `r45-6120809f5de8b4f5` |
| campaign canonical identity digest | `6120809f5de8b4f5612ee2a9528e301d1ce34fe6c985027b7421b8514e2f2ff2` |
| `campaign_spec.json` file SHA-256 | `00043d24c068071027685379da24f92c3b039951c19843f53951d333f27cda6d` |
| source/input closure SHA-256 | `8cda8b17b71c297ca23a3ca485a585f0981fd3cb34b2e25379edbb6a1d2e55fd` |
| final `summary.json` SHA-256 | `bc3d122122179549f1d75d1f30321130c7081d4743b9a48ce52804dd63b65e66` |
| Git HEAD at prepare | `2b5a91a13935b2d7fa8abb9c340b76cf89015cc3`（dirty tree 已逐项记录在 spec） |
| semantic label | `identity_front_newpool_f05b1291_physical_protocol_ports` |
| Python / OR-Tools | 3.13.13 / 9.15.6755 |

五个输入钉值：

| 输入 | SHA-256 |
| --- | --- |
| `candidate_placements.json` | `f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3` |
| `mandatory_exact_instances.json` | `545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6` |
| `generic_io_requirements.json` | `ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e` |
| `canonical_rules.json` | `5012845367e2a0e0b51938cc36a18f46fcdc8daccfa34639f96a05a67dc12a05` |
| `preprocess_plan.json` | `5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee` |

六臂各自在求解前后重算 closure；`closure_same_all_arms=true`，无运行中漂移。

## 2. 修正后的松弛与 soundness 边界

### 2.1 正规形

任取同一 ghost 矩形下的 live 可行布局，可做如下只删不增的正规化：

1. 保留全部 266 个 mandatory facilities（19 groups，body area 3,544，其中 219 个需供电）；
2. 两个 generic-input 商品各需一个实体输入口，只保留实际承载它们的协议箱并取并集，所以 active boxes 至多 2；中枢的 14 个实体输入口也可直接担当 provider；
3. 对每个保留的受电 body 选一根 live covering pole，再取这些 pole 的并集，所以 active poles 至多 `219 + active_boxes <= 221`；
4. 保留 628 个 routing-visible 实体口 witness：312 in（310 fixed + 2 generic）与 316 out（264 fixed + 52 generic）；
5. 忘掉 belt 连通路径，只保留 body、供电覆盖、ghost/body 互斥及 active stored-port 格不落 body 的必要条件。

模型采用 stored-port identity 语义：stored 口格就是带子 witness 格。未激活口即使越界也不否决 pose；只有实际选中的实体口需要在 70×70 内且不落任何 active body。ghost 只与实体 body 互斥，不阻塞 front。模型没有全局 front `AllDifferent`，允许不同物理口共享同一带子格；仅对两个有商品标签的 generic-input witness 保留“同 provider 时必须是不同实体口”的必要约束。

因此当前模型 `M` 是 live 问题的松弛：

`live feasible => normalized M feasible`。

其逆否命题给出窄证书规则：只有当本模型在某锚点 **clean `INFEASIBLE`**，且输入、源码、模型、oracle、进程退出与输出哈希门全部通过时，才可把该锚点记为研究级合法上界候选。它仍不是 sealed `CERTIFIED_INFEASIBLE`。`FEASIBLE` 也只会是松弛 witness，不是 live 布线 witness；`UNKNOWN` 什么也不证明。

### 2.2 独立 oracle 与 Proto 拓扑门

oracle 不复用 builder 的汇总数，直接对照 production `routing_visible_port_demands`、mode token、operation profiles、当前池几何与 `PROJECT_LOCK.md` 的 RFSC 空集合同。核心重算结果：

- 82,829 poses、21 modes、266 mandatory、19 groups；
- 628 witnesses、最多 489 bodies、`628 x 489 = 307,092` front→body references；
- full ghost-anchor domain：7×7 为 4,096 个原点，6×8 与 8×6 各 4,095 个；
- 628 条 per-front body-clear `NoOverlap2D` 加 1 条 body+ghost `NoOverlap2D`；
- 无 front-front mixed、无 ghost-front mixed、无全局 front `AllDifferent`；
- optional box 的反向使用蕴含、active-prefix/严格序、conditional power，以及 221 个 designated pole coverer 均从 Proto 逐项核对。

最终 constraint histogram 固定为：

| kind | count |
| --- | ---: |
| `bool_or` | 2 |
| `element` | 663 |
| `exactly_one` | 270 |
| `interval` | 2,236 |
| `linear` | 11,813 |
| `no_overlap_2d` | 629 |
| `table` | 900 |

三锚点 `CpModel.Validate()` 均为空错误，oracle `certificate_eligible=true`。这只说明若未来得到 clean `INFEASIBLE`，模型有资格进入上界判读；本轮没有触发该分支。

## 3. 模型规模与 Proto 身份

| anchor / seed | variables | constraints | Proto bytes | Proto SHA-256 | prepare HWM |
| --- | ---: | ---: | ---: | --- | ---: |
| 7×7 / 71 | 10,816 | 16,513 | 4,083,135 | `5fe0c314b879bf1ec224dd99798deff711f694585169fd8c4fb5acc9136a1ead` | 911,332 KiB |
| 6×8 / 72 | 10,816 | 16,513 | 4,083,135 | `54c04ecd527609e2951b04ae0255c03bc1c006ec06223e58224fd58cbed953d7` | 911,364 KiB |
| 8×6 / 73 | 10,816 | 16,513 | 4,083,135 | `ccdcd5703ef81404d24a30f3b08aae828ea29c91bcc943d01e3cba10a05fc7ef` | 910,868 KiB |

每个锚点的 600s/1,200s 两臂 Proto SHA、字节数、变量数和约束数逐字一致；`model_same_by_anchor=true`。solve gate（500K vars / 8 GiB build HWM）和硬墓碑（1M vars / 2M constraints / 10 GiB build HWM）均有大余量。

## 4. 六臂结果

固定 profile：`strict_lean`、1 worker、`PYTHONHASHSEED=0`、无旧 hint；probing level 0、probe DT 0.05、presolve iterations 1、linearization 0、merge-no-overlap work 0、solver internal memory 10,000 MiB。

| run key | terminal / solver | run wall | solver wall | branches / conflicts | deterministic time | cgroup RAM peak | swap peak |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `g7x7-t600-s71` | `CLEAN_UNKNOWN / UNKNOWN` | 630.205s | 600.040s | 409,449 / 466 | 206.386 | 1.441 GiB | 0 |
| `g6x8-t600-s72` | `CLEAN_UNKNOWN / UNKNOWN` | 630.516s | 600.024s | 410,970 / 466 | 206.984 | 1.433 GiB | 0 |
| `g8x6-t600-s73` | `CLEAN_UNKNOWN / UNKNOWN` | 630.141s | 600.014s | 408,899 / 466 | 205.818 | 1.436 GiB | 0 |
| `g7x7-t1200-s71` | `CLEAN_UNKNOWN / UNKNOWN` | 1,230.234s | 1,200.036s | 765,729 / 530 | 419.328 | 1.434 GiB | 0 |
| `g6x8-t1200-s72` | `CLEAN_UNKNOWN / UNKNOWN` | 1,230.468s | 1,200.035s | 767,933 / 530 | 420.389 | 1.440 GiB | 0 |
| `g8x6-t1200-s73` | `CLEAN_UNKNOWN / UNKNOWN` | 1,229.572s | 1,200.029s | 751,122 / 527 | 410.078 | 1.443 GiB | 0 |

六臂均为 fresh process / attempt `a01`，worker exit 0，stderr/stdout 为空，result、run-record、terminal 与输出哈希全通过。`memory.events` 的 `high/max/oom/oom_kill/oom_group_kill` 六臂均为 0；无任何重叠 service，`no_overlap_observed=true`。

最终 cgroup 合同按已验证的安全上限设置为：

- `MemoryHigh=34G`（软回收/节流线，不是最大值）；
- `MemoryMax=38G`（RAM charge 硬墙，触墙时先回收并可把匿名页换出）；
- `MemorySwapMax=16G`（独立 swap 上限）；
- `OOMPolicy=continue`。

本轮实际峰值远低于 34G，且 swap 为 0，所以终态不受 cgroup 节流、换页或 OOM 混淆。

## 5. RND-06 / RND-07 重判

### RND-06 — 重验完成，窄结论恢复

旧 10.7K 模型来自 offset-front、旧池和旧端口账，继续不具权威性。本轮用当前输入和源码闭合后重建为 10,816 / 16,513，并按同 seed、1 worker、600s/1,200s 完成六臂。结果重新支持两条窄事实：

1. 当前 necessary-condition master 的确紧凑且能在约 1.44 GiB 内稳定运行；
2. 当前固定 strict-lean profile 在三个真锚点上到 1,200s 仍全 UNKNOWN。

但“锚点不可行”“已有上界证书”均不成立。

### RND-07 — corrected-front baseline 完成；广义条目仍需重验

600s→1,200s 大致把 branches 和 deterministic time 翻倍，只把 conflicts 从 466 提到约 527–530，三锚点终态没有变化。修正模型下重新得到 UNKNOWN，且六臂 `memory.events` 全零、swap 全零，因此本轮终态不是当前 cgroup 内存限制造成的。

但本轮没有重跑历史全部参数、对称、分解、多 worker 或替代编码矩阵；旧 18–20 GiB 内存墙在当前模型/profile 下未复现，因此不得作为当前结构墙证据继续继承——这不否定它是旧错误模型上的历史观测。故只可记“本 profile 在本预算内不收敛”，不得升级为“CP-SAT 结构性不可解”“加时间必无效”或“solver-tractability 工程已穷尽”。这些战略判词继续撤回，RND-07 若要恢复更广结论仍处于需重验状态。

## 6. 验收与剩余边界

最终代码面验收：

- Round45 focused pytest：`49 passed in 87.43s`；
- `preflight_gate.py --full`：19/19 PASSED，pytest `4594 passed, 74 skipped`；
- `preflight_gate.py --slow-tests`：PASSED，`31 passed, 4668 deselected`；
- Ruff：通过；
- strict clean-room external bundle deterministic check：5 files 通过；
- campaign：`COMPLETE 6/6`，`campaign_integrity_valid=true`、`all_selected_attempts_integrity_valid=true`、`closure_same_all_arms=true`、`model_same_by_anchor=true`。

剩余认识论边界：

- 三个锚点实际可行还是不可行，仍未知；
- 本模型忘掉 belt connectivity，故未来 `FEASIBLE` 也不能当 live witness；
- 三锚点的结论不能自动外推为全局面积上界；
- 本轮没有生成、修改或封存 production certificate；
- 若继续推进，必须选择新的、明确授权的可解性杠杆或证明技术，不能把本轮 UNKNOWN 改写成不可行结论。
