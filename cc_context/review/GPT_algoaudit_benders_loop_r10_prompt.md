# 终末地 IndustrialPlanner 精确求解器 — Benders/LBBD 主循环面 round 10 (把 r9 三修复钉成攻击面: routing build/precheck 消费侧的【第 4 个】同型缝 — build-time 0==1 / summary-only proof 载体 / 非布尔 proof bit / 默认 feasible 漂移)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_0590f9ca.zip`, sha256 `0590f9ca30aac5bb7afe18945eb36d347ea8b0c5b467fd6baff4679eff8c5234`, 对应干净 git 树 HEAD `7fec29a` (本面 round-1 = r8 三修复 + round-2 = r9 三修复**全部已合入**, 这是**带修复的新树**, 不是修复前的树)。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告, 不要在错包上工作**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

`data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) **已随包内置并校验过**, 不需要再生; 若校验对不上, 报告, 不要伪造或重写它。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **Benders/LBBD 主循环** (`src/search/benders_loop.py` 为核, `_run_exact_binding_and_routing()` 是本面核心消费函数)。

## 本面定义与历史 + 本轮性质 (关键, 必读)

本面历史 (报告在包内 `cc_context/review/` 与 `cc_context/review/archive/`):
- r3 = F-BL-R3-01 (预算耗尽误当穷尽证明铸 nogood) + F-BL-R3-02 (routing 非三态 status 落 INFEASIBLE 分支);
- r4 = F-BL-R4-01 (binding 状态契约同型缝五消费点, `_record_unexpected_binding_status()` 统一 fail-closed);
- r5 = 零 soundness + LOW F-BL-R5-PS-01 (env 门控 power placement forensic 分支 status×summary 错配, 完整性非 soundness);
- r6 + 涟漪确认轮 = 零 soundness finding (较弱 thinking 模型审的);
- r7 = 真 Pro 首轮重审, 抓出并修 HIGH F-BL-R7-01 (routing precheck 非白名单 status 在主循环入口没 fail-closed, 被 `RoutingSubproblem.build()` 转译成 CP-SAT INFEASIBLE → 可能铸 master whole-layout nogood 删合法解);
- r8 = 真 Pro, 把 r7 钉成攻击面, 抓出并修 3 个 finding (F-BL-R8-01/02/03), 均已落地 + 入 LOCK (`PROJECT_LOCK.md:150`);
- **r9 = 真 Pro, 把 r8 钉成攻击面, 抓出并修 3 个 finding (F-BL-R9-01/02/03), 均已落地 + 入 LOCK (`PROJECT_LOCK.md:151`)**。

**本轮 r10 性质 = 把 r9 的三条修复【钉成攻击面】, 不复读 r9 判读, 不重报 F-BL-R9-01/02/03 本身。** r9 修复要点 (已在包内树 HEAD `7fec29a`):
- **F-BL-R9-01** (build-time 第 3 个 `0==1`): `RoutingSubproblem.build()` 走正常 feasible build 时, `_add_port_adherence()` (`routing_subproblem.py:1207-1209, 1225-1227`) 在端口 front cell 不在 `commodity_active_cells` 中、或无 routing var 时插 `0==1`, 但 `build_stats["domain_analysis"]["status"]` 仍是 `feasible`。r8 的 build-domain status 护栏 (只看 domain_analysis.status) 漏掉它。修复: build 后、solve 前读 `build_stats["port_adherence"]["blocked_ports"]` (`benders_loop.py:6199-6224`), 正数即 fail-closed UNKNOWN。
- **F-BL-R9-02** (summary-only proof 载体): `front_blocked`/`relaxed_disconnected` precheck summary 缺 `_analysis` mapping 时, 同一性校验 (`benders_loop.py:5505-5552` 段) 被跳过, 旧逻辑可直接从 summary-only 证据铸 placement-local nogood。修复: 非 feasible precheck **必须**携带 mapping `_analysis` 且 status 匹配, 否则 `routing_precheck_missing_domain_analysis` → UNKNOWN 不加 cut。
- **F-BL-R9-03** (非布尔 proof bit): reject-status cut 旧逻辑用 `bool(summary.get("binding_selection_safe_reject"))`, 使 truthy 文本如 `"False"` 算 True; 且只信 summary 不比 `_analysis`。修复: safe-reject proof bit 必须是 **literal `True`** (`value is True`, `benders_loop.py:5559-5563`) 且 summary 与 `_analysis` 一致 (`:5565-5596`), 否则 UNKNOWN 不加 cut。
- 回归: `src/tests/test_exact_contract.py` 的 `test_feasible_routing_build_port_adherence_blocked_ports_fail_closed_before_cut` / `test_front_blocked_precheck_without_analysis_fails_closed_before_cut` / `test_reject_precheck_status_requires_true_safe_reject_before_cut`; 另更新 `src/tests/test_p0_certified_soundness_fixes.py` 既有 fake precheck 适配新 `_analysis` proof-carrier 契约。

**本轮唯一攻击面 (照 owner 裁决, 一句话): 钉 r9 三修复, 找 routing build/precheck 消费侧的【第 4 个同型缝】 —— 还有没有别的 (a) build-time `0==1` 触发点、(b) summary-only / 非 proof-bearing 载体被当真证明消费、(c) 非布尔 / truthy-非-literal proof bit、(d) `analysis.get(..., "feasible")` 这类缺键默认 feasible 漂移点, 在 canonical 默认路径不可达 → 都是 drift-hardening, 别在 certified 路径重报。** 下面三条攻击线把这个面拆细。

### A1 (主攻·穷举第 4 个 build-time `0==1`) `RoutingSubproblem.build()` 还有没有【未被 3 护栏覆盖】的 contradiction 插入点?

r9 已把 build() 的三类 `0==1` 兜住 (duplicate / 非 feasible domain status / port_adherence)。请**穷举 `build()` 及其在正常 feasible 路径上调用的每个 `_add_*()` 子函数**, 找第 4 个能让 routing 返回 INFEASIBLE、而 LBBD 三护栏 (`benders_loop.py:6160-6224` duplicate + build-domain status + port_adherence.blocked_ports) **都看不到**的 contradiction:
- `build()` 正常路径 (`routing_subproblem.py:829-837`) 依次调 `_create_routing_variables` / `_add_obstacle_exclusion` / `_add_capacity_constraints` / `_add_bridge_constraints` / `_add_continuity_constraints` / `_add_directed_edge_balance_constraints` / `_add_port_adherence` / `_add_gap_rule` / `_add_bridge_count_hint`。请逐个查: 这些函数里**除 `_add_port_adherence` 已被 r9 兜住外**, 有没有别的直接 `model.Add(0 == 1)` / 等价空域约束 (如 `AddBoolOr([])`、空 domain 变量、`sum([]) == 1`、容量上界 0 但需求正、bridge/continuity 的退化空集) 能让模型 INFEASIBLE, 而这条不可行**不写进任何 build_stats 被消费的 proof-bearing 键** (`domain_analysis.status` 仍 feasible、无 `duplicate_terminal_front_keys`、`port_adherence.blocked_ports == 0`)?
- 关键判据: r9 的三护栏读的是 **build_stats 里三个特定键**。如果某个 `_add_*` 插了不可行约束**却没在任一被消费键上留痕**, 那么 build 后护栏 (`benders_loop.py:6177-6224`) 全部放行 → `routing_model.solve()` 返回 INFEASIBLE (`benders_loop.py:6279` 之后) → 进 binding 枚举/穷尽链 → 可铸 whole-layout nogood (`benders_loop.py:6337` 之后)。这就是第 4 个同型缝。请**最对抗地**找这条路, 找到给可复现 probe; 找不到就在 REVIEW 里**逐函数列出**每个 `_add_*` 为什么不会插 build_stats-不可见的 `0==1` (或它的不可行一定反映进三键之一)。
- 注意 `routing_subproblem.py:1582`、`1698` 的 `Add(0 == 1)` 是 **solve/connectivity guard** 阶段 (不是 `build()` 退出路径) —— 这些是 routing 子问题**内部 solve 流程**, 属 F-RT-* 跨面 (不审其几何正确性); 但**本面要审**: 主循环对这条 solve 流程返回的 status 消费是否 sound (它走 `routing_model.solve()` 的返回值, 由 `benders_loop.py:6241/6260/6279` 三态消费契约接, 已 r3/r7 覆盖 —— 请确认这条 solve-time 不可行不会被当成"build 已护栏过所以一定是真不可行")。

### A2 (同型残留·proof-bearing vs telemetry 载体) LBBD 还从 build_stats / precheck summary 消费了哪些键当 proof? 有没有把 telemetry-only 键当证明?

r9 的三护栏只关注 **`domain_analysis` / `duplicate_terminal_front_keys` / `port_adherence`** 三键。但 `routing_subproblem.py` 还写了别的 build_stats 键: `state_space` (`:1006`)、`directed_edge_balance` (`:1116`)、`gap_rule` (`:1242`)、`last_solve` (`:1742/1779/1829`)。请对抗地查 LBBD 主循环 (`benders_loop.py` 全文 + `_update_routing_shrink_from_build_stats` / `_update_routing_state_space` / `_record_unexpected_routing_build_domain_status` `:6638`) 对这些键的消费:
- ① 有没有任何键被主循环读出来**当作 proof-bearing 判据** (用来决定铸 cut / 判 INFEASIBLE / 升 whole-layout nogood / 输出 CERTIFIED), 而它其实是 **telemetry-only** (shrink 统计 / state-space 计数 / 上次 solve 摘要)? 把 telemetry 当 proof = soundness 缝。请逐个键判读"它驱动了哪个决策分支"。
- ② 反向: precheck summary (`routing_precheck_summary`, `benders_loop.py:5474-5479` 段构造) 里被当 proof 消费的字段 (`status` / `binding_selection_safe_reject` / `blocked_ports` / `conflict set`)。r9 已硬化了 `status` (白名单+同一性) 和 `binding_selection_safe_reject` (literal True + summary/_analysis 一致)。请查**剩下的** proof-bearing 字段: front_blocked 分支 (`benders_loop.py:5640-5954` 段) 消费的 `blocked_ports` 列表 / conflict set, 在铸 placement-local nogood / lazy-demand cut 时, 有没有"summary 给的 blocked_ports 形状畸形 (空 / 非 list / 元素非预期) 却被当真冲突核消费"的非布尔/非 literal proof bit 缝? 它是不是也该有 r9-03 那种 literal/类型严格校验?
- ③ `_analysis` (`routing_domain_analysis`) 里**除 `status` 和 `binding_selection_safe_reject` 外**, 还有没有别的字段 (如 `commodity_active_cells` / `blocked_ports` / `domain_stats`) 被主循环或 build 当 proof 消费, 而它的"缺键默认值"或"畸形形状"会制造放行缝? (= r9-01 的 `commodity_active_cells={}` 那类缺口的同型扩展, 但换一个字段。)

### A3 (修复不完备·默认 feasible 漂移链) `analysis.get("status", "feasible")` 默认 feasible 链是否在每处都有对侧护栏兜?

r9 修复后, **precheck 侧**缺 status 用 `MISSING_STATUS` sentinel (deny-unknown), 但 **routing_subproblem.py 内部**仍多处用 `analysis.get("status", "feasible")` 默认 feasible:
- `build()` 真矛盾门: `routing_subproblem.py:821` 键 `str(analysis.get("status", "feasible"))` —— 缺 status 时**不**插 `0==1`, 走正常 build。
- `_bind_domain_analysis` 写 build_stats: `routing_subproblem.py:862` 键 `str(analysis.get("status", "feasible"))` —— 缺 status 时 build_stats 里 status = `feasible`。
- LBBD build 后护栏: `benders_loop.py:6177-6184` 对 `build_stats["domain_analysis"]` 缺 status 时**反而**用 `MISSING_STATUS` sentinel (deny-unknown) —— 与 routing 侧的默认 feasible **不对称**。

请穷举判读这个**不对称链**:
- ① routing 侧 `build()` 真矛盾门 (`:821`) 缺 status 默认 feasible → **不插** `0==1` → 走正常 feasible build。如果这条"缺 status 的 analysis"几何上其实不可行 (例如 active_cells 全空但 port_specs 非空), 那 `_add_port_adherence` 会插 `0==1` (被 r9-01 兜) —— **但**如果它的不可行性**不**经 port_adherence 暴露 (回到 A1 的第 4 个 `0==1` 问题), build 后 `build_stats["domain_analysis"]["status"]` 因 `:862` 默认 feasible 而被护栏放行。这两条 (A1 + 默认 feasible) 是否在某条路径上**叠加**成一个真放行缝? 请验证 first-party `analyze_exact_routing_domain()` 的**每个 return 分支**是否都显式带 status 键 (`routing_subproblem.py:407-417, 484-494, 596-612, 646-653` 等), 使缺 status 只在 hand-built / 外置 `_domain_analysis` fork 时发生 (= canonical-unreachable, drift hardening)。
- ② LBBD build 后护栏 (`:6177`) 缺 status 用 sentinel deny-unknown, 但它读的源 `build_stats["domain_analysis"]["status"]` 由 `:862` 写, **永远带 status 键** (因为 `:862` 总是 stamp 一个 `str(...)`) —— 所以 LBBD 侧的 `MISSING_STATUS` 分支 (`:6181`) **实际不可达**? 请确认: 是否存在任何路径让 `build_stats["domain_analysis"]` 是 Mapping 但**没有** status 键 (使 `:6181` sentinel 真的触发), 还是 `:862` 保证它一定有 → `:6181` 是死防御 (无害但说明护栏与源契约耦合)。判读这个耦合: 如果将来有人改 `:862` 让它在某情形**不** stamp status, LBBD 侧 sentinel 是否仍 fail-closed (是 → 防御到位; 否 → 不完备)。
- ③ 大小写 / 空白 / 类型 / enum 反向放行 (r9-A3 已查过 precheck 侧): 请对 **build 侧** `build_stats["domain_analysis"]["status"]` 和 `port_adherence.blocked_ports` 的类型规范化再查一遍。`blocked_ports` 经 `int(...)` (`benders_loop.py:6206`), 异常落 `port_adherence_blocked_ports = 1` (fail-closed, 保守 OK)。请确认**没有反向**: 某个真·非零 blocked_ports 经某种类型/规范化 (如 `"0"` 字符串、`0.0` float、bool `False`、`None`) 被 `int()` 算成 0 而**放行** (例如 `int("0")==0` 但其实有 blocked port, 或 `blocked_ports` 键存在但值是空 list `[]` 而非计数 → `int([])` 抛 TypeError 落 1 保守, 但 `int(0.4)==0` 这类截断放行)? 这方向若全保守则只是 availability; **反向放行**是 soundness, 必须确认无。

## 若 A1/A2/A3 都证伪 → 本轮转又一次独立全面 soundness 重审

如果上述三线都实证站不住 (build 无第 4 个 build_stats-不可见的 `0==1`、无 telemetry-当-proof 缝、默认 feasible 漂移链在每处都有对侧护栏兜), 则本轮回到 LBBD soundness 不变量的**独立全面重审**, 换新角度往深挖 (别复读 r7/r8/r9 的判读表)。核心不变量仍是:

- **status 契约完整性**: 主循环每个消费 subproblem status 的分支, 非预期/非三态/预算耗尽/异常 status 必须 fail-closed 到 UNKNOWN, 绝不能被误读成 INFEASIBLE (→ 误铸 nogood 删合法解) 或 CERTIFIED。重点扫 r3-r9 之后**新加或改动**的消费点 (separator / power witness / PCR / D2 / pose-bool delegate 的主循环消费侧), 以及 routing solve 返回值的全分支 (`benders_loop.py:6241/6260/6279` FEASIBLE/TIMEOUT/非 INFEASIBLE, 以及 `:6279` 之后的 INFEASIBLE → binding 枚举链)。
- **cut / 缓存跨 iteration·跨 candidate 生命周期与单调性**: 加进 master 的每个 cut 永远有效; cut 的有效性证明若依赖"加 cut 那一刻"的瞬时状态 (binding model 内容 / routing 域 / 选中 ghost anchor / iteration 计数 / 外置 domain), 跨复用时该前提是否被保持 (cut 污染 = soundness 缝); condition literals 解析失败必须 fail-closed 不加而非降级成无条件 cut; 缓存命中结果逐个判读 proof-bearing vs telemetry-only。
- **时间预算全出口终态**: 所有 stage 的 timeout / 预算耗尽出口都收敛到 UNKNOWN/TIMEOUT 而非 INFEASIBLE/CERTIFIED; 单调时钟; 预算检查点之间最长未检查窗口有界。

## 面边界 (只审本面, 跨面不审)

本面 = Benders/LBBD 主循环 (`src/search/benders_loop.py`)。以下**明确列入"不审"**, 怀疑跨面缺陷时**交叉引述 `PROJECT_LOCK` 契约条款而非在本轮重证**:
- 其余 7 面各自的内部正确性: master 几何 (`exact_coordinate_master` / pose-bool master 的 F-GM-* 条款)、binding 子问题内部 (F-BIND-* 条款)、routing 子问题内部编码 (F-RT-* 条款, 含 connector cell / 多组件 / duplicate front key / 外置域裁剪 / FEASIBLE 连通性重证 / `_add_port_adherence` 的几何正确性 / `analyze_exact_routing_domain` 内部判定正确性)、cuts 独立面 (F-CUT-* / CUT-*-H* / PCR-R5 系列 / CUT-R12/13/14/15-H1 power 条款)、preprocess / campaign / scheduler / flow 诊断内部。
- 本面只审 LBBD 主循环对这些子问题**返回值的消费**是否 sound (status 解读 / build_stats 消费 / cut 铸造前提 / 预算终态), 不重证子问题自身的几何/编码正确性。具体例: `RoutingSubproblem.build()` 里某个 `0==1` 的几何判定是否**该**插 (duplicate / 非 feasible status / port adherence / 其它) 是 F-RT-* 面; 本面只审主循环**对 build 产出的 INFEASIBLE / build_stats 各键的消费**是否 sound (会不会把 build-time 不可行当真证明消费成删合法解的 nogood)。

## 明确不要报的

- **F-BL-R9-01 / F-BL-R9-02 / F-BL-R9-03 修复本身** (已 lock 已修, 见 `PROJECT_LOCK.md:151`); 本轮只攻它们的**第 4 个同型残留 / 反向缺陷 / 不完备**, 不重报已修项。
- **F-BL-R8-01 / R8-02 / R8-03 修复** (已 lock 已修, `PROJECT_LOCK.md:150`); **F-BL-R7-01 修复** (`PROJECT_LOCK.md:136` 末段) 与 r3-r6 已修 finding (F-BL-R3-01 / R3-02 / R4-01 / R5-PS-01) 与已审 sound 结论。
- **env-gated / exploratory 行为不属 P1.2 soundness**: `EXACT_USE_POSE_BOOL_MASTER` / `EXACT_POWER_PLACEMENT_SUBPROBLEM` / `EXACT_B1_BYPASS_ROUTING_PRECHECK` / `EXACT_B1_D2_COMMODITY_FLOW` / `EXACT_B1_PATCH_ROUTING_CORE` 等都 env-gated, **不在 certified 默认路径**。env-gated cut 路径的 **soundness** 仍可审 (若你发现一条 env-gated 路径能在 env 开启时铸出删合法解的 cut, 报为 hardening 并明确标 env-gated, 不当 certified soundness reset)。但**不要**在 certified 默认路径重报这些 env-gated 行为。
- 设计决策 (owner 已定): canonical 口径 / 266 强制设施口径 / `min_side >= 6` 是 admissibility 不是 tie-break / omni_wireless / 52-Port 不变量。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate, 不是 bug); P1.3B `step_8_apply_to_master` 禁区 (未集成边界, 不报); persisted `exact_safe_cuts` 是 telemetry 非 proof (V82, 不当 proof source 误报)。
- `facility_pools` pose dict 浅拷贝共享 (r5 已挂账保守备注, 当前无 mutation 路径)。
- `candidate_placements.json` 已随包内置校验 (不报"缺文件"); `_codex_archive/` 只读历史参考 (非活跃代码)。

## 自验环境与已知基线 (硬不变量 = 0 failed)

- candidate 已随包, 全量 `python -m pytest -q src/tests` 应 **0 failed** (collect ≈3166 项, passed 数目以实跑为准; **硬不变量是 0 failed**)。沙盒 pytest-randomly 报 seed 错就加 `-p no:randomly`。跑不完全量就跑专项 (`src/tests/test_exact_contract.py` + `src/tests/test_p0_certified_soundness_fixes.py` + 上述 r9 回归 + `src/tests/test_routing.py`) 并**如实声明**没跑全量。
- `python scripts/check_p1_2_proof_obligations.py` 应 pass (anchors 8 obligations)。
- finding **必须**带可复现 probe (monkeypatch 构造一条能触发的输入, 断言 fail-open 终态: routing INFEASIBLE 被消费 / whole-layout nogood 被铸 / placement-local nogood 被铸 / 输出 CERTIFIED 而前提不成立) 或 file:line 严谨论证; **实证推翻你的怀疑就不要报** (宁可少报一条假阳, 不要拿"理论上可能"凑数)。

## 严重度纪律

- **false-CERTIFIED** = 把非证明状态转译成 INFEASIBLE 证明 / 铸出删合法解的 nogood / 任何路径输出 CERTIFIED 而其证明前提不成立, **且发生在 canonical 数据 + 默认 env (无 EXACT_* 实验旋钮)** = **soundness reset** —— P1.2 闭环只认这一类, 是本轮唯一会改 owner 三连清白计数的发现。
- **env-gated / conditional / false-INFEASIBLE 保守失败 / 过早截断 / fail-closed 把合法路径误判成 UNKNOWN** = **hardening / availability**, 标 **LOW** 并**明确标注是 env-gated 或 conditional / canonical-unreachable**, 不算 soundness reset。

## 交付物 (REVIEW.md)

- 逐条 finding: severity / file:line / 可复现 probe 或严谨论证 / 修法 (有把握附 unified diff + regression, **LF 行尾**, 不重写 candidate 工件)。
- 若确认 sound: **明确写"本轮零 soundness finding"**, 并按本轮三攻击线分段判读 ——
  ① A1: 逐函数列出 `build()` 正常 feasible 路径上每个 `_add_*()` 子函数是否插 build_stats-不可见的 `0==1` (或其不可行一定反映进三护栏键之一); 明确判定有无第 4 个 build-time contradiction 缝;
  ② A2: 列出 LBBD 从 build_stats / precheck summary / `_analysis` 消费的**每个**字段, 各自判读 proof-bearing vs telemetry-only, 有无 telemetry-当-proof 或非 literal/非类型严格的 proof bit 缝;
  ③ A3: 默认 feasible 漂移链 (`routing_subproblem.py:821/862` ↔ `benders_loop.py:6177-6224`) 的对称性判读 + blocked_ports/status 类型规范化反向放行排查;
  ④ (若转全面重审) 新角度的 status 消费点 / cut 生命周期 / timeout 终态判读 (不复读 r7/r8/r9 判读表, 只列你新查的角度)。
- 真 Pro 确认轮, 独立下结论。前轮结果不构成本轮任何先验 —— r9 抓到 3 个不代表本轮一定还有, 也不代表一定干净; 按你自己最对抗的独立判断走。
