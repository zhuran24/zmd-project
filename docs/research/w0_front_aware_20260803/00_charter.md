# W0 front-aware 下界线 · 线章程

> **性质**：research-only。本线全部产物的 authority 布尔恒 false，`ledger_effect: "none"`。
> **双 ledger 状态**：`U=(1188,18)` 本线不碰；`L=absent`，且在 G3 独立 strict checker 零 issue 并复算出 ≥(42,6) 之前**不登记任何值**。
> **当前进度（2026-08-03）**：G1 语义层与 catalog 冻结线（甲段）、G1 组合层与门判定（乙段）均已落地并真跑过；
> **G1 终态 = INFEASIBLE**，机器证据与措辞限定见 `RESULT.md`。G2/G3 未开工。
> **本文是现状文书**，不是史料台账；被推翻的口径直接改写为当前真相，历史在 git 里。

---

## 1. 方向裁定记录

owner 2026-08-03 拍板：W0 下界主线按 **17 号处方**转向 front-aware pattern generator 路线，
派生定理四层分类工作并入本线，不单开批。

裁定依据（两份已消化的证据文书）：

- **19 号**（`../cleanroom_rederivation_20260718/19_w0_seed_death_sentence_recomputation_20260803.md`）：
  W0 pinned geometry seed「先天绑不上端口」的死刑指控独立复算**成立，且在仓库语义下更强**。
  219 台制造机中 129 台无法承担任何真实 operation class；即使放宽到最弱要求（每台 ≥1 自由输入
  front + ≥1 自由输出 front），219 个身位也只有 91 个可活。pinned seed 线续跑无意义。
- **20 号**（`../cleanroom_rederivation_20260718/20_h20_row_power_oracle_unsat_20260803.md`）：
  16 号 H20 沙漏梳备胎在其自述的第一道门 UNSAT 出局（as constructed）。

因此旧 pinned-seed、D6 class swap、单纯延长 routing 时间不再占用主要计算预算。

---

## 2. 三道门（G1 / G2 / G3）

门的定义照 17 号原文，措辞收紧到可执行。

### G1 · pattern 覆盖门

先不生成 route，求出完整的 body / pole / mode / active-front / 6×7 孔洞几何。

**硬指标**（17 号原文）：`dead_for_any_actual_class = 0`，且所有 operation class 计数精确匹配。

**判定**（`run_g1.py gate`，五条全绿才算 PASS）：

1. exact-cover master 返回 `OPTIMAL` 或 `FEASIBLE`，且其记录的 catalog manifest sha256 与实际 catalog 一致；
2. expansion 成功、杆集合已做包含极小化、`g1_geometry.json` 通过严格 schema 解析；
3. 独立审计 `verdict == "PASS"` 且 `issues == []`；
4. 审计在独立子进程（`python -I -S -B`，ortools 不可 import）跑出，其 `inputs.geometry.sha256` 等于门自己算的几何 sha256；
5. run receipt 闭合。

**G1 PASS 不登记任何下界。** 它只说明"这份几何过了便宜的必要条件"。

### G2 · portal / SCC 门

在固定的 G1 几何上构造通用 directed SCC（17 号 §4：规则允许一条 lane 同时携带多种 commodity、
19 种共用同一 component、无 capacity 限制，因此"一个通用 SCC + 574 个制造终端方向接口 +
boundary/core 的 generic terminal"是一个很强但完全合法的充分构造）。

失败必须返回具名原因——access isolation / portal incompatibility / free-space articulation /
component direction obstruction——不得只返回笼统的整图不可行。

### G3 · strict witness 门

补齐 required instance ID、commodity binding 与 route component JSON，直接运行**独立 strict checker**。
只有 checker 零 issue、并复算出至少 `(area, min_side) = (42, 6)`，才允许正式登记下界。

---

## 3. §0b v2.4 门序过堂记录

