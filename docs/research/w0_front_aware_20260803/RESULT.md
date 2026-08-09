# W0 front-aware G1 · 乙段收口（RESULT）

> **性质**：research-only。本文全部数字与判词的 authority 布尔恒 false，`ledger_effect: "none"`。
> **双 ledger**：`U=(1188,18)` 本线不碰；`L=absent`，本批**没有登记任何值**，也没有资格登记。
> **基线**：分支 `w0/front-aware-g1-20260803`，起点 main `0dcb531`。
> 解释器 `.venv-uvbolt-backup/bin/python`（3.13.13），CP-SAT 9.15.6755，workers ≤ 4，同时刻至多一个 solve。
> **文档分区**：§1–§9 是 08-03 乙段收口的记录，§10 是 08-03 修复批，§11 是 08-04
> fix-and-rerun 批（strict 语义收敛后的全量重跑，终态止损）。**§1–§9 的一切列数、
> 面积数、缺口数都是 loose 连通读法下的 08-03 快照**，当前口径见 §11.3；
> G1 终态两轮与本批一致（`INFEASIBLE`），没有被改写过。

---

## 1. G1 终态（08-03 两轮；strict 重跑后的当前口径见 §11）

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

> **口径注（2026-08-04 复核）**：本表全部列数/面积数按 evaluator 的 **loose 连通读法**
> （多源 BFS 并集）统计；按 charter 登记的 strict 同分量语义过滤后 L0 1,354 → 877 签名、
> L1 并集 1,672 → 1,084 签名，面积缺口 212 → 576 格（均为本表 catalog 口径，非
> pattern 空间健全缺口）。strict 过滤只删列，两轮 `INFEASIBLE` 不受影响。详见 `CONSULT_VERDICT_20260804.md` 与 00_charter.md §6 勘误注。

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
并且证明了第一个量（总台数）可以用瞄准解决。第二个量（面积）**本轮协议没有解决**——
L1-a 每族只跑完菜单前 25 个名次（§5.1，预算被深度吃掉），面积预门在这种受限搜索下仍
判 SHORT。这是**受限搜索的读数**，不是"面积量不能用瞄准解决"的结论
（2026-08-04 复核订正：初版把受限搜索写成了决断性结论）。

---

## 6. L2–L4：未跑，也未被排除

剩余缺口 **212 格**（扣孔洞代价 231 格）。本批**没有**跑 L2、L3、L4，也**没有**证明它们够不到 212 格。
本节记录的是两条当前列集下的观测，以及为什么它们不能当成反事实上界。

| 档 | 当前列集下的观测 | 这条观测**不是**什么 |
|---|---|---|
| **L2** portal 桩每边 2 格降到 1 格 | 每区多出 4 格 usable × 24 区 = 96 格自由格；要重生成全部 catalog（掩码 sha256 变了）并改甲段的 golden 测试 | **不是**面积增量的上界。packing ceiling 根本不受 usable 约束（CLEAN 146 vs usable 188、边界类 134 vs 171、CORNER 118 vs 158），多 4 格自由格可能解锁一整台 5×5（+25 面积）。而且方向可能相反：portal 桩正是一条自由空间连通性限制，本批诊断出的卡点恰恰是"密度顶上去时自由空间碎掉"——L2 可能是最强的杠杆，不是陪跑项 |
| **L3** negotiated portal | 两轮的极小核里没有出现 seam 族（本档位下 master 就没有 seam 约束），所以当前模型里它加 0 格 | **不是**"反事实增益为零"。L3 改的是 portal / 连通性词汇，换词汇后的 catalog 是另一份 catalog；当前核里没有 seam 族只说明当前模型没有这个词 |
| **L4** 跨缝孔洞 fragment | 当前列集的孔洞代价是 19 格（并集实测 3,113 − 3,094） | **不是**跨缝 hole 新词汇的健全上界。19 是"这份 catalog 里最密 pattern 与最密带孔 pattern 的差"，不是新词汇能回收多少 |

