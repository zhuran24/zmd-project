# 终末地 IndustrialPlanner 精确求解器 — binding 面 round 11 (真 Pro 确认轮·R10 单 finding 修复验证 + float/取整/容量精度同型残留猎取 + 又一次独立全面 soundness 重审)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_3b23181e.zip`, sha256 `3b23181e036be5daaf15d9166b76bb9d7b6acb49d81da3e046b8a07f1ec326b6`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照 (HEAD `eb5c012`, **本轮全部修复已合入 —— 这是带修复的新树, 不是修复前的树**)。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

`data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) **已随包, 已校验**, 无需再生; 仍不准伪造/改写。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → **binding 端口绑定** → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **binding 子问题 (端口绑定 CP-SAT 模型)** (`src/models/binding_subproblem.py` 为核, 配 `src/models/port_binding.py` 域枚举引擎 / `src/preprocess/operation_profiles.py` 容量 rate→slot 取整 / `src/search/benders_loop.py` 的 binding 注入与 safe-reject ladder)。

## 本面定义与历史 + 本轮性质 (关键, 必读)

本面 = binding 子问题是否**忠实编码规则**: 端口 exact-one 商品绑定 / 容量 (rate→slot 取整) / generic 通用槽 + wireless 虚拟槽 / `__unused__` 哨兵 / binding→routing 接口 (`extract_port_specs`) / binding-local safe-reject ladder / generic I/O 需求工件 (`load_generic_io_requirements`) 的 fail-closed 装载。只管 binding 选出的 port_specs 既不 stricter-than-rule (false-INFEASIBLE) 也不 looser-than-rule (false-FEASIBLE)。历史:

- r1-r7 = thinking/更早模型, 抓 F-BIND-R1-01/R1-02 (哨兵 + loader fail-open)、R2-01/R2-02 (master 侧 loader + JSON 重复 key)、R3-01..05/R4-01/R5-01 (proof 单解析单快照封印); r6/r7 = 零 finding (达 thinking 饱和下沿)。
- r8 = 真 Pro 首轮重审, 抓 2 个 finding (F-BIND-R8-01 conditional-HIGH overload fallback / F-BIND-R8-02 LOW generic-input 完备性), 均已修。
- r9 = 真 Pro 确认轮, 在 R8-02 同族里再抓 F-BIND-R9-01 (LOW availability, output-only 工件绕过完备性校验), 已修。
- **r10 = 真 Pro 确认轮, 确认 R9-01 修复 sound 且完备, 并在「容量 rate→slot 精确取整」新角度上又抓 1 个 finding, 已修, 本轮就是来确认它**:
  - **F-BIND-R10-01 (conditional HIGH soundness, latent-on-canonical)** = `_rate_to_slots()` (`operation_profiles.py`) 原实现 `int(math.ceil((rate / capacity) - 1e-9))` 把**略高于整数容量倍数**的 rate 向下取整一槽 —— 例如 `ceil(1.0000000005 / 1.0 - 1e-9) = 1` (应为 2)、`ceil(2.0000000005 / 1.0 - 1e-9) = 2` (应为 3) —— **少要一个物理绑定槽** → binding 域枚举 (`port_binding._enumerate_side_binding_patterns`) 可在端口不足下仍满足 exact-one + demand 约束 → false-FEASIBLE / false-CERTIFIED 方向。修复: 改为从 `PreprocessContext` 的 exact `Fraction` rate/capacity 用**有理数 ceiling** (`(num + den - 1) // den`) 算槽数, 不再有 float 容差。`OperationPortProfile.input_rates/output_rates/belt_capacity_per_tick` 全部改成 `Fraction` 类型, 新增 `_to_exact_fraction()` 转换器。**canonical profile 只用 rate ∈ {0.2, 1, 2, 3} + capacity 1.0, 永不落进 `(N, N+1e-9]` 带 (17 recipe 全部 0 mismatch), 所以这是 latent-on-canonical**, 打包数据下不触发, 是给未来/替代 rate 的不变量加固。lock 已收紧 (`PROJECT_LOCK.md:147`)。

