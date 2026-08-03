# W0 front-aware G1 · 乙段收口（RESULT）

> **性质**：research-only。本文全部数字与判词的 authority 布尔恒 false，`ledger_effect: "none"`。
> **双 ledger**：`U=(1188,18)` 本线不碰；`L=absent`，本批**没有登记任何值**，也没有资格登记。
> **基线**：分支 `w0/front-aware-g1-20260803`，起点 main `0dcb531`。
> 解释器 `.venv-uvbolt-backup/bin/python`（3.13.13），CP-SAT 9.15.6755，workers ≤ 4，同时刻至多一个 solve。

---

## 1. G1 终态

**`INFEASIBLE`**，升级梯走到 **L1**（两轮，见 §4/§5）；**L2–L4 未跑、未被排除**（§6），L5 按开线书不做。

措辞按章程 §9 限定：

> 在**本 catalog**（L0 单份，或 L0 ∪ L1 ∪ L1-dense 三份的并集，digest 记在各自 run root 的
> `config.json`）、**本类表**（现场从冻结 `canonical_rules.json` +
> `mandatory_exact_instances.json` 推导的九行表）、**本 hole 词汇**（不跨区的 6×7 / 7×6）
> 与**本限制档位**（`derived_theorems.json` 登记的 `R-*` 组合）下，该 exact-cover 实例不可满足。

**不外推**：不是 benchmark 不可行，不是其他限制档位不可行，不是关于几何的结论。
G1 的 INFEASIBLE 只能读作"本充分限制族内无解"，不是必要条件的否定（章程 §3 三极纪律）。

一句话判读（三段，缺一段就成了越界）：**当前松弛（3,392 ≥ 3,325）没有排除几何；
现有 catalog 的直接短板是生成密度；连通性下这个限制档位本身装不装得下 3,325，未决。**

限制档位允许的 body 面积上界（无连通性的松弛模型，十个 region class 全部已证 OPTIMAL）
是 3,392 格，需求 3,325 格；而两轮生成后 catalog 能供的最好面积只有 3,113 格。
能确定的是：catalog 与松弛上界之间差 279 格，master 的缺口 212 格落在这 279 格里。
**不能**确定的是这 279 格里有多少是连通性根本不允许的——本批想拿一个连通性感知的健全上界
来分开这两件事，失败了（§3 探测 B：300 s 连平凡界都没证下来）。所以竞争假设
**「这套 `R-*` 限制档位在连通性下面积本来就不够」并未被排除**，而它才是更有后果的那个：
若真是它，G1 的 `INFEASIBLE` 就是关于限制档位的真结论，不是 catalog 薄的记账。

**勘误**：提交 `81e8316` 的标题写「病灶定位到生成器密度」，口径强于证据。
提交标题不可改写，本节是当前口径。

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
| 删除法核 | 21 族试删 21 次求解 1.4 s，**在这 21 族上已证极小** | 21 族 21 次 2.2 s，**在这 21 族上已证极小** |

规模落在开线书要求的"几百~几千 pattern 选择变量的小 CP-SAT"里，不是 prod-scale。

### 2.1 不可行核（删除法，两轮都无 undecided）

**「极小」的准确范围**：极小性是**在 21 个具名 family 上**的——C1 每个 region class 一族、
C2b 每个 class 一族、C2c 总台数、C3 孔洞。C2a（bucket 供给守恒）在 `build_master` 里是
无条件张贴的裸 `model.add`，从不进删除候选，所以 `proved_minimal: true` 不覆盖它。
两轮的核都验了两半：只留核仍不可满足、再放掉核里任何一族就可满足。

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
| **L0** | 甲段冻结 catalog（1,354 签名 + 7 个现场合成的空 pattern = 1,361 列） | `INFEASIBLE`；核 = 九个 cover + 总台数 |
| **L1-a** | 每目标解上限 3 → 20、菜单前 80 名次、5,400 s | 面积上界 3,013 → 3,087；**总台数上界反降到 207** |
| **L1-b** | 菜单按台数筛（`--min-bodies 10`）、5,400 s | 每个 region class 都拿到 10–11 台的合法 pattern |
| **L1 并集** | L0 ∪ L1-a ∪ L1-b，按签名去重 | 总台数闸**破了**（244 ≥ 219）；面积仍短 212 格 → `INFEASIBLE` |
| **L2–L4** | 未跑 | §6：未跑，也未被排除；两条当前列集下的观测不是反事实上界 |
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

## 6. L2–L4：未跑，也未被排除

剩余缺口 **212 格**（扣孔洞代价 231 格）。本批**没有**跑 L2、L3、L4，也**没有**证明它们够不到 212 格。
本节记录的是两条当前列集下的观测，以及为什么它们不能当成反事实上界。

