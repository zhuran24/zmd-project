# 终末地 IndustrialPlanner 精确求解器 — Benders/LBBD 主循环面 round 8 (真 Pro·把 r7 修复钉成攻击面: routing precheck status 契约的"门 vs build"对象同一性 + 同型残留)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_b4041f3e.zip`, sha256 `b4041f3eb065e9756a1dbd21f3e513479dfd504e2024b74fb08a2d235af08893`, 对应干净 git 树 HEAD `8c61e1e`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告, 不要在错包上工作**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

`data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) **已随包内置并校验过**, 不需要再生; 若校验对不上, 报告, 不要伪造或重写它。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **Benders/LBBD 主循环** (`src/search/benders_loop.py` 为核)。

## 本面定义与历史 + 本轮性质 (关键, 必读)

本面历史 (报告在包内 `cc_context/review/` 与 `cc_context/review/archive/`):
- r3 = F-BL-R3-01 (预算耗尽误当穷尽证明铸 nogood) + F-BL-R3-02 (routing 非三态 status 落 INFEASIBLE 分支);
- r4 = F-BL-R4-01 (binding 状态契约同型缝五消费点, `_record_unexpected_binding_status()` 统一 fail-closed);
- r5 = 零 soundness + LOW F-BL-R5-PS-01 (env 门控 power placement forensic 分支 status×summary 错配, 完整性非 soundness);
- r6 + 涟漪确认轮 = 零 soundness finding (这两轮是较弱 thinking 模型审的);
- **r7 = 真 Pro 首轮重审, 抓出并已修 1 个 HIGH soundness: F-BL-R7-01** —— routing precheck 的非白名单 status 在 LBBD 主循环入口没有 fail-closed, 会被 `RoutingSubproblem.build()` 转译成 CP-SAT `INFEASIBLE` 进而可能铸 master whole-layout nogood 删合法解。

**本轮 r8 性质 = 把 r7 的修复【钉成攻击面】, 不是复读上轮判读, 也不重报 F-BL-R7-01 本身。** r7 修复要点 (已在包内, `PROJECT_LOCK.md:136` 末段已 lock 为 F-BL-R7-01 条款):
- 新增白名单常量 `_EXACT_ROUTING_PRECHECK_VERIFIED_STATUSES = {"feasible", "front_blocked", "relaxed_disconnected"}` (`src/search/benders_loop.py:123`)。
- 在 routing build / 各 cut 分支之前用 `precheck_status not in _EXACT_ROUTING_PRECHECK_VERIFIED_STATUSES` 做门 (`src/search/benders_loop.py:5383`), 非白名单立即写 fail-closed summary (`subproblem_status_contract_violation="unexpected_routing_precheck_status"`, `master_follow_up="fail_closed_unknown"`) 并 `return RUN_STATUS_UNKNOWN, None`, 不 build routing, 不加 cut。
- precheck 调用异常被捕获转成 `{"status": "ERROR", ...}` 再走同一契约。
- 回归: `src/tests/test_exact_contract.py::test_unexpected_routing_precheck_status_returns_unknown_without_routing_cut`。

**本轮三条攻击线 (找同型残留 / 反向缺陷 / 修复不完备), 这是 r8 的核心**:

### A1 (主攻·反向缺陷) 门检查的 status 对象 vs build 消费的 status 对象, 是不是同一个?

这是 r7 修复**最可能不完备**的地方, 请最对抗地查:
- r7 的门 (`benders_loop.py:5383`) 检查的是 `precheck_status = str(routing_precheck_summary.get("status", "feasible"))` —— 即 `run_exact_routing_precheck()` 返回字典的**顶层 summary** status。
- 但触发 `0 == 1` 的 `RoutingSubproblem.build()` (`src/models/routing_subproblem.py:821` `if str(analysis.get("status", "feasible")) != "feasible":`) 键的是它收到的 **`domain_analysis` 形参**那个 dict 的 `status`。
- 主循环把 `routing_domain_analysis = routing_precheck.get("_analysis")` (`benders_loop.py:5372`) 传给 build (`benders_loop.py:5940/5952` 的 `domain_analysis=routing_domain_analysis`)。

请独立确认/证伪: **门检查的 `summary["status"]` 与 build 键的 `_analysis["status"]` 在所有路径上是否恒等?**
- `run_exact_routing_precheck()` 当前 (`routing_subproblem.py:646-654`) 把 `"status": str(analysis["status"])` 与 `"_analysis": analysis` 一起返回, 看似恒等 —— 但请穷举:
  ① 有没有任何路径 (现在或可被外部/异常构造) 让 summary status ∈ 白名单 (尤其 `"feasible"`) 通过门, 而传给 build 的 `_analysis["status"]` 是非 `feasible` 值 → build 加 `0==1` → routing INFEASIBLE → 可能进 whole-layout nogood? (= 门被旁路的 soundness 缝, 与 F-BL-R7-01 反向同源。)
  ② r7 修复在 `routing_precheck is None` 时合成 fallback dict (`benders_loop.py:5364-5371`) `status="feasible"` 且**没有 `_analysis` 键** → `routing_domain_analysis = None`。判读这条 None 路径下 build 走 `RoutingSubproblem(routing_grid, commodities)` (无 domain_analysis, 内部重算) 是否真的安全, 还是把"precheck 没跑成"静默当成了 feasible 继续 (完整性 vs soundness 各自判读)。
  ③ `from_placement_core` 路径 (`benders_loop.py:5936`) 与裸 `RoutingSubproblem(...)` 路径 (`5949`) 收到的 `domain_analysis` 是否都经过同一个被门校验过的 status 对象? 有没有哪条 build 路径用的 analysis 来自一个**没被门检查过的**来源 (例如 placement-core 内部重算出一个新 status)?

### A2 (同型残留) build-time 重算 vs precheck-time status 的一致性

`RoutingSubproblem.build()` 里 `0 == 1` 有**两个**触发点, 不止 status 那一个:
- `benders_loop` 入口门只看 precheck 给的 status。
- 但 build 在 `routing_subproblem.py:761` 用 `self._duplicate_terminal_front_keys = _duplicate_terminal_front_keys(self.grid.port_specs)` **build 时重算** duplicate terminal front keys, 命中则 `routing_subproblem.py:814-816` 无条件 `self.model.Add(0 == 1)` —— 这发生在 status 白名单检查 (`:821`) **之前**, 且 `benders_loop` 入口门**管不到它**。

请判读: precheck 的 `analyze_exact_routing_domain` 已把 duplicate terminal keys 归类为 `front_blocked` (`routing_subproblem.py:398-417`, 白名单内), 所以正常路径 precheck 会先 reject。但请对抗地查:
- ① 有没有 precheck 看到的 `port_specs` 与 build 时 `RoutingSubproblem` 收到的 `port_specs` **不是同一份** (中途被 transform / placement-core reuse 重算) 的窗口, 使 build 时新冒出一个 precheck 没见过的 duplicate → build `0==1` → INFEASIBLE, 而入口门因为 precheck status=`feasible` 放行?
- ② F-RT-R4-02 (`PROJECT_LOCK.md:124`) 要求 precheck 与 solver build **两处都**对 duplicate terminal front keys fail-closed。请判读: 当 build 因 duplicate 触发 `0==1`、routing 返回 INFEASIBLE 时, 主循环对这个 routing INFEASIBLE 的消费 (binding 枚举 / 穷尽 / whole-layout nogood) 是否仍然 sound —— 即这个 INFEASIBLE 是真不可行证明, 还是又一个被转译的非证明? (注意 F-RT-R4-02 把它定性为 canonically unreachable + 外部构造才触发; 但 LBBD 主循环对它的**消费**是否 fail-closed, 是本面问题。)

### A3 (修复不完备) 异常捕获与 status 规范化的覆盖完备性

r7 给 precheck 调用包了 `except Exception → {"status": "ERROR"}` (`benders_loop.py:5328-5361`)。请穷举:
- ① 异常捕获覆盖的是 `run_exact_routing_precheck()` 调用本身。但门检查之前 (`benders_loop.py:5302-5316`) 还构造了 `routing_grid` (`RoutingGrid.from_placement_core` / `RoutingGrid(...)`) —— 这些构造抛非 `TypeError` 异常时, 是 fail-closed UNKNOWN 还是会冒泡成未捕获异常 / 被外层吞成别的终态? 判读这条 routing_grid 构造失败路径的终态。
- ② `precheck_status = str(routing_precheck_summary.get("status", "feasible"))` 用 `"feasible"` 作默认 (`benders_loop.py:5381`)。如果 precheck 返回的 dict **缺 `status` 键** (畸形返回), 默认值是白名单内的 `"feasible"` → 放行 build。判读: 这个"缺键默认 feasible"是 fail-open 还是有上游保证 status 键恒在? 与 r7 的 fail-closed 姿态是否自洽 (缺键应 deny-unknown 而非默认 feasible)?
- ③ 大小写 / 前后空白: 门用精确成员判定 (`precheck_status not in {...}`), 白名单是小写。如果上游任何路径能产出 `"Feasible"` / `"FEASIBLE"` / `" feasible"` 这类大小写或带空白的 status, 它会落进非白名单分支 → fail-closed UNKNOWN (保守, availability 方向) —— 这方向无 soundness 风险, 但请确认**没有反向**情形 (某个非 feasible 的真状态因大小写规范化恰好匹配上白名单成员而被放行)。

## 若 A1/A2/A3 都证伪 → 本轮转又一次独立全面 soundness 重审

如果上述三线都实证站不住 (门与 build 的 status 对象恒等、duplicate 重算消费 sound、异常/缺键覆盖完备), 则本轮回到 LBBD soundness 不变量的**独立全面重审**, 换新角度往深挖 (别复读 r7 的三张表)。核心不变量仍是:

- **status 契约完整性**: 主循环每个消费 subproblem status 的分支, 非预期/非三态/预算耗尽/异常 status 必须 fail-closed 到 UNKNOWN, 绝不能被误读成 INFEASIBLE (→ 误铸 nogood 删合法解) 或 CERTIFIED。重点扫 r3-r7 之后**新加或改动**的消费点 (separator / power witness / PCR / D2 / pose-bool delegate 的主循环消费侧)。
- **cut / 缓存跨 iteration·跨 candidate 生命周期与单调性**: 加进 master 的每个 cut 永远有效; cut 的有效性证明若依赖"加 cut 那一刻"的瞬时状态 (binding model 内容 / routing 域 / 选中 ghost anchor / iteration 计数 / 外置 domain), 跨复用时该前提是否被保持 (cut 污染 = soundness 缝); condition literals 解析失败必须 fail-closed 不加而非降级成无条件 cut; 缓存命中结果逐个判读 proof-bearing vs telemetry-only。
- **时间预算全出口终态**: 所有 stage 的 timeout / 预算耗尽出口都收敛到 UNKNOWN/TIMEOUT 而非 INFEASIBLE/CERTIFIED; 单调时钟; 预算检查点之间最长未检查窗口有界。

## 面边界 (只审本面, 跨面不审)

本面 = Benders/LBBD 主循环 (`src/search/benders_loop.py`)。以下**明确列入"不审"**, 怀疑跨面缺陷时**交叉引述 `PROJECT_LOCK` 契约条款而非在本轮重证**:
- 其余 7 面各自的内部正确性: master 几何 (`exact_coordinate_master` / pose-bool master 的 F-GM-* 条款)、binding 子问题内部 (F-BIND-* 条款)、routing 子问题内部编码 (F-RT-* 条款, 含 connector cell / 多组件 / duplicate front key / 外置域裁剪 / FEASIBLE 连通性重证)、cuts 独立面 (F-CUT-* / CUT-*-H* / PCR-R5 系列 / CUT-R12-H1 power-conditioned 条款)、preprocess / campaign / scheduler / flow 诊断内部。
- 本面只审 LBBD 主循环对这些子问题**返回值的消费**是否 sound (status 解读 / cut 铸造前提 / 预算终态), 不重证子问题自身的几何/编码正确性。

## 明确不要报的

- **F-BL-R7-01 修复本身** (已 lock 已修, 见 `PROJECT_LOCK.md:136`); 本轮只攻它的同型残留 / 反向缺陷 / 不完备, 不重报已修项。
- r3-r6 已修 finding (F-BL-R3-01 / F-BL-R3-02 / F-BL-R4-01 / F-BL-R5-PS-01) 与已审 sound 结论。
- 设计决策 (owner 已定): canonical 口径 / 266 强制设施口径 / `min_side >= 6` 是 admissibility 不是 tie-break / omni_wireless / 52-Port 不变量。
- exploratory **行为 / 性能** (但 env 门控 cut 路径的 **soundness** 仍要审)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate, 不是 bug); P1.3B `step_8_apply_to_master` 禁区 (未集成边界, 不报); persisted `exact_safe_cuts` 是 telemetry 非 proof (V82, 不当 proof source 误报)。
- `facility_pools` pose dict 浅拷贝共享 (r5 已挂账保守备注, 当前无 mutation 路径)。
- `candidate_placements.json` 已随包内置校验 (不报"缺文件"); `_codex_archive/` 只读历史参考 (非活跃代码)。

## 自验环境与已知基线 (硬不变量 = 0 failed)

- candidate 已随包, 全量 `python -m pytest -q src/tests` 应 **0 failed** (passed ≈3058, 具体数目以实跑为准; **硬不变量是 0 failed**)。沙盒 pytest-randomly 报 seed 错就加 `-p no:randomly`。跑不完全量就跑专项 (`src/tests/test_exact_contract.py` + 上述回归) 并**如实声明**没跑全量。
- `python scripts/check_p1_2_proof_obligations.py` 应 pass (anchors 8 obligations)。
- finding **必须**带可复现 probe (monkeypatch 构造一条能触发的输入, 断言 fail-open 终态) 或 file:line 严谨论证; **实证推翻你的怀疑就不要报** (宁可少报一条假阳, 不要拿"理论上可能"凑数)。

## 严重度纪律

- **false-CERTIFIED** (把非证明状态转译成 INFEASIBLE 证明 / 铸出删合法解的 nogood / 任何路径输出 CERTIFIED 而其证明前提不成立) = **soundness** —— P1.2 闭环只认这一类, 是本轮唯一会改 owner 三连清白计数的发现。
- **false-INFEASIBLE 保守失败 / 过早截断 / fail-closed 把合法路径误判成 UNKNOWN** = **availability**, 标 **LOW** 加固即可, 不算 soundness。

## 交付物 (REVIEW.md)

- 逐条 finding: severity / file:line / 可复现 probe 或严谨论证 / 修法 (有把握附 unified diff + regression, **LF 行尾**, 不重写 candidate 工件)。
- 若确认 sound: **明确写"本轮零 soundness finding"**, 并按本轮三攻击线分段判读 ——
  ① A1 门 vs build 的 status 对象同一性结论 (列出所有 build 路径收到的 analysis 来源 + 各自是否经过门校验);
  ② A2 duplicate-terminal build-time 重算的消费终态判读;
  ③ A3 异常 / 缺键 / 大小写覆盖完备性判读;
  ④ (若转全面重审) 新角度的 status 消费点 / cut 生命周期 / timeout 终态判读 (不复读 r7 三张表, 只列你新查的角度)。
- 真 Pro 确认轮, 独立下结论。前轮结果不构成本轮任何先验 —— r7 抓到一个 HIGH 不代表本轮一定还有, 也不代表一定干净; 按你自己最对抗的独立判断走。
