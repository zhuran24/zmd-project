# 终末地 IndustrialPlanner 精确求解器 — binding 面 round 10 (真 Pro 确认轮·R9 单 finding 修复验证 + 同型残留猎取 + 又一次独立全面 soundness 重审)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_b4041f3e.zip`, sha256 `b4041f3eb065e9756a1dbd21f3e513479dfd504e2024b74fb08a2d235af08893`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照 (HEAD `8c61e1e`)。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

`data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) **已随包, 已校验**, 无需再生; 仍不准伪造/改写。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → **binding 端口绑定** → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **binding 子问题 (端口绑定 CP-SAT 模型)** (`src/models/binding_subproblem.py` 为核, 配 `src/models/port_binding.py` 域枚举引擎 / `src/preprocess/operation_profiles.py` 容量→槽 / `src/search/benders_loop.py` 的 binding 注入与 safe-reject ladder)。

## 本面定义与历史 + 本轮性质 (关键, 必读)

本面 = binding 子问题是否**忠实编码规则**: 端口 exact-one 商品绑定 / 容量 (rate→slot 取整) / generic 通用槽 + wireless 虚拟槽 / `__unused__` 哨兵 / binding→routing 接口 (`extract_port_specs`) / binding-local safe-reject ladder / generic I/O 需求工件 (`load_generic_io_requirements`) 的 fail-closed 装载。只管 binding 选出的 port_specs 既不 stricter-than-rule (false-INFEASIBLE) 也不 looser-than-rule (false-FEASIBLE)。历史:

- r1-r7 = thinking/更早模型, 抓 F-BIND-R1-01/R1-02 (哨兵 + loader fail-open)、R2-01/R2-02 (master 侧 loader + JSON 重复 key)、R3-01..05/R4-01/R5-01 (proof 单解析单快照封印); r6/r7 = 零 finding (达 thinking 饱和下沿)。
- r8 = 真 Pro 首轮重审, 抓 2 个 finding (F-BIND-R8-01 conditional-HIGH overload fallback / F-BIND-R8-02 LOW generic-input 完备性), 均已修。
- **r9 = 真 Pro 确认轮, 在 R8-02 同族里再抓 1 个 finding, 已修, 本轮就是来确认它**:
  - **F-BIND-R9-01 (LOW availability hardening)** = R8-02 的完备性校验当初被收窄在 `if input_commodities:` gate 下, 只在 `required_generic_inputs` 非空时才查 canonical generic-input 覆盖。一个**非空但 output-only** 的 `generic_io_requirements.json` (`required_generic_outputs` 有合法外部源商品, `required_generic_inputs` 为空) 不是 "output+input 双空" 的合法退化态, 却会**绕过**完备性校验 → routing-free 集合为空 → 无线终品 (`qiaoyu_capsule` / `valley_battery`) 的 producer 输出被重新暴露成 routing terminal → orphan source / spurious `front_blocked` / false-INFEASIBLE (R8-02 同族)。修复把完备性校验从 `if input_commodities:` 内移出, 改为 gated on "output+input 双空 early return" (`binding_subproblem.py:256-257`), 任何非空工件 (含 output-only) 都接受完备性校验; lock 已收紧 (`PROJECT_LOCK.md:135`)。

**本轮 r10 = 真 Pro 确认轮。姿态 (关键):** 你的任务**不是**重报已修的 R9-01 本身, 而是: ① 独立判定 R9-01 修复是否**真 sound 且完备** (gate 现在 keyed on "工件双空" early return, 这条新边界自身正确吗?); ② 把这个修复点当**攻击面**, 在同一缺陷家族里找「同类的下一个」—— 还有没有**别的 generic I/O 需求工件畸形/退化态**绕过完备性或角色校验? 还有没有**别的把无线终品重新暴露成 routing terminal** 的路径 (R8-02/R9-01 攻击的是 loader 侧完备性; routing-free 集合的**消费侧** `extract_port_specs` / `_filter_pose_binding_domain` 排除是否对**所有**派生方式一致)? ③ 确认 R9-01 修复**没有反向引入** false-FEASIBLE 或新的 false-INFEASIBLE (现在更多工件形态会 fail-closed, 是否误拒了某个**合法**配置?)。前轮修复点已对外公开, 请把它当**起点**而非终点。

**同时 (并行第二目标): 又一次独立全面 soundness 重审。** R9 之后本面已是 thinking 多轮 + Pro 三轮的深度。本轮 attack surface = 本面核心 soundness 不变量本身 (见下 "核心不变量清单"), 请**换一个新角度**往深挖, **别复读上轮的判读结论** (上轮已确认的 Q1/Q2/Q3 判读不必重证, 但如果你用新角度发现上轮判读有漏洞, 那正是高价值 finding)。包内带其它面同期修复, 各面有自己的线, 别重报。

## 本面核心 soundness 不变量清单 (独立全面重审的锚点)

逐条**独立从规则推导预期语义再比对实现** (勿从实现学语义 —— F-RT-R2-01 教训: diff-fuzz oracle 抄了 solver 的反相 key, 对那一类盲 900 实例):

1. **端口 exact-one 商品绑定**: 每个物理端口/虚拟槽恰好绑一个商品或 `__unused__` 哨兵; 不存在跨 commodity 共享同一物理端口 cell 叠加吞吐 (false-FEASIBLE)。
2. **容量 rate→slot 取整**: `_rate_to_slots()` (`operation_profiles.py`) 的 `ceil(rate/capacity - 1e-9)` 是否既不少给槽 (吞吐不足却 FEASIBLE, false-FEASIBLE) 也不多要槽 (合法配置因槽不够 INFEASIBLE, false-INFEASIBLE); `_enumerate_side_binding_patterns()` (`port_binding.py`) 在 `total_slots > cell_count` 时 raise 而非伪装空域。
3. **generic 通用槽 + wireless 虚拟槽语义**: generic-output 只接 `boundary_io`/`protocol_core`, generic-input 只接 `wireless_sink`; 每 slot `ExactlyOne(real_commodities + __unused__)`; 需求约束 `sum(vars)==required` (含 `required==0` 强制全 false)。
4. **`__unused__` 哨兵精确计数**: 哨兵 binding-internal, 永不进 `extract_port_specs` / 任何 routing/flow 面; reserved name 在需求 loader 被拒; `R<S`/`R=S`/`R>S` 三态计数正确 (不依赖当前 52=52 满额巧合)。
5. **routing-free 终品对偶排除**: canonical `sink_kind==generic_input` 终品 (`qiaoyu_capsule`/`valley_battery`) 无线消费, 其 producer **输出**口必须从 `extract_port_specs()` 排除; **输入**口 (原料) 保留 routed。排除必须在**每个** routability 消费侧成立 (loader 侧完备性 = R8-02/R9-01; 消费侧 = `extract_port_specs` + RAB `_filter_pose_binding_domain`)。
6. **generic I/O 需求工件 fail-closed 装载**: section 缺失/类型错/负数/重复 key/非有限数/reserved 哨兵/角色错 (output 非 external_boundary / input 非 generic_input) 全 fail-closed; 非空工件必须正槽覆盖所有 canonical generic_input 终品 (R8-02/R9-01)。
7. **binding-local safe-reject ladder**: `front_blocked`/`relaxed_disconnected` 先加 binding-level nogood 并枚举剩余 alternatives, 只有 binding CP-SAT `INFEASIBLE` (overload env-on 时还需 env-off replay 仍 INFEASIBLE) 才允许铸 whole-layout nogood; budget exhaustion 永不当 exhaustion proof。

## 审查重点 (行号基于本包 HEAD 8c61e1e 的 binding_subproblem.py / benders_loop.py, 解包后请自核, 别照抄)

### Q1 [验 R9-01 修复 soundness + 新 gate 边界, 最高优先]

修复点: `_validate_generic_io_requirement_roles()` (`binding_subproblem.py:249-341`)。结构: `:254-255` 取 output/input commodity 元组; `:256-257` **新 early return = 仅 output+input 双空**; `:276-304` 角色校验 (output=external_boundary / input=generic_input); `:306-341` **完备性校验现已无条件执行** (只要过了双空 early return) = canonical generic-input 全覆盖 + 正槽数, 否则 ValueError。请独立深挖:

- (a) **新 gate 边界正确性**: 现在完备性 gate keyed on "output **和** input **都**为空" 才跳过。请独立确认这条新边界自身 sound: 是否还有**别的非空畸形态**应被完备性挡住却漏了? 例如 —— input section 存在但**只声明部分** canonical generic-input 终品 (覆盖 `qiaoyu_capsule` 漏 `valley_battery`)? input 声明了**非 canonical** 商品占位 (角色校验在 `:291-304`, 它会先 raise 还是先过完备性)? output 声明了 canonical generic-input 终品到 output section (跨 section 错配)? 逐个走读 `:254-341` 的判定顺序, 给出每种畸形态最终落到哪条 raise / 是否漏过。
- (b) **修复不引入新 false-INFEASIBLE (反向缺陷)**: 现在更多工件形态 fail-closed。请判: certified 主链上 binding 真实收到的 `required_generic_inputs` 是否**保证**满足 "正槽覆盖所有 canonical generic_input 终品" (即新校验在真实路径上**只会过不会误拒**)? 是否存在某个**合法** certified 配置 (例如某 candidate 几何上确实不需要某个无线终品), 现在被新完备性强制 fail-closed → 新 false-INFEASIBLE? 请从随包 `data/preprocessed/generic_io_requirements.json` + canonical `commodity_metadata` 反推: 完备性是 binding 的**真不变量** (每个 placed 实例的 generic input 口都要被需求覆盖, owner 已确认) 还是过强假设? 给规则依据。
- (c) **完备性判据 + 消费侧口径一致 (同型残留猎取核心)**: 完备性校验把 canonical set 取自 `commodity_metadata[*].sink_kind==generic_input` (`:312-317`)。但 routing-free 集合的**消费侧**实际口径来自 `required_generic_inputs` 正槽 (`binding_subproblem.py:406-410` 构造 `routing_free_sink_commodities`), 被三处消费: `_build_*` 域里跳过 (`:629`)、`extract_port_specs()` fixed 输出侧跳过 (`:1060`)、generic 输出侧跳过 (`:1097`)。请核: loader 完备性确保 `required_generic_inputs` 全覆盖 → routing-free 集合等于 canonical generic-input 全集; 但**三个消费点**是否都用同一个 `self.routing_free_sink_commodities`, 有没有**第四个**派生 routing 可见性的侧信道 (类比 F03-R3-01 教训: build-time filter `_filter_pose_binding_domain` 是独立侧信道, 不从 port specs 派生) 用了**别的**口径 (例如直接读 canonical 而非读 `required_generic_inputs` 正槽, 或反之) → 一边校验过、另一边漏排除 → 残留 orphan terminal? 这是 R9-01 攻击面的正向延伸: loader 完备性补好了, 消费侧一致性是同族下一个攻击点。

### Q2 [generic I/O loader 其它畸形态 + 角色校验完备 (R8-02/R9-01 家族枚举)]

R8-02/R9-01 都是 generic I/O 需求工件 loader 的 fail-open 缺口。请把整条 loader 链当家族, 独立枚举还有没有**别的**畸形 proof input 绕过 fail-closed:

- (a) **section 解析链**: `load_generic_io_requirements()` (`:154-200`) → `_load_generic_io_requirement_section()` (`:203-219`, 缺 section raise / 非 Mapping raise) → `_normalize_generic_io_requirement_mapping()` (`:222-246`, reserved 哨兵 raise / bool/非 int raise / 负数 raise)。请核: 这条链是否对**所有** proof-relevant 畸形 (空字符串 key、重复 key、`NaN`/`Infinity`、超大整数、Unicode 同形 key、section 是 list 而非 dict) 都 fail-closed? 重复 key 由 `_load_strict_json` (`:178`) 挡 (F-BIND-R2-02), 请确认 `_load_strict_json` 真的是 strict-parse (不是裸 `json.loads`)。
- (b) **角色校验 (`:276-304`) 完备性**: output 商品必须 `source_kind==external_boundary`, input 商品必须 `sink_kind==generic_input`。请判: 一个商品**同时**是 external_boundary 和 generic_input (dual-role) 会怎样? 一个 input 商品 canonical 里**缺 sink_kind 字段** (None vs "generic_input") 是否被 `:299` 的 `!= "generic_input"` 正确挡住? canonical `commodity_metadata` 自身缺失/非 Mapping 时 (`:269-274`) 是否 fail-closed?
- (c) **master 侧入口 fork**: F-BIND-R2-01 要求 master 侧 `load_generic_io_requirements_artifact()` 委托同一 fail-closed binding loader, 不能有第二个更宽松的 parser。请独立确认 R9-01 的 loader 改动**没有**在 master 侧留下未同步的旧校验逻辑 (master 侧若有自己的 generic-input 完备性副本, 现在和 binding 侧是否一致? 还是只委托?)。回溯 `master_model.py` 的 generic I/O 入口确认无 proof-surface fork。

### Q3 [R9-01 修复回归 + 全面重审残余角度]

- (a) **toy/test 退化态保护**: 修复保留了 "output+input 双空" early return。请确认所有 binding 测试 fixture 用的 toy 需求 (test-only 显式传 map 的路径) 不经过 disk loader 校验 (`PortBindingModel.__init__` `:379-405` 的分支: 显式传 map → 不调 `load_generic_io_requirements`)。即新完备性只在 disk 装载路径触发, test fixture 不被误伤 —— 但**生产/runtime 代码**绝不该走显式 toy map 路径 (F-BIND-R1-02 lock:99)。请确认无生产代码绕过 disk loader。
- (b) **全面重审新角度 (任选高价值方向, 别复读上轮 Q1/Q2/Q3 判读)**: 例如 —— ① `_rate_to_slots` 的 `-1e-9` 容差在**边界 rate** (恰好整除 / 略超整除) 上是否产生 off-by-one 槽数 (false-FEASIBLE 少给槽 / false-INFEASIBLE 多要槽)? ② generic-output 满额 52=52 不变量: `extract_port_specs` 在 `R<S` (某槽落 `__unused__`) 时是否正确**不导出** `__unused__` 同时**导出**所有真实绑定 (不漏不重)? ③ `_filter_pose_binding_domain` (RAB build-time filter, env-gated) 在 `routing_context=None` certified 主链是否真的**完全不参与** (确认 certified 主链 `routing_context` 为 None → 不经 RAB filter, 这是跨面边界, 但 binding 侧的 None 判定逻辑属本面)? ④ exact-one 约束在 generic 槽与 fixed binding 混合实例上有无 double-binding 漏洞 (一个商品被 fixed 口和 generic 口同时计数)? 请挑你独立判断最可能藏 soundness 缺陷的方向深挖, 给可复现 probe 或 file:line 论证。

## 明确不要报的

- **R9-01 / R8-01 / R8-02 本身已修, 重复报不算** (lock:134/135 已追加条款); 只报: 修复**不完备**、**有同型残留**、或**引入新缺陷 (反向 false-FEASIBLE/INFEASIBLE)**。
- 已修 lock 条款: F-BIND-R1-01/R1-02 (lock:98/99)、R2-01/R2-02 (lock:100/101)、R3-01..05/R4-01 (lock:102)、R5-01 (lock:103)、R8-01 (lock:134)、R8-02/R9-01 (lock:135); 关联 F-BL-R3-01/R3-02/R4-01/R7-01 (lock:136 budget exhaustion 非 exhaustion proof + status contract)、safe-reject 边界 (lock:134)。r6/r7/r8/r9 已审结论不必重证。
- **跨面边界 (明确列入"不审")**: ① 上游 master/preprocess 保证 pose 端口坐标几何正确 (geometry-master 面); ② 下游 routing 内部对偶 (deletion-core/lazy-demand/separator/PCR-CUT) 属 cuts/routing 面, 本面只验 binding 侧 `extract_port_specs` + RAB `_filter_pose_binding_domain` 排除是否对 routing-free 终品成立; ③ 需求工件单快照封印的 outer/worker 部分属 campaign/scheduler 面; ④ RAB-SEP / PCR-CUT / pose-bool master 均 env-gated 默认关, certified 主链 `routing_context=None` 不经 RAB filter — env-on 行为属 cuts 面; ⑤ master 侧 generic I/O 入口是否委托同一 loader 属本面 (Q2c), 但 master 自身的 hard-constraint/optional-lower-bound 推导属 geometry-master 面。怀疑跨面时**交叉引述 PROJECT_LOCK 契约** (如 lock:96/97/128) 而非重证。
- 设计决策 (canonical / 266 口径 / omni_wireless 虚拟槽 / 52-Port 满额不变量 / `min_side>=6` admissibility, owner 已定)。
- master / routing / cuts / preprocess / benders / campaign / scheduler 各面 (各自有线)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 行为/性能不审; persisted `exact_safe_cuts` 是 telemetry 非 proof。

## 自验环境与已知基线

- candidate 已随包, 全量 `python -m pytest -q src/tests` 应 **0 failed** (passed ≈3058, HEAD 8c61e1e; 数目以实跑为准, **硬不变量 = 0 failed**; 沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。跑不完就跑 binding 专项 (`test_binding*` / `test_port_binding*` / `test_wireless_sink_binding_semantics`) + `test_exact_contract` + `cuts/test_family_port_exposure` + 如实声明哪些跑了哪些没跑完。
- `python scripts/check_p1_2_proof_obligations.py` pass (8 obligations)。
- finding 必须带**可复现 probe 或严谨 file:line 论证**; **实证推翻你的怀疑就不要报**。
- 规则文本: `specs/05_facility_instance_definition.md` §5.4.3 (协议箱无线消费 + 生产端对偶排除, 行约 101-109); 商品角色真源 `rules/canonical_rules.json` `commodity_metadata` (source_kind/sink_kind, `qiaoyu_capsule`/`valley_battery` 在约 305-314)。
- 契约: `PROJECT_LOCK.md:96/97` (无线终品 routing-free 对偶排除 + 每个消费侧都成立)、`:98/99` (哨兵 + loader fail-closed)、`:134` (safe-reject + R8-01 overload fallback)、`:135` (R8-02/R9-01 loader 完备性)、`:136` (budget-exhaustion / status contract)。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾, `patch -p1 --dry-run` 可过)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附分段判读: ① R9-01 新 gate 边界 soundness + 畸形态枚举结论 (Q1) / ② generic I/O loader 家族 fail-closed 完备 + master 侧无 fork (Q2) / ③ R9-01 无回归 + 全面重审新角度结论 (Q3), 每条带规则依据。
- 真 Pro 确认轮; 前轮修复点是攻击面起点, 按你**自己的独立判断**下结论。

## 严重度纪律

- **false-CERTIFIED = soundness** (P1.2 闭环只认这个); 把合法解误删成 INFEASIBLE 但**对外保守失败** (false-INFEASIBLE / 保守 UNKNOWN) = availability, 标 **LOW** 加固。
- R9-01 本身是 LOW availability hardening (fail-open malformed proof input 诱发 spurious front_blocked); 同族残留默认同档, 除非你能证明它能直接铸出 false-CERTIFIED (那才升 HIGH soundness)。

## 范围边界

重点 = R9-01 修复 soundness + generic I/O loader 同族残留 + 消费侧口径一致 + 无回归 + 又一次独立全面 soundness 重审; 其余面不审。