**本轮 r11 = 真 Pro 确认轮。姿态 (关键):** 你的任务**不是**重报已修的 R10-01 本身, 而是: ① 独立判定 R10-01 的 Fraction 重写是否**真 sound 且完备** (有理数 ceiling 在所有合法 rate/capacity 上都正确吗? `_to_exact_fraction()` 的 `float → Fraction(str(float))` 转换边界自身无新缝吗?); ② 把这个修复点当**攻击面**, 在同一缺陷家族 (binding 容量链上的 float / 取整 / 精度) 里找「同类的下一个」—— **R10-01 只修了 `_rate_to_slots` 一处取整, 但容量链上是否还有别的 float-epsilon / 浮点比较 / 截断取整缝?** (见下 Q1/Q2 的具体猎取清单, 含 r10 修复**自己留下的** float 转换 seam); ③ 确认 R10-01 修复**没有反向引入** false-INFEASIBLE (现在有理数 ceiling 更严, 是否把某个**合法**配置因多要槽误判 INFEASIBLE? `Fraction(str(float))` 是否在某些输入上算出比真实需求**更多**的槽?) 或破坏任何下游消费者 (`input_slots`/`output_slots` property 的类型契约从 float-key 变 Fraction-key, 下游 `aggregate_*` / 聚合 / 诊断有没有静默坏掉?)。前轮修复点已对外公开, 请把它当**起点**而非终点。

**同时 (并行第二目标): 又一次独立全面 soundness 重审。** R10 之后本面已是 thinking 多轮 + Pro 四轮的深度。本轮 attack surface = 本面核心 soundness 不变量本身 (见下 "核心不变量清单"), 请**换一个新角度**往深挖, **别复读上轮的判读结论** (上轮 r10 已确认的 Q1/Q2/Q3 判读 —— R9-01 gate 边界 sound、generic I/O loader 家族 fail-closed、routing-free 消费侧一致、master 侧无 fork、RAB env-gated 不参与 certified 主链 —— 不必重证, 但如果你用新角度发现上轮某条判读有漏洞, 那正是高价值 finding)。包内带其它面同期修复, 各面有自己的线, 别重报。

## 本面核心 soundness 不变量清单 (独立全面重审的锚点)

逐条**独立从规则推导预期语义再比对实现** (勿从实现学语义 —— F-RT-R2-01 教训: diff-fuzz oracle 抄了 solver 的反相 key, 对那一类盲 900 实例):

1. **端口 exact-one 商品绑定**: 每个物理端口/虚拟槽恰好绑一个商品或 `__unused__` 哨兵; 不存在跨 commodity 共享同一物理端口 cell 叠加吞吐 (false-FEASIBLE)。
2. **容量 rate→slot 取整 (本轮 R10-01 焦点)**: `_rate_to_slots()` (`operation_profiles.py:65-74`) 的有理数 ceiling 是否既不少给槽 (吞吐不足却 FEASIBLE, false-FEASIBLE) 也不多要槽 (合法配置因槽不够 INFEASIBLE, false-INFEASIBLE); `_enumerate_side_binding_patterns()` (`port_binding.py:143-152`) 在 `total_slots > ordered_cell_count` 时 raise 而非伪装空域。
3. **generic 通用槽 + wireless 虚拟槽语义**: generic-output 只接 `boundary_io`/`protocol_core`, generic-input 只接 `wireless_sink`; 每 slot `ExactlyOne(real_commodities + __unused__)`; 需求约束 `sum(vars)==required` (含 `required==0` 强制全 false)。
4. **`__unused__` 哨兵精确计数**: 哨兵 binding-internal, 永不进 `extract_port_specs` / 任何 routing/flow 面; reserved name 在需求 loader 被拒; `R<S`/`R=S`/`R>S` 三态计数正确 (不依赖当前 52=52 满额巧合)。
5. **routing-free 终品对偶排除**: canonical `sink_kind==generic_input` 终品 (`qiaoyu_capsule`/`valley_battery`) 无线消费, 其 producer **输出**口必须从 `extract_port_specs()` 排除; **输入**口 (原料) 保留 routed。排除必须在**每个** routability 消费侧成立 (loader 侧完备性 = R8-02/R9-01; 消费侧 = `extract_port_specs` + RAB `_filter_pose_binding_domain`)。
6. **generic I/O 需求工件 fail-closed 装载**: section 缺失/类型错/负数/重复 key/非有限数/reserved 哨兵/角色错 (output 非 external_boundary / input 非 generic_input) 全 fail-closed; 非空工件必须正槽覆盖所有 canonical generic_input 终品 (R8-02/R9-01)。
7. **binding-local safe-reject ladder**: `front_blocked`/`relaxed_disconnected` 先加 binding-level nogood 并枚举剩余 alternatives, 只有 binding CP-SAT `INFEASIBLE` (overload env-on 时还需 env-off replay 仍 INFEASIBLE) 才允许铸 whole-layout nogood; budget exhaustion 永不当 exhaustion proof。

