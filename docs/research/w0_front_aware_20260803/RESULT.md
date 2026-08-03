# W0 front-aware G1 · 乙段收口（RESULT）

> **性质**：research-only。本文全部数字与判词的 authority 布尔恒 false，`ledger_effect: "none"`。
> **双 ledger**：`U=(1188,18)` 本线不碰；`L=absent`，本批**没有登记任何值**，也没有资格登记。
> **基线**：分支 `w0/front-aware-g1-20260803`，起点 main `0dcb531`。
> 解释器 `.venv-uvbolt-backup/bin/python`（3.13.13），CP-SAT 9.15.6755，workers ≤ 4，同时刻至多一个 solve。

---

## 1. G1 终态

**`INFEASIBLE`**，升级梯走到 **L1**（两轮，见 §4/§5）；L2–L4 按 §6 的算术被排除，L5 按开线书不做。

措辞按章程 §9 限定：

> 在**本 catalog**（L0 单份，或 L0 ∪ L1 ∪ L1-dense 三份的并集，digest 记在各自 run root 的
> `config.json`）、**本类表**（现场从冻结 `canonical_rules.json` +
> `mandatory_exact_instances.json` 推导的九行表）、**本 hole 词汇**（不跨区的 6×7 / 7×6）
> 与**本限制档位**（`derived_theorems.json` 登记的 `R-*` 组合）下，该 exact-cover 实例不可满足。

**不外推**：不是 benchmark 不可行，不是其他限制档位不可行，不是关于几何的结论。
G1 的 INFEASIBLE 只能读作"本充分限制族内无解"，不是必要条件的否定（章程 §3 三极纪律）。

一句话说清病灶：**卡的不是几何允许多少，是生成器实际造得出多少。**
限制档位允许的（松弛、已证 OPTIMAL）body 面积上界是 3,392 格，需求 3,325 格；
而两轮生成后 catalog 能供的最好面积只有 3,113 格。缺口 212 格全部落在
"松弛上界"与"真造得出来的合法 pattern"之间的那 279 格里。

---

## 2. 两轮的机器证据

两个运行根都在
`/home/zhuran24/zmd-pj/.artifacts/w0_front_aware_20260803/g1_run/stage_b/`，
各含 `config.json` / `master/pre_gate.json` / `master/master_result.json` /
`master/cpsat.log` / `gate.json` / `receipt.json`，receipt 闭合、root closure 验过。

| | **L0**（`stage_b/L0/`） | **L1 并集**（`stage_b/L1_union/`） |
|---|---|---|
| catalog | 甲段冻结 catalog | L0 ∪ L1 ∪ L1-dense，按签名去重 |
| pattern 列 | 1,361 | 1,674 |
| master 规模 | 1,378 变量 / 29 约束 | 1,691 变量 / 29 约束 |
| master | `INFEASIBLE`，0.20 s | `INFEASIBLE`，0.28 s |
| 规模闸 | 未触发（20,000 / 200,000） | 未触发 |
| 删除法核 | 21 族试删 21 次求解 1.4 s，**已证极小** | 21 族 21 次 2.2 s，**已证极小** |

规模落在开线书要求的"几百~几千 pattern 选择变量的小 CP-SAT"里，不是 prod-scale。

### 2.1 不可行核（删除法，两轮都已证极小、无 undecided）

**L0**：

```
assume_cover[BOTTOM_I1..I4]   assume_cover[CLEAN]   assume_cover[CORNER]
assume_cover[LEFT_J1..J3]     assume_total_bodies
```

读法：**九个非 CORE region class 各自"恰选一个 pattern"，加上"全图恰 219 台机器"，
这十条合起来就已经不可满足。** 与 class 需求无关、与孔洞无关——两者删掉后模型仍不可满足，
所以不在核里。`assume_cover[CORE]` 也不在核里：CORE 区域怎么选都贡献 0 台机器。

**L1 并集**：同样十条，**外加** `assume_class[5L]`、`assume_class[6I3]`、`assume_class[6I5]`。

核从"凑不出 219 台"移到了"凑得出 219 台，但凑不出其中的 5×5 与 6×4 那一份"——
这正是 §2.2 面积口径预测的形态：新加的密集 pattern 几乎全是 3×3 堆出来的。