`docs/项目说明/00_master_roadmap.md` §0b v2.4 要求：新开任何构造/求解管线，门序须显式对照该节过堂并留记录。

| §0b 角色 | G1 | G2 | G3 |
|---|---|---|---|
| **① 切分（三档形态）** | 健全影子：端口 front 合法性 + class 计数——**不依赖任何路由决策即可求值**。精确本体留给 G3 | 影子：通用 SCC 可达性，不依赖商品绑定 | **精确本体**：独立 strict checker 逐谓词终审 |
| **② 住址（三腿）** | 尺寸：196 格局部 CP-SAT ×N + 千级 master；传播力：class 计数是全局算术律、传播极强；机器兼容：CP-SAT 原生 | 固定 G1 几何后退化为图问题 | stdlib checker，无求解器 |
| **③ 管线序（便宜→贵）** | **最便宜**：pattern 评估毫秒级，master 秒~分钟级 | 中：SCC 构造分钟级 | 最贵，但只跑漏斗底部的幸存者 |
| **④ 下游验证人** | 早期拒绝**带证书**（master 的 assumption core / 审计的 issue code）；早期放行是**暂定** | 同上，失败原因必须具名 | **终审**：零 issue + 复算 ≥(42,6) 才动 ledger |

**三极登记（§0b v2.3-2）**：G1 生成器 = **充分限制**极（比真规则严，构造出的必合法）；
`T-DEAD-BODY` / `T-CAPABILITY-BUCKET` = **必要投影**极；G3 checker = **精确语义**极。
三极不得混用——**G1 的 INFEASIBLE 不是必要条件的否定**，只能读作"本充分限制族内无解"。

**反面校准**：W0 pinned seed 把"可毫秒求值、不依赖任何路由决策的端口合法性"埋进末端小时级大求解，
六次 UNKNOWN 被读成"难"而非"无解"。G1 就是把这个影子前置成第一道门；
`dead_for_any_actual_class = 0` 是**构造式不变量**（pattern 里根本不许出现 dead body），不是事后统计。

**双 ledger 纪律（§0b v2.3-6）**：本线只可能抬下界账。`L=absent` 在 G3 独立 checker 零 issue
且复算 ≥(42,6) 之前不登记任何值；`U=(1188,18)` 本线不碰；资源中止（超时 / 预算耗尽）不改任何账。

---

## 4. 端口语义强制条款

**类需求一律从仓库冻结权威现场推导，绝不抄任何外部文书的表。**

推导公式（`g1_port_semantics.derive_class_table`，只用 `rules/canonical_rules.json` +
`data/preprocessed/mandatory_exact_instances.json`）：

```
slots(c) = ceil( amount(c) / ticks_per_cycle / belt_capacity_per_tick )
r_in  = Σ_c slots(inputs[c])
r_out = Σ_c slots(outputs[c])
```

**执行形态**：`src/tests/test_w0_g1_port_semantics.py` 对每个 mandatory operation 断言
本线推导结果 == `src.models.port_binding.routing_visible_port_demands(op, frozenset())`。
任何一行不等 = 测试红、批停。这条测试就是本条款本身。

### 九行类表

| class | 外部文书别名 | template | r_in | r_out | count | 组成 operation |
|---|---|---|---|---|---|---|
| `3L`  | 3L  | manufacturing_3x3 | 1 | 1 | 109 | crusher_blue_iron 34 + crusher_source 18 + parts_maker 6 + refinery_blue_iron 34 + refinery_steel 17 |
| `3O2` | 3O2 | manufacturing_3x3 | 1 | 2 | 6   | crusher_buckwheat |
| `3O3` | 3O3 | manufacturing_3x3 | 1 | 3 | 11  | crusher_sandleaf |
| `3I2` | 3I2 | manufacturing_3x3 | 2 | 1 | 6   | molding_bottle |
| `5L`  | 5L  | manufacturing_5x5 | 1 | 1 | 32  | planter_buckwheat 11 + planter_sandleaf 21 |
| `5O2` | 5O2 | manufacturing_5x5 | 1 | 2 | 17  | seed_collector_buckwheat 6 + seed_collector_sandleaf 11 |
| `6I3` | 6G  | manufacturing_6x4 | 3 | 1 | 32  | grinder_dense_blue_iron 17 + grinder_dense_source 9 + grinder_fine_buckwheat 6 |
| `6I4` | 6F  | manufacturing_6x4 | 4 | 1 | 3   | filling_capsule |
| `6I5` | 6B  | manufacturing_6x4 | 5 | 1 | 3   | packaging_battery |

