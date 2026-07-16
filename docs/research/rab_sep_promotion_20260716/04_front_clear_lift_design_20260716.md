# 04 — front-clear 上收批：master 编码设计文书 v2（2026-07-16）

> 前置材料链：01（命题 N soundness 备忘录 v2，11 席对抗幸存）→ 02（②段执行记录，
> `815a73e`）→ 03（③段 prod 演习判读：通道工作正常但 6 迭代无收敛迹象；本轮
> 审查顺带订正了它的内存峰值行与"dedup 拒重"推测）。owner 拍板"1"= 开本批。
> 任务 1（数学面）主线亲手收口；任务 2（master 编码侦察）codex 席完成、主线
> 抽查承重锚点属实。行号 @ HEAD `815a73e`。
>
> **v2 改判说明**：v1 经四席对抗验证（soundness×2 codex/opus 独立、CP-SAT 编码
> codex、成本/批边界 codex；wf_d123bca7，420k tokens/94 tool calls）。判决：
> **数学必要条件与设计方向 holds**；v1 的编码拓扑断言、成本预算、A/B 验收判据、
> 批边界四面被推翻。全部承重发现经主线亲手复核坐实（ghost combined NoOverlap
> `:4176-4180` + dedup `:4207-4247`、mem.log 四峰值逐字节、counter 语义 `:6544`、
> checker import-closure `:13176`），本 v2 全量吸收。§9 为逐条处置表。

## §0 一句话设计

把命题 N 的必要条件（经计数等价定理收缩成"每侧自由 front 计数 ≥ 该侧
routing-visible 需求"）以 **共享单向 free-cell 证书（独立 NoOverlap 拓扑）+
mode 条件 front 索引 + AddElement 计数** 的坐标原生形态写进 certified
coordinate master 的 build 期，使 ③段实测的"每轮 ~215 个 EMPTY_DOMAIN owner、
每轮 510s 学一批"整族组合在 master 内一次性不可行。soundness 继承 01 文书；
**编码拓扑的生死线 = free 证书绝不能与 ghost 互斥（§3.1）**。

## §1 数学承重面（任务 1，主线收口；审查后仅措辞收窄）

### 1.1 计数等价定理

**陈述**：对 `supports_exact_pose_level_binding` 成立（= 零 generic slot，
`port_binding.py:31-33`）的实例 i、pose p、布局 L：

```
RAB filter-empty(i, p | L)
  ⟺ (#{输入侧 port cell：front 在网格内且未被 L 占据} < req_in(op, snapshot))
   ∨ (#{routing-visible 输出侧 port cell：front 在网格内且未被 L 占据} < vis_out(op, snapshot))
```

**注意 demand 不是纯 op 常量**：它是 demand(op, certified generic_io
snapshot)——RFSC 集由 `binding_subproblem.py:511-540` 的
required_generic_inputs snapshot 构造，filter（`:963-976`）与 routing 端口
导出（`:1439-1459`）共用同一排除规则。上收编码必须吃同一 snapshot（§3.4）。

**证明梗概**（锚点 `src/models/port_binding.py:28-142`）：枚举器按侧生成
pattern、pose 级 domain 是各侧 pattern 的积；侧内 slot→port cell 任意分配；
RFSC 输出槽 routing-invisible、可落被堵 cell 不消耗自由 front。某侧 pattern
集为空 ⟺ 该侧自由 front 的 port cell 数 < 该侧需求；整域空 ⟺ 某侧空。⇐
方向：计数够则任取一组分配即得非空 pattern。

### 1.2 已验前提（全部亲手跑过或审查席独立复核）

