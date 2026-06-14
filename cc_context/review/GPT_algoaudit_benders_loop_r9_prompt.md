# 终末地 IndustrialPlanner 精确求解器 — Benders/LBBD 主循环面 round 9 (真 Pro·把 r8 三修复钉成攻击面: precheck/build status 契约的剩余 fail-open 缝 + build_stats 缺键默认 feasible 的反向同源)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_3b23181e.zip`, sha256 `3b23181e036be5daaf15d9166b76bb9d7b6acb49d81da3e046b8a07f1ec326b6`, 对应干净 git 树 HEAD `eb5c012` (本轮 r8 的全部修复均已合入, 这是**带修复的新树**, 不是修复前的树)。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告, 不要在错包上工作**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

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
- **r8 = 真 Pro, 把 r7 钉成攻击面, 抓出并修 3 个 finding (F-BL-R8-01/02/03), 均已落地 + 入 LOCK (`PROJECT_LOCK.md:150`)**。

**本轮 r9 性质 = 把 r8 的三条修复【钉成攻击面】, 不复读 r8 判读, 不重报 F-BL-R8-01/02/03 本身。** r8 修复要点 (已在包内树 HEAD `eb5c012`):
- **F-BL-R8-01** (env-gated false-deletion): `EXACT_USE_POSE_BOOL_MASTER=1 + EXACT_B1_BYPASS_ROUTING_PRECHECK=1` 下, bypass 把局部 `precheck_status` `front_blocked→feasible` (`benders_loop.py:5488-5493`) 但没改 `routing_domain_analysis['status']` → build 仍插 `0==1` → 旧循环可能消费成 whole-layout nogood。修复: 在 build 后、solve 前读 `build_stats['domain_analysis']['status']` (`benders_loop.py:6055-6075`), 非 `feasible` 直接 fail-closed UNKNOWN; 另在 precheck 门后加 summary status 与 `_analysis['status']` 同一性校验 (`benders_loop.py:5457-5482`)。
- **F-BL-R8-02** (availability hardening): precheck 缺顶层 `status` 键原默认 `feasible` (fail-open) → 改 `MISSING_STATUS` sentinel (`benders_loop.py:123, 5439-5443`), 不在白名单内, fail-closed。
- **F-BL-R8-03** (same-type residual): build 阶段 duplicate terminal-front keys / 非 feasible domain status 的 `0==1` (`routing_subproblem.py:814-816, 821-822`) 在 LBBD 消费侧加二次护栏 (`benders_loop.py:6034-6053` duplicate + `6055-6075` build-domain status)。
- 白名单常量 `_EXACT_ROUTING_PRECHECK_VERIFIED_STATUSES = {"feasible", "front_blocked", "relaxed_disconnected"}` (`benders_loop.py:124-125`)。
- 回归: `src/tests/test_exact_contract.py` 的 `test_missing_routing_precheck_status_returns_unknown_without_routing_build` / `test_routing_precheck_summary_analysis_mismatch_fails_closed_before_build` / `test_front_blocked_precheck_bypass_does_not_consume_build_contradiction` / `test_duplicate_terminal_front_keys_at_routing_build_fail_closed_before_cut`。

**本轮三条攻击线 (找同型残留 / 反向缺陷 / 修复不完备), 这是 r9 的核心**:

### A1 (主攻·反向同源) build-time 护栏读的 `build_stats['domain_analysis']['status']` 自身会不会被默认成 feasible 而漏掉真矛盾?