所以停在 L1 不是任何算术判定的结果——L2–L4 未跑、未被排除；停下只因本批的预算与授权到此为止：
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
——08-03 三席审查中，codex 对抗席在独立 worktree 跑出 full preflight 19/19 全绿；opus 质量席在独立 worktree 跑的快 lane 有 1 处失败、经其在基线 `0dcb531` 上复现判为预先存在（非本线回归）。
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

### 10.1 五笔提交

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

---

## 11. fix-and-rerun 批（2026-08-04）：strict 语义收敛 + 全量重跑，终态 **止损**

任务书 `.artifacts/w0_fixrerun_20260804/opening_brief.md`（v2.1）。分支
`w0/fixrerun-20260804`，起点 main `cf13b3c`。做的事：把 §4 口径注里那条「实现是 loose、
登记是 strict」的欠账修掉，把连通性从后置过滤搬进生成模型，修 `:431` 的带孔预算错口径，
把 `O-FRONT-SIMULTANEITY` 做成 G1 PASS 的 fail-closed 前置，然后按旧协议全量重生成
catalog 并重跑 master。

**终态**：任务书 §0 四分里的 **止损**——strict 语义直产的 catalog 供给 2,544 < 3,325，
预门在 master 之前就判 SHORT，master 重跑仍 `INFEASIBLE`。止损的含义与不含义见 §11.6。

### 11.1 七步执行记录（九笔提交）

| # | 提交 | 内容 | preflight 收据（`.artifacts/w0_fixrerun_20260804/`） |
|---|---|---|---|
| 1 | `4497e05` | 步骤 1：`R-PAT-CONN` 实现收敛到登记的 strict 语义（单根分量）——evaluator 的 `portal_component` 从多源 BFS 并集改为单源、anchor 判据随之收紧；charter 与 `derived_theorems.json` 同步 | `preflight_c1_evaluator_strict.log` |
| 2 | `3fd3f98` | 步骤 2：带孔 target 预算判据改**动态 maxK**（`hole_forced_free_credit`），不再按 42 硬扣 | `preflight_c2_hole_budget_maxk.log` |
| 3 | `682d337` | 步骤 3：连通性内聚进生成器 CP-SAT（单源流证书，根 = `min(live_stubs)`，与 evaluator 的 `component_root` 同规则），剥落路径废除 | `preflight_c3_inmodel_connectivity.log` |
| 4 | `8a039ed` | 步骤 5：`O-FRONT-SIMULTANEITY` 关闭检查 + gate 第六条 clause，且它是 `_terminal_state` 的硬前置（义务未关时终态只能是 `OBLIGATION_OPEN`，拼不出 PASS） | `preflight_c4_obligation_failclosed.log` |
| 5 | `523dcd8` | 复核修复：义务登记表单次读取，摘要与解析同源同字节 | `preflight_c5_registry_single_read.log` |
| 6 | `76c8c14` | 复核修复：补真正的离走廊孔洞 fixture（`R-PAT-CONN` + `R-HOLE-IN-REGION` 双违例） | `preflight_c6_off_corridor_hole_fixture.log` |
| 7 | `ec3cdd6` | 复核修复：in-model 筛除量改**配对 loose 对照解**，`corridor_tax` 降级为 fail-closed 不变量 | `preflight_c7_inmodel_paired_control.log` |
| 8 | `abc41f2` | 复核修复：`NO_POSE` / `NO_HOLE_POSE` 从 `targets_unproved` 拆出 | `preflight_c8_no_candidate_split.log` |
| 9 | `af51fdf` | 文档精度：对照解计入共享 admission clock 显式化、`NO_HOLE_POSE` 注释改「未运行 solver」 | `preflight_c9_doc_precision.log` |

表里九笔覆盖任务书的步骤 1/2/3/5 与复核修复；**步骤 4（catalog 全量重生成）与步骤 6
（master 重跑）是运行不是提交**，收据在 §11.2 与 §11.4；步骤 7（文书收尾）= 本章 +
`PROBE_REPORT.md` §四 + `CONSULT_VERDICT_20260804.md` §三勘误注 +
`STOPLOSS_CHECKPOINT_20260804.md`。