| 前提 | 验证方式 | 结果 |
|---|---|---|
| front 永不落自身体格 | 全池 66,405 pose 逐一检查 | 0 违规 → 共享 free 证书对 front cell sound |
| 同 pose 同侧 port cell 的 front 两两不同 | 同上 | 0 共享 → port cell 计数 = front cell 自由位求和 |
| 每侧积结构 / 侧内任意分配 | 源码逐行（port_binding.py） | 成立 |
| 范围排除边界（v2 收窄措辞） | `port_binding.py:31-49`、`binding_subproblem.py:1063-1065` | **generic-slot op 不进入 fixed pose-level RAB EMPTY_DOMAIN 定理及第一版 lift 的范围**（≠"在所有子系统豁免 front 约束"——boundary_io/protocol_core 的 generic output 在 `:1119-1158` 仍有 front 过滤；此为文档精度订正【F3】） |
| RFSC 输出不可见 | op 需求表提取（operation_profiles.py） | RFSC={qiaoyu_capsule, valley_battery} |
| **设施体格全为矩形**（v2 新增显性前提【RECT】） | 审查席全池复核：7 设施类 66,405 pose occupied_cells == bbox | 0 非矩形 → 选项 A 的"interval 排斥集 = 精确 occupied_cells"仅在此前提下取等；实施必须加 fail-closed 哨兵钉死该不变量 |

### 1.3 第一梯级（静态 OOB 剪枝）实测 = 零收益

全部 18 个 op×pool 组合按"网格内 front 计数 < 需求"扫描 canonical pose 池：
0 个静态死 pose（生成器 edge-starvation 过滤已把 OOB-front 形态挡在池外，
`placement_generator.py:80-108,289-307`）。**本批全部价值在第二梯级，静态
剪枝不做。**

## §2 master 编码现状（任务 2 侦察收口 + v2 审查修正）

- 默认 certified 路径 = `CoordinateExactMasterDelegate`（`master_model.py:2598-2609`）。
  mandatory 按 `(facility_type, operation_type)` 聚 group、每 group count 个
  匿名 slot：`x/y/mode` IntVar（`:2900-2902`）+ 域表（`:2916-2933`）；体格
  interval 起点 = **physical footprint start（`slot.x + footprint_dx_min`，
  `:2684`），不是裸 slot.x**【F2 订正】。无 instance×pose Bool 矩阵。
- `master_pose_bool_literals=4761` 全部是 C1 pole pose Bool——**C1 现贡献
  4,761 boxes / 9,522 个 interval 对象**（AddNoOverlap2D 同下标 x/y interval
  对 = 1 box；v1 把 9,522 误当 box 数【F2b 订正】）。
- **NoOverlap 真实拓扑（v2 核心修正，主线亲核）**：core-only
  `AddNoOverlap2D(_core_x_intervals, _core_y_intervals)`（`:3758`）之后，
  ghost 阶段建 `combined = [*_core_*, *_ghost_*]` 的第二条 NoOverlap
  （`:4176-4180`），随后 `_dedup_subsumed_core_no_overlap`（`:4207-4247`）在
  core 是 combined 子集时**清空 core-only 前身**。既有回归
  `test_coordinate_no_overlap_dedup.py` 钉"带 ghost 时只剩一个活约束"。
  **ghost overlay 不是不相交的另一套——它是 core 列表的超集**；v1 "free 加
  进 body 那套、自然不进 ghost 那套"的结构断言不成立。
- C1 coverage 通道（`:6358-6417`）= 单向证书 + AddElement witness 先例；
  pose 条件化惯用式 = `OnlyEnforceIf` / `_eq_literal` 精确 iff（`:7596-7656`，
  缓存键 `(var.Index(), value)` 无碰撞风险【F3-eq 复核通过】）。
- 反例先例：全域 slot×pose match 数百万 selector；历史 grid-front-clear
  pose-bool 实验 333K vars/867K constraints 全 UNKNOWN。
- 封印面：`exact_coordinate_master.py`、`benders_loop.py`、
  `binding_subproblem.py`、`port_binding.py` 均已在 close-kernel V99 floor；
  checker 有 **import-time closure 扫描**（`check_p1_2_proof_obligations.py:13176`
  一带）——sealed 文件引入的新模块自动要求进 floor。

## §3 设计方案（第二梯级，坐标原生）

### 3.1 free-cell 单向证书通道 —— 三集合、双 NoOverlap 拓扑（生死线）

新变量：`free[c] ∈ {0,1}`，c 遍历 70×70=4,900 格；padded (W+2)×(H+2) 平面
数组（边界一圈常量 0）供 front 索引读取。

通道语义（单向）：`free[c]=1 ⟹ c 不被任何已选设施体格占据`。

**Lowering（唯一方案，吸收三席同洞发现）**：维护**三个独立 interval 集合**
——physical_body（现 `_core_*`）、front_free（新列表，**绝不 append 进
`_core_*`**）、ghost（现 `_ghost_*`）——和**两条同时活跃的 NoOverlap**：