| 档 | 当前列集下的观测 | 这条观测**不是**什么 |
|---|---|---|
| **L2** portal 桩每边 2 格降到 1 格 | 每区多出 4 格 usable × 24 区 = 96 格自由格；要重生成全部 catalog（掩码 sha256 变了）并改甲段的 golden 测试 | **不是**面积增量的上界。packing ceiling 根本不受 usable 约束（CLEAN 146 vs usable 188、边界类 134 vs 171、CORNER 118 vs 158），多 4 格自由格可能解锁一整台 5×5（+25 面积）。而且方向可能相反：portal 桩正是一条自由空间连通性限制，本批诊断出的卡点恰恰是"密度顶上去时自由空间碎掉"——L2 可能是最强的杠杆，不是陪跑项 |
| **L3** negotiated portal | 两轮的极小核里没有出现 seam 族（本档位下 master 就没有 seam 约束），所以当前模型里它加 0 格 | **不是**"反事实增益为零"。L3 改的是 portal / 连通性词汇，换词汇后的 catalog 是另一份 catalog；当前核里没有 seam 族只说明当前模型没有这个词 |
| **L4** 跨缝孔洞 fragment | 当前列集的孔洞代价是 19 格（并集实测 3,113 − 3,094） | **不是**跨缝 hole 新词汇的健全上界。19 是"这份 catalog 里最密 pattern 与最密带孔 pattern 的差"，不是新词汇能回收多少 |

所以停在 L1 的理由不是"算术已经排除了后面三档"，而是本批的预算与授权到此为止：
L2 要重生成全部 catalog，属于另立一批的量级；L5（跨区供电）开线书明写停下交 owner。

有一个量是确定的：**松弛上界 3,392 与实际造得出的 3,113 之间那 279 格**。
甲段 §7 与本批探测 B 一致指向同一个机制——密度顶上去时自由空间碎掉，front 格名义上空着实际够不着；
而连通性在生成模型里很贵（探测 B：加流约束后 300 s 连平凡界都没证下来）。
这 279 格里有多少是连通性根本不允许的、有多少是生成器没找到的，**本批分不开**。

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

---

## 9. 收据勘误与未闭合观测

### 9.1 preflight 收据只覆盖 9 笔提交里的 4 笔

开线书通则要求每笔提交前 full preflight 全绿。实况：

| 提交 | 收据 |
|---|---|
| `67e91cd` / `f3fe328` / `33b532a` / `cfd8fe7` / `53b3cff` | 无正文声明、无日志 |
| `aecbd71` / `3ced133` | 提交正文声明 PASSED（19/19，6772 passed / 170 skipped），无日志 |
| `27fbe46` / `81e8316` | 提交正文写 19/19，并留下 `stage_b/preflight_c1.log` 与 `preflight_c2.log`——但两份**字节相同**（sha256 `f0f21fda…23bef`，同为 6798 passed / 170 skipped、192.87 s）。两份文件只能证明**一次**运行：wall clock 不可能复现到厘秒 |

所以「每笔提交前 full 全绿」这句话在证据上不成立。能说的只有：**当前 HEAD 全量绿有独立复核**
——08-03 三席审查中，codex 对抗席与 opus 质量席各自在独立 worktree 跑过 full preflight。
前五笔无留档收据是可 bisect 性与收据完整性的缺口，不是健全性缺口（`aecbd71` 是那五笔之后的
累积绿灯）。**本文不补写历史。**

**修复批起**每笔提交前在 worktree 内跑一次 full preflight，日志一笔一个文件落
`.artifacts/w0_front_aware_20260803/g1_run/stage_c/`，带真实时间戳、不复制。

### 9.2 「所有证据已闭合」的准确范围

闭合的是**两个 master run root**（`stage_b/L0/`、`stage_b/L1_union/`）：receipt 闭合、
root closure 验过，两位独立审查者也逐字段核过磁盘。以下观测**没有**收据，只活在本文与生成
日志里，按"未闭合观测"读：

- §5.2 探测 C 的那个精确 10 台 CLEAN pattern（3×3 ×7 @L3 + 5×5 ×2 @L2 + 6×4 ×1 @L5）。
  "10 台存在"本身有收据——`L1_dense` catalog 里留着四个合法的 10 台 CLEAN pattern——
  但这个精确组成没有单独存档；
- §3 探测 A（台数松弛上界）与探测 B（连通性感知面积上界，300 s、bound 258）两次探测；
- 甲段 §7 的"每个被承诺的 front 格保留一个自由邻格"加强测。

### 9.3 既有收据里的 `cpsat_version: "unknown"`

`stage_b/{L0,L1_union}/master/master_result.json` 与 `catalog/manifest.json` 记的求解器版本都是
`"unknown"`。成因是两处 `_ortools_version()`（`g1_exact_cover_master.py`、`g1_pattern_generator.py`）
读的是 `cp_model.__version__`——ortools 9.x 的这个属性不存在（版本在 `ortools.__version__`），
而 `getattr` 的默认值把失败吞掉了。所以本文与 `CATALOG_REPORT.md` 里的 "CP-SAT 9.15.6755"
是环境实测，**不由 run root 的任何收据背书**。既有 run root 不重跑，收据保持原样。

### 9.4 worktree 卫生

实施 worktree 有一个有意保留的未跟踪项：`.venv-uvbolt-backup`（指向仓库根同名 venv 的
symlink），preflight 与所有 G1 运行都用它当解释器。除此之外无未跟踪文件、无未提交改动，
`git diff --check` 零告警。

