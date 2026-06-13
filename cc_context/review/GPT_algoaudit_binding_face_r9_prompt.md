# 终末地 IndustrialPlanner 精确求解器 — binding 面 round 9 (真 Pro 确认轮·R8 双 finding 修复验证 + 同型残留猎取)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_1e136b90.zip`, sha256 `1e136b90a290684874398ce5f2ddaceac156481d2178fa1333db9ba14b8e16f2`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照 (HEAD 26e4543)。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

**本包变化 (与历史轮不同)**: `data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) **已随包, 已校验**, 无需再生; 仍不准伪造/改写。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → **binding 端口绑定** → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **binding 子问题 (端口绑定 CP-SAT 模型)** (`src/models/binding_subproblem.py` 为核, 配 `src/models/port_binding.py` 域枚举引擎 / `src/preprocess/operation_profiles.py` 容量→槽 / `src/search/benders_loop.py` 的 binding 注入与 safe-reject ladder)。

## 本面定义与历史 + 本轮性质 (关键, 必读)

本面 = binding 子问题是否**忠实编码规则**: 端口 exact-one 商品绑定 / 容量 (rate→slot 取整) / generic 通用槽 + wireless 虚拟槽 / `__unused__` 哨兵 / binding→routing 接口 (`extract_port_specs`) / binding-local safe-reject ladder。只管 binding 选出的 port_specs 既不 stricter-than-rule (false-INFEASIBLE) 也不 looser-than-rule (false-FEASIBLE)。历史:
- r1-r7 = thinking/更早模型, 抓 F-BIND-R1-01/R1-02 (哨兵 + loader fail-open)、R2-01/R2-02 (master 侧 loader + JSON 重复 key)、R3-01..05/R4-01/R5-01 (proof 单解析单快照封印); r6/r7 = 零 finding (达 thinking 饱和下沿)。
- **r8 = 真 Pro 首轮重审 (double Pro), 抓 2 个 finding, 均已修, 本轮就是来确认它们**:
  - **F-BIND-R8-01 (conditional HIGH soundness)** = overload separation env-on 后 binding re-solve 返回 INFEASIBLE 时, 未统一走 env-off fallback 重解; overload separation 注入的是**可砍合法解的 HARD nogood**, 局部耗尽被误当成真 binding/routing exhaustion → 铸 whole-layout nogood (false-INFEASIBLE 方向)。
  - **F-BIND-R8-02 (LOW availability)** = `generic_io_requirements` loader 漏「声明非空 generic input 后必须正槽数覆盖所有 canonical `sink_kind=generic_input` 终品」的完备性校验; 漏声明/零槽数会悄缩 binding capacity 并把终品移出 routing-free sink 集 → producer 无线输出变孤儿 terminal → spurious front_blocked / false-INFEASIBLE。

**本轮 r9 = 真 Pro 确认轮。姿态 (关键):** 你的任务**不是**重报已修的 R8-01/R8-02 本身, 而是: ① 独立判定两处修复是否**真 sound 且完备**; ② 把这两个修复点当**攻击面**, 在同一缺陷家族里找「同类的下一个」(还有没有别的 binding INFEASIBLE→exhaustion 路径绕过 fallback / 还有没有别的需求工件完备性缺口); ③ 确认修复**没有反向引入** false-FEASIBLE 或新的 false-INFEASIBLE。前轮修复点已对外公开, 请把它当**起点**而非终点。包内带其它面同期修复, 各面有自己的线, 别重报。

## 审查重点 (行号基于本包 benders_loop.py / binding_subproblem.py)

### Q1 [验 R8-01 修复 soundness + 同型残留, 最高优先 false-INFEASIBLE]
修复点: `_retry_current_binding_without_overload_separation` (`benders_loop.py:5270-5285`, nonlocal 改 binding_model/binding_status) + 谓词 `_binding_used_overload_separation` (`:6183`) + 3 个 INFEASIBLE 调用点 (`:5464` 初始/safe-reject, `:5867`, `:6100`)。语义: env-on overload 用过 → INFEASIBLE 时 env-off replay `binding_rejected_selections` 重解, 仅当 env-off **也** INFEASIBLE 才让调用处走 exhaustion break; 未用 overload (`:5272-5275`) → 直接返回原 INFEASIBLE (真)。请独立深挖:
- (a) **同型枚举**: 全仓是否还有**其它** binding re-solve / binding INFEASIBLE → `binding_exhausted`/whole-layout nogood 的路径**没经过**这个 fallback? 重点核 overload nogood 注入点 `_add_storage_box_overload_nogoods` 的所有 caller、`benders_loop:5215` 一带的 binding INFEASIBLE→nogood 分支、以及 precheck safe-reject 重解 / relaxed_disconnected 重解 / routing-INFEASIBLE 后重解这几条线是否都被 3 个调用点覆盖 (r8 修复声称覆盖五处, 请核对是否真的一处不漏)。
- (b) **修复不引入 false-FEASIBLE**: env-off replay 必须仍尊重 `binding_rejected_selections` (不得把已拒绝的非法 binding 重新提出当合法解); env-off 重解出的 binding 若 FEASIBLE, 其 port_specs 是否与 env-on 主链同源校验 (容量/exact-one 不被 overload-off 放松)?
- (c) 谓词 `_binding_used_overload_separation` 是否可能漏判 (overload 实际用了却返回 False → 跳过 fallback → false-INFEASIBLE 复发) 或误判 (没用却返回 True → 多余重解, 仅性能)。

### Q2 [验 R8-02 修复 soundness + 边界, false-FEASIBLE/INFEASIBLE]
修复点: `_validate_generic_io_requirement_roles` (`binding_subproblem.py:249-342`)。结构: 空 output+input 需求 → early return (`:256-257`, 合法退化态); 角色校验 output=external_boundary / input=generic_input (`:276-304`); **完备性校验 gated on `if input_commodities:` (`:312-342`)** = 声明了非空 generic input 后, 必须覆盖所有 canonical `sink_kind=generic_input` 终品且槽数>0, 否则 ValueError。请独立验:
- (a) **gate 收窄是否过窄漏洞**: 仅在非空 input 才查完备性 — 这是为不破坏空需求 toy/test 的收窄 (owner 原 patch 删 early return 破 166 测试)。请判: certified 主链上 binding 收到的 `required_generic_inputs` 是否**保证非空** (即完备性校验在真实路径上**一定触发**)? 若某真实 certified 路径合法地传入空 input 但实际应有终品需求, 完备性就被 gate 跳过 → false-FEASIBLE。请从 loader caller (`:190-196`) + 主链注入点回溯确认。
- (b) **完备性判据是否精确**: `canonical_generic_inputs` 取自 `commodity_metadata` 中 `sink_kind=generic_input` 全集 (`:313-318`), 与 routing-free sink 集 (`required>0` 的 generic_input, 见 face 3/routing 的 `routing_free_sink_commodities`) 的口径是否一致 — 若两处对「哪些是 generic_input 终品」定义漂移, 仍可能一边校验过、另一边漏排除。请对照 canonical + specs/05 §5.4.3 独立推导预期集再比对 (勿从实现学语义, F-RT-R2-01 教训)。
- (c) `int(input_requirements[commodity]) <= 0` (`:329`) 的取整/类型: 非 int (bool/float/str) 是否在更上游 loader 已被 strict 解析挡掉, 还是这里 `int()` 会吞掉 (与 R1-02/R2-01 同型)?

### Q3 [两修复交互 + 回归]
R8-01 的 env-off retry 路径是否会重新装载 generic_io 需求工件 (再触发 R8-02 校验)? 若会, 两次校验结果是否一致、有无因 env 切换导致需求集变化? R8-02 的完备性校验有没有可能**误拒**一个合法的「部分 generic input 生产配置」(某 candidate 几何上只用到部分终品) → 新的 false-INFEASIBLE? 请确认完备性是 binding 的**真不变量**(规则要求每个 placed 实例的 generic input 口都要被需求覆盖) 而非过强假设。

## 明确不要报的

- **R8-01 / R8-02 本身已修, 重复报不算** (lock:103 区已追加条款); 只报: 修复**不完备**、**有同型残留**、或**引入新缺陷**。
- 已修 lock 条款: F-BIND-R1-01/R1-02 (lock:98/99)、R2-01/R2-02 (lock:100/101)、R3-01..05/R4-01 (lock:102)、R5-01 (lock:103); 关联 F-BL-R3-01 (lock:135 budget exhaustion 非 exhaustion proof) + safe-reject 边界 (lock:134)。r6/r7 已审结论。
- **跨面边界**: ① 上游 master/preprocess 保证 pose 端口坐标几何正确; ② 下游 routing 内部对偶 (deletion-core/lazy-demand/separator) 属 cuts/routing 面, 本面只验 binding 侧 `extract_port_specs` + RAB `_filter_pose_binding_domain` 排除; ③ 需求工件单快照封印的 outer/worker 部分属 campaign/scheduler 面; ④ RAB-SEP / PCR-CUT / pose-bool master 均 env-gated 默认关, certified 主链 routing_context=None 不经 RAB filter — env-on 行为属 cuts 面。
- 设计决策 (canonical / 266 口径 / omni_wireless 虚拟槽 / 52-Port 满额不变量 / `min_side>=6` admissibility, owner 已定)。
- master / routing / cuts / preprocess / benders / campaign / scheduler 各面 (各自有线)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 行为/性能不审; persisted `exact_safe_cuts` 是 telemetry 非 proof。

## 自验环境与已知基线

- candidate 已随包, 全量 `python -m pytest -q src/tests` 应 **0 failed** (passed ≈3050, HEAD 26e4543, 含本会话新增 memory-guard 测试; 数目以实跑为准, 硬不变量是 0 failed)。跑不完就跑 binding 专项 (`test_binding*` / `test_port_binding*`) + `test_exact_contract` + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass (8 obligations)。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。
- 规则文本: `specs/05_facility_instance_definition.md` §5.4.3 (协议箱无线消费 + 生产端对偶排除); 商品角色真源 `rules/canonical_rules.json` commodity_metadata (source_kind/sink_kind)。
- 契约: `PROJECT_LOCK.md:103` (F-BIND 区, 含 R8-01/R8-02), `:134/135` (safe-reject / budget-exhaustion 边界)。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附三段判读: ① R8-01 overload fallback 修复 soundness + 同型枚举结论 (Q1) / ② R8-02 完备性校验修复 soundness + gate 收窄边界判读 (Q2) / ③ 两修复交互 + 无新缺陷 (Q3), 每条带规则依据。
- 真 Pro 确认轮; 前轮修复点是攻击面起点, 按你自己的独立判断下结论。

## 范围边界

- 重点 = R8-01/R8-02 修复 soundness + 同型残留 + 无回归的真 Pro 确认; 其余面不审。