```
NoOverlap2D(physical_body ∪ front_free)   # free 证书约束
NoOverlap2D(physical_body ∪ ghost)        # 既有 ghost overlay
```

free box = `[cx,cx+1)×[cy,cy+1)` 绝对格坐标（与 body/C1 同系，无 footprint
偏移）。**为什么这是生死线**：若 free 混入 `_core_*`，combined 那条会把
ghost 变成 free 的 blocker——而 routing/RAB 语义里 ghost 内 cell 是真自由格
（`routing_binding_context.py:62-81` 显式跳过 ghost_pick）。max-empty-rect
目标下设施端口朝向 ghost 是常态形态，这个错误 = **系统性切掉真最优解**，
且 §5 v1 的验收判据抓不到它。三席各自独立构造了具体超杀反例（如：
filling_capsule 6 输入 front 全落 ghost 内、数学条件 6≥4 满足、错误编码判
0<4 拒绝）。dedup 交互：既有子集校验会正确拒绝清空 body∪free 那条（free
∉ combined），但 lift ON 时"只剩一个活约束"的既有回归断言必须改为双活约束
断言；哨兵测试钉两条约束的 interval 成员集精确 = B∪F 与 B∪G。

方向性完备（不超杀）：free 是自由选择变量，真自由格总可置 1（含 ghost 内
格——按上述拓扑 ghost 不排斥 free）。**代价修正【F-01】：body interval 同
时进两个重型 propagator**——预算不再是"box 数翻倍"而是"双活跃全局
NoOverlap"（§5）。

### 3.2 需求侧：mode 条件 front 索引 + AddElement 计数

对每个范围内 mandatory slot s、每侧 σ ∈ {in, vis_out}、该侧第 j 个 port cell：

1. `f_{s,σ,j}` = padded 平面索引 IntVar：
   `f == (y+1+dy_m)*(W+2) + (x+1+dx_m)`，`OnlyEnforceIf(mode==m)`
   （mode 文字复用 `_eq_literal`，每 slot 4 个、缓存去重）。
2. `b_{s,σ,j} ∈ {0,1}`：`AddElement(f, padded_free, b)`。
3. 每侧 `Sum_j b >= demand_σ(op, snapshot)`；mandatory 恒 active、无条件。

**安全前提显性化【F1-padding】**：真实 front 偏移可达 -2/+6，一圈 padding
本身**不足以**独立兜住任意偏移——当前密闭性依赖既有 mode↔x/y 精确域耦合
（allowed_tuples/region，`:1750,:2916,:2935`）。审查席全池实测：66,405 pose
的 f ∈ [73,5110] ⊂ [0,5184)，0 OOB、0 flatten alias、padding 圈实际未被触
及。实施纪律：①不依赖 AddElement 拒越界兜底（9.15 语义：越界值被约束排除
而非 build 报错）；②R5 黄金对照逐 pose 断言 **padded row 与 column 各自在
界 + f 与枚举器 front 坐标双向相等**，不只断言标量 f。

规模（审查席实算订正【F5】，v1 毛估作废）：范围内 **219 slot**（266 −
boundary_io 46 − protocol_core 1），全部恰 4 mode；f IntVar/AddElement
**1,702**（输入 869 + 可见输出 833）；mode 条件等式 **6,808**；唯一 mode
文字 **876**；Bool 合计 **~7.5k**（4,900 free + 1,702 b + 876 eq-literal）；
interval **+4,900 boxes / +9,800 对象**。

### 3.4 需求数值来源：SSOT（v2 强化为结构要求）

**新公共 helper `routing_visible_port_demands(operation_type,
generic_io_snapshot)` 放进 `src/models/port_binding.py`（已在 V99 floor），
binding filter 与 lift 编码都改为消费它**——不是"两处各自实现同口径"，是
字面同一实现【F2/F-09】。明确禁止复用 coordinate master 现有
`_group_port_demand`（约 `:7020`）：它把全部 output、RFSC、generic 都计入，
口径过大，误用 = 直接超杀。一致性哨兵：filter 与 lift 的 demand 数值逐 op
相等 + 显式断言 lift 不经过 `_group_port_demand`。