不用 CP-SAT 自带的 assumption 核，因为实测同一模型的 enforcement-literal 形态
**300 s UNKNOWN**，而普通形态 **0.2 s INFEASIBLE**——证书不该比答案还贵。
删除法每族一次廉价求解，返回的是真正的极小不可满足子集
（`src/tests/test_w0_g1_master.py` 把"只留核仍不可满足"和"再放掉核里任何一族就可满足"
两半都验了）。

### 2.2 同一结论的第二条独立路径：无求解器的供给预门

`master/pre_gate.json` 的 `T-SUPPLY-CEILING`（每个 region class 各自独立取最好的 pattern
再乘区域数，**故意高估**；只有 ceiling < demand 才是结论）：

| 口径 | 需求 | L0 供给上界 | L1 并集供给上界 |
|---|---|---|---|
| **body 面积** | **3,325** | **3,013 · SHORT** | **3,113 · SHORT** |
| **body 面积（扣孔洞代价）** | **3,325** | **2,996 · SHORT** | **3,094 · SHORT** |
| 总台数 | 219 | **210 · SHORT** | 244 · 不排除 |
| 3×3 族 | 132 | 168 | 209 |
| 5×5 族 | 49 | 88 | 88 |
| 6×4 族 | 38 | 72 | 72 |
| 九个 class 逐条 | 3–109 | 72–225 | 72–284 |

"扣孔洞代价"行：全图恰有一个区域要背 6×7 孔洞，而任一 region class 带孔洞的 pattern
不可能比它最密的 pattern 更密（孔洞就是 42 格 body-free）。所以整板至少让出
`min over class (最密 − 最密带孔洞)` 那么多格——L0 是 17 格，并集是 19 格。

**两条路径在两轮里都独立到达同一处**：求解器的极小核与无求解器的算术上界指的是同一件事。
L0 是"总台数不够"，L1 并集是"面积不够、且短缺集中在大模板上"。

---

## 3. 余量有多小（为什么这不是"多跑一会儿就好"）

甲段用无连通性的松弛模型给每个 region class 证了 packing ceiling（十个全 OPTIMAL）：

```
松弛面积上界 = 16×146 + 7×134 + 118 + 0(CORE) = 3392
需求                                          = 3325
slack                                         =   67 格 = 2%
```

本批另跑了三次探测，负结果同样记在这里：

**探测 A（台数松弛上界，catalog 无关）**：把甲段的 ceiling 模型从"最大化面积"改成
"最大化台数"，十个 region class 全部 OPTIMAL：CLEAN 16 台、七个边界类各 14 台、
CORNER 12 台、CORE 0 台，合计 **366 ≥ 219**。所以**台数本身不构成对本限制档位的排除**——
L0 的 210 是 catalog 的性质，不是几何的性质。这是决定去走 L1 的依据，后来也被 L1 证实。

**探测 B（连通性感知的健全面积上界）**：给松弛模型补一组 `inc` 布尔（"这格属于 portal 连通
分量"）+ 单商品流连通性，并把 capability 约束从"这侧留够空 front 格"改成
"这侧留够**在分量里的** front 格"。这仍是健全上界（真 pattern 取 `inc :=` 真分量即满足全部约束）。
CLEAN 上跑 300 s：**best 122、bound 258、FEASIBLE**——上界比平凡上界（usable = 188）还松，
**一点没收紧**。流编码把模型变得太难。结论：连通性感知的紧上界要另想办法，
不是加一个流约束就能拿到的；这条路本批放弃，如实记录。

**探测 C（密集 pattern 存在性）**：见 §5.2，正结果。

（甲段试过的另一条加强——"每个被承诺的 front 格保留一个自由邻格"——十个 class 的 ceiling
一格没降，见 `CATALOG_REPORT.md`。本地度数条件不 binding，这与探测 B 的失败一致：
真正杀死密度的是全局连通性，而全局连通性不便宜。）

---

## 4. 升级梯走到哪档

蓝图 §12.2 的梯子：L0 如设计 → L1 扩 catalog → L2 调 portal 桩 → L3 negotiated portal
→ L4 跨缝 hole fragment → L5 跨区供电（**本批不做，停下交 owner**）。

