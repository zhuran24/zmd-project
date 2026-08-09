# front 错位事故历史重判附录（2026-07-18）

## 1. 适用范围与判定规则

本附录对 `history.json` 中 8 类、40 条历史 finding 作逐项落账。Batch 3+5 已以提交
`9c0f724` 完成模型修复与换钉；该提交修复的是当前模型，**不会自动恢复旧模型产出的数字、
证书或全称结论**。状态含义如下：

源账为 `.artifacts/front_offset_incident_20260718/history.json`（24,009 bytes，
SHA-256 `d7669e53b936a8d1861f83d112b1e6e7516ff005b772fe7df8f0d46da022228c`）；
事故因果链与批次边界见 [`00_incident_survey_and_fix_plan.md`](00_incident_survey_and_fix_plan.md)。

| 状态 | 数量 | 审计含义 |
| --- | ---: | --- |
| 作废 | 16 | 旧结果不再具有业务或证明效力；只能作为事故史料保存。 |
| 需重验 | 12 | 结论继续保持撤回，须在修复模型、原可比配置和独立规则 oracle 下重跑后才能恢复。 |
| 不受影响 | 12 | 指定的结构、方法或工具结论可保留；不得外推为相关 front 结果仍有效。 |

## 2. M5 生产跑（1 作废／1 需重验／1 不受影响）

### M5-01 — 需重验

- **结论**：仓内没有找到真实 production `CANDIDATE_PROPOSED` 及 binding/routing PASS 工件；现有记录仅证明 master 未产候选及后续 campaign smoke 状态。
- **动作**：查找仓外 checkpoint、proposal marker、candidate bytes 或完整日志；找不到则删除“已有 M5 proposal/PASS”的历史说法，禁止用 master OPTIMAL 代替。

### M5-02 — 作废

- **结论**：即使外部 proposal 存在，旧 binding、routing 与 fixed-witness PASS 也使用错位 front，不能证明真实游戏可行；proposal 本身亦非 durable `CERTIFIED`。
- **动作**：废弃旧 PASS，仅可把 placement bytes 作为待验输入；重跑 binding、routing、terminal fixed-witness 和 sink replay，禁止续 seal。

### M5-03 — 不受影响

- **结论**：默认参数非病态、fixed/probing/symmetry 切刀和约 60 GiB 出解尖峰属于 master 参数与资源归因，不依赖 front-clear。
- **动作**：保留资源结论，但不得把 master OPTIMAL 写成游戏可行或 `CANDIDATE_PROPOSED`。

## 3. RAB-SEP 三段批（3 作废／1 需重验／1 不受影响）

### RAB-01 — 需重验

- **结论**：命题 N 的抽象方向可能成立，但旧审查验证的是 `port+delta` 的体外第 2 格，不是实际口前格。
- **动作**：以 port 坐标自身重述命题，复核 active-domain、adherence、post-solve connectivity，并加入第 1/第 2 格互换与共享中格反例。

### RAB-02 — 作废

- **结论**：旧 EMPTY_DOMAIN 证书、瘦 fallback sound 结论和 certified allowlist 资格均依赖错位 blocker，可能删除合法布局。
- **动作**：废弃旧证书业务效力并撤下旧资格；在修复模型上重做逐 pattern 拒因、blocker 完备性和独立可行反例验证。

### RAB-03 — 作废

- **结论**：固定占据 98.5%、0.07 秒剪 98.7%、219/219 空域、1,293 cuts 及 core 分布等数字全部统计了第 2 格。
- **动作**：撤销全部数字；对相同 frozen placements、六轮布局及相同 seed/cap 重跑 corrected-front RAB。

### RAB-04 — 作废

- **结论**：“binding 枚举为零、每次重解学习约 215 族、F-6 踏车被结构性绕开”实际由错误 EMPTY_DOMAIN 触发。
- **动作**：废弃战役结论；做 RAB OFF/ON 同 revision 对照，重采枚举轮数、真实 EMPTY_DOMAIN、routing attempts、cut 接纳率和收敛性。

### RAB-05 — 不受影响

- **结论**：证书必须完整列出 owner/blocker、归因不全 fail-closed、ghost 不进占据等 F-BL-R11-01 工程纪律与坐标平移无关。
- **动作**：保留结构守卫并复用于新证书；不得用它替旧证书恢复效力。

## 4. Front-Clear Lift（2 作废／3 需重验／1 不受影响）

### FCL-01 — 需重验

- **结论**：filter-empty 与 free-front 计数不足的组合证明骨架可能保留，但旧 front 集及其全池前提均针对错误坐标。
- **动作**：改用 port 坐标，重验同侧唯一性、边界、共享中格、矩形 footprint 和 filter/count 双向等价。

### FCL-02 — 作废

- **结论**：F-GM-FCL-01 明确计算 `port+delta`，不能继续作为 sound 上界剪枝。
- **动作**：废弃旧语义背书；使用 identity 索引，补共享中格哨兵、全池 differential 和独立 reverifier，并在 reseal 后重新申请启用。

### FCL-03 — 作废

