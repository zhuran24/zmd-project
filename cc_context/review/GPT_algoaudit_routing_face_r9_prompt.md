# 终末地 IndustrialPlanner 精确求解器 — routing 面 round 9 (真 Pro 独立重审·网格布线 soundness)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_b4041f3e.zip`, sha256 `b4041f3eb065e9756a1dbd21f3e513479dfd504e2024b74fb08a2d235af08893`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照 (HEAD `8c61e1e`)。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。`data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) **已随包**, 已校验, 不需再生。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → **routing 网格布线** → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **routing 网格布线子问题 + 连通性 guard + lazy connectivity cut + precheck 三态消费** (`src/models/routing_subproblem.py` 为核, 配 `src/search/benders_loop.py` 的 routing precheck 调用/消费点; `src/models/flow_subproblem.py` 是诊断旁路, 不产认证结论)。

## 本面定义与历史 + 本轮性质 (关键, 必读)

本面 = routing 子问题的 soundness: 域分析/precheck (产 status)、CP-SAT 约束编码 (route-state 变量 / 方向连续性 / 逐边守恒 / cell-layer 容量 / bridge 共存 / pattern 封闭集 / obstacle·connector 域排除 / 端口 adherence)、连通性 guard (reachability 重验)、lazy connectivity cut (W/X 证书)、precheck 三态消费契约。历史:

- r2 = F-RT-R2-01 (terminal 极性朝向 connector, 紧凑 corridor false-INFEASIBLE) + F-RT-R2-02 (层重叠下逐边通道守恒, 局部「≥1 支撑」放行隐形 splitter/merger = false-FEASIBLE);
- r3 = F-RT-R3-01 (port connector cell 是 terminal 节点非 belt 格, 商品穿别的 connector / 复用 terminal 侧 = false-FEASIBLE);
- r4 = F-RT-R4-01 (同 commodity terminal fronts 被强压单连通分量, 双孤岛合法布局 false-INFEASIBLE) + F-RT-R4-02 (重复 terminal key multiplicity 丢失, 外置 port_specs hardening);
- r5 = F-RT-R5-01 (外置 routing 域只减 connector 没与 free grid 求交, stale/恶意域在 solid 格上建 route-state = 穿墙 false-FEASIBLE);
- r6 = 零 finding (guard 本体首次独立深审);
- r7 = 零 finding (约束本体直审 + precheck 生产者 + 自由攻击角);
- **r8 = 零 finding (本面首个真 Pro 轮)**: Q1-Q8 逐项复核 + probe (极性 / 逐边守恒 terminal 例外 / connector 两层锁 / 外置域 clip / pattern 封闭集 count=48 / cell-layer capacity / guard 图语义+pooling+fail-closed / lazy W/X 证书 / precheck 三态契约一致性 + TypeError default-feasible 回退), 全部判 sound, 无补丁。

**本轮 r9 = 又一次独立全面 soundness 重审 (上一轮零 finding)。姿态要求:**

r8 是真 Pro, 但它的覆盖方式是「顺着既定 Q1-Q8 检查单逐项确认」。**本轮请换一个攻击角度, 别复读 r8 的逐项判读** —— 把 routing 当作一个 soundness 不变量尚未被穷尽的面, 从「**soundness 责任在 CP-SAT 编码与事后 guard 之间如何切分**」这条主线重新切入: 哪些非法布局必须靠 CP-SAT 逐边守恒挡住、哪些必须靠 guard reachability 挡住、两者之间有没有谁都不管的缝。前 7 轮 + r8 的 clean 不构成任何先验; 真 Pro 同期切到其它面 (Benders F-BL-R7-01、cuts CUT-R12/R13-H1 thinking 审 11+ 轮才被 Pro 抓出、preprocess F-PRE-R15/R16、几何 master F-GM-R11-PB-REQ-POLE-01) 都在「前轮判 clean」的面上挖出真 finding —— 所以 routing 连零 3 不等于本轮默认干净。

注意: 包内带其它面同期落的修复条款 (master / cuts / preprocess / benders / binding), 各面有自己的线, **别在本轮重报**。

## 本轮主攻线 (CP-SAT 编码 vs 事后 guard 的 soundness 分工, 4 块新角 + 4 块回归核)

任何比规则**更严**的约束 = false-INFEASIBLE (漏真最大矩形, availability); 任何比规则**更松** = false-FEASIBLE (放过非法布线, soundness, 更危险)。**本轮优先攻 A1-A4 (新角); B1-B4 是回归核, 只在你怀疑残留/反向缺陷时进。** 行号基于本包 `routing_subproblem.py` (1873 行) / `benders_loop.py`, 扫一眼确认引用真实别照抄。