| 档 | 做了什么 | 结果 |
|---|---|---|
| **L0** | 甲段冻结 catalog（1,354 签名 + 10 个合成空 pattern） | `INFEASIBLE`；核 = 九个 cover + 总台数 |
| **L1-a** | 每目标解上限 3 → 20、菜单前 80 名次、5,400 s | 面积上界 3,013 → 3,087；**总台数上界反降到 207** |
| **L1-b** | 菜单按台数筛（`--min-bodies 10`）、5,400 s | 每个 region class 都拿到 10–11 台的合法 pattern |
| **L1 并集** | L0 ∪ L1-a ∪ L1-b，按签名去重 | 总台数闸**破了**（244 ≥ 219）；面积仍短 212 格 → `INFEASIBLE` |
| **L2–L4** | 未跑 | §6：三档合起来也够不到 212 格，理由是算术不是疲劳 |
| **L5** | 未跑 | 开线书写明"停下交 owner" |

---

## 5. L1 详情

### 5.1 L1-a：更深不等于更好

配置：`--budget-seconds 5400 --target-seconds 2 --solutions-per-target 20 --max-targets 80`。
产物 `stage_b/L1_catalog/`。实测每个 region class 只跑完菜单前 **25** 个名次
（20 个解 × 每解一次求解 ≈ 16 s/目标，预算被深度吃掉）。

结果两面：CLEAN 最好面积 128 → **134**（追平甲段 A/B 里见过的最好值），
但**最密仍是 9 台**，而且 CLEAN 一个带孔洞的 pattern 都没产出——
孔洞在菜单排序里加 0.5 分，前 25 名次里根本轮不到。单独拿 L1-a 去跑 master
比 L0 更差（总台数上界 207）。**这就是并集存在的理由**：不同瞄准的生成轮次是互补的，
不是替代的，所以 loader 支持按签名并集（`load_catalogs` 收多个目录，首个目录优先）。

### 5.2 探测 C：9 台不是几何墙，是菜单排序的产物

219 台机器摊到 24 个可用区域是 **9.125 台/区**，而两份 catalog 里最密的 pattern 都是 9 台。
差一点点，值得单独问一句：**存在 10 台的合法 CLEAN pattern 吗？**

直接驱动生成器自己的按目标模型，只跑 CLEAN 里 body_total ≥ 10 的目标
（258 个，跑了 56 个，1,048 s，每目标 30 个解 × 5 s）：

```
new best valid: 10 bodies
  target = 3x3 ×7 (level 3) + 5x5 ×2 (level 2) + 6x4 ×1 (level 5), hole=False
```

**存在。** 9 台的上限是 `H-TARGET-MENU` 的**排序**产物：菜单按"到该区域普查比例份额的距离"
排序，10 台以上的目标排在几百名开外，两轮预算都没走到那里。

处置（本批落地）：给 `build_target_menu` 加 `min_bodies` 过滤器——**过滤而不是重排**，
登记的排序启发式原样保留，瞄准的那一轮成为一个可命名的独立 pass。

### 5.3 L1-b：瞄准密集端

配置：`--min-bodies 10 --budget-seconds 5400 --target-seconds 5 --solutions-per-target 8`。
产物 `stage_b/L1_dense/`。每个 region class 都拿到了 10–11 台的合法 pattern
（CLEAN 10、BOTTOM_I2/LEFT_J2/LEFT_J3/CORNER 11、其余 10），CORE 仍然 0——与甲段的结论一致。

代价也很清楚：这些密集 pattern 的**面积**偏低（CLEAN 最好 122，低于 L1-a 的 134），
因为凑台数最省地方的办法就是多摆 3×3。孔洞 pattern 一个没有（10 台 + 42 格孔洞装不下）。

### 5.4 并集的判读

并集 1,674 列。总台数上界 210 → **244**，闸破了；面积上界 3,013 → **3,113**，仍短 212 格
（扣孔洞代价后短 231 格）。master 的极小核相应地从"凑不出 219 台"移到
"凑得出 219 台，但凑不出 5L / 6I3 / 6I5 那一份"。

