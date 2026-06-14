# 终末地 IndustrialPlanner 精确求解器 — routing 面 round 10 (真 Pro 独立重审·CP-SAT 局部物理 vs guard 端到端可达的分工缝)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_3b23181e.zip`, sha256 `3b23181e036be5daaf15d9166b76bb9d7b6acb49d81da3e046b8a07f1ec326b6`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), **干净 git 树, HEAD `eb5c012` (本轮全部修复已合入 —— 这是带修复的新树, 不是上一轮那棵)**。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。`data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) **已随包**, 已校验, 不需再生。

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
- r8 = 零 finding (本面首个真 Pro 轮, Q1-Q8 逐项复核 + probe);
- **r9 = 零 finding**: 按「CP-SAT 编码 vs 事后 guard 分工」主线, A1 splitter/merger 悬臂守恒分工 (var 粒度=整 pattern 一个 BoolVar, 任一臂置 0 禁整 state) / A2 逐边守恒桶为空短路 + 跨层别名 (逐 `(2D edge, commodity)` 守恒 + per-(cell,layer) AtMostOne, 单 sender 伪造双 receiver → `1==2` 拒) / A3 guard layer-agnostic 邻接与 CP-SAT 同构 (successor/predecessor 的对侧 receiver/sender 桶本就 layer-agnostic) / A4 commodities 检查域完整性 (front 派生链保证任何产 front 的 commodity 必入 guard 检查域) / B4 guard fail-closed + lazy W/X + precheck 三态契约, 全部判 sound, 无补丁, 24 项专项回归 + `check_p1_2_proof_obligations` 8 obligations pass。

**本轮 r10 = 又一次独立全面 soundness 重审 (上一轮 r9 零 finding)。姿态要求:**

r9 把攻击线划在「**每个 route-state / 每条 2D 边 / 每个 commodity 自身**的局部物理可实现性」: 它逐一证明了**单个** state 的所有臂被消费、**单条** 2D 边上 send/recv 数量相等、**单个** commodity 的 front 必被检查。r9 把 guard 的 reachability 当成「在 CP-SAT 已局部闭合的图上做存在性可达」并判它与 CP-SAT 语义同构。

**本轮请换一个更上层的攻击角度, 别复读 r9 的逐项判读** —— 把攻击面从「单边/单 state 守恒」抬到「**count-conservation + 存在性 reachability 的组合, 到底证不证得出一个真正可同时实现的流 (realizable simultaneous flow)**」这条主线。核心怀疑不是某一条边或某一个 state 错, 而是: CP-SAT 只保证**逐边通道数守恒 (count balance)** + **逐 (cell,layer) AtMostOne**, guard 只保证**逐 front 的存在性可达 (每个 source 到某 sink、每个 sink 被某 source 达, OR 语义)** —— 两者都是局部/存在性断言, 它们的**合取**是否等价于「存在一个把所有 source 的供给同时送达所有 sink 的可行多商品流」? 经典 gap = **reachability ≠ feasible flow**: 可达性允许两条逻辑路径**共享**同一条物理通道而各自宣称连通, 守恒只锁逐边总量却不锁**配对** (谁喂谁)。本轮就攻这个缝。

前 7 轮 + r8 + r9 的 clean 不构成任何先验。真 Pro 同期切到其它面 (Benders F-BL-R7-01、cuts CUT-R12/R13-H1 审 11+ 轮才被抓出、preprocess F-PRE-R15/R16、几何 master F-GM-R11/R12-PB) 都在「前轮判 clean」的面上挖出真 finding —— 所以 routing 连零 4 不等于本轮默认干净。

注意: 包内带其它面同期落的修复条款 (master r12 / benders r8 env-gated hardening / 各 hardening finding 已入 LOCK), 各面有自己的线, **别在本轮重报**。本轮 HEAD `eb5c012` 是带这些修复的新树, routing 面相对 r9 树**本体无改动** (r9 零 finding), 所以你看到的 routing 代码与 r9 同; 攻击角度必须是新的, 不是等代码变了。

## 本轮主攻线 (count-conservation + existential-reachability 的组合 soundness, 4 块新角 A1'-A4' + 1 块回归核 B)