### A1 splitter/merger 的「悬臂」守恒 — CP-SAT 与 guard 谁兜底? (本轮重点)

`_iter_state_patterns()` (:867-905) 允许 L0 splitter (1 进 2/3 出) 与 merger (2/3 进 1 出)。一个被选中的 splitter 声明了 2 个 `flow_out` 方向; guard 的 `_route_state_adjacency()` (:1311-1330) 对每个 `flow_out` 方向生成一条邻接边, `_reachable_route_states()` (:1332-1350) 做可达性。问题: **guard 只证「某 source 达每个 sink、每个 source 达某 sink」(:1645-1657), 它不要求 splitter 的每条 `flow_out` 臂都有真实下游 receiver state** —— 这条「每臂必须被消费」的守恒是否完全由 CP-SAT `_add_directed_edge_balance_constraints()` (:1068-1118) 的逐边 `sum(send)==sum(recv)` 兜住?

请独立追问:
- 某条 splitter `flow_out` 臂指向的邻格不在 `active_cells` → 逐边守恒 `continue` 跳过 (:1096-1097), 但 successor 约束 (:1135-1146) 会把该 out-side var 置 0。**置 0 是否真覆盖到「splitter 已被选中且该臂悬空」这个组合** —— 即一个 component_type=splitter 的 route-state, 它的某个 flow_out 方向 var 被强制 0, 会不会让这个 state 本身变成不可选 (好), 还是允许 state 选中但该方向「不算数」(坏, 物理上 splitter 少一条臂 = 实为 belt, 但被当 splitter 占用)? 关键: route-state var 是「整个 pattern」一个 BoolVar 还是「每方向」分开 —— 核 `_create_routing_variables()` (:942-980) 的 var 粒度与 `_vars_by_cell_dir_out_commodity` 索引桶的填充 (:964-980), 确认 splitter 的多个 flow_out 是否共享同一个 state-var (那么置 0 任一臂 = 禁掉整 state) 还是可分裂。
- 同理 merger 的多 `flow_in` 臂: predecessor (:1158-1194) + 逐边守恒, 是否每条进臂都有真实上游 sender。
- **guard 侧的反向风险**: `_route_state_adjacency` 把 splitter 当「flow_out 任一方向可达即扩展」, 若 CP-SAT 真允许 splitter 选中而某臂无 receiver, guard 的可达性会**乐观**地认为该 state 仍连通 (因为另一条臂通了), 从而放过一个物理上「凭空分流/合流」的非法 incumbent = false-FEASIBLE。请确认 CP-SAT 侧是否**先于** guard 就把这类 state 排除掉, 使 guard 永远看不到悬臂 splitter。给 probe: 构造一个会逼出 splitter 的小场景, dump 选中 state 的 flow_in/flow_out 基数, 验证每条臂都有对应 send/recv var 选中。

### A2 逐边守恒的「桶为空」短路与跨层别名 (F-RT-R2-02 的反向缺陷面)

`_add_directed_edge_balance_constraints()` (:1111-1112): `if not send_vars and not recv_vars: continue`。即当某有向边两侧索引桶都为空时跳过该边。`send_vars`/`recv_vars` 来自 `_vars_by_cell_dir_out_commodity` / `_vars_by_cell_dir_in_commodity` (**注意: 这两个桶是 layer-agnostic 的, 跨 ground+elevated 合并同一 2D cell-dir**)。请核:
- 「桶为空才 continue」是否可能在「一侧桶非空、另一侧桶空」时**不**短路, 从而加一条 `sum(非空) == sum(空=0)` 把非空侧逼 0 —— 这是正确的 fail-closed 还是会误杀合法 (一侧本就该 0)? 即守恒方程在边界 (邻格 active 但该方向无 pattern 产生 var) 的语义。
- **跨层别名的核心 (F-RT-R2-02 修复点钉成攻击面)**: 既然 send/recv 桶 layer-agnostic, 一条 `sum(send)==sum(recv)` 是否真能阻止「ground belt 的 send 臂与 elevated bridge 的 recv 臂在同一 2D 有向边上配错对」? r8 判它能 (一个 sender 不能同时支撑 ground+elevated 两个 receiver), 请**独立重证**: 写出 send/recv 桶里各 layer 的成员, 验证守恒方程是「逐 2D 边总量相等」而非「逐 (layer,边) 相等」—— 若是前者, 2 个 ground sender 配 1 ground + 1 elevated receiver 的总量也相等, 守恒方程满足但物理上 elevated 那条边的 sender 缺位。这条边的 sender 缺位是否由 elevated 侧的 predecessor/continuity 单独兜住 (:1158-1194 是 layer 分桶的 `_vars_by_cell_layer_dir_in_commodity`)? 核 layer-agnostic 守恒 + layer-aware 连续性的**联合**是否无缝, 还是存在一个总量平衡但分层错配的 false-FEASIBLE。

