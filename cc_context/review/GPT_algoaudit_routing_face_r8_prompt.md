# 终末地 IndustrialPlanner 精确求解器 — routing 面 round 8 (真 Pro 重审·网格布线 soundness 全面复核)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_f4418b04.zip`, sha256 `f4418b045b257e186c0d06ad6045908a33118d597b8f65666fb39691378965d1`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照 (HEAD 2e1da65)。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → **routing 网格布线** → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **routing 网格布线子问题 + 连通性 guard + lazy connectivity cut** (`src/models/routing_subproblem.py` 为核, 配 `src/search/benders_loop.py` 的 routing precheck 调用/消费点)。

## 本面定义与历史 + 本轮性质 (关键, 必读)

本面 = routing 子问题的 soundness: 域分析/precheck (产 status)、CP-SAT 约束编码 (route-state 变量 / 方向连续性 / 边守恒 / cell-layer 容量 / bridge 共存 / pattern 封闭集 / obstacle·connector 域排除 / 端口 adherence)、连通性 guard (reachability 重验)、lazy connectivity cut (W/X 证书)。历史 (**前 6 个 HIGH 全部是 GPT thinking 模型或更早所抓**):
- r2 = F-RT-R2-01 (terminal 极性朝向 connector, 紧凑 corridor false-INFEASIBLE) + F-RT-R2-02 (层重叠下逐边通道守恒, 局部「≥1 支撑」放行隐形 splitter/merger = false-FEASIBLE);
- r3 = F-RT-R3-01 (port connector cell 是 terminal 节点非 belt 格, 商品穿别的 connector / 复用 terminal 侧 = false-FEASIBLE);
- r4 = F-RT-R4-01 (同 commodity terminal fronts 被强压单连通分量, 双孤岛合法布局 false-INFEASIBLE) + F-RT-R4-02 (重复 terminal key multiplicity 丢失, 外置 port_specs hardening);
- r5 = F-RT-R5-01 (外置 routing 域只减 connector 没与 free grid 求交, stale/恶意域在 solid 格上建 route-state = 穿墙 false-FEASIBLE);
- r6 = 零 finding (guard 本体首次独立深审);
- r7 = 零 finding (约束本体直审 + precheck 生产者 + 自由攻击角, 连零 2 达饱和下沿)。

**本轮 r8 = 真 Pro 重审。关键背景, 决定本轮姿态:**
**此前本面全部轮次 (r2-r7) 都是较弱的 GPT thinking 模型审的; 本轮起切到 GPT Pro 扩展模式 (真深度推理)。** 同期真 Pro 一切到其它面就抓出 thinking 漏了多轮的真 finding: Benders/LBBD (F-BL-R7-01)、cuts (CUT-R12-H1 / CUT-R13-H1, thinking 审 11+ 轮没发现)、preprocess (F-PRE-R15-01 / R16-01 / R16-02)、几何 master (F-GM-R11-PB-REQ-POLE-01 / STALE-01)。**所以本面绝不能因为「thinking 连零 2 达饱和下沿」就默认干净 —— 请把 routing 当作一个从未被深度审过的面, 用你最独立、最对抗的判断, 重走一遍布线编码 soundness。前轮 clean 不构成任何先验。**

注意: 包内带其它面同期落的修复 (master / cuts / preprocess / benders / binding 条款), 各面有自己的线, **别在本轮重报**。

## 审查重点 (布线编码 soundness, 8 块, 按优先级)

任何比规则**更严**的约束 = false-INFEASIBLE (漏真最大矩形); 任何比规则**更松** = false-FEASIBLE (放过非法布线, 更危险)。请独立审 (行号基于本包 routing_subproblem.py):

### Q1 方向/极性编码 (DIR_OPP 一致性, source/sink 对称)
`_index_port_fronts()` (:786-799) 把 source front 编为 `recv_dir = DIR_OPP[dir]`、sink front 编为 `send_dir = DIR_OPP[dir]`。极性消费点: `_add_port_adherence()` (:1196-1237)、边守恒 recv_dir (:1099)、successor/predecessor (:1142/:1180)。任一处残留原 `dir` (非 Opp) → corridor false-INFEASIBLE 或料不进 connector false-FEASIBLE。请**从规则文本独立推导**极性 (不抄实现键方向, F-RT-R2-01 教训), 核 source/sink 对称。