## 审查重点 (行号基于本包 HEAD `eb5c012` 的源码, 解包后请自核, 别照抄)

### Q1 [验 R10-01 修复 soundness + 有理数 ceiling + Fraction 转换边界, 最高优先]

修复点: `_rate_to_slots()` + `_to_exact_fraction()` (`operation_profiles.py:49-74`)。结构: `:49-62` 新 `_to_exact_fraction()` (Fraction 透传 / bool raise / int→`Fraction(v,1)` / float→`Fraction(str(v))` 且非有限 raise / str→`Fraction(v)` / 其它 raise); `:65-74` `_rate_to_slots()` 改为 `required = rate_fraction / capacity` 后 `(required.numerator + required.denominator - 1) // required.denominator`。`OperationPortProfile` 三字段 (`input_rates`/`output_rates`/`belt_capacity_per_tick`, `:27-31`) 改 `Fraction` 类型; `build_operation_port_profiles()` (`:78-110`) 直接传 `recipe.input_rate()`/`output_rate()`/`context.belt_capacity_per_tick` (它们在 `preprocess_context.py:39/42/82` 本就是 `Fraction`)。请独立深挖:

- (a) **有理数 ceiling 正确性**: `(num + den - 1) // den` 是 `ceil(num/den)` 的标准整数公式, 但**前提是 `den > 0` 且 `num >= 0`**。`_rate_to_slots` 在 `rate_fraction <= 0` 时 `return 0` (`:68`)、`capacity <= 0` 时 raise (`:71-72`), 所以进到 `:73-74` 时 `required = rate/capacity > 0`。但 `Fraction` 的 `numerator`/`denominator` 是否**保证** `denominator > 0` 且符号都在 numerator 上 (Python `Fraction` 总是正分母、最简形式)? 若 `required` 是某个**整数** (如 `Fraction(2,1)`), 公式给 `(2+1-1)//1 = 2` 正确; 若是 `Fraction(7,5)`, 给 `(7+5-1)//5 = 11//5 = 2 = ceil(1.4)` 正确。请独立确认在所有 `required > 0` 的有理数上这个公式**恰好** = `ceil`, 无 off-by-one。
- (b) **`Fraction(str(float))` 转换边界 (R10-01 自己引入的新转换缝)**: 修复用 `Fraction(str(value))` 把 float 转 Fraction (`:59`)。`str(0.1)` → `'0.1'` → `Fraction(1,10)` (精确十进制), 而 `Fraction(0.1)` (直接传 float) → `Fraction(3602879701896397, 36028797018963968)` (IEEE754 二进制残差)。修复选了 `str()` 路径 = 取**人类可读十进制**而非二进制真值。请判: 这条选择对**本面 soundness** 是更安全还是引入新缝? 具体 —— 若某个 canonical/未来 rate 在 JSON 里写成 `0.30000000000000004` (某计算产物), `str()` 保留它 vs 真值, 槽数会差吗? 反过来, 若真实 rate 是二进制不可表示的 `0.1` 而存成 float, `Fraction(str(0.1))=1/10` 给的槽数是否就是规则意图的槽数? **注意本面真实路径上 rate 来自 `PreprocessContext` 且本就是 `Fraction` (`_to_exact_fraction` 对 Fraction 是 identity 透传, `:50-51`), 所以 float 分支在 certified 主链上根本不触发** —— 请确认这一点 (即 R10-01 的 float→Fraction 边界只在 test/toy 直接传 float 时才走), 若确属 test-only 则 (b) 不构成 certified soundness 缝, 但请明说它**是否**可能在某个**生产**入口被 float 喂入。
- (c) **反向缺陷 (新 false-INFEASIBLE / 下游类型契约破坏)**: 有理数 ceiling 比 float-epsilon ceiling **更严** (不再抹掉 `(N, N+1e-9]` 的真实需求)。请判: certified 主链上 binding 真实收到的 rate (canonical 17 recipe, rate ∈ {0.2,1,2,3}) 在新公式下槽数是否与旧公式**完全一致** (lock 说 0 mismatch, 请独立复核 `0.2/1.0` → `Fraction(1,5)` → `(1+5-1)//5 = 5//5 = 1` 槽, 旧 `ceil(0.2-1e-9)=1`, 一致)? 更关键: `input_slots`/`output_slots` property (`:33-45`) 的返回**值**仍是 `int` (槽数), 但 `input_rates`/`output_rates` 的 **value 类型**从 `float` 变成了 `Fraction` —— 下游 `aggregate_commodity_rates()` (`:148-163`) 现在对 `rate` 做 `float(rate) * count` (`:159/161`), `aggregate_port_slots()` (`:167-189`) 用 `profile.input_slots` (仍 int)。请核: **有没有别的消费者**直接拿 `profile.input_rates[c]` 当 float 用 (期望 float 却拿到 Fraction), 在算术/比较/序列化/JSON dump 上静默坏掉 (Fraction 不能直接 `json.dumps`)? 若有, 是 certified proof 路径还是诊断路径? (诊断路径坏掉 = availability/telemetry, 非 soundness reset。)