九份收据各是一次独立运行（staged 范围，结果 `PASSED`，pytest 1,544 passed；真实时间戳，
不复制）。**措辞订正（08-04 复核）**：初版写「18 项检查全 OK」不字面成立——日志按
`[n/18]` 编号（18 是声明的总项数），实际打印 15 个编号段、20 条 `OK`；能报告的是
overall `PASSED`。首轮四笔经 codex 复核
**BLOCK**（1 high 3 low），修复轮四笔经复验 **PASS_WITH_NOTES**，low-3 由主线自修。
g1 全套 407 passed（`g1_suite_after_fixes.log`，复验席独立重跑同绿）。
`--full` 两次是 **BLOCKED**，唯一阻塞项是既存的 r4 fixture 环境态（18 errors，全部
`test_r4_external_brain_handoff_v1.py`；本批前基线同红、base-vs-head 字节同），
记在 §11.7 欠账 3，不记本批账。

**步骤 2 的动态 maxK 实测值**（`hole_forced_free_credit`，本批运行口径 `spine=false`）：
CLEAN 2、边界七族与 CORNER 各 4、CORE 0；同函数在 `spine=true` 下给 13–16，
所以它必须是算出来的、不能写常量。

**步骤 3 的形态选择**：单源流，根取 `min(live_stubs)`。移植探测臂建模时**没有**照抄
loose 臂的多源 flow——多源等于把并集语义原样搬进模型，那样重跑等于白跑。

### 11.2 三跑协议（参数逐一复原自旧三份 manifest 的 `config` 块）

| | L0 | L1a | L1b |
|---|---|---|---|
| `budget_seconds` | 5,400 | 5,400 | 5,400 |
| `target_seconds` | 2.0 | 2.0 | 5.0 |
| `solutions_per_target` | 3 | 20 | 8 |
| `max_targets` | 无 | 80 | 无 |
| `min_bodies` | 1 | 1 | 10 |
| 实测 wall | 5,401.0 s | 2,315.9 s | 5,403.9 s |

三跑共用：`workers=4`、`seed=0`、`spine=false`、`ceiling_seconds=30`、
`max_derived_subsets=3`、十族全跑。串行，每时刻至多一个 solve。
冻结输入：`rules/canonical_rules.json`（17,510 B，`5012845367e2…`）、
`data/preprocessed/mandatory_exact_instances.json`（88,261 B，`545b98c2b4f9…`）。
求解器 9.15.6755 / Python 3.13.13——**新 run root 记的是真实版本号**，
§9.3 记的 `cpsat_version: "unknown"` 缺陷在本批产物上不复现。

产物：`.artifacts/w0_fixrerun_20260804/regen/{L0,L1a,L1b}/catalog/`，
并集 **760 签名**（逐族 78/85/85/85/46/0/109/101/69/102），master 收 **770 列**
（每族另加一条现场合成的空 pattern）。

### 11.3 供给账：strict 直产 vs 旧 loose（逐族最好 body 面积，单位格）

同一把尺子先量旧并集验刻度：旧 loose 三份 catalog 复算得 3,113 / 1,672 签名 /
最小孔损 19@BOTTOM_I3——与台账逐字一致，量具可信。

| 区域族 | 区数 | 旧 loose best（08-03） | **新 strict best（08-04）** | 旧 loose 带孔 best | 新 strict 带孔 best |
|---|---|---|---|---|---|
| BOTTOM_I1 | 1 | 126 | **117** | 100 | 86 |
| BOTTOM_I2 | 1 | 119 | **117** | 95 | 92 |
| BOTTOM_I3 | 1 | 119 | **117** | 100 | 86 |
| BOTTOM_I4 | 1 | 125 | **111** | 100 | 91 |
| CLEAN | 16 | 134 | **103** | 104 | 86 |
| CORNER | 1 | 110 | **107** | 85 | 83 |
| LEFT_J1 | 1 | 125 | **108** | 100 | 92 |
| LEFT_J2 | 1 | 125 | **110** | 101 | 85 |
| LEFT_J3 | 1 | 120 | **109** | 95 | 86 |
| CORE | 1 | 0 | 0 | — | — |
| **无孔基线合计** | | **3,113** | **2,544** | | |
| **计最小孔损后** | | 3,094（−19@BOTTOM_I3） | **2,528**（−16@LEFT_J1） | | |
| **对 3,325 的缺口** | | 212 | **781** | | |