合计 132 / 49 / 38 = 219 台；body 面积 3325 格；front 需求 574 格。
class id 由 `(template, r_in, r_out)` 确定性铸造，不是手工命名；17 号用的 6G/6F/6B 在别名列。

### 两处对上游文书的更正

**更正 1——repo 语义不是商品种类数，是 slot 数。**
19 号第 4 步把"repo 语义"刻画为冻结 recipes 的**商品种类数**（全部 3x3 恰 1 进 1 出、
全部 5x5 恰 1 进 1 出、全部 6x4 恰 2 进 1 出）。实测该刻画不成立：repo 的需求 SSOT 是
slot 数，`routing_visible_port_demands` 明写 `req_in = sum(input_slots.values())`，而
`input_slots` 走 `_rate_to_slots` = ⌈rate / belt_cap⌉。

种类数比真需求**更弱**（`crusher_sandleaf` 真需 3 个自由输出前格，种类数只算 1 个）。
按种类数放行的几何会在 G3 必死——正是本线要修的病（把便宜的必要条件后置）的同构再犯。
巧合的是，按 slot 数推导出的九行表逐行等于 17 号的 `operation_classes`；
**结论相同不等于依据相同**，本线以现场推导 + 交叉校验为准。

**更正 2——live bucket 是 8 个，不是 11 个。**
G1 蓝图用一对独立坐标 `(o, i)` 参数化 3×3 的 capability，数出 6 个 3×3 bucket。
这两个坐标并不独立：正方形的 mode 集在"交换一个 side pair 的两侧"下封闭
（`TB`/`BT`、`RL`/`LR` 成对存在），所以"能扇出到 n"与"能扇入 n"是同一个条件——
存在 pair 满足 `n_X ≥ 1 ∧ n_Y ≥ 2`，反过来读就是 `n_Y ≥ 2 ∧ n_X ≥ 1`。
3×3 只有 3 个可达 bucket，全表 `3 + 2 + 3 = 8`。蓝图的 `M3_o2_i0` / `M3_o3_i0` / `M3_o1_i1` 无所指。

capability 因此塌缩成一个整数：

```
cap = max over pairs with both sides non-empty of max(n_X, n_Y)
```

| bucket | 蓝图别名 | 可承担 class |
|---|---|---|
| `M3_1i1o`      | M3_o1_i0 | 3L |
| `M3_1i2o+2i1o` | M3_o2_i1 | 3L, 3O2, 3I2 |
| `M3_1i3o+2i1o` | M3_o3_i1 | 3L, 3O2, 3O3, 3I2 |
| `M5_1i1o`      | M5_o1    | 5L |
| `M5_1i2o`      | M5_o2    | 5L, 5O2 |
| `M6_3i1o`      | M6_i3    | 6I3 |
| `M6_4i1o`      | M6_i4    | 6I3, 6I4 |
| `M6_5i1o`      | M6_i5    | 6I3, 6I4, 6I5 |

两处更正都是"推导而非转抄"直接换来的。是否另发 21 号更正文书 = owner 事项（推荐发，一页）。

---

## 5. 派生定理登记表

机器可读镜像在 `derived_theorems.json`；两者的 id 集合与代码锚点由
`src/tests/test_w0_g1_charter_contract.py` 钉死。四层分类照 §0b v2.2 三档 + v2.3 三极扩容。