### Q2 [binding 容量链同型残留猎取 (float / epsilon / 截断取整 家族枚举) — 核心]

R10-01 攻击的是 `_rate_to_slots` 一处取整缝。请把**整条 binding 容量精度链**当家族, 独立枚举还有没有**别的** float-epsilon / 浮点比较 / 截断取整 / 精度损失点, 能诱发 false-FEASIBLE (少要槽) 或 false-INFEASIBLE (多要槽):

- (a) **容量链上其余取整/比较点**: 全仓 grep `_rate_to_slots` 的所有调用方 (`operation_profiles.py:36/43` 的 property; 其它面如有) + 任何**别的**把连续 rate / 需求映射成离散槽数/端口数的地方。`port_binding._enumerate_side_binding_patterns` (`:143-178`) 的 `total_slots = sum(count for _, count in required)` (`:149`) 是整数求和 (count 已是 `_rate_to_slots` 的 int 产物), 但请确认它消费的 `required` 元组 count 全程是 int 不是 float。`binding_subproblem.py` 里 `int(required) > 0` (`:409`)、`int(utility.generic_input_slots)` 等强转点是否对**所有** proof-relevant 数值都先验证是整数再 `int()` (而非静默截断一个 float)? 有没有 `round()` / `int(float_expr)` / `>= float` / `<= float` 形式的浮点比较潜伏在容量/需求判定里?
- (b) **wireless-sink 槽数 + generic 槽数的整数性**: `_normalize_wireless_sink_generic_input_slots` (`binding_subproblem.py:82-99`) + `load_wireless_sink_generic_input_slots` (`:101-151`) 把 plan 里的 `wireless_sink.generic_input_slots` 装载成槽数。请核这条链是否对 float/bool/负数/非有限 fail-closed (类比 R10-01: 一个写成 `3.0000000001` 的 plan 值若被 `int()` 截断成 3 而非 raise, 是同型缝)。`OperationPortProfile.generic_input_slots/generic_output_slots` (`:29-30`) 是 `int`, 来自 `int(utility.generic_input_slots)` (`:105-106`) —— `utility.generic_input_slots` 上游是否已保证整数, 还是这里 `int()` 可能截断浮点?
- (c) **`aggregate_*` 诊断路径的 float 累加 (R10-01 自己留下的 seam)**: R10-01 的 patch 在 `aggregate_commodity_rates` 里把原来的 `rate * count` 改成 `float(rate) * count` (`:159/161`), 即在**聚合诊断**边界才转 float。请判: 这个 `float(Fraction)` 转换在聚合路径上有没有引入精度损失, 而该聚合产物**是否**被任何 certified proof 消费 (例如 preprocess sizing gate / 容量校验 / master 的 optional lower bound 推导)? 若聚合产物只进诊断/telemetry → 非 soundness; 若它进了某个**判定 FEASIBLE/INFEASIBLE 或推导 demand 下界**的 proof 路径 → float 累加误差可能在 266 实例规模上放大成槽数/需求 off-by-one (这才是高价值 finding)。请回溯 `aggregate_commodity_rates` / `aggregate_port_slots` 的消费者, 区分 proof 消费 vs 诊断消费。