### Q2 边守恒 (terminal 例外精确边界)
`_add_directed_edge_balance_constraints()` (:1068-1118): 每 commodity 每非 terminal cell-to-cell 有向边 `sum(send) == sum(recv)`; 跳过 sink connector side (:1092)、source connector side (:1100)、`(nx,ny) not in active_cells` (:1096)。请核 terminal 跳过条件多跳/漏跳一格的后果 (放行幻影 splitter false-FEASIBLE / 过约束 false-INFEASIBLE), 及与 port adherence terminal 处理的衔接。

### Q3 connector 占用 (terminal-side vs solid 两层锁 + 域 clip)
`_port_connector_cells()` (:120-133)、`_resolve_routing_domain_context()` 统一 `resolved_free_cells = free_cells − port_connector_cells` (:344/:363)、`_bind_domain_analysis()` 二次求交 (:847-859)。三个剔除点任一漏 → 穿 connector false-FEASIBLE。备注: `routable_cells = free_cells | port_cells` (:685/:703) 现无消费者 (stale API, 已挂账), 请确认它确实无 live 消费者再下结论。

### Q4 obstacle 域排除 (只在 active domain 建 var + 外置域求交)
`_add_obstacle_exclusion()` (:1022-1024) 是 **no-op** (注释明示障碍排斥由「只在 active free cells 建 route-state」实现, `_create_routing_variables():947`)。这是 F-RT-R5-01 核心: 只要 active 域含一个 occupied/connector/出界格, 就在墙上建 var 且 guard 接受 = 穿墙 false-FEASIBLE。核 `_bind_domain_analysis` 求交是否覆盖 component **和** active 两个集合 (:850-857), connector/occupied/出界三类是否同口径挡回。

### Q5 pattern 封闭集 (belt/splitter/merger/bridge 枚举完整性)
`_iter_state_patterns()` (:867-905): L1 只 4 直桥 (:868-875); L0 belt 12 (:877-885) + splitter 16 (:887-895, 1进2出+1进3出) + merger 16 (:897-905) = 48。漏 pattern → 合法拓扑无法表达 false-INFEASIBLE; 多 pattern (转弯 bridge / U-turn belt / 自环) → false-FEASIBLE。对照 specs/03 (:306-344) + specs/09 (:51-55) 独立推导封闭集, set-equality 核对。

### Q6 cell-layer capacity AtMostOne (全 var 入桶)
`_add_capacity_constraints()` (:1026-1030) 对 `_vars_by_cell_layer` 桶加 AddAtMostOne; var 入桶在 `_create_routing_variables():974`。任何 var 创建点漏入桶 → 同层多 state 共存 (物理非法 false-FEASIBLE)。确认 :964-980 是唯一 var 创建点。

### Q7 guard 本体 (reachability / terminal 例外 / 多源多汇 pooling / fail-closed)
`_validate_selected_route_connectivity()` (:1591-1687) 重建 selected route-state graph 逐 commodity 检 missing/unreachable (:1659-1666), 直接读 `_selected_route_keys(solver)` (:1604) 非 extract 产物; 邻接 `_route_state_adjacency()` (:1311-1330)、BFS (:1332-1350)、terminal 例外只在 GROUND_LAYER (:1299)。`solve()` (:1728-1842) CP-SAT OPTIMAL/FEASIBLE 后**必过 guard** (:1773) 才返 FEASIBLE, 失败加 self-checked cut/fallback nogood, 预算耗尽清 witness 返 TIMEOUT (:1737-1753); `extract_routes()` (:1844-1870) 双门闩 (status + `_connectivity_guard_accepted`)。核: ① guard 重建图 (layer-agnostic 邻接) 与 CP-SAT successor/predecessor 编码语义有无漂移; ② 多源多汇 pooling 判据 (:1645-1657 每 source 达某 sink + 每 sink 被某 source 达) 与 specs/08 pool 模型是否精确匹配; ③ TIMEOUT 清 witness 是否彻底。**r7 advisory 挂账**: `_route_state_adjacency` 当纯 potential-graph oracle 用时未显式过滤 source-entry arcs (当前仅影响 lazy-cut 保守度非 soundness) — 请重审此 advisory 是否真无 soundness 影响。lazy cut: `_add_source_side_connectivity_cut()` (:1535-1589) + `_self_check_source_side_connectivity_cut()` (:1435-1533) 独立重验 W/X 证书 (source∈W、sink∉W、移除 X 断开全部 source→sink、incumbent∩X=∅), 任一不成立 fallback selected-positive nogood (:1689-1699) — 核此证书逻辑。