| id | 层 | 适用门 | 代码锚点 |
|---|---|---|---|
| `T-FRONT-IDENTITY` | 精确语义 | G1/G2/G3 | `g1_pattern_evaluator.PORT_FRONT_IDENTITY` |
| `T-PORT-SLOTS` | 精确语义 | G1/G3 | `g1_port_semantics.CLASS_TABLE` |
| `T-FRONT-FREE` | 精确语义 | G1/G3 | `g1_pattern_evaluator.is_front_usable` |
| `T-DEAD-BODY` | **必要投影** | G1 | `g1_pattern_evaluator.dead_for_any_actual_class` |
| `T-CAPABILITY-BUCKET` | **必要投影**（无损抽象） | G1 | `g1_port_semantics.BUCKET_SERVABLE` |
| `T-ARCHETYPE-COLLAPSE` | **必要投影**（等价变换） | G1 | `g1_exact_cover_master.COLLAPSE_EQUIVALENCE`（乙段） |
| `T-SUPPLY-CEILING` | **必要投影**（算术上界） | G1 | `g1_exact_cover_master.bucket_supply_ceiling`（乙段） |
| `T-EMPTY-PATTERN` | 精确语义（词汇完备性） | G1 | `g1_exact_cover_master.EMPTY_PATTERN`（乙段） |
| `T-POLE-MINIMAL` | **充分限制**（带证明） | G1/G3 | `g1_pattern_evaluator.minimize_poles` |
| `R-BODY-IN-REGION` | **充分限制** | G1 | `g1_region_model.BODY_IN_REGION` |
| `R-FRONT-IN-REGION` | **充分限制** | G1 | `g1_region_model.FRONT_IN_REGION` |
| `R-PORTAL-FIXED` | **充分限制** | G1/G2 | `g1_region_model.PORTAL_STUBS` |
| `R-PAT-CONN` | **充分限制** | G1/G2 | `g1_pattern_evaluator.portal_component` |
| `R-POWER-LOCAL` | **充分限制** | G1 | `g1_pattern_evaluator.power_local_ok` |
| `R-HOLE-IN-REGION` | **充分限制** | G1 | `g1_pattern_schema.HoleSpec` |
| `R-CORE-FRONT-RESERVE` | **充分限制** | G1 | `g1_region_model.RESERVED_FRONTS` |
| `R-BOUNDARY-LAYOUT` | **充分限制** | G1 | `g1_region_model.FIXED_FURNITURE` |
| `T-SCC-UNIVERSAL` | **充分限制**（17 号 §4，§0b v2.3 三极第二极） | G2 | 本批只登记不实现 |
| `H-TARGET-MENU` | 启发式 | G1 | `g1_pattern_generator.TARGET_MENU` |
| `H-GEN-OBJECTIVE` | 启发式 | G1 | `g1_pattern_generator.FRONT_PROXY_OBJECTIVE` |
| `H-SPINE-LANE` | 启发式 | G1 | `g1_pattern_generator.SPINE_LANE` |
| `H-DERIVED-SUBSETS` | 启发式 | G1 | `g1_pattern_generator.derive_subsets` |

两条乙段新登记的说明：

- `T-EMPTY-PATTERN` 是**词汇完备性**而不是限制。甲段生成器的每个菜单目标都要求 ≥1 台机器，
  所以它从不产出"什么都不放"的 pattern；而 CORE 区域已被证明放不下任何机身（§7）。
  两件事凑在一起，master 会因为"CORE 无 pattern 可选"报 INFEASIBLE——那是记账错误冒充结论。
  因此 master 的 catalog loader 现场合成空 pattern，并**照常过 evaluator** 才准入。
- `T-SUPPLY-CEILING` 是把 §7 的面积预门推广到 bucket / 总台数 / 模板族三个口径，
  无求解器、跑在 master 之前。方向唯一：**ceiling < demand 才是结论**（证明这份 catalog 盖不住普查），
  ceiling ≥ demand 什么也不排除。