### Q3 [R10-01 回归 + R9-01/R8-02 家族再确认 + 全面重审残余角度]

- (a) **R10-01 回归 + 类型迁移完整性**: `OperationPortProfile` 从 float-rate dataclass 迁到 Fraction-rate, 这是**类型契约变更**。请确认: ① 所有构造 `OperationPortProfile` 的地方 (`build_operation_port_profiles` `:85/100`, test fixture 如有) 都传 Fraction (或被 `_to_exact_fraction` 兜住); ② 模块顶层 `OPERATION_PORT_PROFILES = build_operation_port_profiles(DEFAULT_PREPROCESS_CONTEXT)` (`:113-115`) import-time 构造在新类型下仍成功 (无 import-time crash); ③ `find_unprofiled_operations` / `count_operations` / `get_operation_port_profile` 不碰 rate 类型, 不受影响。全量 pytest 应覆盖, 但请点名 `test_operation_profiles.py` 里新增的 R10-01 回归 (`test_rate_to_slots_does_not_round_down_slightly_over_integer_rates`) 是否**真正锚住**不变量 (它断言 `1.0000000005`→2、`2.0000000005`→3; 但它传的是 **float** 走 `_to_exact_fraction` 的 float 分支 —— 这测的是 float 入口的正确性, 是否也该有一条 **Fraction 入口** + **边界整除** (`Fraction(2,1)`→2 不是 3) 的回归锚? 缺这条锚是否让未来 float→Fraction 退化无人看守?)。
- (b) **R9-01/R8-02 generic I/O loader 家族再确认 (换角度, 别复读 r10 判读)**: r10 已确认 output-only / partial-input / 跨 section 错配 / dual-role / 缺字段都 fail-closed。本轮换角度: ① 完备性校验取 canonical set 自 `commodity_metadata[*].sink_kind==generic_input` —— 若 canonical **新增**一个 `sink_kind==generic_input` 终品 (owner-gated 扩展), loader 完备性会要求需求工件覆盖它, 但**随包需求工件**不含它 → 新 false-INFEASIBLE? 这是设计意图 (扩展 canonical 必须同步扩展需求工件, 属 owner gate) 还是真缝? 给规则依据。② `routing_free_sink_commodities` 用 `int(required) > 0` 判正槽 (`:409`); 完备性校验用的"正槽"判据与这里是否**同一口径** (都是 `> 0`)? 若完备性接受 `required==某极小正值` 但别处判 `>= 1` 阈值 → 口径裂缝。
- (c) **全面重审新角度 (任选高价值方向, 别复读上轮 Q 判读)**: 例如 —— ① exact-one 约束在 generic 槽与 fixed binding **混合**实例上有无 double-binding 漏洞 (一个商品被 fixed 口和 generic 口同时计数满足 demand, 实际物理吞吐不够)? ② `extract_port_specs` 在 `R<S` (某槽落 `__unused__`) 时是否正确**不导出** `__unused__` 同时**导出**所有真实绑定 (不漏不重), 且导出的 port_spec 槽数与 binding 模型选中的槽数一致 (没有把 `_rate_to_slots` 算出的"需求槽数"与"实际枚举出的物理槽数"混淆)? ③ `_enumerate_side_binding_patterns` 的 `total_slots > ordered_cell_count` raise (`port_binding.py:150-152`) 是否在**所有** profile 上先于 binding CP-SAT 求解触发 (即容量不足是 build-time raise 而非 solver-time 伪 INFEASIBLE)? raise 被谁 catch? catch 后是否被误读成 binding INFEASIBLE 铸 nogood (与 lock:134/136 status contract 的交互)? 请挑你独立判断最可能藏 soundness 缺陷的方向深挖, 给可复现 probe 或 file:line 论证。