行号基于本包 `routing_subproblem.py` (1873 行) / `benders_loop.py`, 扫一眼确认引用真实别照抄。任何比规则**更严** = false-INFEASIBLE (漏真最大矩形, availability, LOW); 任何比规则**更松** = false-FEASIBLE (放过非法布线, soundness, HIGH)。**本轮优先攻 A1'-A4' (新组合视角); B 是回归核, 只在你怀疑残留/反向缺陷时进。**

### A1' 共享内部通道的「双重记账」—— 两个 source→sink 需求各自宣称连通同一条 belt 链 (本轮重点)

guard `_validate_selected_route_connectivity()` (:1591-1687) 对每个 commodity 用 **OR 语义**判连通: `reachable_from_any_source` (:1645) = 所有 source 起点的并集可达集; `unreachable_sinks` (:1646-1650) = 不在该并集里的 sink; `source_fronts_without_sink` (:1652-1657) = 从该 source 出发可达集与 `all_sink_nodes` 不交的 source。即它只证「**每个 source 能到某 sink**」「**每个 sink 能被某 source 达**」, **从不证「所有 source 的供给能被一条不超订的物理流同时送达所有 sink」**。这是 reachability, 不是 max-flow / feasible-flow。

CP-SAT 侧只有 `_add_directed_edge_balance_constraints()` (:1068-1114) 的逐 2D 边 `sum(send_vars)==sum(recv_vars)` + `_add_capacity_constraints()` (:1026-1029) 的逐 (cell,layer) `AddAtMostOne`。请独立追问 **这个组合是否堵死「共享通道双重记账」**:

- 设一个 commodity 有 2 个 source front S1/S2 与 2 个 sink front K1/K2, 几何上有一条公共内部 belt 链 C (一串 belt state) 同时落在 S1→某汇和 S2→某汇的路径上。每个 belt cell 的每个方向只有一个 route-state var (per-(cell,layer) AtMostOne), 一条 belt state 只声明 1 进 1 出。**问题**: guard 的 reachability 是在**选中 state 集合**上做图遍历 (:1611 `adjacency = _route_state_adjacency(selected, sink_fronts)`), 它判 S1 可达 K1、S2 可达 K2 时, 这两条逻辑路径**能不能复用 C 里同一批 belt state**? 若能, guard 判「两个 source 都连通」, 但物理上 C 是单通道 —— 一条 belt 一个 tick 只过一个单位, 两股供给挤一条单 belt = 物理不可实现。这是否被 CP-SAT 的逐边 `sum(send)==sum(recv)` 挡住? 关键区别: 守恒锁的是**每条边 send 数 == recv 数**, 但 belt 是**单入单出** (pattern 封闭集里 belt 只有 12 个单进单出 state), 一条 belt state 选中 ⇒ 它那条出边 send=1, 下游那条边 recv=1 —— 数字平衡, 但**它只承载「一股」流**; 两个 source 若都必须穿过 C 才能各自到汇, 守恒方程**逐边仍然 1==1 成立**, 因为守恒不数「几股逻辑流穿过」, 只数「几个 state 选中」。请判: 这种「单 belt 链被两条逻辑 source→sink 路径共用」的布局, CP-SAT 会判 FEASIBLE 吗? 若会, 它物理上对应什么 (是合法的「先汇合再分流」拓扑 = splitter/merger 显式出现, 还是一个无 splitter 的纯 belt 链被默许承载两股)? 
- **决定性追问**: 若 C 是纯 belt 链 (无 splitter/merger), 它**不可能**同时是 S1→K1 和 S2→K2 两条独立流的载体 —— 真要两股就必须在 C 入口有 merger、出口有 splitter, 而那些会改变 state pattern 和逐边 count。请构造 probe: 强制一个「两 source 两 sink 共用一条纯 belt 中段、无 splitter/merger」的几何, 看 CP-SAT 是 INFEASIBLE (好, 守恒 + AtMostOne 逼出矛盾) 还是 FEASIBLE 且 guard 放行 (坏, 双重记账 false-FEASIBLE)。dump 选中 state 的逐边 send/recv count 与 belt 链中段每格的 in/out 基数, 验证守恒是否真把「两股挤一 belt」逼成矛盾。**这是 r9 没碰的角**: r9 A1 只证单 state 的臂不悬空, A2 只证单边不跨层伪造双 receiver, 都没问「整张图的 reachability 是否等于一个不超订的可行流」。

### A2' count-balance 下的「层错配」配对 —— 守恒锁总量不锁 L0↔L0/L1↔L1 配对

