# 终末地 IndustrialPlanner 精确求解器 — routing 面 round 11 (真 Pro 独立重审·跨 commodity 耦合 vs 逐 commodity 隔离验证的缝)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_0590f9ca.zip`, sha256 `0590f9ca30aac5bb7afe18945eb36d347ea8b0c5b467fd6baff4679eff8c5234`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), **干净 git 树, HEAD `7fec29a` (rounds 1+2 及各面同期修复全部已合入 —— 这是带修复的新树)**。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。`data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) **已随包**, 已校验, 不需再生。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → **routing 网格布线** → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **routing 网格布线子问题 + 连通性 guard + lazy connectivity cut + precheck 三态消费** (`src/models/routing_subproblem.py` 为核, 配 `src/search/benders_loop.py` 的 routing precheck 调用/消费点; `src/models/flow_subproblem.py` 是诊断旁路, 不产认证结论)。

## 本面定义与历史 + 本轮性质 (关键, 必读)

本面 = routing 子问题的 soundness: 域分析/precheck (产 status)、CP-SAT 约束编码 (route-state 变量 / 方向连续性 / 逐边守恒 / cell-layer 容量 / bridge 共存 / pattern 封闭集 / obstacle·connector 域排除 / 端口 adherence)、连通性 guard (reachability 重验)、lazy connectivity cut (W/X 证书)、precheck 三态消费契约。历史:

- r2 = F-RT-R2-01 (terminal 极性朝向 connector, false-INFEASIBLE) + F-RT-R2-02 (层重叠下逐边通道守恒, 局部「≥1 支撑」放行隐形 splitter/merger = false-FEASIBLE);
- r3 = F-RT-R3-01 (port connector cell 是 terminal 节点非 belt 格, false-FEASIBLE);
- r4 = F-RT-R4-01 (同 commodity terminal fronts 被强压单连通分量, false-INFEASIBLE) + F-RT-R4-02 (重复 terminal key multiplicity 丢失, 外置 port_specs hardening);
- r5 = F-RT-R5-01 (外置 routing 域只减 connector 没与 free grid 求交, 穿墙 false-FEASIBLE);
- r6/r7/r8 = 零 finding (guard 本体 / 约束本体 + precheck 生产者 / 首个真 Pro Q1-Q8 逐项);
- r9 = 零 finding: 「**逐 state / 逐 2D 边 / 逐 commodity 自身**的局部物理可实现性」—— 单 state 臂被消费、单边 send==recv、单 commodity front 必被检查、guard reachability 与 CP-SAT 局部语义同构;
- **r10 = 零 finding**: 「**count-conservation + existential-reachability 的组合是否等价 realizable simultaneous flow**」主线 —— A1' 共享纯 belt 中段双重记账 (无 splitter 时入口缺 receiver 边被 CP-SAT 逼成 INFEASIBLE, 有 splitter/merger 才 FEASIBLE) / A2' count-balance 下层错配配对 (确认代码 layer-agnostic, 但 specs/09:59 写「接驳层级 L'」非同层, 故非当前规则下 bug) / A3' 孤立 cycle 喂 merger (存在 source-less 选中环, 但只占格不伪造连通, 判 LOW cleanliness 非 soundness) / A4' source/sink 数量配平 vs 存在性 (routing 面契约 = 拓扑可达非单位 max-flow, 数量配平在 binding/pool, `PROJECT_LOCK.md:142` 明确单位流守恒不能表达 splitter/merger), 全 clean, 无补丁, 13+2+2 专项回归 + `check_p1_2_proof_obligations` 8 obligations pass。

**本轮 r11 = 又一次独立全面 soundness 重审 (连续两轮 r9/r10 真 Pro 零 finding)。姿态要求:**

r9 把攻击线划在「**单**个 route-state / **单**条 2D 边 / **单**个 commodity 自身」的局部物理可实现性; r10 把它抬到「**单个 commodity 内部** count-conservation + reachability 是否等价可行流」。**两轮有一个共同的、从未被触碰的盲区: 它们都在「单个 commodity 内部」推理, 从未问过「不同 commodity 之间的耦合」。**

**本轮请换到「跨 commodity 耦合 (cross-commodity coupling) vs 逐 commodity 隔离验证 (per-commodity isolated validation)」这条全新主线。** 核心事实 (你必须自己从源码确认):

- CP-SAT 把不同 commodity 耦合在一起的**唯一**约束, 是逐 (cell, layer) 的 `AddAtMostOne` (`routing_subproblem.py:1026-1029`)。这个桶 `_vars_by_cell_layer` 的 key 是 `(x, y, layer)` —— **不带 commodity** (`:735` 定义, `:974` 填充)。所以一个 `(cell, layer)` 上**所有 commodity 的所有 route-state 合起来最多选 1 个**。这正对应 `specs/09:49` 的 `∑_{k∈𝒦} r ≤ 1` (容量约束对所有 commodity k 求和)。
- **除此之外, routing 的每一条 soundness 约束都是逐 commodity 隔离的**: 逐边守恒 `_add_directed_edge_balance_constraints` (`:1068-1114`) 按 `(2D edge, commodity)`; successor/predecessor (`:1120-1194`) 按 commodity; 端口 adherence (`:1196-1237`) 按 commodity; **连通性 guard (`:1591-1687`) 逐 commodity 独立做 reachability** (`commodities_to_check` 逐个循环, `_compute_selected_source_side_closure` `:1390` 显式 `selected_for_commodity = {key ... if key[5]==commodity}`); lazy W/X cut (`:1375-1433`) 也 `_potential_route_keys_for_commodity`。
- **结论性怀疑**: 每个 commodity 各自被证「拓扑连通」, 但它们共享同一张 70×70×2 物理网格, 只通过一个**与 commodity 无关**的 per-cell-layer AtMostOne 互相竞争。**问题: 逐 commodity 隔离的 guard reachability + 跨 commodity 的 AtMostOne, 它们的合取, 是否真能证「所有 commodity 的选中子图能在同一张物理网格上同时实现 (mutually consistent simultaneous realization)」? 还是存在一个缝, 让某个跨 commodity 的物理冲突/共享, 因为没有任何单一 per-commodity 检查能看见它, 而被放行成 false-FEASIBLE?**

前 10 轮的 clean 不构成任何先验。真 Pro 同期切到其它面 (Benders F-BL-R7-01、cuts CUT-R12/R13-H1 审 11+ 轮才被抓出、preprocess F-PRE-R15/R16/R17/R18、几何 master F-GM-R11/R12-PB) 都在「前轮判 clean」的面上挖出真 finding —— 所以 routing 连零 5 不等于本轮默认干净。

注意: 包内带其它面同期落的修复条款 (各面有自己的线, 已入 LOCK), **别在本轮重报**。HEAD `7fec29a` 相对 r10 树 routing 面**本体无算法改动** (r9/r10 零 finding), 攻击角度必须是新的 (跨 commodity), 不是等代码变了。

## 本轮主攻线 (cross-commodity coupling soundness, 4 块新角 C1-C4 + 1 块回归核 B)

行号基于本包 `routing_subproblem.py` (1873 行) / `benders_loop.py`, 扫一眼确认引用真实别照抄。任何比规则**更严** = false-INFEASIBLE (漏真最大矩形, availability, LOW); 任何比规则**更松** = false-FEASIBLE (放过非法布线, soundness, HIGH)。**本轮优先攻 C1-C4 (跨 commodity 视角); B 是回归核, 只在你怀疑残留/反向缺陷时进。**

### C1 跨 commodity 物理一致性 —— 逐 commodity 各证连通, 合起来是否仍在一张网格上可实现 (本轮重点)

guard (`:1591-1687`) 对 `commodities_to_check` 逐个循环, 每个 commodity 用**只属于该 commodity 的选中 state** (`:1390` `selected_for_commodity`) 重建图、做 reachability。**它从不跨 commodity 看任何东西**。把不同 commodity 锁在一起的只有 `_add_capacity_constraints` (`:1026-1029`) 的 per-(cell,layer) `AddAtMostOne` (commodity-agnostic 桶)。请独立追问这个分工是否堵死所有跨 commodity 物理矛盾:

- AtMostOne 锁的是「一个 (cell, layer) 最多 1 个 route-state (跨所有 commodity)」。这等价于 `specs/09:49` 的 `∑_{k∈𝒦} r_{c,L} ≤ 1`。**问题 1**: 这个 per-cell-layer 的互斥, 是否足以保证「两个 commodity 的选中子图物理上不冲突」? 物理冲突的完整集合是什么 —— 是否只有「同 (cell, layer) 同占」一种? 还是存在**别的**跨 commodity 物理冲突, AtMostOne 锁不住、而逐 commodity guard 又看不见? 候选: (a) 两个 commodity 的 belt 在**同 cell 不同 layer** (L0 belt + L1 bridge) 共存 —— 规则 `specs/09:54` 只许「L1 有桥则 L0 要么空要么直线 belt」, 这个跨 commodity 的 L0/L1 约束由 `_add_bridge_constraints` (`:1031-1042`) 处理, 但它**只在同一 cell 内**把 `l1_any` (该 cell 所有 L1 var 的 max, 跨 commodity) 与 `l0_nonstraight` (该 cell 所有 L0 非直 var, 跨 commodity) 互斥 —— **请核: 这个跨 commodity 的 L0-nonstraight ⊥ L1-any 是否完整覆盖了「L1 有桥 ⇒ L0 只能空或直线」的全部物理含义**? 特别是: commodity A 的 L1 bridge 与 commodity B 的 L0 直线 belt 同 cell 共存 —— 规则允许 (L0 是直线), 但物理上一个 cell 的 L0 直线带和它正上方的桥, 两者朝向是否必须一致/无关? bridge 的「无缝起降」(`specs/09:55`) 是否要求桥端正下方的 L0 必须是**同 commodity** 的接驳格, 还是任意 commodity 的直线带都行? 若规则要求桥端接驳必须本 commodity 而代码允许跨 commodity 桥压别人的直线带, 是否 false-FEASIBLE?
- **决定性追问**: 构造一个 probe, 两个 commodity A/B, 几何上逼出「A 的 L1 bridge 段」与「B 的 L0 belt 段」在同一批 cell 上交错共存, 各自 guard 判连通 ✓。dump 每个共存 cell 的 (L0 占用 commodity, L0 pattern, L1 占用 commodity, L1 pattern), 对照 `specs/09:51-55` 桥规则逐条核: 是否有任何一种被 CP-SAT + guard 接受的跨 commodity L0/L1 共存, 在真实游戏里**无法同时建造** (如桥端落在异 commodity 的转弯带上、或桥正下方 L0 是异 commodity 的非直线 state 而 `_add_bridge_constraints` 因某种 bucketing 漏掉)? **这是 r9/r10 没碰的角**: 它们只在单 commodity 内看 L0/L1 (r9 A2/r10 A2' 都是「同 commodity 一条 2D 边上 L0+L1 共存」), 从未问「**异** commodity 的 L0 与 L1 在同 cell 共存的物理合法性」。

### C2 端口 front cell 跨 commodity 共享 —— 一个 free cell 同时当两个 commodity 的 terminal front

`_add_port_adherence` (`:1196-1237`) 对每个 port spec 要求其 front cell `(fx,fy)` 上**该 commodity** 的对应方向 route-state 恰为 1。`_terminal_fronts_by_commodity` (`:1244-1256`) 把 source/sink front 按 commodity 分桶。**问题**: 同一个物理 free cell `(fx,fy)` 能不能同时是 commodity A 的 source front **和** commodity B 的 sink front (或两个不同 commodity 的 front)?

- 若能: cell `(fx,fy)` 上 L0 层既要为 A 选一个含某方向的 state, 又要为 B 选一个含某方向的 state —— 但 per-(cell,layer) AtMostOne (`:1026-1029`) **只允许 L0 上选 1 个 state (跨 commodity)**。所以 A 的 front state 和 B 的 front state 在同 cell 同 L0 互斥, 两个 port adherence (`sum==1` each) 同时要求各自 ≥1 个不同 commodity 的 state on 同 (cell, L0) → AtMostOne 与两个 `==1` 矛盾 → CP-SAT INFEASIBLE。**请核这是否真的发生**: port adherence 的 `vars_for_port` (`:1214/:1220`) 是按 `(fx, fy, GROUND_LAYER, dir, commodity)` 取的, 带 commodity; 两个不同 commodity 的 front 在同 cell 各自 `sum==1`, 配 commodity-agnostic AtMostOne, 是否正确逼出矛盾 (好) 还是有缝让两个 commodity 共享同一个物理 front cell 而 guard 各自判连通 (坏, 一个 cell 物理上只能跑一种 commodity 一条带, 却被两个 commodity 的认证同时占用)?
- **更细的缝**: bridge 桥从一个 commodity 的 front cell **正上方 L1** 穿过 —— front cell 的 L0 被 commodity A 的 terminal state 占, L1 被 commodity B 的桥占, AtMostOne 各层独立不冲突。但 `specs/09:54` 要求「L1 有桥 ⇒ L0 空或直线 belt」; A 的 terminal front state 是不是「直线 belt」? source front 的 state `flow_in = Opp(dir)` 单进, 它的 flow_out 可能转弯 (非直线)。若 A 的 front state 非直线而 B 的桥压在其正上方, `_add_bridge_constraints` (`:1031-1042`) 是否把这个 cell 的 A-front-nonstraight 纳入了 `l0_nonstraight_vars`? 看 `:983-984`: `elif component_type != "belt" or not _is_straight_state(...)` 才进 `_l0_nonstraight_vars` —— **terminal front 的 state 是什么 component_type**? 它会不会因为是 belt-straight 而漏出 `l0_nonstraight`, 让一座异 commodity 桥合法压在一个本不该被压的 terminal 接驳带上? 请构造 probe 验证 terminal front state 的 component_type / straight 判定, 以及桥能否压在异 commodity terminal front 正上方。

### C3 跨 commodity 的「借道」与 AtMostOne 的方向盲点 —— 守恒逐 commodity, 互斥跨 commodity, 两者错位

逐边守恒 (`:1068-1114`) 是 `(2D edge, commodity)` 的, successor/predecessor (`:1120-1194`) 也带 commodity; 但 AtMostOne (`:1026-1029`) 跨 commodity。请追问这个「守恒带 commodity / 互斥不带 commodity」的错位是否制造缝:

- 设 cell C 的 L0 被 commodity A 的一个 belt state 占 (AtMostOne 用掉了 C-L0 的唯一名额)。commodity B 的逐边守恒/successor 在涉及 C 时, B 在 C-L0 上的所有候选 var 都因 AtMostOne 被压成 0 —— 这正确地阻止 B 借道 C。**但 guard 呢**: guard 对 B 做 reachability 时, `_route_state_adjacency` (`:1311-1330`) 只在 **B 自己的选中 state** 上建图, C 上没有 B 的选中 state (被 AtMostOne 压 0), 所以 B 的路径自然绕开 C。这看起来一致。**真正要攻的缝**: AtMostOne 只锁「同 cell-layer 最多 1 state」, 它**不锁 A 与 B 的 state 在相邻 cell 之间的方向兼容性**。两个 commodity 的带子在物理上能不能「交叉而不共格」—— A 的带从 C 向东出、B 的带从 C 北邻向南进 C 南邻, 几何上两条带在 C 这个十字路口**交叉**但不共占 C? 真实游戏里两条不同物料的传送带能否在不共格的前提下垂直交叉 (无桥)? 若**不能** (交叉必须靠桥, 即其中一条必须上 L1), 而 CP-SAT 因为守恒/AtMostOne 都不锁「相邻异 commodity 带的交叉」→ 允许两条 L0 带在相邻格几何交叉无桥 → guard 各自判连通 → false-FEASIBLE。请核: 是否存在任何约束 (隐式或显式) 阻止两个 commodity 的 L0 带在相邻格几何交叉而不借桥? 还是 routing 抽象里「带只占格、不占格间的边」, 所以相邻格交叉本就合法 (两条带只是擦肩, 物料不混)? 从 `specs/09` 推: 防撞约束 (`:47-49` capacity & collision-free) 锁的是**格内**单占, 它**锁不锁格间交叉**? 若规则只锁格内、交叉在格间合法, 则 C3 不成立 (这是设计而非 bug); 若规则隐含「物料流交叉必须立体分层 (桥)」而代码没锁, 则 HIGH。**给出你自己的规则依据**, 别默认任一结论。

### C4 lazy W/X cut 与 guard 的跨 commodity 一致性 —— cut 逐 commodity 加, 但 nogood 影响全局

lazy source-side cut `_add_source_side_connectivity_cut` (`:1535-1589`) 和 self-check (`:1435-1533`) 都是**逐 commodity** 的 (`_potential_route_keys_for_commodity` `:1375`, `_compute_selected_source_side_closure` `:1390` 过滤 `key[5]==commodity`)。cut 形如 `∑_{s∈X} r_s^k ≥ 1`, 只约束 commodity k 自己的 var。**问题**: 这个逐 commodity 的 cut 是否可能与**别的 commodity 的可行性**产生跨 commodity 干扰, 让一个本该可行的全局布局被误删 (false-INFEASIBLE, LOW) —— 或更糟, 让一个本该被拒的 incumbent 在加 cut 后**换 commodity 共享格的方式**重新满足 guard 而实际仍不可实现 (soundness)?

- self-check 的「移除 X 后 full potential graph 断开全部 source→sink」(`PROJECT_LOCK.md:127`) 是在 **commodity k 自己的 potential graph** 上验的 (`:1416` `_potential_route_keys_for_commodity(commodity)`)。它**不考虑别的 commodity 占了哪些格**。所以 k 的 potential graph 是「假设 k 能用所有 active cell」的 over-approx (没扣掉被别 commodity 选中、经 AtMostOne 实际不可用的格)。r9/r10 advisory 已四次判这个 over-approx「只损保守度非 soundness」(potential 图更密 ⇒ 断开更难 ⇒ cut 更难过)。**本轮换跨 commodity 角度重看**: 这个 over-approx **不扣别 commodity 占格**, 会不会在某个跨 commodity 场景下, 让 self-check 误判「移除 X 后断开」(因为 over-approx 图里有一条路径其实被别 commodity 占格堵死, 但 self-check 看不见, 反而认为连通 → 判 X 不是有效 cut → fallback nogood)? 还是反向 (over-approx 更连通 ⇒ 更难判断开 ⇒ 更易 fallback, 仍只损保守度)? r9/r10 判后者; 你独立判, 给出跨 commodity 场景下的方向分析。若你能构造一个跨 commodity 布局让逐 commodity self-check 的 W/X 证书**误判连通**从而附上一个无效 cut (删掉合法续解) → false-INFEASIBLE LOW; 若能让它放过一个本该被拒的 incumbent → soundness HIGH (但 cut 是 `≥1` 加约束, 只会更严不会更松, 仔细论证为何不可能/可能)。

### B 回归核 (只在怀疑残留 / 反向缺陷时进, 不重报已 lock 修复本身)

- **F-RT-R2-01 极性** (`PROJECT_LOCK.md:120`)、**F-RT-R2-02 逐边守恒** (:121)、**F-RT-R3-01 connector 两层锁** (:122)、**F-RT-R4-01 多孤岛** (:123)、**F-RT-R4-02 重复 key** (:124)、**F-RT-R5-01 外置域 clip** (:125): 已 lock 修复点, **不重报修复本身**; 只在你能给出**同型残留 / 反向缺陷 / 修复不完备**的 file:line + probe 时报。
- guard fail-closed 边界: `solve()` (`:1728-1842`) CP-SAT OPTIMAL/FEASIBLE 后**必过** `_validate_selected_route_connectivity()` (`:1774`) 才返 FEASIBLE; 拒绝则 `_add_source_side_connectivity_cut()` (`:1797`) 或 fallback `_add_selected_route_nogood()` (`:1814`) 后续解; 预算耗尽清 `_solver`/置 UNKNOWN 返 TIMEOUT (`:1739-1753`); `extract_routes()` (`:1844-1849`) status + `_connectivity_guard_accepted` 双门闩。r9/r10 已核 TIMEOUT 清 witness 彻底; **本轮只在你结合 C1-C4 跨 commodity 新视角发现 guard 接受边界有新缝时再报**。
- lazy W/X 证书: `_add_source_side_connectivity_cut()` (`:1535-1589`) + `_self_check_source_side_connectivity_cut()` (`:1435-1533`) 独立重验 W/X (source∈W、sink∉W、移除 X 在 full potential graph 断开全部 source→sink、incumbent∩X=∅), 任一不成立 fallback selected-positive nogood。acceleration-only (`PROJECT_LOCK.md:127`)。**advisory 第五次复核**: `_route_state_adjacency` 当 potential-graph oracle 时未显式过滤 source-entry arcs + 不扣别 commodity 占格 (见 C4) —— r7/r8/r9/r10 均判仅影响保守度非 soundness。**结合 C4 跨 commodity 视角独立重判**, 若仍是保守度损失明确写。
- precheck 三态契约: routing 端 `analyze_exact_routing_domain()` (`:385`) 产 status ∈ `{feasible, front_blocked, relaxed_disconnected}`; benders allowlist `_EXACT_ROUTING_PRECHECK_VERIFIED_STATUSES` (`benders_loop.py:123`), 非 allowlist fail-closed UNKNOWN (`benders_loop.py:5439-5455`, F-BL-R7-01)。r9/r10 已逐项核 (ERROR 合成 / 缺 status / summary↔analysis 一致性 / safe-reject literal-bool / blocked_ports 兜底, F-BL-R9-01/02/03)。**本轮只在你发现新的 precheck→证书 转写缝时报**, 别复读前轮三态判读。

## 明确不要报的

- 已修 lock 条款 (重复报不算): **F-RT-R2-01/R2-02** (`PROJECT_LOCK.md:120/121`)、**F-RT-R3-01** (:122)、**F-RT-R4-01/R4-02** (:123/124)、**F-RT-R5-01** (:125); 关联 routing soundness 条款 :126 (CP-SAT FEASIBLE 非认证边界, guard 必证)、:127 (lazy cut acceleration-only + W/X 自验)、:134 (binding-local safe-reject 先 binding nogood)、:136 (F-BL-R7-01 status allowlist)、:117 (全封闭空矩形允许, exterior 连通不在 exact 契约)。**钉为攻击面 ≠ 重报修复本身**: 只有给出同型残留 / 反向缺陷 / 修复不完备的新 file:line + probe 才算 finding。
- `routable_cells` / `RoutingGrid.neighbors()` stale API (无 live proof consumer, r6-r10 已审结)。
- **exploratory / env-gated 行为不属 P1.2 soundness**: `EXACT_USE_POSE_BOOL_MASTER` / `EXACT_POWER_PLACEMENT_SUBPROBLEM` / `EXACT_B1_BYPASS_ROUTING_PRECHECK` / `EXACT_B1_PATCH_ROUTING_CORE` 等都 env-gated, 非 certified 默认路径 (`pose_bool_master_not_certified` / readiness gate 阻断)。这些通道的缺陷标 conditional/env-gated hardening, **不是 soundness reset**。
- 设计决策 (canonical / 266 口径 / omni_wireless / 52-Port 不变量 / `min_side>=6` admissibility, owner 已定)。
- master / binding / cuts / preprocess / benders / campaign / scheduler 各面 (各自有线, 本轮 HEAD 已带它们的修复, 别重报)。
- preflight `phase_1_2_spike_close` BLOCKED 是 owner gate (不报); P1.3B `step_8_apply_to_master` 禁区; exploratory 行为/性能不审; persisted `exact_safe_cuts` 是 telemetry 非 proof。
- **ghost 不含 exterior-path 要求是 owner 已定的禁区, 别建议加**。
- `candidate_placements.json` 已随包并校验 (sha256 `adcc2a6e...`, 45,773,799 bytes), 不准伪造; 别建议改 candidate 生成。

## 自验环境与已知基线

- candidate 已随包, 全量 `python -m pytest -q src/tests` 应 **0 failed** (passed ≈3092, 数目以实跑为准, 硬不变量 = 0 failed; 沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。跑不完就跑 routing 专项 (`src/tests/test_routing.py` / `test_exact_contract.py` / `test_p0_certified_soundness_fixes.py` / `test_d2_separator_support_context.py` 等) + 如实声明哪些没跑。
- `python scripts/check_p1_2_proof_obligations.py` pass (8 obligations)。
- finding 必须带**可复现 probe 或 file:line 严谨论证**; 实证推翻你的怀疑就不要报。
- specs 真实文件名 (本包确认行号): pool/commodity 语义 = `specs/08_topological_flow_subproblem.md`; routing 约束规则 = `specs/09_exact_grid_routing_subproblem.md` (**容量单占跨 commodity = :47-49; 桥规则 = :51-55; 方向连续性「接驳层级 L'」= :57-59; 端口度数 = :69-75; P0 guard addendum = :100-106; lazy cut = :108-117**); pattern 封闭集 = `specs/03_rule_canonicalization.md` (:306-345); connector 语义 = `specs/06_candidate_placement_enumeration.md`; 端口 exact-count = `specs/04` §4.5/§4.7。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附分段判读 (本轮跨 commodity 主攻线): C1 跨 commodity 物理一致性 (L0/L1 异 commodity 共存 + 桥规则) / C2 端口 front cell 跨 commodity 共享 / C3 异 commodity 带相邻格交叉无桥 / C4 lazy W/X 逐 commodity cut 的跨 commodity 一致性 / B 回归核 (guard fail-closed + lazy W/X advisory 第五次 + precheck 三态) 的真 Pro 复核。**每段给出你的独立规则依据** (从 specs/09 容量单占 :47-49 / 桥规则 :51-55 / 方向连续性 :57-59 推: routing 面对「跨 commodity 物理冲突」到底锁了哪些、漏了哪些, 哪些是设计上合法的擦肩), 不复读 r9/r10 判读。
- 真 Pro 独立确认轮; 前轮 (含 r8/r9/r10 真 Pro) 连零不代表本轮默认干净; 按你自己的独立、对抗判断下结论。

## 严重度纪律

只有 **canonical 数据 + 默认 env 下** 放过非法布线被认证 FEASIBLE = soundness, P1.2 闭环只认这个, **HIGH = soundness reset**。env-gated / conditional / false-INFEASIBLE (保守失败, 漏真最大矩形) / lazy-cut 保守度 / precheck 早剪过严 = hardening/availability, **明确标 LOW 加固, 不是 reset**。跨 commodity 那种「两条带物理上能合法擦肩、抽象里本就只锁格内单占」的情形, 若不能被用来伪造一个本该 false 的连通/可实现认证, 标设计/cleanliness 而非 HIGH。

## 范围边界

重点 = 布线编码 soundness 三块 (CP-SAT 约束本体 / guard + lazy cut / precheck 消费 + benders 契约一致性) 在「**跨 commodity 耦合 (per-cell-layer AtMostOne) 与逐 commodity 隔离验证 (守恒/successor/guard/W-X cut) 之间是否留有跨 commodity 物理冲突的缝**」这条新主线下的真 Pro 独立复核; 其余 7 面及各自子问题正确性不审。怀疑跨面时交叉引述 `PROJECT_LOCK.md` 对应条款而非在本轮重证。