### Q8 precheck 三态消费 + benders r7 status 契约 (新, 重点)
`benders_loop.py` 消费 routing precheck status: allowlist `_EXACT_ROUTING_PRECHECK_VERIFIED_STATUSES = {feasible, front_blocked, relaxed_disconnected}` (:123-125), 检查点 (:5366-5393) 非 allowlist fail-closed UNKNOWN (F-BL-R7-01)。三态消费: front_blocked/relaxed_disconnected binding-local safe-reject ladder (:5406-5460, F-RT clause :134)、front_blocked cut ladder (:5462-5782)、relaxed_disconnected binding alt 耗尽 → whole-layout nogood (:5784-5822)。
**契约一致性 (本面要核)**: routing 端 `analyze_exact_routing_domain()` 实际产出 status 集合 = `{feasible (:615), front_blocked (:408/:485), relaxed_disconnected (:597)}`, 与 allowlist 完全一致 (`CONNECTIVITY_GUARD_TIMEOUT :1743` 是 build_stats 子键非 precheck status)。请**独立验证此一致性**, 并核:
- ① ERROR 合成路径 (benders_loop.py:5316-5320/:5336-5346 异常时合成 `{"status":"ERROR"}` → 非 allowlist fail-closed UNKNOWN) 是否覆盖所有 precheck 异常面;
- ② **TypeError 被单独 catch 成 `routing_precheck=None` → default feasible 回退** (:5313-5314/:5332-5334) 是否会掩盖真实 blocked 后果 (后续 full CP-SAT 兜底, 但请核这个 default-feasible 回退的 soundness — 是否存在 TypeError 路径下本该 blocked 却走 feasible 默认导致漏证);
- ③ 若未来 routing 新增第 4 个 status (如 budget-partial), allowlist + default `"feasible"` 兜底 (:5350-5356/:5366) 是否仍 fail-closed。
另: 有无裸用 precheck 结论直接产 candidate-wide INFEASIBLE 证书 (r7 扫过 heuristic_feasible_finder.py:152-184 = best-effort 非 proof producer、campaign_triage/telemetry 仅分类) — 请独立重扫消费点。relaxed_disconnected 进 whole-layout nogood 必须是 full routing 的必要条件证明 (更宽图断开 ⇒ 收缩后必断)。

## 明确不要报的

- 已修 lock 条款 (重复报不算): **F-RT-R2-01/R2-02** (:120/:121)、**F-RT-R3-01** (:122)、**F-RT-R4-01/R4-02** (:123/:124)、**F-RT-R5-01** (:125); 关联 routing soundness 条款 :126 (CP-SAT FEASIBLE 非认证边界, guard 必证)、:127 (lazy cut acceleration-only + W/X 自验)、:134 (binding-local safe-reject 先 binding nogood)、:135 (F-BL-R7-01 status allowlist)、:117 (全封闭空矩形允许, exterior 连通不在 exact 契约)。
- `routable_cells` stale API (无 live 消费者, 已挂账); r6/r7 已审结论。
- 设计决策 (canonical / 266 口径 / omni_wireless / 52-Port 不变量 / `min_side>=6` admissibility, owner 已定)。
- master / binding / cuts / preprocess / benders / campaign / scheduler 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 行为/性能不审; persisted `exact_safe_cuts` 是 telemetry 非 proof。
- **ghost 不含 exterior-path 要求是 owner 已定的禁区, 别建议加**。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **≈3044 passed, 0 failed** (HEAD 2e1da65, 本包基点)。跑不完就跑 routing 专项 (`test_routing*` / `test_exact_contract*` 等) + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass (8 obligations)。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。
- **specs/08 真实文件名 = `specs/08_topological_flow_subproblem.md`** (pool/commodity 语义在此); routing 约束规则在 `specs/09_exact_grid_routing_subproblem.md` (:43-128); pattern 在 `specs/03_rule_canonicalization.md` (:306-344); connector 语义在 `specs/06_candidate_placement_enumeration.md`。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附三段判读: 约束本体忠实度 (Q1-Q6 逐项, 每条约束的规则依据) / guard + lazy cut soundness (Q7) / precheck 三态消费 + benders r7 契约一致性 (Q8) 的真 Pro 复核。
- 真 Pro 首轮重审, 前轮 thinking 连零不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = 布线编码 soundness 三块 (约束本体 / guard + lazy cut / precheck 消费 + 契约一致性) 的真 Pro 复核; 其余面不审。