r9 A2/A3 的结论是: 逐 2D 边 `sum(send)==sum(recv)` 是 layer-agnostic 的, 配 per-(cell,layer) AtMostOne, 所以一条边最多 2 个 sender (1 L0 + 1 L1) 配 2 个 receiver, 守恒锁成 0/0、1/1、2/2。r9 判「2 配 2 时两条物理通道都在, guard 只在已存在通道上做可达」。**本轮独立重证这个 2-配-2 情形的配对正确性**:

- 当某条 2D 有向边出现 send=2 (1 个 L0 sender + 1 个 L1 sender) 且 recv=2 (1 个 L0 receiver + 1 个 L1 receiver), 守恒方程 `2==2` 满足。但守恒是**总量等式**, 它**不强制** L0-sender 配 L0-receiver、L1-sender 配 L1-receiver。请独立核: 是否存在一种选择, 总量 `2==2` 成立, 但**物理配对是 L0-sender → L1-receiver 跨层、L1-sender → L0-receiver 跨层**? 这种跨层配对在物理规则里是否合法 (specs/09 :43-128 belt 与 bridge 在同一 2D 边上能不能层间换乘)? 若**不合法**而 CP-SAT 允许 (因为它只锁总量), 那么 guard 的 layer-agnostic 邻接 (:1311-1330 用 `(nx,ny,recv_dir,commodity)` 不带 layer) 会把 L0-sender 接到 L1-receiver 当成合法边 → 接受一个物理上跨层错配的 incumbent = false-FEASIBLE。
- **谁兜底**: r9 说 layer-aware 的 successor/predecessor (`_vars_by_cell_layer_dir_*`, :1128/:1166) 单独兜住。但仔细看: successor (:1147-1156) 只要求「out_var 选中 ⇒ 对侧**某** (layer-agnostic) receiver ≥1」(`recv_sum >= 1`, recv_vars 来自 layer-agnostic `_vars_by_cell_dir_in_commodity` :1148), predecessor (:1186-1194) 对称。**successor/predecessor 本身也是 layer-agnostic 的对侧桶 + `>=1` 存在性**, 不是 layer-matched 的! 那 L0-sender 的 successor 约束被一个 L1-receiver 满足、L1-sender 的 successor 被 L0-receiver 满足, 是否就让跨层错配通过了所有约束 (逐边总量 2==2 ✓、successor 各自 ≥1 ✓、AtMostOne 每 (cell,layer) 各 1 ✓)? 请**严格追问**: 整套约束里有没有**任何一条**真正强制「同一条物理流在 cell-to-cell 边上保持同 layer」, 还是 layer 只在「同 cell 内 L0/L1 不能都选 nonstraight」(`_add_bridge_constraints` :1031-1042) 这一处被约束, 而 cell-to-cell 的层连续性从未被锁? 若从未被锁 → 这是 r9 漏掉的真缝。给 probe: 构造一个能逼出 send=2/recv=2 的 bridge-overlap 边, 强制 L0-sender + L1-sender, 看能否解出一个总量平衡但 L0→L1 / L1→L0 跨层换乘的 incumbent, 且 guard 放行。**这是 A2' 与 r9 A2 的本质区别**: r9 攻「单 sender 伪造双 receiver (1==2)」并证它被拒; 本轮攻「2==2 总量平衡下的层错配」, r9 默认 layer-aware 连续性兜底, 本轮要逐约束验证那个兜底是否真存在。

### A3' guard reachability 对「中间 state 必须真转发」的假设 —— 可达 ≠ 流贯通

guard 的 `_reachable_route_states()` (:1332-1350) 是纯图 BFS/DFS: A→B 的边来自 `_route_state_adjacency` (:1311-1330), 条件是「A 的某 flow_out 方向指向邻格、邻格有个选中 state B 的 flow_in 含对侧方向」。请追问 guard 把「可达」当「连通证明」时, 对**中间节点**的隐含假设:

- guard 判 source 可达 sink, 走的是 source-start-node → ... → sink-node 的有向路径。路径上每个中间 belt state B 被「路过」时, guard 只检查「A→B 边存在 (B 的 flow_in 有对侧方向)」, **不检查 B 的 flow_out 是否真把流转出去给路径下一跳** —— 等等, 实际上 adjacency 是按 B 自己的 flow_out 再生成 B→C 边的, 所以路径确实是「A.flow_out → B.flow_in, B.flow_out → C.flow_in」。**但 splitter/merger 呢**: 一个 merger B (2 进 1 出) 在路径上, guard 从 A1 经 B 的一条进臂到达 B, 再从 B 的唯一出臂到 C。B 的**另一条进臂** A2 是否必须也连到某 source? 这正是「每臂被消费」的对偶 ——「每臂被供给」。r9 A1 证了 CP-SAT 的逐边守恒 + 共享 BoolVar 使「选中 merger ⇒ 两条进臂都有上游 sender」。**本轮的新角**: 即使 CP-SAT 保证每条进臂有 sender, guard 的 reachability **是否要求 merger 的所有进臂都从 source 可达**? 设 merger B 的进臂 A1 来自真 source S, 进臂 A2 来自一个**选中但孤立的 belt cycle** (一圈自闭合的 belt, 逐边守恒满足、AtMostOne 满足, 但不连任何 source/sink)。CP-SAT 会不会允许这种「孤立 cycle 喂 merger 一条臂」的选择? guard 从 S 经 A1 到 B 到下游, 判 source 可达 sink ✓; 那个孤立 cycle 既不是 source 也不是 sink, guard 的逐 commodity OR 检查**根本不把它当检查对象** —— 它不在 `source_fronts`/`sink_fronts` 里, 也不会触发 `missing`/`unreachable`。**问题**: 这个孤立 cycle 是否物理可实现 (一圈 belt 凭空循环、无源无汇)? 若不可实现而 CP-SAT 允许它选中并喂 merger 的一条臂, 是否构成 false-FEASIBLE (布局被认证, 但含一个物理上无法运转的孤立环)? 请核: CP-SAT 有没有「每个选中 belt state 必须在某 source→sink 路径上」的约束, 还是只有逐边守恒 (守恒允许孤立 cycle, 因为环上每条边 1==1)? guard 有没有「无 source 支撑的选中 state 必须为空」的检查, 还是只检查 source/sink front 的可达? 给 probe: 强制一个「真 source→sink 路径 + 一个不相连的选中 belt 环」, 看 CP-SAT FEASIBLE 且 guard 放行否; 若放行, 判它是 soundness 漏洞 (认证了不可实现的孤立环) 还是良性 (孤立环不影响 source/sink 的真连通, 只是冗余占格 —— 但它占了 free cell, 可能挤掉别的, 不过对**本 commodity 的连通认证**无害)。**严重度判定要谨慎**: 若孤立环只是冗余占格不影响连通正确性, 这是 availability/cleanliness 非 soundness; 只有当孤立环能被用来「伪造」某个本该 false 的连通 (如喂 merger 让一个本无足够供给的 sink 看似被满足) 时才是 HIGH。

### A4' source/sink **数量** 守恒 —— guard 只证存在性, 不证供需配平

guard 对每个 commodity 证「每 source 到某 sink、每 sink 被某 source 达」(:1645-1657)。这是**二部存在性** (每个左点有右邻、每个右点有左邻), **不是完美匹配也不是流配平**。请独立追问规则到底要求哪个:

- specs/08 (`08_topological_flow_subproblem.md`) 的 pool 模型: 一个 commodity 的供给和需求是怎么配平的? 是「每个 sink 至少被一个 source 供到即可」(存在性, guard 当前实现), 还是「总供给 == 总需求, 且存在一个把供给分配到需求的可行流」(配平)? 若规则要求配平而 guard 只证存在性, 是否存在一个布局: 1 个 source 经分流同时「逻辑可达」3 个 sink (guard ✓: 每 sink 被该 source 达、该 source 到某 sink), 但物理上单 source 的产能只够喂 1 个 sink, 另 2 个 sink 实际断供? 注意: 项目把 commodity 当**全局 pool** (`PROJECT_LOCK.md` global pooling 条款: shared boundary/core 资源 commodity-aggregated), 端口数量由 binding 面的 52-port / exact-count 保证 (specs/04 §4.5)。所以「供需数量配平」**是否本就不在 routing 面的责任内** —— routing 只证拓扑可达, 数量配平由 binding/pool 语义在别处保证? 请明确判: 若是后者 (routing 不负责数量配平, 只负责拓扑连通, 而拓扑连通的正确判据就是「每 source 到某 sink、每 sink 被某 source 达」), 那 guard 的存在性语义就是**对的**, A4' 不成立。**但请独立从 specs 推这个分工**, 不要因为「r9/r8 都这么判」就接受 —— 给出你自己的规则依据: routing 面的 soundness 契约到底是「拓扑可达」还是「可行流」, 二者在本项目的 pool 语义下是否等价。若你能举出一个「拓扑可达成立但任何可行流都不存在」的布局且它被认证 FEASIBLE, 那是 HIGH。