## 明确不要报的

- **R10-01 / R9-01 / R8-01 / R8-02 本身已修, 重复报不算** (lock 已追加条款); 只报: 修复**不完备**、**有同型残留**、或**引入新缺陷 (反向 false-FEASIBLE/INFEASIBLE / 下游类型契约破坏 proof 路径)**。
- 已修 lock 条款: F-BIND-R1-01/R1-02 (lock:98/99)、R2-01/R2-02 (lock:100/101)、R3-01..05/R4-01 (lock:102)、R5-01 (lock:103)、R8-01 (lock:134)、R8-02/R9-01 (lock:135)、**R10-01 (lock:147)**; 关联 F-BL-R3-01/R3-02/R4-01/R7-01 (lock:136 budget exhaustion 非 exhaustion proof + status contract)、safe-reject 边界 (lock:134)。r6/r7/r8/r9/r10 已审结论不必重证。
- **跨面边界 (明确列入"不审")**: ① 上游 master/preprocess 保证 pose 端口坐标几何正确 + canonical rate 数值真源 (geometry-master / preprocess 面; rate 自身的值是否对属 preprocess 面, 本面只验 rate→slot 取整忠实); ② 下游 routing 内部对偶 (deletion-core/lazy-demand/separator/PCR-CUT) 属 cuts/routing 面, 本面只验 binding 侧 `extract_port_specs` + RAB `_filter_pose_binding_domain` 排除是否对 routing-free 终品成立; ③ 需求工件单快照封印的 outer/worker 部分属 campaign/scheduler 面; ④ RAB-SEP / PCR-CUT / pose-bool master 均 env-gated 默认关, certified 主链 `routing_context=None` 不经 RAB filter — env-on 行为属 cuts 面; ⑤ master 侧 generic I/O 入口是否委托同一 loader 属本面 (r10 已确认无 fork, 不必重证, 除非新角度发现裂缝)。怀疑跨面时**交叉引述 PROJECT_LOCK 契约** (如 lock:96/97/128) 而非重证。
- **env-gated / 默认关 行为不属 P1.2 certified soundness**: `EXACT_USE_POSE_BOOL_MASTER` (被 `pose_bool_master_not_certified` 挡) / `EXACT_POWER_PLACEMENT_SUBPROBLEM` (deny-unknown) / `EXACT_B1_BYPASS_*` / `EXACT_B1_PATCH_ROUTING_CORE` / `EXACT_BINDING_USE_OVERLOAD_SEPARATION` / RAB-SEP 均 env-gated, 它们的缺陷最多是 hardening/availability, 明确标; 只有在 canonical + 默认 env 下能铸 false-CERTIFIED 才是 soundness reset。
- 设计决策 (canonical / 266 口径 / omni_wireless 虚拟槽 / 52-Port 满额不变量 / `min_side>=6` admissibility, owner 已定)。
- master / routing / cuts / preprocess / benders / campaign / scheduler 各面 (各自有线)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 行为/性能不审; persisted `exact_safe_cuts` 是 telemetry 非 proof。