### 3.5 范围（第一版）

同 v1：只做 mandatory × `supports_exact_pose_level_binding` op（219 slot）；
optional 无物理端口天然出范围；零需求侧不生成约束。

## §4 soundness 论证

### 4.1 必要性链

命题 N（11 席幸存）+ 计数等价定理（前提已验）⟹ 任何 certified-feasible
布局中范围内实例每侧自由 front 计数 ≥ 该侧需求 ⟹ master 加此约束 = 纯必要
条件，不排除任何可认证解，对 `max_lex` 最优性证明 sound。方向性完备由
§3.1 拓扑保证。

### 4.2 安全方向规则（v2 修订）

1. **free 排斥集 = physical_body（含 C1 pole）∪ 无 ghost**。
   **R3 已关闭为 verified-safe（双席独立源码核实 + 主线复核）**：selected
   C1 pole 经 `extract_solution` 以 facility_type='power_pole' + occupied_cells
   进 master 解（`:7469-7488`），`build_routing_binding_context` 把它们进
   blocker 集（`routing_binding_context.py:62-81`）——pole 是 RAB blocker，
   收纳 pole interval 与 RAB 一致，无需豁免分支。
2. **矩形前提**（§1.2 新行）：interval 排斥 = bbox；bbox == occupied_cells
   当前全池成立；哨兵 fail-closed 钉死，未来出现非矩形设施即挡批。
3. **demand ≤ 真实需求**：SSOT（§3.4）+ snapshot 同源。
4. **不完备只降剪枝**：范围排除、需求低估、free 单向性、以及"错误串读把
   被占 front 读成 free=1"类缺陷（under-pruning）都只弱化条件【F4b】；
   致命方向唯超杀——R5 黄金对照因此必须**双向 equality**。

### 4.3 与迭代通道的关系（验收判据重写【F-05/F-06】）

lift 吞并整族的验收判据 v1 写法（"EMPTY_DOMAIN cut → ~0"）**作废**——
`binding_domain_empty_cut_count` 只数**被成功采纳的 cut**（`benders_loop.py:6544`
在 `_add_exact_persisted_nogood` 成功后递增；cert 不完备 owner 在 `:6505`
之前已被跳过），lift 失效 + cut 全被拒 = counter 0 = 假绿。v2 判据：

> **master 产生 FEASIBLE incumbent 并真正进入 binding build 时，lift 覆盖
> 范围内的 raw empty-domain 事件数（按 liftable scope 分桶）必须严格 = 0；
> 任何正值 = lift 失败。** master 未到 binding（INFEASIBLE/UNKNOWN）时本项
> = NOT_EVALUATED，不得判绿。accepted-cut counter 仅作诊断。

RAB 迭代通道保留不拆：范围外 op 仍靠它；它是运行时皮带——lift 有缺口时
filter 仍 EMPTY_DOMAIN 出证兜底（两层独立 enforcement 同一数学条件）。

## §5 成本与验证计划（v2 全面重写）

**预算状态：UNVALIDATED FORECAST**【F-03/F-04】。v1 的 +1-5s/+0.25GiB/
21-26GiB 区间证据链被推翻：E2' 的"×4.15 约束仅 +4.1% solve"是 Boolean/
linear cut 负载（无 interval、不动 NoOverlap 列表，`git show e719e5d` 核
实），与 NoOverlap rectangle 扩容不是同一成本路径；C1 数据只弱支持"~10K
rectangles 模型 build 可行"。**正确基线（③段 mem.log 全量重扫，主线复核）**：
单 worker VmHWM 19.98 GiB、RSS 峰 19.57 GiB、swap 峰 8.07 GiB（运行早期）、
同采样 RSS+swap 峰 21.60 GiB。历史 41.6+18.6GiB 尖峰是 **w6 体制**定性先例，
对 w1 无倍率意义。新模型 HWM = UNKNOWN，待 A/B 校准。规模事实：现
master_interval_count=19,592 对象（9,796 boxes：ghost 4,225 + body 5,571）；
+4,900 free boxes 对 body 集是 +88%，且 body 进双 propagator。

**验证阶梯（六级，吸收 F-05/06/07 与 SUGGESTED 改稿）**：