对照口径三条，别混：旧 **loose** 直产 3,113（缺 212）；旧 catalog 事后按 strict 重滤
2,749（缺 576；`PROBE_REPORT.md` §一 量化锚与 `CONSULT_VERDICT_20260804.md` §六）；
本批 strict **直产** 2,544（缺 781）。
重滤只删列，直产是换了模型重新找——两者不是同一个量，直产更低不等于实现变差
（判读见 §11.6）。

台数账：strict 并集的 **count supply ceiling 241 ≥ 需求 219**（计最小孔损 2@CORNER 后
239）——**ceiling 高于需求 20，count 预门不触发**。这个 20 不是 class-feasible master
的余量：ceiling 逐族独立取最好 pattern 相乘，故意高估，只有 ceiling < demand 才是结论。

真正短的是面积与 **M6 模板供给 34 < 需求 38**（`master/pre_gate.json` 的
`__template:M6__`，合并的是 6I3 + 6I4 + 6I5 的总需求 32+3+3）。它与 master 不可行核里
那条 `assume_class[6I3]` 是**两个相关但不等同的 6×4 供给信号**（08-04 复核订正，初版写
「同一件事」）：同一份 pre_gate 里 6I3 单类 ceiling 63 ≥ 需求 32、并不 short；而删除核
只留 6I3，表达的是「九个 cover + 总台数 + 6I3」这一组充分矛盾，不是预门那条合并短缺。

### 11.4 master 收据（run root `.artifacts/w0_fixrerun_20260804/regen/gate_union/`）

- 无求解器预门 `T-SUPPLY-CEILING`：`SHORT`，三条短缺 `__body_area__` 2,544、
  `__body_area_with_hole__` 2,528、`__template:M6__` 34（需求 38）。
- master：`INFEASIBLE`，solver wall 0.123 s、deterministic 0.271 s、1,472 branches；
  规模 787 变量 / 29 约束 / 770 列。
- 不可行核（删除法，21 族 21 次求解 0.953 s，`proved_minimal: true`，无 undecided）：
  九个非 CORE 的 `assume_cover[*]` + `assume_total_bodies` + **`assume_class[6I3]`**。
  与 08-03 的 L1 并集核相比，`assume_class[5L]`、`assume_class[6I5]` 退出、`6I3` 留下。
- gate：`verdict: NOT_PASSED`、`terminal_state: INFEASIBLE`；第五条 receipt 闭合
  `ok: true`（写 receipt 前后各验一次）；第六条 `ok: false`——`O-FRONT-SIMULTANEITY`
  保持未 discharge，理由是 `"no geometry: the master produced nothing to check"`。
  **这是 fail-closed 的正确形态**：master 没产出几何，义务就没有可核对的对象，
  于是它开着；开着的义务使 PASS 结构上不可达。义务登记表 sha256 `b6c449c4…` 进 gate
  与 receipt。

### 11.5 报警计量三表（任务书步骤 4 的三个语义各不相同的表）

**表①·in-model 筛除量 = 配对 loose 对照解**（旧的 `corridor_tax` 计量已废：它在 accept
路径上按构造恒零，是 fail-soft 零）。做法：每个被 strict **证明**不可行的 target，用同
预算、同模型、只把连通性换回 loose 读法再解一次。

| 跑 | strict 证死 target | 其中 loose 也证死 | **loose 可解（= 连通税）** | loose 未判 | 对照解耗时 |
|---|---|---|---|---|---|
| L0 | 417 | 402 | **0** | 15 | 260.6 s |
| L1a | 119 | 119 | **0** | 0 | 60.7 s |
| L1b | 626 | 569 | **0** | 57 | 580.7 s |