### A3 guard 图语义 vs CP-SAT 语义的精确同构 (layer 维度被 guard 投影掉的后果)

guard 的 `_route_state_adjacency` (:1311-1330) 用 `(nx, ny, recv_dir, commodity)` 做 `by_input` 索引 (`_route_state_input_index` :1274-1283), **丢掉了 layer**。即 guard 把 ground state 的 flow_out 接到邻格**任一 layer** 的 flow_in (只要 cell+dir+commodity 匹配)。而 CP-SAT 的 successor/predecessor 是 layer-aware 的 (`_vars_by_cell_layer_dir_*`)。请独立核:
- guard 这个 layer-agnostic 邻接是 CP-SAT 连通语义的**保守 over-approx (更易判连通 → 更易接受 incumbent)** 还是 **under-approx (更易判断开 → 更易拒)**? 若是 over-approx, 它能否让一个「ground→邻格 elevated→...」这种 CP-SAT 实际不允许的跨层接续在 guard 里被当成合法路径, 从而接受一个 CP-SAT 编码本不该连通的 incumbent = false-FEASIBLE? 关键: bridge (elevated) 的 flow_in/flow_out 是 `Opp` 直桥 (:868-875), 它能否成为 guard 路径的中间跳? 物理规则里 ground belt 与 elevated bridge 在同一 cell 的接续语义 (specs/09 :43-128, specs/03 :306-344) 是什么, guard 的跨层接续有没有越权放行。
- 反过来若是 under-approx 只影响 availability (LOW)。请明确判到底哪一侧。

### A4 `commodities` 集合完整性 + guard 检查域 (漏检一个 commodity = 漏证)

guard 的检查域 `commodities_to_check = sorted(set(source_fronts) | set(sink_fronts) | set(self.commodities))` (:1614)。`self.commodities` 在 `:731` 赋值。请核:
- 一个有 port_spec、产生了 source/sink front, 但因某种原因**不在** `self.commodities` 里的 commodity, 会不会被 guard 漏检? (`set(source_fronts)|set(sink_fronts)` 已并入似乎兜住了, 但请确认 `source_fronts`/`sink_fronts` 的来源 `_terminal_fronts_by_commodity()` :1244-1256 是从 `_source_port_fronts`/`_sink_port_fronts` 派生, 而后者由 `_index_port_fronts()` :786-799 遍历 `self.grid.port_specs` 填充 —— 这条链是否保证「任何产生 front 的 commodity 必被 guard 检查」)。
- 反向: 一个 commodity 在 `self.commodities` 但其 front 在域 clip (:847-859) 后全被剔出 active → guard 期望 source/sink 非空但选中节点空 → `missing_sources`/`missing_sinks` 触发 failure 拒绝 (:1620-1666)。确认这条是 fail-closed (拒) 而非 fail-open。
- `commodities_to_check` 里 `expected_sources` 与 `expected_sinks` **同时非空才算需连通** —— 但 :1664-1665 有 `or not expected_sources or not expected_sinks` 进 failure。即只有 source 没 sink (或反之) 的 commodity 会被判 failure。这是否与 precheck `analyze_exact_routing_domain` 对「只有单边 front」的 commodity 的处理 (:507-573 relaxed_disconnected 分支) 一致, 还是 guard 与 precheck 对「单边 commodity」给出矛盾结论 (一个放一个拒)?

### B1 极性/边守恒/connector/外置域 clip 回归核 (只在怀疑残留时进)

F-RT-R2-01 极性 (:786-799 source `recv_dir=Opp`, sink `send_dir=Opp`; 消费点 :1099/:1142/:1180/:1196-1237)、F-RT-R2-02 逐边守恒已在 A2 攻、F-RT-R3-01 connector 两层锁 (:120-133 / :847-859 / successor·predecessor 的 source/sink connector side 剪枝 :1132-1146/:1170-1184)、F-RT-R5-01 外置域 clip (:847-859 component+active 双集合 `& routable_domain_cells`)。**这些是已 lock 修复点, 不重报修复本身**; 只在你能给出**同型残留 / 反向缺陷 / 修复不完备**的 file:line + probe 时报。

### B2 obstacle no-op 域排除 (F-RT-R5-01 的另一面)