---

## 10. 修复批（2026-08-03，三席审查之后）

G1 没有重跑，终态与所有数字不变。本批做的是四件事：把记账改对、把 fail-open 的门改成
fail-closed、把机器证据搬进 git、把 `.artifacts` 根登记进治理台账。

### 10.1 四笔提交

| 提交 | 内容 | preflight 收据（`.artifacts/w0_front_aware_20260803/g1_run/stage_c/`） |
|---|---|---|
| `26a0cbe` | 生成器冒烟测试的墙钟闸 2 s → 30 s，消掉并发假红 | `preflight_c3_stability_20260803T212945Z.log` |
| `d61acd1` | 记账：端口语义冲突记录、21 号更正文书、L2–L4 改口径、收据勘误（§9） | `preflight_c4_docs_20260803T213246Z.log` |
| `29252c8` | 代码：receipt 第五门 fail-closed、审计自证隔离、generic_io 进管线、预门矛盾断言 | `preflight_c5_failclosed_20260803T214903Z.log` |
| `d0fe0ff` | 证据耐久 + 治理登记 + 本节 | `preflight_c6_evidence_20260803T215915Z.log` |
| 本笔 | 措辞收尾（本表补全 + 章程 §5 一处措辞） | `preflight_c7_wording_20260803T220347Z.log` |

每笔提交前在 worktree 内跑一次 `preflight_gate.py --full`，日志一笔一个文件、真实时间戳、
不复制（§9.1 的缺口从本批起不再产生）。

### 10.2 门判定的三处实质变化

1. **第五条（run receipt）从 fail-open 变 fail-closed。** run root 的 manifest 改为
   「这次运行写了什么」，不再是「枚举目录看到什么」——枚举出来的 manifest 会把闯入的文件
   一起收编，对它做闭合检查永远失败不了。现在闭合检查先于 receipt 写出，写完再验一次，
   后一次失败就删掉刚写的 receipt。**闭合失败留不下 receipt，也留不下 PASS。**
   两条端到端回归复现了 08-03 对抗审查的故障注入场景。
2. **第四条（审计隔离）改为消费子进程的自证。** `front_viability_audit.py` 的报告新增
   `environment` 块（`ortools_importable` / 解释器 flags / `sys.path` / 已加载的 `g1_*`
   与 `src.*` 模块），门读它，而不是读自己九行前构造的 argv（那在生产路径上恒真）。
3. **预门与 master 的矛盾会被抬起来。** `pre_gate` 判 `SHORT`（无求解器地证明这份 catalog
   盖不住普查）而 master 却给出解，说明两者之一错了——现在是第一条 fail 并具名，
   不再是两份文件并排躺在 run root 里。

另外 `run_g1.py` 开始消费 `data/preprocessed/generic_io_requirements.json`：
required 52 output slots / 2 input slots 对固定家具的 52 / 14，覆盖不成立就 fail-closed，
sha256 绑进 `config.json` 与 receipt。

### 10.3 机器证据进 git

两个 master run root 的 12 个小文件（`{config,gate,receipt}.json` +
`master/{pre_gate,master_result}.json` + `master/cpsat.log`，共 47 KB）**字节原样**拷进
`evidence/`，来源路径与逐文件 sha256 见 `evidence/README.md`。
`.artifacts/` 里的原件一个字节没动（它们的 root closure 经不起任何改动）。
catalog（约 9 MB）不进 git，它的 per-file sha256 记在两个 `config.json` 里。

### 10.4 治理登记与它的后果

`.artifacts/w0_front_aware_20260803/` 已按 `data/repository_governance/README.md` 的步骤
登记进 `code_assets.json` 的 `read_only_historical_evidence_roots`（`research_evidence` /
`non_code_asset` / `read_only_preserve_in_place`）。同时把 `expected_current_class_counts`
更新到本分支实况（本线新增 10 个测试模块 + 9 个研究模块 = test 655 / historical_evidence 455），
live checker 因此从「计数漂移」变成 PASS——那个漂移是甲/乙段就带上的，不是本批引入的。

**后果，下一批必须知道**：治理 README 明写「不得往已登记的根里追加」。W0 线的下一批
（L2 / G2）要另开一个新的顶层 `.artifacts/<root>/`，不能继续写进
`.artifacts/w0_front_aware_20260803/`。

### 10.5 本批没做的三件事

- **19 号文书的反向指针没加。** 本批允许改动面里只有新建 21 号，19 号本体一个字节未改；
  从 19 号指向 21 号的那半句留给有权改它的批次。指针目前由 21 号与章程 §4 单向承担。
- **`evaluate_pattern` 的 distinct-representatives 检查没加。** 跨 body front 共享的
  合法性论证与「同时性未证」义务已登记（章程 §5 的 `O-FRONT-SIMULTANEITY`），
  按义务写明在 G1 转绿前必须二选一补上。本批选了登记，不选改判据——改判据会动 catalog
  的准入语义，那是重跑 G1 的量级。
- **L2 与任何 G1 重跑。** 按修复批任务书不做，等 owner 知悉本批结论后另立批。