- `T-POLE-MINIMAL` 在乙段是**全局**跑的：`R-POWER-LOCAL` 是买来给 master 省约束的每区限制，
  板面一旦成型，邻区的杆本来就可能已经覆盖到某台机器，而仓库的不冗余谓词管的是整板。
  删杆只会让格子变自由，因此不可能作废任何 front 见证或缩小孔洞。

**「带前件条件 cut」一层在 G1 为空**，理由必须写明：本线 shadow-only，不向任何 master 输出学习 cut；
生成器内部的 nogood 只在单次子解生命周期内存在、不导出、不跨 antecedent 复用，
因此 §0b v2.3-3 的前件纪律不被触发。将来若有 cut 导出，必须连同其前件登记进本表。

---

## 6. 区域划分与充分限制

板面沿 W0 framework 的供电格切成 25 个区域：`T[i,j] = [14i, 14i+13] × [14j, 14j+13]`，`i,j ∈ 0..4`，
无缝覆盖 70×70。**区域 = 一个 14×14 供电格**，不用 domino——domino 只在存在跨格耦合时才有价值，
而本节末尾的四条充分限制把跨格耦合全部消灭；跨缝孔洞留作乙段升级梯档位。

**固定家具**（不是决策，承自 W0 framework）：46 个 boundary_storage_port（左基线 23 个
anchor `(0,1+3k)` 1×3、下基线 23 个 anchor `(1+3k,0)` 3×1，零间隙）+ 1 个 protocol_core
（anchor `(3,59)`、9×9、orientation 1 = framework 的 `inputs_east_west`）。共 219 格。
其口前格 46 + 20 = 66 格由 `R-CORE-FRONT-RESERVE` 全部留空。

`(0,0)` 不被任何固定家具占，但两条零间隙基线把它的两个邻格都占满，因此它是一个**永久孤立的
自由格**——空板的 body-free 空间就已经是 2 个连通分量。连通性判据据此写成「全部 active front +
reserved 口前格 + 孔洞落在**同一个**分量里」，而不是「全图只有一个分量」。

**十个 region class**（按 (fixed mask, reserved mask) 的平移等价类归并；`usable = 196 − fixed − reserved`）：

| region class | 区域 | 数量 | fixed | reserved | usable |
|---|---|---|---|---|---|
| `CLEAN` | `(i,j), i≥1, j≥1` | 16 | 0 | 8 | 188 |
| `LEFT_J1` / `LEFT_J2` | (0,1) / (0,2) | 各 1 | 14 | 11 | 171 |
| `LEFT_J3` | (0,3) | 1 | 14 | 10 | 172 |
| `BOTTOM_I1` / `BOTTOM_I2` / `BOTTOM_I4` | (1,0) / (2,0) / (4,0) | 各 1 | 14 | 11 | 171 |
| `BOTTOM_I3` | (3,0) | 1 | 14 | 10 | 172 |
| `CORNER` | (0,0) | 1 | 26 | 12 | 158 |
| `CORE` | (0,4) | 1 | 95 | 31 | 70 |

全图 usable = **4435** 格。LEFT/BOTTOM 各自拆开是因为 boundary 口周期 3 与区域周期 14 相位不同
（LEFT_J1 局部 y ∈ {0,3,6,9,12}、J2 ∈ {1,4,7,10,13}、J3 ∈ {2,5,8,11}），不是冗余分类。

四条把跨区耦合消灭的充分限制（登记表 §5 有对应条目）：`R-BODY-IN-REGION`（body 不跨缝）、
`R-FRONT-IN-REGION`（active front 与本体同区 ⇒ master 零 seam 变量）、
`R-PORTAL-FIXED`（每边留 2 格 body-free 桩，相邻区域的桩隔缝 4-邻接 ⇒ 全图自由空间连通由构造给出）、
`R-POWER-LOCAL`（每区自己的杆覆盖本区全部机器；固定家具 `needs_power=false`，不构成供电义务）。

