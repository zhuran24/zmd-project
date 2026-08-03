# 21 号：更正 19 号第 4 步对「仓库端口语义」的刻画（2026-08-03）

**性质**：research-only 更正文书。不产生任何 bound / witness / soundness claim；
`U=(1188,18)`、`L=absent` 不受影响。

**更正范围**：只更正 19 号（`19_w0_seed_death_sentence_recomputation_20260803.md`）
**第 4 步**里对*仓库*端口语义的一句刻画。19 号的其余四步、它的总判决
（W0 pinned geometry seed「先天绑不上端口」的死刑指控成立）以及它的所有几何计数**都不受影响**——
§3 逐条说明该判决在两种语义下都成立。

**19 号本体一个字节未改**，它是复算当天的存档。反向指针由本文与
`../w0_front_aware_20260803/00_charter.md` §4 承担。

---

## 1. 被更正的那一句

19 号第 4 步写道（原文）：

> framework 的类划分 need 向量（3I2[2,1]/3O3[1,3]/6G[3,1]/6F[4,1]/6B[5,1]…）与仓库冻结
> `canonical_rules.json` recipes 的商品种类数**不符**——按 repo 语义全部 3x3 recipe 恰 1 进 1 出、
> 全部 5x5 恰 1 进 1 出、全部 6x4 恰 2 进 1 出。

以及由它派生的一句处方（19 号「含义与边界」）：

> 修复设计必须用 repo 端口语义（种类数），不得沿用 GPT 吞吐类划分。

**错在「repo 语义 = 商品种类数」这个等号。** 商品种类数确实是那三行
（3x3 = 1 进 1 出、5x5 = 1 进 1 出、6x4 = 2 进 1 出），但仓库的端口需求 SSOT 不是它。

---

## 2. 仓库的端口需求 SSOT 是 slot 数

三处源码，都可当场复算：

- `src/models/port_binding.py` 的 `routing_visible_port_demands`：
  `req_in` = 输入侧 **slot 计数总和**（`sum(input_slots.values())`），`req_out` 同理。
  binding 子问题拿去做精确计数的就是这两个数。
- `src/preprocess/operation_profiles.py` 的 `_rate_to_slots`：
  `slots(c) = ⌈ amount(c) / ticks_per_cycle / belt_capacity_per_tick ⌉`。
- 实测反例一行足够：`crusher_sandleaf` 的 outputs 是 `{"sandleaf_powder": 3}`——
  **1 个商品种类、3 个 slot**。种类数说它要 1 个自由输出前格，仓库要 3 个。

从冻结 `rules/canonical_rules.json` + `data/preprocessed/mandatory_exact_instances.json`
现场推导，266 个 mandatory 实例里的 219 台制造机分成九类：

| class | template | r_in | r_out | count |
|---|---|---:|---:|---:|
| `3L`  | manufacturing_3x3 | 1 | 1 | 109 |
| `3O2` | manufacturing_3x3 | 1 | 2 | 6 |
| `3O3` | manufacturing_3x3 | 1 | 3 | 11 |
| `3I2` | manufacturing_3x3 | 2 | 1 | 6 |
| `5L`  | manufacturing_5x5 | 1 | 1 | 32 |
| `5O2` | manufacturing_5x5 | 1 | 2 | 17 |
| `6I3` | manufacturing_6x4 | 3 | 1 | 32 |
| `6I4` | manufacturing_6x4 | 4 | 1 | 3 |
| `6I5` | manufacturing_6x4 | 5 | 1 | 3 |

推导代码与逐 operation 的交叉校验测试在 W0 front-aware 线：
`docs/research/w0_front_aware_20260803/g1_port_semantics.py`（`derive_class_table`）与
`src/tests/test_w0_g1_port_semantics.py`（对每个 mandatory operation 断言
本线推导结果 == `routing_visible_port_demands`）。