### B 回归核 (只在怀疑残留 / 反向缺陷时进, 不重报已 lock 修复本身)

- **F-RT-R2-01 极性** (`PROJECT_LOCK.md:120`)、**F-RT-R2-02 逐边守恒** (:121, 已在 A1'/A2' 攻)、**F-RT-R3-01 connector 两层锁** (:122)、**F-RT-R4-01 多孤岛** (:123)、**F-RT-R4-02 重复 key** (:124)、**F-RT-R5-01 外置域 clip** (:125): 这些是已 lock 修复点, **不重报修复本身**; 只在你能给出**同型残留 / 反向缺陷 / 修复不完备**的 file:line + probe 时报。
- guard fail-closed 边界: `solve()` (:1728-1842) CP-SAT OPTIMAL/FEASIBLE 后**必过** `_validate_selected_route_connectivity()` (:1774) 才返 FEASIBLE; 拒绝则 `_add_source_side_connectivity_cut()` (:1797) 或 fallback `_add_selected_route_nogood()` (:1814) 后续解; 预算耗尽清 `_solver`/置 UNKNOWN 返 TIMEOUT (:1740-1753); `extract_routes()` (:1844+) status + `_connectivity_guard_accepted` 双门闩。r9 已核 TIMEOUT 清 witness 彻底; **本轮只在你结合 A1'-A3' 新视角发现 guard 接受边界有新缝时再报**。
- lazy W/X 证书: `_add_source_side_connectivity_cut()` (:1535-1589) + `_self_check_source_side_connectivity_cut()` (:1435-1533) 独立重验 W/X (source∈W、sink∉W、移除 X 在 full potential graph 断开全部 source→sink、incumbent∩X=∅), 任一不成立 fallback selected-positive nogood。这是 acceleration-only (`PROJECT_LOCK.md:127`)。**advisory 第四次复核**: `_route_state_adjacency` 当 potential-graph oracle 时未显式过滤 source-entry arcs —— r7/r8/r9 均判仅影响保守度非 soundness (connector side 已被域剔除)。**结合 A1' 的「共享通道双重记账」新视角重看**: 这个 over-approx 的 potential graph 会不会让 `_self_check` 的「移除 X 后 full graph 断开」判断**误判断开** (over-approx 图更密, 断开更难, 所以 cut 更难过 = 仍只损保守度) 还是**误判连通** (放过无效 cut)? r9 判前者; 你独立判, 若仍是前者明确写。
- precheck 三态契约: routing 端 `analyze_exact_routing_domain()` (:385) 产 status ∈ `{feasible, front_blocked, relaxed_disconnected}`; benders allowlist `_EXACT_ROUTING_PRECHECK_VERIFIED_STATUSES` (`benders_loop.py:123`), 非 allowlist fail-closed UNKNOWN (`benders_loop.py:5381-5408`, F-BL-R7-01)。r9 已逐项核 (ERROR 合成 / TypeError default-feasible 不污染后续证书链 / 缺 status 字段 current producer 不可达 / 无裸用 precheck 结论产 candidate-wide INFEASIBLE 的 live path)。**本轮只在你发现新的 precheck→证书 转写缝时报**, 别复读 r9 三态判读。

## 明确不要报的