- **结论**：45 哨兵、286,636 pose、1,314 corpus、1,294 空域与 20 负控等“零 mismatch”只证明多个组件共享同一错误定义。
- **动作**：撤销其游戏语义证明力；三面验证全部重跑，并使用不共享生产坐标 helper 的异构 oracle。

### FCL-04 — 不受影响

- **结论**：demand SSOT、双 NoOverlap、ghost 隔离、env 值域、clone identity、诊断不污染 proof、reseal 与 OFF-path 隔离均可复用。
- **动作**：保留这些工程资产；坐标变化后仍须重跑门禁与 reseal。

### FCL-05 — 需重验

- **结论**：probe 2/3/4 的 presolve 展开、两次 30 分钟 UNKNOWN 及“fixed 不是残余瓶颈”均来自旧 FCL 模型。
- **动作**：按原配方重跑，记录 proto、branches/conflicts、RSS/swap、incumbent 和终态；旧 UNKNOWN 不得外推。

### FCL-06 — 需重验

- **结论**：23h50m44s UNKNOWN 只是真实记录了错误模型性能，不能支持“时间杠杆已死”。
- **动作**：先做修复模型短档基线；确认 proto/内存合理后再决定是否重跑 24 小时，期间结论保持撤回。

## 5. Round 1–5（4 作废／3 需重验／2 不受影响）

### RND-01 — 作废

- **结论**：约 1,499 次 routing precheck rejection、零 routing attempts 及“真墙”定位直接来自第 2 格检查。
- **动作**：废弃瓶颈定位与数字；用相同 6×6/6×7/7×6、cap 和 seed 重跑。

### RND-02 — 作废

- **结论**：1,240 格需求、-38 缺口和 46/45 打包结论把 port 误作 connector 后又前移一格，且未允许相对口共享中格。
- **动作**：撤销旧算术；按 body 与使用中 port 坐标的并集重新计算。

### RND-03 — 作废

- **结论**：`front_blocked=582/620`、剪掉 16,987/16,992 patterns、216/266 binding 空域及 routing fatal 均查错格。
- **动作**：废弃数字和 fatal 判定；对同一 placement 重建 binding/RAB 后再进入 connectivity。

### RND-04 — 作废

- **结论**：582→138、138→104、83–85 地板和 PASS 163/FAIL 56 均由同一错位 predicate 得出；所谓独立复算只是同错复现。
- **动作**：撤销整组数字；重跑两个构造器、joint pose+binding 优化及独立规则 verifier。

### RND-05 — 需重验

- **结论**：“必要条件成立则 lifted INFEASIBLE 可作原问题上界”的逻辑模板仍成立，但旧必要条件及 sound 审查实例均错误。
- **动作**：重证“真实可行蕴含 lift 条件”，并重做计数等价、全池前提、共享格反例和独立 UNSAT 复验。

### RND-06 — 需重验

- **结论**：三锚点 10.7K-variable lifted master 的 `UNKNOWN@1200s` 来自旧模型，不能继续支持“证书小且 sound、仅 solver 证不动”。
- **动作**：按相同 seed、worker 和 600/1,200 秒档重跑，重新报告变量、约束、RSS 和终态。

### RND-07 — 需重验

- **结论**：303K rectangle refs、18–20 GiB 及“结构墙、solver 攻法用尽”无法跨越几何模型变更继承。
- **动作**：继续撤回战略判词；先建立 corrected-front profile，再选择值得复跑的对称、分解和参数臂。

### RND-08 — 不受影响

- **结论**：area-42 witness 加三个不可行锚点、经 up-closure 闭合的四实例条件式规约不依赖 front 坐标。
- **动作**：保留规约结构；四个组件的实际状态仍须在修复语义下重跑。

### RND-09 — 不受影响

- **结论**：620 个 routing-visible 端口需求及“吞吐不能替代连通性”的窄定理与 front 坐标无关。
- **动作**：保留结论，但不得据此恢复旧 front 预算或锚点判死。

## 6. Witness 构造战役（3 作废／1 需重验／0 不受影响）

### WIT-01 — 作废

- **结论**：两格纵深、5,400/4,750/4,100 面积账和 3% 余量均来自错误两层解释，也漏掉相对口共享。
- **动作**：撤销面积账；按 body 与使用中 port 坐标的集合并重算。

### WIT-02 — 作废

- **结论**：greedy/comb/skyline/BL/CP-SAT 的 193–241 各项战绩和排名均以 `port+delta` 作为保留 front。
- **动作**：废弃排名表；使用相同 ghost、排序、seed、hint 和预算重跑各构造器。

### WIT-03 — 作废

- **结论**：“12 发零违规、构造器与 binding 一致”是构造器和审计共享错误 `port_front_status` 的共模假绿。
- **动作**：废弃零违规证书；建立不调用生产 helper 的审计，覆盖两种第 1/第 2 格互换和相对口共享。

### WIT-04 — 需重验

- **结论**：三次 CP-SAT UNKNOWN、30 分钟 LNS 弱于贪心、229–241 工具谱地板及 hardness 判断都依赖错误构造域。
- **动作**：重跑可行性与 maximize 臂；新上限分布和独立零违规审计产生前，战役优先级判断保持撤回。