种类数是比 slot 数**更弱**的必要条件：按种类数放行的几何可能在真 binding 处死。
把它当作「repo 语义」用在修复设计上，等于把一道便宜的必要条件调松——
这正是 W0 线要治的病（便宜的必要条件被后置）的同构再犯。

---

## 3. 死刑结论在两种语义下都成立

19 号的判决只依赖一件事：**能活的身位远少于 219**。三种口径下都成立，因为
「要求越强 → 活得越少」是单调的，而三种口径的强弱关系是确定的。

| 口径 | 每台的最弱要求 | 可活身位 | 出处 |
|---|---|---|---|
| 最弱要求（19 号第 4 步自己算的兜底） | 3x3/5x5/6x4 一律 ≥1 进 + ≥1 出 | **91/219**（43 + 33 + 15） | 19 号第 4 步 |
| 商品种类数（被更正的那句） | 3x3 (1,1)、5x5 (1,1)、6x4 (2,1) | ≤ 91（6x4 那 15 个只会更少） | 由上一行单调推出 |
| slot 数（仓库真语义，本文书确认） | 3x3 (1,1)、5x5 (1,1)、6x4 (3,1) | ≤ 91；GPT 审计器实测 **90/219**（dead = 129） | 19 号第 2 步复跑 |

三行的关系：

- **91 是存活上界**，在一个比任何真实类都弱的要求下算出来的——所以它对更强的要求同样封顶。
- **GPT 的 129 dead / 90 alive** 是在 GPT 的 need 向量下算的。那组向量与上表九行**逐行相同**
  （见 §4），也就是 slot 语义下的答案。90 ≤ 91 与单调性一致：要求变强，多死一台。
- 种类数口径夹在两者之间：3x3、5x5 与最弱要求同为 (1,1)，6x4 要求 (2,1) 强于 (1,1)、弱于 (3,1)。

**因此无论按哪种语义读，seed 都只剩 90–91 个可活身位、要装 219 台机器。** 死刑成立。
19 号第 4 步那句刻画错在「repo 语义是什么」，不在「seed 是否死」——后者是纯 body-front
几何计数，与 class 划分方案、routing 方案、commodity 绑定全都无关。

---

## 4. 顺带订正：GPT need 向量与仓库语义的关系

19 号第 4 步据此推测「GPT 的 need 向量疑似其自有吞吐模型产物（吞吐在 certified 范围外）」。
实测结果相反：那组向量与从冻结 rules 现场推导的 slot 表**逐行相同**
（3I2[2,1] / 3O3[1,3] / 6I3(=6G)[3,1] / 6I4(=6F)[4,1] / 6I5(=6B)[5,1]，计数 109/6/6/11/32/17/32/3/3）。

这不放松「不得沿用外部文书的表」的纪律，也不改变吞吐仍在 certified 范围外这一事实：

- 相同的是**结论**，不是**依据**。外部表没有可核对的推导；本线的九行表由代码从冻结权威推导，
  并由逐 operation 断言测试钉在 `routing_visible_port_demands` 上。
- 纪律的执行形态因此是「现场推导 + 红线测试」，不是「照抄外部表」；
  巧合本身不构成沿用，也不构成对外部表的背书。

19 号处方句里的括号词随之更正：**修复设计必须用 repo 端口语义（slot 数）**。

---

## 5. 影响面

- **W0 front-aware 线（G1）**：类需求按 slot 九行表执行，记账见
  `../w0_front_aware_20260803/00_charter.md` §4（含与开线书字面条款冲突的记录）。
  该线 08-03 的 G1 终态是 `INFEASIBLE`，与本更正无关：把 catalog 投影回种类数语义重跑，
  L0 与 L1 并集仍双 `INFEASIBLE`（对抗审查席独立复跑的结果）。
- **19 号其余部分**：包完整性、脚本复跑、front = 体外第 1 格、手工抽验，四步全部不受影响。
- **20 号**（H20 沙漏梳 UNSAT）：不涉及本更正。
- **任何 ledger**：不动。本文书不携带界，也不改任何状态。