1. **build-only 审计**：双 NoOverlap 拓扑/成员集精确断言（B∪F、B∪G）、
   dedup 不误清、4,900 distinct flat id、proto 计数、RSS/build 秒、
   **direct-build vs core-clone parity**（§7 F-10 面）。
2. **全池 differential**：66,405 pose 逐一——枚举器 front 坐标/需求 vs
   master 索引式/demand 双向相等（R5 黄金对照）。
3. **无 solve corpus 结构检查**【F-07 六步】：A/B runner 持久化每个 raw
   EMPTY_DOMAIN 事件（owner pose + 全部 blocker poses + 完整 layout/hash）
   ——③段那 1293 条无 payload 不可追溯用；新 corpus 上逐事件验证"lift 约
   束确实排除该赋值"，**并检查实际 built proto 的 free interval membership/
   mode guard/Element index/demand**（防"只验设计意图"共模假绿【R18】），
   加 RAB-nonempty owner 负控（防 checker 只见剪枝不见超杀）。
4. **单锚点 live smoke**：必须到达 binding build 且范围内 raw empty = 0。
5. **同 revision、独立进程的 lift OFF/ON 性能 A/B**：逐迭代 wall/branches/
   conflicts/RSS/swap 落盘；**显式 systemd-run MemoryMax/MemorySwapMax +
   OOM 判据**（1s 采样只是观测不是保护【R16】）。
6. 扩 anchor/worker/时间窗（在 4/5 全绿后）。

单锚点 6 迭代 A/B 的定位**降格为 integration/performance smoke**——lift
成功臂通常只有 1 个 master 布局样本，证不了整族吞并【F-06】；吞并由 2+3
承担。

## §6 风险登记簿（v2：R3 关闭、新增 R11-R18）

| # | 风险 | 缓解 |
|---|---|---|
| R1 | **双活跃全局 NoOverlap propagator**（不再是"box 翻倍"）→ solve 恶化 | 阶梯 1/5 硬对照；恶化即停批回报 |
| R2 | 占据 universe 漂移 | 拓扑成员集哨兵（阶梯 1）+ 矩形不变量哨兵 |
| R3 | ~~pole 是否 routing blocker~~ **已关闭 verified-safe**（§4.2.1） | — |
| R4 | demand 口径漂移 | SSOT helper + 一致性哨兵 + 禁 `_group_port_demand` 断言 |
| R5 | mode 索引/padding off-by-one | 全池双向黄金对照（row+column+f 三断言） |
| R6 | Element 索引域越界静默收紧 | 紧域构造 + 不依赖 Element 兜底 + 域哨兵 |
| R7 | 与 symmetry 单调序互作 | free/element 匿名 per-slot；异常时加 symmetry off 臂 |
| R8 | 新变量无 hint | 可接受；A/B 退化再评估 |
| R9 | sealed 批执行风险 | reseal SOP + ②段两轮演练 |
| R10 | 侦察/审查报告错漏 | 承重项全部主线亲核（v2 头注） |
| R11 | free 误并入 body+ghost → 系统性超杀 | §3.1 生死线 + ghost 内 free-可置-1 行为哨兵 |
| R12 | 旧 dedup/"单活约束"回归与新拓扑冲突 | lift-ON 双活约束断言；dedup 子集校验天然拒清 B∪F |
| R13 | raw 事件 vs accepted-cut 混淆 → 验收假绿 | §4.3 判据重写；scope 分桶 raw 遥测落盘 |
| R14 | core build/clone 间 feature identity/proto binding 漂移 | coordinate_binding 封存 lift 状态；clone 禁重读 env；parity 测试（阶梯 1） |
| R15 | corpus 只存 accepted cuts、无 raw 事件/负控 | 阶梯 3 corpus 规格写死 |
| R16 | kB/GiB、末值/峰值、异时峰值相加等读数错误；采样当保护 | 数字全部脚本产出+复核；实验挂 MemoryMax/MemorySwapMax |
| R17 | allowlisted env 非法值被静默当 OFF → 假 A/B | 严格值域：unset/0/false/off=OFF、1/true/on=ON、其它 fail-closed |
| R18 | offline checker 只验数学意图不验 proto 接线 → 共模假绿 | 阶梯 3 强制读实际 built proto |

## §7 实施批边界（v2 重写【F-08/09/10/11】）