## 7. Proof-Logging PB（1 作废／1 需重验／1 不受影响）

### PB-01 — 作废

- **结论**：旧 6×6 `UNSATISFIABLE` 不仅继承第 2 格几何，还把 front-clear
  条件的 RHS 写成 `d-|F|`；正确式为 `-d*x-sum(occ) >= -|F|`。旧 OPB
  因此独立地过约束，并非真实锚点的预期松弛。
- **动作**：丢弃旧 UNSAT 与 proof 的业务效力；用修正坐标和修正代数重建
  OPB，先过不导入 encoder 的 translation gate，再求解并验证完整 proof。

### PB-02 — 不受影响

- **结论**：RoundingSat 产 PBP、VeriPB 3.0.2 验证 proof，以及“证书只证明给定 OPB”的信任边界仍成立。
- **动作**：保留工具链，并把独立 translation gate 设为业务证书前置条件。

### PB-03 — 需重验

- **结论**：66,136 vars、240,904 constraints、25 MiB 及“项目首份机器可查 INFEASIBLE 证书”均绑定旧 OPB；60×60 smoke 只证明互操作。
- **动作**：重算规模；若恢复“首份项目证书”称号，必须新增独立业务翻译审计。

## 8. 五月 24 Lever 历史（2 作废／2 需重验／4 不受影响）

### MAY-01 — 作废

- **结论**：每轮约 500–610 `front_blocked` 和“所有 candidate 均系统性堵”直接统计第 2 格。
- **动作**：撤销数字和普遍化结论；重放相同 anchors 与 iterations。

### MAY-02 — 作废

- **结论**：47,666 个约束、十个 `INFEASIBLE@47–56s` 及对应约束集均检查错格。
- **动作**：废弃全部数字与状态；如需历史对照，以 port 坐标重建后重跑。

### MAY-03 — 不受影响

- **结论**：master 不知道 binding 最终激活哪些 port，因而假定所有 port active 会超杀；这个量词错误不受坐标平移影响。
- **动作**：保留逻辑证明，示例数字改用修复语义。

### MAY-04 — 需重验

- **结论**：Phase 6 两路径及 Lever 24 的变量/约束、时长、UNKNOWN 和 32 GiB RSS 均使用旧 channel/blocker。
- **动作**：重跑代表性 path-1、path-2 和单商品 Lever 24 cheap gate，重报规模、RSS 与终态。

### MAY-05 — 不受影响

- **结论**：channel 按 pose×port×commodity 增长，以及删除任一维度会损害 exactness、规则真源或问题本体的复杂度教训不依赖 front 平移。
- **动作**：保留渐近结论，并与待重验的 benchmark 常数分开记录。

### MAY-06 — 需重验

- **结论**：“24 lever 全 dead、范式调查已穷尽”是被多个 front-dependent 证据污染的全称判断。
- **动作**：重建 lever ledger，只重跑受污染项并保留纯 master/power/area/resource 项；完成前全称结论保持撤回。

### MAY-07 — 不受影响

- **结论**：L1–L14 中的 master、面积、power、cut 粒度结论及 L16 振荡主要不依赖 front。
- **动作**：保留这些局部结论，不得外推为 24 项仍全部 dead。

### MAY-08 — 不受影响

- **结论**：共享编码会相关同错、hash/size pin 不证明语义、文档入口会漂移，以及 cut lifecycle/schema/validator/reseal 等教训仍成立。
- **动作**：保留并强化：把 port 坐标契约、spec 示例及第 1/第 2 格反例纳入独立 named-TCB 与文档漂移检查。

## 9. Cut 框架工程线（0 作废／0 需重验／2 不受影响）

### CUT-01 — 不受影响

- **结论**：typed registry、resolver、step8、typed lowering、semantic dedup、ledger/epoch，以及 F1/F6/F7 和 shadow-only F5 均不读取 port front。
- **动作**：保留编排与信任边界；不得把该保全结论外推为任何新 front 命题已 sound。

### CUT-02 — 不受影响

- **结论**：批 C 的 int/string orientation 归一化使 frozen pool 投影忠实镜像 live master，与 `_DIR_DELTA` 无关。
- **动作**：无需重跑；修复后的工件变化不得误归因于 orientation adapter。

## 10. 恢复条件与留痕要求

任何“需重验”项恢复前，重跑记录至少应钉住 revision（含 `9c0f724`）、输入 hash、seed、
worker、时限、环境、生产模型摘要和独立 oracle 版本，并保存原始终态与资源指标。任何“作废”
项即使新实验得到相似数字，也只能形成新 revision 下的新结论，不能给旧证书或旧数字追认效力。

## 11. 阶段性复验索引（2026-07-18）

本轮已完成项、证据 hash、失败终态和未执行项统一记录在
[`02_batch4_revalidation_results.md`](02_batch4_revalidation_results.md)。该记录只新增当前 revision
下的诊断证据，不自动改变本附录 40 条账目的三态裁决；特别是 FCL 生产臂、Round 1–5 与 PB
可验证证明仍未完成。