**「loose 可解」一栏三跑全零**（08-04 复核重写；初版把 72 个 loose 未判并进了否定结论，
是「UNKNOWN 当否定」的复发）。逐项能说的：

- **loose 可解 = 0**（417+119+626 = 1,162 个 strict 证死 target 里一个都没有）；
- **loose 也证死 = 1,090**（402+119+569）——只对这 1,090 个能排除「strict 连通性是
  **唯一**死因」；
- **loose 未判 = 72**（L0 15 + L1b 57；L1b 逐族 I1 8 / I2 10 / I3 5 / I4 7 / J1 8 /
  J2 9 / J3 7，CLEAN 0、CORNER 3）。manifest 自己写明 `loose_unproved` 「says nothing」，
  这 72 个既不能记进连通税、也不能记进「连通税为零」。

所以本批的准确口径是：**当前没有坐实的连通性独杀案例，但「连通税严格为零」未证**。
另注：「loose 也证死」只排除唯一死因，**不构成**对死因是「面积/装载」的积极鉴定——
本批没有做死因归属实验，初版那句「死因全是面积/装载」一并撤回。

**表②·postcheck divergence**：三跑十族 30 个格子全 **0**。它是「solver 产出的 spec 被
evaluator 拒绝」的分歧计数，strict 内聚正确时应恒 0；非零会当场 `GeneratorBlocked`，
所以落盘的 catalog 必然带 0——这条要读成「没有反证」，不是「已证等价」。

**表③·retired path 状态**：`strip_dead_bodies`、`post_filter_connectivity_reject`、
`corridor_tax_meter` 三条路径 2026-08-04 **显式废除**（manifest 的 `retired_paths` 逐条
写明废除理由），不是静默留一个 0 冒充「没发生」。

**预算截断的量**（同一份 manifest 的 `target_status_counts`）：L0 未判 1,260、L1a 465、
L1b 788；`targets_no_candidate` 54/54/0（CORE 的 `NO_POSE`，已从未判里拆出）。
其中 L0 的 CLEAN 一族 251 个 target 里 **193 个未判**。

### 11.6 判读：BUDGET_CENSORED，不是 strict-G1 家族死刑

**能说的**：在本批的三跑协议（每 target 2–5 s、总预算 5,400 s/跑）下，strict 语义的
catalog 拼不满普查——供给 2,544 对需求 3,325。这是**关于本协议预算下这份 catalog** 的
读数（`BUDGET_CENSORED`）。

**不能说的**：不能读成「strict 限制档位下不存在能拼满的 catalog」，更不能读成
「strict-G1 家族死刑」。禁外推的三条佐证：

1. **未判带巨大**：L0 CLEAN 251 个目标里 193 个未判（§11.5）。缺口最敏感的正是 CLEAN
   （×16），而它恰是被截断最狠的一族。
2. **同族已有更好的实测值**：strict 专用探测臂在 480 s 内为 CLEAN 找到 **120**
   （`probe_20260803/raw/result_CLEAN_strict.json`），而本批 catalog 的 CLEAN best 只有
   **103**。两者的 `R-PAT-CONN` **判据同级**（08-04 复核订正，初版误写「探测臂略松」）：
   归档的 `probe_20260803/code/area_probe.py`（`:129` 起）同样把 fixed front、live stub、
   active front 与孔洞格全部钉进**单源**分量；用当前 evaluator 重读九份 strict probe
   witness 9/9 通过，CLEAN 120 的 violations 为空。两者的差是**搜索目标、target-menu
   与预算产物**：探测臂无 target menu、单族定向搜索 480 s，catalog 那一跑的 5,400 s
   要摊给十族上千个目标、CLEAN 只分到其中一小块——17 格的差指向预算分配，
   不是语义天花板。