- 已修 lock 条款 (重复报不算): **F-RT-R2-01/R2-02** (`PROJECT_LOCK.md:120/121`)、**F-RT-R3-01** (:122)、**F-RT-R4-01/R4-02** (:123/124)、**F-RT-R5-01** (:125); 关联 routing soundness 条款 :126 (CP-SAT FEASIBLE 非认证边界, guard 必证)、:127 (lazy cut acceleration-only + W/X 自验)、:134 (binding-local safe-reject 先 binding nogood)、:136 (F-BL-R7-01 status allowlist)、:117 (全封闭空矩形允许, exterior 连通不在 exact 契约)。**钉为攻击面 ≠ 重报修复本身**: 只有给出同型残留 / 反向缺陷 / 修复不完备的新 file:line + probe 才算 finding。
- `routable_cells` / `RoutingGrid.neighbors()` stale API (无 live proof consumer, r6/r7/r8/r9 已审结)。
- **exploratory / env-gated 行为不属 P1.2 soundness**: `EXACT_USE_POSE_BOOL_MASTER` / `EXACT_POWER_PLACEMENT_SUBPROBLEM` / `EXACT_B1_BYPASS_ROUTING_PRECHECK` / `EXACT_B1_PATCH_ROUTING_CORE` 等都 env-gated, 非 certified 默认路径 (`pose_bool_master_not_certified` / readiness gate 阻断)。这些通道的缺陷标 conditional/env-gated hardening, **不是 soundness reset**。
- 设计决策 (canonical / 266 口径 / omni_wireless / 52-Port 不变量 / `min_side>=6` admissibility, owner 已定)。
- master / binding / cuts / preprocess / benders / campaign / scheduler 各面 (各自有线, 本轮 HEAD 已带它们的修复, 别重报)。
- preflight `phase_1_2_spike_close` BLOCKED 是 owner gate (不报); P1.3B `step_8_apply_to_master` 禁区; exploratory 行为/性能不审; persisted `exact_safe_cuts` 是 telemetry 非 proof。
- **ghost 不含 exterior-path 要求是 owner 已定的禁区, 别建议加**。
- `candidate_placements.json` 已随包并校验 (sha256 `adcc2a6e...`, 45,773,799 bytes), 不准伪造; 别建议改 candidate 生成。

## 自验环境与已知基线

- candidate 已随包, 全量 `python -m pytest -q src/tests` 应 **0 failed** (passed ≈3074, 数目以实跑为准, 硬不变量 = 0 failed; 沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。跑不完就跑 routing 专项 (`src/tests/test_routing.py` / `test_exact_contract.py` / `test_p0_certified_soundness_fixes.py` / `test_d2_separator_support_context.py` 等) + 如实声明哪些没跑。
- `python scripts/check_p1_2_proof_obligations.py` pass (8 obligations)。
- finding 必须带**可复现 probe 或 file:line 严谨论证**; 实证推翻你的怀疑就不要报。
- specs 真实文件名: pool/commodity 语义 = `specs/08_topological_flow_subproblem.md`; routing 约束规则 = `specs/09_exact_grid_routing_subproblem.md` (:43-128); pattern = `specs/03_rule_canonicalization.md` (:306-345); connector 语义 = `specs/06_candidate_placement_enumeration.md`; 端口 exact-count = `specs/04` §4.5。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附分段判读 (本轮主攻线): A1' 共享内部通道双重记账 / A2' count-balance 下层错配配对 / A3' 孤立 cycle 喂 merger·可达≠流贯通 / A4' source/sink 数量守恒 vs 存在性 / B 回归核 (guard fail-closed + lazy W/X advisory 第四次 + precheck 三态) 的真 Pro 复核。**每段给出你的独立规则依据** (从 specs/08·specs/09 推 routing 面的 soundness 契约到底是「拓扑可达」还是「可行流」), 不复读 r9 判读。
- 真 Pro 独立确认轮; 前轮 (含 r8/r9 真 Pro) 连零不代表本轮默认干净; 按你自己的独立、对抗判断下结论。

## 严重度纪律

只有 **canonical 数据 + 默认 env 下** 放过非法布线被认证 FEASIBLE = soundness, P1.2 闭环只认这个, **HIGH = soundness reset**。env-gated / conditional / false-INFEASIBLE (保守失败, 漏真最大矩形) / lazy-cut 保守度 / precheck 早剪过严 = hardening/availability, **明确标 LOW 加固, 不是 reset**。A3' 那种「孤立环冗余占格但不影响真连通正确性」的情形, 若不能被用来伪造一个本该 false 的连通认证, 标 LOW/cleanliness 而非 HIGH。

## 范围边界

重点 = 布线编码 soundness 三块 (CP-SAT 约束本体 / guard + lazy cut / precheck 消费 + benders 契约一致性) 在「count-conservation + existential-reachability 组合是否等价可行流」这条新主线下的真 Pro 独立复核; 其余 7 面及各自子问题正确性不审。怀疑跨面时交叉引述 `PROJECT_LOCK.md` 对应条款而非在本轮重证。