**这是本批最有信息量的一步**：它把"catalog 薄"这个笼统说法拆成了两个可分别测量的量，
并且证明了第一个量可以用瞄准解决、第二个量不能。

---

## 6. 为什么不继续走 L2–L4

剩余缺口 **212 格**（扣孔洞代价 231 格）。三档能贡献的上限逐条算：

| 档 | 它能加多少 body 面积 | 够不够 212 |
|---|---|---|
| **L2** portal 桩每边 2 格降到 1 格 | 每区多 4 格 usable × 24 区 = **≤ 96 格**，且要重生成全部 catalog（掩码 sha256 变了）并改甲段的 golden 测试 | 不够 |
| **L3** negotiated portal | **0 格**——它只谈缝的相容性，而两轮的极小核里根本没有 seam 族（本档位下 master 就没有 seam 约束） | 不够 |
| **L4** 跨缝孔洞 fragment | 至多把孔洞代价摊掉，即 **19 格**（并集实测 3,113 − 3,094） | 不够 |
| L2+L3+L4 全上 | ≤ 115 格 | **仍不够** |

所以停在 L1 不是预算耗尽，是**这三档瞄的不是那个量**。真正的量是
"松弛上界 3,392 与实际造得出的 3,113 之间那 279 格"，而甲段 §7 与本批探测 B 一致指向
同一个原因：**密度顶上去时自由空间碎掉，front 格名义上空着实际够不着**，
而连通性在生成模型里很贵（探测 B：加流约束后 300 s 连平凡界都没证下来）。

**交给下一批 / owner 的下一步**（本批不做、也不擅自开工）：
把自由空间分量条件搬进生成模型（需要一个比单商品流便宜的编码），
或者松掉某条 `R-*` 充分限制并重走三极性登记与预门。
L5（跨区供电）按开线书明写停下交 owner。

---

## 7. 本批落地的东西

| 东西 | 路径 |
|---|---|
| exact-cover master（C1–C5、空 pattern、供给预门、删除法核、多目录并集） | `docs/research/w0_front_aware_20260803/g1_exact_cover_master.py` |
| 几何展开（类指派、全局杆极小化、provisional 实例） | `docs/research/w0_front_aware_20260803/g1_expand_solution.py` |
| 运行编排（六子命令、独占 run root、G1 五条判定） | `docs/research/w0_front_aware_20260803/run_g1.py` |
| 菜单台数过滤器 `min_bodies` | `g1_pattern_generator.build_target_menu` |
| 测试 | `src/tests/test_w0_g1_master.py`、`test_w0_g1_expand.py`、`test_w0_g1_gate.py` |
| L0 运行根 | `.artifacts/w0_front_aware_20260803/g1_run/stage_b/L0/` |
| L1 并集运行根 | `.artifacts/w0_front_aware_20260803/g1_run/stage_b/L1_union/` |
| L1-a / L1-b catalog | `.artifacts/.../stage_b/L1_catalog/`、`.../L1_dense/` |
| preflight 日志 | `.artifacts/.../stage_b/preflight_*.log` |

新登记的派生定理（章程 §5 与 `derived_theorems.json` 同步）：
`T-EMPTY-PATTERN`（词汇完备性）、`T-SUPPLY-CEILING`（算术上界，无求解器，跑在 master 之前）。

---

## 8. 本批没有做、也不该被读成做了的事

- **没有登记下界**。`L` 仍是 absent。G1 就算过了也不登记（章程 §2 写死）；本批连过都没过。
- **没有碰上界账**。`U=(1188,18)` 一个字节没动。
- **没有证明 benchmark 不可行**，也没有证明这个限制档位在几何上不可行——
  §1 与 §3 的措辞限定是硬的：被证明的是"这两份 catalog 盖不住普查"。
- **没有碰 certified 面**。改动只落在 `docs/research/w0_front_aware_20260803/` 与 `src/tests/`；
  `src/`（非 tests）、`scripts/preflight_gate.py`、两个 checker、`PROJECT_LOCK.md`、
  `.artifacts/ab16_*`、r3–r6 root 零触碰。
- **没有 skip / xfail**。`src/tests/test_w0_g1_charter_contract.py` 用 AST 把这条钉死。