四条边一律预留桩（含贴图边），多浪费约 30 格，换来 16 个内部区域几何完全相同 —— 即 master 的 16 倍对称塌缩。

---

## 7. 甲段实测结论

### CORE 区域承载 0 台制造机（CP-SAT 证明 OPTIMAL）

`R-CORE-FRONT-RESERVE` 把 core 的 20 个口前格全部留空后，CORE 区域（usable 70）的自由空间只剩
宽 2 的环带与被 reserved 格切断的底带，放不下任何 3×3 本体。**219 台机器必须挤进其余 24 个区域。**

### 算术预门：面积上不排除，但余量只有 67 格

每个 region class 跑一次"最大化 body 面积"的 CP-SAT（计数自由、每台按其模板最便宜的
capability level、忽略连通性），得到的是**供给上界**：

| region class | 数量 | packing ceiling | 状态 |
|---|---|---|---|
| `CLEAN` | 16 | 146 | OPTIMAL |
| `LEFT_J1`–`J3` / `BOTTOM_I1`–`I4` | 7 | 134 | OPTIMAL |
| `CORNER` | 1 | 118 | OPTIMAL |
| `CORE` | 1 | 0 | 无可行 pose |

`supply_upper_bound = 16×146 + 7×134 + 118 = 3392`，`demand = 3325`，**slack = 67 格（2%）**。

读法（fail-closed 方向唯一）：这个上界**故意高估**（忽略自由空间连通性、每台按最便宜 level 计），
所以 `supply < demand` 会**否定整个限制档位**，而 `supply ≥ demand` **什么也不排除**。
当前结论是 `NOT_EXCLUDED_BY_AREA` —— 面积上过关，但 master 必须把几乎每个区域都塞到它被证明的极限。

试过一条加强：给上界模型补「每个被承诺的 front 格必须保留一个自由邻格」——
这是 evaluator 存活判据的必要后果，加上仍是 sound 上界。实测**十个 class 的 ceiling
一格没降**。本地度数不是瓶颈，真正杀死本体的是自由空间分裂成多个分量，那是 G2 的活。

### catalog 供给比需求少 312 格

正式 catalog（1354 个签名，manifest sha256 `dbcb32ef…`）每类取面积最大的 pattern
乘倍数求和 = 3013，比 demand 3325 少 **312 格（9.4%）**。
**在这份 catalog 上跑 G1 必然 INFEASIBLE，且只说明 catalog 薄**——
按 §9 的措辞纪律不得写成关于几何的结论。

机制不只是预算不够。把 CLEAN 菜单里面积顶到 ceiling 的目标用 30–90s 重解：
名次 107 的目标 CP-SAT 最优地摆出 11 台、面积正好 146，evaluator 一过只剩 2 台、面积 50。
**建模内的 front 代理弱于 evaluator 的存活判据**——模型只要求那一侧留够空 front 格，
evaluator 还要求这些格落在自由空间分量里；密度顶到 ceiling 时自由空间碎掉，
front 格名义上空着实际够不着。这也解释了 catalog 里 `rejected_dead_body = 0`
而 `stripped_to_smaller` 高达 168–238：死体不是被拒绝，是被剥掉。

完整数字与乙段加深方向见 `CATALOG_REPORT.md`。

## 7b. 乙段实测结论（摘要，全文见 `RESULT.md`）

**G1 终态 = INFEASIBLE**，升级梯走到 L1（两轮），L2–L4 按算术排除、L5 按开线书停下交 owner。

- L0（甲段 catalog）：master 0.2 s `INFEASIBLE`，删除法极小核 = 九个非 CORE 的 `assume_cover`
  + `assume_total_bodies`；无求解器预门独立给出同一件事——总台数上界 210 < 219。
