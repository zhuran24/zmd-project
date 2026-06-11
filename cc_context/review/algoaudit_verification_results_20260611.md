# 算法 soundness 换方向审查 · 验收结果（2026-06-11）

## 背景

V80–V99 共 19 轮外审全部审「交付工件能否被伪造成 CERTIFIED」（反伪造外壳，路 A），收敛到极窄壳层缝、clean 连击 0。owner 直觉 + c 调研报告（`cc_context/review/proof_carrying_workload_assessment_20260611.md`）诊断：真缺陷在没人审的求解器核心。遂换方向，发 3 个正交 prompt（A=Benders/LBBD、B=几何/master、C=子问题/cut oracle），明确要求**放下伪造交付工件、只审求解器算法/建模本身对不对**。A 不慎开了两条独立会话（交叉验证）。共 8 个 finding。

验收方法：A-1 由 CC 主会话自核原始代码坐实；其余 7 个由 workflow 7 agent **对抗式**核原始代码（默认怀疑、尽力证伪、找 GPT 漏看的缓解约束），禁止跑 pytest（避免并行 `.pytest_tmp` 互删），纯静态判别。

## 最终判别表

| # | finding | 判别 | 定级 | 默认 certified 路径 |
|---|---|---|---|---|
| A-1 | routing CP-SAT 局部连续 ≠ 全局连通 | ✅ confirmed（CC 自核） | **P0 false-CERTIFIED** | 是 |
| B-01 | coordinate master no-overlap/ghost/power 用模板固定尺寸而非候选 pose 真实 footprint | ✅ confirmed | **P0 false-CERTIFIED** | 是（38×manufacturing_6x4 + 46×boundary_storage_port 真实强制实例） |
| A-2 | front_blocked precheck（binding-local 证据）跳过 binding 枚举直接铸 master pose-presence nogood | ✅ confirmed | **P0 false-INFEASIBLE → 漏真最大矩形 = objective-level false CERTIFIED** | 是 |
| C-3 | F2 cutset oracle edge_capacity=1 忽略 elevated bridge 层（真实 2 层容量） | 🔶 likely_real，机制真但 **dormant** | P1 latent | 否——F2 未接 master（`src/cuts/lifecycle.py` step_8 = NotImplementedError；`generate_cutset_cuts` 仅测试引用；live 走真双层 RoutingSubproblem） |
| C-4 | D2 hard separator 2D cell `AddAtMostOne` 比 routing 严格（routing 允许双层共用 2D cell） | 🔶 likely_real，机制真但**双 env 默认关** | P1 | 否（需 EXACT_B1_D2_COMMODITY_FLOW + EXACT_USE_POSE_BOOL_MASTER 双开；Path-17 D2 范式已 dead 0/8 CERTIFIED） |
| C-1 | binding generic output slot `AddExactlyOne` 强制全占 | ❌ refuted | 非 bug | — |
| C-2 | routing 对 port 坐标二次偏移 | ❌ refuted | 非 bug | — |
| B-02 | pose-bool exact master 没表示完整 ghost-anchor existential domain | ❌ refuted | 非公开路径 | 否 |

## 三个确认的真 P0（certified_exact 路径当前 unsound）

### A-1 — routing 局部连续 ≠ 全局连通（false CERTIFIED）
`src/models/routing_subproblem.py:864-937` 的连续性只有局部 successor/predecessor（「某 state 有出边→邻格有接收 state」），`_add_port_adherence`（939-973）只钉 source/sink front cell 各一个 state，**全文无 source→sink 全局连通/流守恒约束**。`solve()`（1005-1006）CP-SAT 一 FEASIBLE 即返回 FEASIBLE，`benders_loop` 提升为 CERTIFIED。可让 source 侧孤立边 S→N、sink 侧孤立边 P→T 各满足局部支撑+端口约束但 S/T 不连通 → 货没运到却报 FEASIBLE。A1 会话实测反例（窄走廊 3-commodity，sink_reachable 全 False 却 FEASIBLE）与代码吻合。

### B-01 — no-overlap 用模板固定尺寸而非真实 footprint（false CERTIFIED）
`exact_coordinate_master.py:2154/2170` slot.dims 取 `templates[tpl]["dimensions"]` 单一固定 (w,h)；2333-2354 用这个 int 常量建 `NewIntervalVar`/`NewOptionalIntervalVar`；3047 `AddNoOverlap2D` 用这对固定 interval。而 mode 变量能在同 slot 自由选朝向：`gen_rect_manufacturing` 对 6x4 同时生成 o=0 真实 6x4、o=1 真实 4x6，`_candidate_pose_indices_for_group` 不做朝向过滤。GPT 点名的缓解（mode_rect_domains/allowed_tuples/use_domain_table）逐一被 agent 排除：`ModeRectDomain`（699-706）只存 anchor 包围盒 x/y 范围 + cell 数，**无 footprint 维度**；AddAllowedAssignments/_add_region_constraints 只约束 (x,y,mode) 取值与 mode→x/y 范围，从不改 interval 尺寸；全文件 grep 无任何按 mode 切尺寸逻辑。选竖向 4x6 pose 时 no-overlap 仍按 6x4 算 → 物理重叠布局通过（false-feasible）。