**必改（sealed，全部走 reseal）**：
- `src/models/exact_coordinate_master.py`——三集合双 NoOverlap、free/element
  编码、`bind_from_core`/`export_core_binding` 携带 lift 状态（feature
  identity、free proto indexes、双 NoOverlap 成员摘要、计数；clone 从
  binding 恢复、不重读 env）、build_stats 扩展（master_interval_count 口径
  含 free）。
- `src/search/benders_loop.py`——新 env `EXACT_MASTER_FRONT_CLEAR_LIFT` 进
  `_CERTIFIED_KNOWN_ENV_NAMES` + `_CERTIFIED_OPERATIONAL_ENV_ALLOWLIST`
  （不进 = 仅因存在就 fail-closed）+ scope 分桶 raw empty 遥测。"不碰 RAB
  通道"修正为"不改 RAB cut/LBBD 控制流；允许 env 分类与遥测扩展"。
- `src/models/port_binding.py`——SSOT helper（已在 floor，reseal 即可）。
- `src/models/binding_subproblem.py`——filter 改为消费 SSOT helper。
- `scripts/check_p1_2_proof_obligations.py` + `data/proof_obligations/
  p1_2_proof_obligations.json`——四文件 pin + checker 自钉 reseal。

**必改（非 sealed）**：`src/tests/test_exact_contract.py`（env 双注册 +
控制器面）、新哨兵/黄金对照测试文件、阶梯 1-5 runner、`PROJECT_LOCK.md`
（新条款：双 NoOverlap 拓扑 + demand SSOT + ghost 排除 + default-OFF）、
`NAV_MAP.md`、`docs/项目说明/18_workflow_env_config.md`。

**条件改**：`master_model.py`（仅当 core binding 需显式新字段）、
`certified_artifact_contract.py`（仅当 semantic projection 变化）、
`conftest.py` slow 登记（仅当新测试 ≥8s）、strong-status allowlist（仅当
扫描出新 pin）。preflight 源码通常不改。

**env 值域**：unset/0/false/off = OFF；1/true/on = ON；其它值 fail-closed
（不静默解释）。默认 OFF；默认值翻转是 A/B 判读后的 owner 拍板项。

**明确不做**：静态剪枝、generic op、optional、动态 attach 形态。

## §9 v1→v2 处置表（四席发现逐条）

| 席位/编号 | 严重度 | 处置 |
|---|---|---|
| 三席同洞：ghost overlay 泄漏（F1/GHOST-LEAK/F4-ghost/F-01） | block/high | **吸收为 §3.1 生死线拓扑**（主线亲核 `:4176-4247`）；R11/R12 |
| soundness-codex F2 + cost F-09（demand SSOT 不可兑现于非 sealed） | medium/high | §3.4 强化：helper 进 port_binding（已在 floor）、binding 同批改消费 |
| soundness-codex F3（generic 措辞过宽） | low | §1.2 收窄 |
| opus RECT（矩形前提未陈述） | low | §1.2 新前提行 + fail-closed 哨兵 |
| opus/cost R3（pole blocker） | low | **关闭 verified-safe**，豁免分支删除 |
| encoding F1（AddElement 越界语义/padding 依赖） | low/medium | §3.2 安全前提显性化 + 测试三断言 |
| encoding F2/F2b（坐标系措辞/box 单位） | low | §2 订正 |
| encoding F3-eq/F4-injective/F4b | low | 复核通过；R5 改双向；build 哨兵 |
| encoding F5（规模复算） | medium | §3.2 数字全套替换（219/1,702/6,808/876/~7.5k） |
| cost F-02（内存基线读错） | high | doc 03 已订正 3 处；§5 新基线 |
| cost F-03/F-04（预算证据链） | high | §5 改 UNVALIDATED FORECAST + w6 定性化 |
| cost F-05/F-06（验收假绿/样本不足） | block/high | §4.3 判据重写 + A/B 降格 smoke + 阶梯 2/3 承担吞并 |
| cost F-07（corpus 检查） | high | 阶梯 3 采纳六步设计；③段 1293 条判不可追溯 |
| cost F-08/F-10/F-11（批边界） | high/medium | §7 全量重写 |
| cost R11-R18 | medium | §6 全部收入 |