`_add_obstacle_exclusion()` (:1022-1024) 是 no-op, 障碍排除靠「只在 active free cells 建 var」(`_create_routing_variables` :942-980)。请确认 `_bind_domain_analysis` 的 `routable_domain_cells = set(self.grid.free_cells) - port_connector_cells` (:848) 对 occupied / connector / 出界三类的拦截口径一致 (r8 已 probe 注入 hostile 域含 source/sink connector + 出界 (999,999), 均未进 r_vars)。新角: 求交用的是 `self.grid.free_cells` —— 核 `RoutingGrid` 与 `RoutingPlacementCore.from_occupied_cells()` 两条构造 (:47-85 / :660-704) 的 `free_cells` 是否都严格 = 70×70 in-grid 非 occupied (placement-core 路径有没有可能漏排某类格)。

### B3 pattern 封闭集 (set-equality, 不复读 r8 计数)

`_iter_state_patterns()` (:867-905): L1 bridge 4 直桥; L0 belt 12 + splitter 16 + merger 16 = 44; 含 L1 共 48。r8 已 probe count=48。**本轮不要只复读计数** —— 请验**有没有规则允许但枚举漏掉的 pattern** (合法拓扑无法表达 = false-INFEASIBLE), 或**枚举里有规则不允许的** (转弯 bridge / U-turn belt `d_out==d_in` 是否真被 :879-880 排除 / 自环 / splitter output 含 input side / merger input 含 output side)。对照 specs/03 (:306-345) + specs/09 (:51-55) 独立推导封闭集做 set-equality。

### B4 guard fail-closed 边界 + lazy W/X 证书 + precheck 三态契约

- guard 接受边界: `solve()` (:1728-1842) CP-SAT OPTIMAL/FEASIBLE 后**必过** `_validate_selected_route_connectivity()` (:1773 附近) 才返 FEASIBLE; 拒绝则加 self-checked lazy cut 或 fallback selected-positive nogood (:1689-1699) 后续解; 预算耗尽清 `_solver`/置 UNKNOWN 返 TIMEOUT (:1737-1753); `extract_routes()` (:1844-1870) status + `_connectivity_guard_accepted` 双门闩。**核 TIMEOUT 清 witness 是否彻底 (有无路径在已 guard-reject 后仍能从 stale solver 取出 route)**。
- lazy cut: `_add_source_side_connectivity_cut()` (:1535-1589) + `_self_check_source_side_connectivity_cut()` (:1435-1533) 独立重验 W/X (source∈W、sink∉W、移除 X 在 full potential graph 断开全部 source→sink、incumbent∩X=∅), 任一不成立 fallback selected-positive nogood。**r7/r8 advisory 挂账**: `_route_state_adjacency` 当 potential-graph oracle 时未显式过滤 source-entry arcs (当前仅影响 lazy-cut 保守度非 soundness, 因 connector side 已被域剔除) —— 请**第三次**独立重审此 advisory 真无 soundness 影响 (结合 A1/A3 的新视角看它是否仍成立)。
- precheck 三态契约: routing 端 `analyze_exact_routing_domain()` 实产 status = `{feasible (:614-630), front_blocked (:408/:485), relaxed_disconnected (:531-597)}`; benders allowlist `_EXACT_ROUTING_PRECHECK_VERIFIED_STATUSES = {feasible, front_blocked, relaxed_disconnected}` (`benders_loop.py:123`), 非 allowlist fail-closed UNKNOWN (`benders_loop.py:5383-5408`, F-BL-R7-01)。**本轮独立验证此一致性, 并核**:
  - ① ERROR 合成 (`benders_loop.py:5330-5335/:5350-5361/:5362-5363`) 是否覆盖所有 precheck 异常面;
  - ② **TypeError 单独 catch → `routing_precheck=None` → default feasible 回退** (`benders_loop.py:5328-5329/:5347-5349/:5364-5371`): r8 判它不漏证 (后续 `RoutingSubproblem.build()` 重跑 production `analyze_exact_routing_domain()` 且仍必过 CP-SAT+guard)。请**独立重证** —— 是否存在某条 TypeError 路径, 让本该 blocked 的布局先以 default feasible 进入, 而后续 build 重跑时因 default-feasible summary 已被消费 (cut ladder / safe-reject 分支已走) 而**不再**重新挡回? 即 default-feasible 的副作用是否仅限「不早剪」还是会污染后续证书链。
  - ③ 未来第 4 个 status / 缺 `status` 字段 payload 命中 default `"feasible"` (`benders_loop.py:5365-5366/:5381`) 是否仍 fail-closed (r8 标为「非当前 producer 可达, 建议契约测试」, 本轮确认当前 producer 确实不可达该路径)。
  - 另: 独立重扫有无裸用 precheck 结论直接产 candidate-wide INFEASIBLE 证书的 live path (r7/r8 扫过 `heuristic_feasible_finder.py` best-effort、`campaign_triage`/telemetry 仅分类、`d2_separator.py` 需 production precheck 已 front_blocked/relaxed_disconnected 才放行)。`relaxed_disconnected` 进 whole-layout nogood 必须是 full routing 的必要条件证明 (更宽 `free_cells - connector` 图断开 ⇒ active-domain 收缩后必断, :500-573)。