### A-2 — front_blocked over-cut（false INFEASIBLE → 漏真最优）
`routing_subproblem.py:356` front_blocked 返回 `binding_selection_safe_reject=True`（语义=仅可拒当前 binding 选择）；端口坐标由 binding_idx 决定（`binding_subproblem.py:770-785`），binding_domains 是同 pose 多绑定枚举（408-456）→「端口前格被占」是当前 binding 的局部事实，换个 binding 端口可能朝向空闲格而可路由。但 `benders_loop.py:5428-5467` 默认 fallback 用 `placement_level_conflict_set` 铸 master pose-presence nogood（`exact_coordinate_master.py:6599` `sum(present)<=N-1`，不带 binding literal），5523 直接 return MASTER_CUT_ADDED_CONTINUE，**跳过 binding 枚举**。对照 relaxed_disconnected（5528-5549）与 routing-INFEASIBLE（5661-5692）两个同标 safe_reject=True 的分支都先 `add_nogood_cut(selection)`+continue 枚举 binding，只 front_blocked 例外。过切 → 可行布局误剪 → master cp_model.INFEASIBLE（4476 return RUN_STATUS_INFEASIBLE）→ max_lex 下漏掉真最大矩形 → 对外 false CERTIFIED。`binding_selection_safe_reject` flag 全仓只被赋值不被消费。

## latent / gated（机制真，当前不在默认路径产错，但须登记）

- **C-3（F2 cutset 容量）**：F2 未接 live 证明路径，dormant；**P1.3B 把 F2 接进 master（step_8）前必须先把 edge_capacity 改成两层容量上界**，否则一接线就是 false-INFEASIBLE。
- **C-4（D2 2D 容量）**：双 env 默认关 + Path-17 D2 已 dead。**可操作加固**：`scripts/production_readiness_gate.py` 未把 `EXACT_B1_D2_COMMODITY_FLOW` 列为 launch blocker（对比已列的 `EXACT_POWER_PLACEMENT_SUBPROBLEM`），带此 env 启动不会被拦——建议补进 blocker 清单。

## 三个 GPT 误判（对抗式核代码筛掉，避免冤枉）

- **C-1**：漏看本 base「52-Port 不变量」（`specs/04_recipe_and_demand_expansion.md:118-132`）——R=52（blue_iron_ore 34+source_ore 18）恰好 = S=52（46 边界口+6 核心出口），spec 明确要求 output 100% 占满不容空置，`AddExactlyOne` 强制全占**正确**。input 有 `__unused__` 是因 input 真有冗余（3 槽 vs 2 需求），output 无冗余故无 sentinel——有原则的非对称。**GPT 的 C-1 补丁会破坏正确逻辑，禁用。**
- **C-2**：certified routing 吃冻结产物 `candidate_placements.json`，端口坐标是「本体边缘格」（`src/cuts/helpers/candidate_placements.py:29-39` 实测：manufacturing_3x3 output port 在本体底行，front=port+dir 才出本体）→ 单次偏移正确，无二次偏移。GPT 误把 placement_generator 约定当成 routing 输入约定。
- **B-02**：`EXACT_USE_POSE_BOOL_MASTER` 在 certified_exact 下被三处 guard fail-closed 拦截（`benders_loop.py:447-450` UNSAFE_ENV_OVERRIDES + V80 allowlist 兜底；create_exact_search_session:1607 / ExactSearchSession.create:1557 raise RuntimeError；主路径 6006-6033 返回 UNPROVEN+BLOCKED），全在 master 构建前触发 → pose-bool delegate 的 ghost-domain 缺陷到不了公开路径。

## 补丁可用性

GPT 对 A-1/A-2/B-01/C-1/C-3/C-4 各附了补丁（多为保守 fail-closed：宁返回 UNKNOWN 也不 false-CERTIFIED）+ 回归测试。交付原件在 `C:\22957\download`（`REVIEW.md`/`REVIEW (1).md`/`zmd_geometry_master_soundness_review_patch.zip`/`zmd_angle_c_patch_package.zip` + 对应 .patch/.diff），解包副本在 `C:\Users\22957\zmd_audit\`。

- **A-1 / A-2 / B-01**：补丁思路（reachability post-solve guard / front_blocked 先枚举 binding / footprint-aware variable-size interval）方向对，是真修复起点；但 GPT 补丁历来常带连带破真实路径 + ruff/mypy 雷，落地前必须本地 probe 复现 + 全量 + preflight（见 GPT 验收纪律）。
- **C-1 补丁：禁用**（会把正确的 52-port 满占改坏）。
- **C-3 / C-4 补丁**：对应 latent，接线/启用前再用。

## 结论

certified_exact 路径**当前 unsound**（3 个真 P0：A-1/B-01/A-2）。P1.2 远不能闭合——它现在交付的「CERTIFIED」对最优性的主张不可靠（可能不可路由、可能物理重叠、可能漏掉真最大矩形）。**优先级翻转**：M1/M2/M4 witness 加固靠后，先修 A-1/B-01/A-2。修求解器核心碰 PROJECT_LOCK 精确边界，须走 lock/spec/test 三件套，是大工程，待 owner 决策开工。