这是 r8 的 F-BL-R8-01/R8-03 build 后护栏**最可能不完备**的地方, 请最对抗地查:
- r8 的 build 后护栏 (`benders_loop.py:6055-6075`) 读 `dict(routing_model.build_stats).get("domain_analysis")`, **只有当它是 `Mapping` 时**才取 status, 非 feasible 才 fail-closed; 否则 `build_domain_status = None` → 护栏**不触发**。
- 但 `build_stats["domain_analysis"]` 由 `_bind_domain_analysis()` (`routing_subproblem.py:861-865`) 写入, 它 stamp 的是 `"status": str(analysis.get("status", "feasible"))` —— **缺 status 键默认 `feasible`**。
- 同时 `build()` 的真矛盾门 (`routing_subproblem.py:821`) 键的也是 `str(analysis.get("status", "feasible"))` —— **同样缺键默认 feasible**, 所以缺 status 时 build **不会**插 `0==1`, 走正常 build。两边默认一致, 看似自洽。

请独立确认/证伪, **穷举所有 `build()` 退出路径与 build_stats 写入路径的配对**:
- ① 有没有任何路径让 `routing_model.build()` 插入了 `0==1` (即 routing 会返回 INFEASIBLE), 而 `build_stats["domain_analysis"]` 要么**不存在该键**、要么**不是 Mapping**、要么**status 字段被默认成了 `feasible`** → 使 build 后护栏 (`6055-6075`) 的 `build_domain_status` 算成 `None` 或 `"feasible"` 而**放行**, 随后 routing solve 返回 INFEASIBLE 被当真证明消费 (→ binding 枚举 / 穷尽 / whole-layout nogood `benders_loop.py:6181-6334`)? 注意 duplicate-terminal 早返回 (`routing_subproblem.py:814-819`) 在写 `duplicate_terminal_front_keys` 之前已调 `_bind_domain_analysis` (`:812`), 由独立的 duplicate 护栏 (`benders_loop.py:6034-6053`) 兜 —— 但请查**除 duplicate / 非 feasible status 之外**, `build()` 里有没有**第三个** `0==1` 触发点或 early-return, 它既不写 duplicate stats 也不让 domain_analysis.status 反映非 feasible (即一个 build_stats 看不见的不可行)。
- ② r8 在 precheck 门用了 `MISSING_STATUS` sentinel (deny-unknown), 但 build 后护栏的 status 源 (`build_stats["domain_analysis"]["status"]`) 仍是 `analysis.get("status", "feasible")` 默认 feasible 链。判读这个**不对称**: precheck 侧缺键 deny-unknown, build 侧缺键默认 feasible —— 在 F-BL-R8-01 反例 (bypass 改局部 precheck_status 不改 _analysis) 之外, 有没有别的路径让 build 侧吃进一个"缺 status / 畸形 analysis"却被默认成 feasible 放行, 而模型其实是 `0==1` 或几何不可行? (= F-BL-R8-02 的 build 侧反向同源。)
- ③ `from_placement_core` 路径 (`benders_loop.py:6010-6015`) 与裸 `RoutingSubproblem(...)` 路径 (`6018-6029`): `routing_domain_analysis is None` 时走 `RoutingSubproblem(routing_grid, commodities)` (无外置 analysis, build 内部 `analyze_exact_routing_domain` 重算 `routing_subproblem.py:804-811`)。请判读: 这条**内部重算**出的 analysis, 其 status 是否 100% 会写进 `build_stats["domain_analysis"]` 被 build 后护栏看到? 有没有 placement-core reuse / 异常 fallback 让内部重算的非 feasible status **没**反映进 build_stats (例如重算抛异常被吞、或 reuse 走了一条不调 `_bind_domain_analysis` 的捷径)?

### A2 (同型残留) r8 护栏覆盖了 build 后 / solve 前, 但 front_blocked / relaxed_disconnected 的 cut 铸造分支自身的 status 消费还 sound 吗?