## 自验环境与已知基线

- candidate 已随包, 全量 `python -m pytest -q src/tests` 应 **0 failed** (passed ≈3074, HEAD `eb5c012`; 数目以实跑为准, **硬不变量 = 0 failed**; 沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。跑不完就跑 binding+容量专项 (`test_operation_profiles` / `test_binding*` / `test_port_binding*` / `test_wireless_sink_binding_semantics`) + `test_exact_contract` + `cuts/test_family_port_exposure` + 如实声明哪些跑了哪些没跑完。
- `python scripts/check_p1_2_proof_obligations.py` pass (8 obligations)。
- finding 必须带**可复现 probe 或严谨 file:line 论证**; **实证推翻你的怀疑就不要报**。
- 规则文本: `specs/05_facility_instance_definition.md` §5.4.3 (协议箱无线消费 + 生产端对偶排除, 行约 101-109); 商品角色真源 `rules/canonical_rules.json` `commodity_metadata` (source_kind/sink_kind, `qiaoyu_capsule`/`valley_battery`); rate/容量真源 `rules/canonical_rules.json` + `rules/preprocess_plan.json` (`belt_capacity_per_tick`, recipe rate), 经 `src/interchange/preprocess_context.py` 装载为 `Fraction`。
- 契约: `PROJECT_LOCK.md:96/97` (无线终品 routing-free 对偶排除 + 每个消费侧都成立)、`:98/99` (哨兵 + loader fail-closed)、`:134` (safe-reject + R8-01 overload fallback)、`:135` (R8-02/R9-01 loader 完备性)、`:136` (budget-exhaustion / status contract)、**`:147` (R10-01 有理数 ceiling)**。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾, `patch -p1 --dry-run` 可过)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附分段判读: ① R10-01 有理数 ceiling soundness + Fraction 转换边界 + 反向缺陷结论 (Q1) / ② binding 容量链 float/epsilon/取整 家族同型残留枚举结论 (Q2) / ③ R10-01 无回归 + generic I/O 家族再确认 + 全面重审新角度结论 (Q3), 每条带规则依据。
- 真 Pro 确认轮; 前轮修复点是攻击面起点, 按你**自己的独立判断**下结论。

## 严重度纪律

- **false-CERTIFIED on canonical + 默认 env = soundness reset** (P1.2 闭环只认这个); env-gated / conditional / 把合法解误删成 INFEASIBLE 但**对外保守失败** (false-INFEASIBLE / 保守 UNKNOWN) = availability/hardening, 明确标 **LOW/conditional**。
- R10-01 本身是 conditional HIGH (latent-on-canonical: 缺陷方向是 false-FEASIBLE/false-CERTIFIED, 但 canonical 数据不触发该边界带); 同族残留按此标尺定档 —— 能在 canonical + 默认 env 下直接铸 false-CERTIFIED 才升真 HIGH soundness reset, 仅 latent / 仅诊断路径 / 仅 future-rate 触发的标 conditional / LOW。

## 范围边界

重点 = R10-01 有理数 ceiling 修复 soundness + binding 容量链 float/epsilon/取整 同族残留 + Fraction 类型迁移无下游 proof 破坏 + 无回归 + 又一次独立全面 soundness 重审; 其余面不审。