- **9 台不是几何墙**：219 台摊到 24 个可用区域是 9.125 台/区，而两份 catalog 最密都是 9 台。
  直接向 CLEAN 的密集目标提问，找到了 **10 台的合法 pattern**——上限是 `H-TARGET-MENU`
  的排序产物（10 台以上的目标排在几百名开外）。因此给菜单加了 `min_bodies` **过滤器**
  （过滤而非重排，登记的排序原样保留）。
- L1 并集（L0 ∪ 深挖轮 ∪ 密集轮，按签名并集）：总台数闸破了（244 ≥ 219），
  但 body 面积上界 3,113 < 3,325，核相应移到 `assume_class[5L]/[6I3]/[6I5]`——
  密集 pattern 几乎全靠 3×3 堆出来。
- 病灶定位：不是几何允许多少（松弛上界 3,392，slack 67），是**生成器造得出多少**
  （3,113，比松弛上界低 279）。差额的原因甲段与本批探测一致：密度顶上去时自由空间碎掉。
  本批试过给松弛模型补单商品流连通性以拿到更紧的健全上界，300 s 内连平凡界都没证下来——
  负结果，如实记录。

---

## 8. 文件与冻结线

| 文件 | 职责 |
|---|---|
| `00_charter.md` | 本文 |
| `derived_theorems.json` | 派生定理登记表的机器可读镜像 |
| `g1_port_semantics.py` | 类表 SSOT：现场推导九行类表与八个 capability bucket |
| `g1_region_model.py` | 25 区域划分、固定家具、reserved 口前格、十个 region class |
| `g1_pattern_schema.py` | 五种 JSON 的严格 schema、canonical 字节与 sha256 |
| `g1_pattern_evaluator.py` | 几何 → capability 的唯一真相源；catalog loader 在此重算 |
| `g1_pattern_generator.py` | 目标驱动的局部 CP-SAT + 签名去重 + 预算闸 + 算术预门 |
| `front_viability_audit.py` | 独立复核器（stdlib-only、可 `-I -S -B`、15 条 issue code） |
| `g1_exact_cover_master.py` | exact-cover master（C1–C5）、空 pattern 合成、供给预门、删除法不可行核 |
| `g1_expand_solution.py` | master 解 → 70×70 几何：类指派、全局杆极小化、provisional 实例、`g1_geometry.json` |
| `run_g1.py` | 六个子命令的编排器；独占 run root + receipt 闭合；G1 五条判定 |
| `CATALOG_REPORT.md` | 甲段交接物：catalog 规模与算术预门结论 |
| `RESULT.md` | 乙段收口：G1 终态、机器证据、升级梯走到哪档 |

**甲段 / 乙段冻结线 = catalog**。`g1_pattern_schema.py` 的五个 schema 常量是冻结面：
乙段可以并列新增 `w0_g1_*_v2`，不得改动任何 `_v1` 字段。

**catalog loader 铁律**：读 catalog 时对每个 pattern 重跑 evaluator、重算签名与不变量；
与文件自报不符 = fail-closed 拒绝整个 catalog（不修正、不警告放行）。

---

## 9. 失败姿势

G1 若 INFEASIBLE / UNKNOWN / SCALE_ABORT / AUDIT_FAIL，停机报告必须逐条写：
① 终态；② 机器证据（assumption core 的具体名字 / 超时的 wall time 与 best bound / 审计 issue code）；
③ 措辞限定——只准写：

> 在**本 catalog**（manifest sha256 …，`complete` 标记 …）、**本类表**（现场从冻结 rules 推导，九行如 §4）、
> **本 hole 词汇**（不跨区的 6×7 / 7×6）与**本限制档位**（登记表中的 `R-*` 组合）下，
> 该 exact-cover 实例不可满足 / 未在 1800s 内返回终态。

禁止外推到 benchmark 不可行，禁止外推到其他限制档位，禁止改任何 ledger。
便宜失败正是门序的价值。