r8 的三条修复都聚焦 **routing build 的 `0==1` 消费**。但白名单内的 `front_blocked` / `relaxed_disconnected` 走的是**另一组**主循环分支 (不经 routing build), 请对抗地查它们的 cut 铸造前提:
- `front_blocked` 分支 (`benders_loop.py:5592-5912`): 含 deletion-core minimizer (`minimize_routing_front_blocked_core` `:5751-5813`)、front-blocked nogood (`:5841-5854`)、PCR-CUT hook。`relaxed_disconnected` 分支 (`benders_loop.py:5914-5988`)。
- 请判读: 这些分支在 **binding alternatives 已穷尽**后铸的 master placement-level nogood, 其有效性证明是否仍依赖"加 cut 那一刻"的瞬时 binding/routing 域? 如果 precheck 给的 `front_blocked` 是基于一份 `port_specs`, 而 master nogood 锁的是 whole-layout, 跨 candidate / 跨 iteration 复用时该前提是否被保持? (cut 污染 = soundness 缝。这是本面 cut-lifecycle 不变量, 不重证 routing 子问题内部 front_blocked 判定的几何正确性 —— 那是 F-RT-* 跨面。)
- 注意 r8 已把 build-time duplicate / 非 feasible 兜住了; 但 **precheck-time** `front_blocked` 直接进 cut 铸造 (不 build routing) 的这条路, r8 没碰。请确认它对 `front_blocked` 的消费是 binding-local-first (PROJECT_LOCK §3 `binding_selection_safe_reject` 条款) 且只在 binding 真穷尽 (env-off INFEASIBLE re-solve) 后才升 master nogood, 没有把"precheck 一句 front_blocked"直接升成删合法解的 master cut。

### A3 (修复不完备) 同一性校验 (5457-5482) 与 sentinel 的覆盖完备性

r8 在门后加了 summary status vs `_analysis.status` 同一性校验 (`benders_loop.py:5457-5482`)。请穷举:
- ① 该校验只在 `routing_domain_analysis is not None` 时跑 (`:5458`)。当 `routing_domain_analysis is None` (含 `routing_precheck is None` fallback `:5422-5429` 不带 `_analysis` 键的情形), 校验被跳过, 后续 build 走内部重算。判读: 这条 None 路径下, "precheck summary 说 feasible 但内部重算可能非 feasible"的缝, 是否完全由 A1 的 build 后护栏兜住? 还是 None 路径有独立漏洞 (例如 summary status ∈ 白名单非 feasible 值如 `front_blocked`, 但 `_analysis` 缺失 → 同一性校验跳过 → 进了 front_blocked 分支或 build, 两边对 None analysis 的解读不一致)?
- ② 同一性校验比的是 `str(routing_domain_analysis["status"])` vs `precheck_status`。但 `precheck_status` 在 `:5488-5493` 的 bypass 里**之后**才被改写 (`front_blocked→feasible`)。请确认校验 (`:5465-5482`) 在 bypass 改写**之前**执行, 所以 bypass 改的是校验后的局部值 —— 那 F-BL-R8-01 的 build 后护栏是唯一兜底。判读: 如果未来有人在校验**之后**、build **之前**再插一个改 `routing_domain_analysis` (而非局部 precheck_status) 的路径, 同一性校验会失效 —— 当前树有没有这样的写 `routing_domain_analysis` 的点? (现状证伪即可, 别报理论。)
- ③ 大小写 / 空白 / 类型: 门用精确成员判定 (小写白名单), sentinel 是 `"MISSING_STATUS"` (大写, 不可能撞白名单, 保守 OK)。请确认**没有反向**情形: 某个真·非 feasible 状态经 `str()` 规范化后恰好等于 `"feasible"` / `"front_blocked"` / `"relaxed_disconnected"` 而被放行 (例如上游用了 enum / 带前后空白的字符串 / 大小写变体)。这方向若全保守 (落非白名单 → fail-closed UNKNOWN) 则只是 availability, 但**反向**放行是 soundness, 必须确认无。

## 若 A1/A2/A3 都证伪 → 本轮转又一次独立全面 soundness 重审

如果上述三线都实证站不住 (build 后护栏的 status 源无缺键放行缝、front_blocked/relaxed_disconnected cut 铸造 sound、同一性校验与 sentinel 覆盖完备), 则本轮回到 LBBD soundness 不变量的**独立全面重审**, 换新角度往深挖 (别复读 r7/r8 的判读表)。核心不变量仍是:

- **status 契约完整性**: 主循环每个消费 subproblem status 的分支, 非预期/非三态/预算耗尽/异常 status 必须 fail-closed 到 UNKNOWN, 绝不能被误读成 INFEASIBLE (→ 误铸 nogood 删合法解) 或 CERTIFIED。重点扫 r3-r8 之后**新加或改动**的消费点 (separator / power witness / PCR / D2 / pose-bool delegate 的主循环消费侧), 以及 routing solve 返回值的全分支 (`benders_loop.py:6091-6147` FEASIBLE/TIMEOUT/非 INFEASIBLE/INFEASIBLE)。
- **cut / 缓存跨 iteration·跨 candidate 生命周期与单调性**: 加进 master 的每个 cut 永远有效; cut 的有效性证明若依赖"加 cut 那一刻"的瞬时状态 (binding model 内容 / routing 域 / 选中 ghost anchor / iteration 计数 / 外置 domain), 跨复用时该前提是否被保持 (cut 污染 = soundness 缝); condition literals 解析失败必须 fail-closed 不加而非降级成无条件 cut; 缓存命中结果逐个判读 proof-bearing vs telemetry-only。
- **时间预算全出口终态**: 所有 stage 的 timeout / 预算耗尽出口都收敛到 UNKNOWN/TIMEOUT 而非 INFEASIBLE/CERTIFIED; 单调时钟; 预算检查点之间最长未检查窗口有界。

## 面边界 (只审本面, 跨面不审)

本面 = Benders/LBBD 主循环 (`src/search/benders_loop.py`)。以下**明确列入"不审"**, 怀疑跨面缺陷时**交叉引述 `PROJECT_LOCK` 契约条款而非在本轮重证**:
- 其余 7 面各自的内部正确性: master 几何 (`exact_coordinate_master` / pose-bool master 的 F-GM-* 条款)、binding 子问题内部 (F-BIND-* 条款)、routing 子问题内部编码 (F-RT-* 条款, 含 connector cell / 多组件 / duplicate front key / 外置域裁剪 / FEASIBLE 连通性重证)、cuts 独立面 (F-CUT-* / CUT-*-H* / PCR-R5 系列 / CUT-R12/13/14-H1 power 条款)、preprocess / campaign / scheduler / flow 诊断内部。
- 本面只审 LBBD 主循环对这些子问题**返回值的消费**是否 sound (status 解读 / cut 铸造前提 / 预算终态), 不重证子问题自身的几何/编码正确性。具体例: `RoutingSubproblem.build()` 里 `0==1` 的几何判定 (duplicate / 非 feasible status / connector) 正确性是 F-RT-* 面; 本面只审主循环对 build 产出的 INFEASIBLE / build_stats 的**消费**是否 sound。

## 明确不要报的

- **F-BL-R8-01 / F-BL-R8-02 / F-BL-R8-03 修复本身** (已 lock 已修, 见 `PROJECT_LOCK.md:150`); 本轮只攻它们的同型残留 / 反向缺陷 / 不完备, 不重报已修项。
- **F-BL-R7-01 修复** (已 lock 已修, `PROJECT_LOCK.md:136` 末段) 与 r3-r6 已修 finding (F-BL-R3-01 / R3-02 / R4-01 / R5-PS-01) 与已审 sound 结论。
- **env-gated / exploratory 行为不属 P1.2 soundness**: `EXACT_USE_POSE_BOOL_MASTER` / `EXACT_POWER_PLACEMENT_SUBPROBLEM` / `EXACT_B1_BYPASS_ROUTING_PRECHECK` / `EXACT_B1_D2_COMMODITY_FLOW` 等都 env-gated, **不在 certified 默认路径**。env-gated cut 路径的 **soundness** 仍可审 (若你发现一条 env-gated 路径能在 env 开启时铸出删合法解的 cut, 报为 hardening 并明确标 env-gated, 不当 certified soundness reset)。但**不要**在 certified 默认路径重报这些 env-gated 行为。
- 设计决策 (owner 已定): canonical 口径 / 266 强制设施口径 / `min_side >= 6` 是 admissibility 不是 tie-break / omni_wireless / 52-Port 不变量。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate, 不是 bug); P1.3B `step_8_apply_to_master` 禁区 (未集成边界, 不报); persisted `exact_safe_cuts` 是 telemetry 非 proof (V82, 不当 proof source 误报)。
- `facility_pools` pose dict 浅拷贝共享 (r5 已挂账保守备注, 当前无 mutation 路径)。
- `candidate_placements.json` 已随包内置校验 (不报"缺文件"); `_codex_archive/` 只读历史参考 (非活跃代码)。