3. **没有坐实的连通性独杀案例**（§11.5 表①）：1,162 个 strict 证死目标里 loose 可解 = 0、
   loose 也证死 1,090。若 strict 语义本身是那堵墙，配对对照里应当出现「loose 可解、
   strict 证死」的成批例子，实测一个没有。**但这不等于「连通税为零」已证**——还有 72 个
   loose 未判，且「loose 也证死」只排除唯一死因、不鉴定死因。

**把两条实测线合起来的描述性读数**（逐族取 catalog 与 strict 探测臂的较大者：
CLEAN 120、I1 118、I2/I3/I4/J1 117、J2 116、J3 110、CORNER 109）= **2,841，仍缺 484**。
这行是**实测找到值的合计，不是上界**（两条线是同一 strict 判据下的两个搜索目标、
两份预算产物，见上条第 2 点），所以它只说明「今天两条线加起来已经找到的量级」离 3,325
还有 484 格；既不证明装不下，也不保证加预算能补上。

**证据等级标记**：2,544 / 2,528 / 241 / 760 / 三跑计量数字 = manifest 与 run root 实数；
138、120、103 等 = 预算内找到值（找到 ≠ 极限）；146/134/118/85/101 = 机器证过的上界或
证死值；「本协议预算下拼不满」= 本批结论；「strict 装不下」= **未证，不得引用**。

### 11.7 登记欠账（`.artifacts/w0_fixrerun_20260804/acceptance_20260804.md` 收编）

1. **G13d 历史机制测试保真度**：`_CountingRegistry` stub 缺 `__fspath__`，放回修前代码
   得到的是 `TypeError` 而不是 `reads==2` 的偷渡复现（生产漏洞与修复本身已被真实文件
   替换探针双向坐实，不受影响）；`_generic_io_contract` 无同形对抗测试。
2. **范围外两处同形 parse/digest TOCTOU**：`g1_exact_cover_master.load_catalogs`
   (`:279`/`:297`)、`front_viability_audit.py` (`:1120`/`:1129`)。早于本批，research-only。
3. **`--full` 的唯一阻塞项 = 既存 r4 fixture 环境态**（W2D detached 仓依赖），三重证据
   隔离，归 r4 线自查。
4. **计量三表新形态**已在 §11.5 落章（本条即其兑现）。
5. **`CONSULT_VERDICT_20260804.md` §三 杆容量数字勘误**：已落该文书 §三勘误注
   （「≈40 根」是估计值冒充容量，正确形态是条件上界 ≤36 / ≤34）。
6. **「bound 从未离开天花板」的作用域纪律**：该断言只对**无孔三族**成立，已落
   `PROBE_REPORT.md` §四。
7. **四份文书的 08-04 验伤复核已回流**（codex 只读对抗席，3 high / 5 medium / 7 low）：
   两处证据等级混用（72 个 loose UNKNOWN 并进否定结论、两个 incumbent 之差当「孔洞真实
   代价」）已在 §11.5/§11.6 与 `PROBE_REPORT.md` §一/§4.1 逐处改口径；band14 slit 不变量、
   模型 B `a=1` 净耗、9→11 类分配计数三处算术订正落 `CONSULT_VERDICT_20260804.md` §三。
   **未闭合的一条**：三个咨询包的「已发出、回复未到」只有本地成形/导出证据（包目录与
   三份 7z），外发动作本身没有工具级收据，四份文书里一律标为 owner-reported。

### 11.8 本批没做、也不该被读成做了的事

- **没有登记任何界**：`U=(1188,18)` 一字节未动，`L` 仍是 absent。所有产物
  `authority.carries_bound=false`、`ledger_effect="none"`。
- **没有松绑任何 `R-*`**、没有建证明机、没有试点 22 号路线、没有实现 G2——按任务书
  §1「明确不做」，止损后只带判读与价签交 owner。
- **没有加预算硬闯**：任务书写死「止损 = 停，不加预算硬闯」。加深预算属于 owner 决策，
  四条路的价签与默认建议在 `STOPLOSS_CHECKPOINT_20260804.md`。
- **没有碰 certified 面**：改动只落在 `docs/research/w0_front_aware_20260803/` 与
  `src/tests/`。