## 明确不要报的

- 已修 lock 条款 (重复报不算): **F-RT-R2-01/R2-02** (`PROJECT_LOCK.md:120/121`)、**F-RT-R3-01** (:122)、**F-RT-R4-01/R4-02** (:123/124)、**F-RT-R5-01** (:125); 关联 routing soundness 条款 :126 (CP-SAT FEASIBLE 非认证边界, guard 必证)、:127 (lazy cut acceleration-only + W/X 自验)、:134 (binding-local safe-reject 先 binding nogood)、:136 (F-BL-R7-01 status allowlist)、:117 (全封闭空矩形允许, exterior 连通不在 exact 契约)。**钉为攻击面 ≠ 重报修复本身**: 只有给出同型残留 / 反向缺陷 / 修复不完备的新 file:line + probe 才算 finding。
- `routable_cells` / `RoutingGrid.neighbors()` stale API (无 live proof consumer, r6/r7/r8 已审结, 已挂账)。
- 设计决策 (canonical / 266 口径 / omni_wireless / 52-Port 不变量 / `min_side>=6` admissibility, owner 已定)。
- master / binding / cuts / preprocess / benders / campaign / scheduler 各面 (各自有线)。
- preflight `phase_1_2_spike_close` BLOCKED 是 owner gate (不报); P1.3B `step_8_apply_to_master` 禁区; exploratory 行为/性能不审; persisted `exact_safe_cuts` 是 telemetry 非 proof。
- **ghost 不含 exterior-path 要求是 owner 已定的禁区, 别建议加**。
- `candidate_placements.json` 已随包并校验 (sha256 `adcc2a6e...`, 45,773,799 bytes), 不准伪造; 别建议改 candidate 生成。

## 自验环境与已知基线

- candidate 已随包, 全量 `python -m pytest -q src/tests` 应 **0 failed** (passed ≈3058, 数目以实跑为准, 硬不变量 = 0 failed; 沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。跑不完就跑 routing 专项 (`src/tests/test_routing.py` / `test_exact_contract.py` / `test_p0_certified_soundness_fixes.py` 等) + 如实声明哪些没跑。
- `python scripts/check_p1_2_proof_obligations.py` pass (8 obligations)。
- finding 必须带**可复现 probe 或 file:line 严谨论证**; 实证推翻你的怀疑就不要报。
- specs 真实文件名: pool/commodity 语义 = `specs/08_topological_flow_subproblem.md`; routing 约束规则 = `specs/09_exact_grid_routing_subproblem.md` (:43-128); pattern = `specs/03_rule_canonicalization.md` (:306-345); connector 语义 = `specs/06_candidate_placement_enumeration.md`。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附分段判读 (本轮主攻线): A1 splitter/merger 悬臂守恒分工 / A2 逐边守恒跨层别名 / A3 guard layer-agnostic 邻接 vs CP-SAT layer-aware 语义 / A4 commodities 检查域完整性 / B4 guard fail-closed + lazy W/X + precheck 三态契约 的真 Pro 复核。每段给出你的独立规则依据, 不复读 r8 判读。
- 真 Pro 独立确认轮; 前轮 (含 r8 真 Pro) 连零不代表本轮默认干净; 按你自己的独立、对抗判断下结论。

## 严重度纪律

false-CERTIFIED (放过非法布线被认证 FEASIBLE) = soundness, P1.2 闭环只认这个, HIGH。false-INFEASIBLE (保守失败, 漏真最大矩形) = availability, 标 LOW 加固。lazy-cut 保守度 / precheck 早剪过严 = availability。

## 范围边界

重点 = 布线编码 soundness 三块 (CP-SAT 约束本体 / guard + lazy cut / precheck 消费 + benders 契约一致性) 的真 Pro 独立复核; 其余 7 面及各自子问题正确性不审。怀疑跨面时交叉引述 `PROJECT_LOCK.md` 对应条款而非在本轮重证。