## 自验环境与已知基线 (硬不变量 = 0 failed)

- candidate 已随包, 全量 `python -m pytest -q src/tests` 应 **0 failed** (passed ≈3074, 具体数目以实跑为准; **硬不变量是 0 failed**)。沙盒 pytest-randomly 报 seed 错就加 `-p no:randomly`。跑不完全量就跑专项 (`src/tests/test_exact_contract.py` + 上述 r8 回归) 并**如实声明**没跑全量。
- `python scripts/check_p1_2_proof_obligations.py` 应 pass (anchors 8 obligations)。
- finding **必须**带可复现 probe (monkeypatch 构造一条能触发的输入, 断言 fail-open 终态: routing INFEASIBLE 被消费 / whole-layout nogood 被铸 / 输出 CERTIFIED 而前提不成立) 或 file:line 严谨论证; **实证推翻你的怀疑就不要报** (宁可少报一条假阳, 不要拿"理论上可能"凑数)。

## 严重度纪律

- **false-CERTIFIED** = 把非证明状态转译成 INFEASIBLE 证明 / 铸出删合法解的 nogood / 任何路径输出 CERTIFIED 而其证明前提不成立, **且发生在 canonical 数据 + 默认 env (无 EXACT_* 实验旋钮)** = **soundness reset** —— P1.2 闭环只认这一类, 是本轮唯一会改 owner 三连清白计数的发现。
- **env-gated / conditional / false-INFEASIBLE 保守失败 / 过早截断 / fail-closed 把合法路径误判成 UNKNOWN** = **hardening / availability**, 标 **LOW** 并**明确标注是 env-gated 或 conditional**, 不算 soundness reset。

## 交付物 (REVIEW.md)

- 逐条 finding: severity / file:line / 可复现 probe 或严谨论证 / 修法 (有把握附 unified diff + regression, **LF 行尾**, 不重写 candidate 工件)。
- 若确认 sound: **明确写"本轮零 soundness finding"**, 并按本轮三攻击线分段判读 ——
  ① A1: 列出 `RoutingSubproblem.build()` 的**所有** `0==1` / early-return 退出路径, 各自写进 / 不写进 `build_stats["domain_analysis"]` 的情况, 以及 build 后护栏 (`benders_loop.py:6055-6075`) 对每条路径的 status 是否能正确算出非 feasible 并 fail-closed (重点: 缺键默认 feasible 是否制造放行缝);
  ② A2: front_blocked / relaxed_disconnected cut 铸造分支对 precheck status 的消费终态判读 (binding-local-first → master nogood 升级前提是否 sound);
  ③ A3: 同一性校验 (5457-5482) + sentinel 的覆盖完备性判读 (None 路径 / bypass 时序 / 大小写规范化反向);
  ④ (若转全面重审) 新角度的 status 消费点 / cut 生命周期 / timeout 终态判读 (不复读 r7/r8 判读表, 只列你新查的角度)。
- 真 Pro 确认轮, 独立下结论。前轮结果不构成本轮任何先验 —— r8 抓到 3 个不代表本轮一定还有, 也不代表一定干净; 按你自己最对抗的独立判断走。
