# P2.0 吞吐认证特化设计稿批（2026-08-07）

**性质**：研究层设计稿批。不改生产代码、不改锁面、不改 canonical。落地立项待 owner 过目。

**勘误二轮（20260807，外审份4 + 核签）**：本 README 在勘误一轮里**整份漏改**，仍挂着已被 `refute_round1/REJUDGE_REPORT.md` 撤销的旧判决。外审份4 的 D-01 逐条点名了四处（`:17` 六例判决、`:19` 无前件分解、`:38` 未过 refute、`:45` 混流只在细流段），核签 `ADJUDICATION_fen4.md` §0 判 **6/6 行号属实、全部 ACCEPT**，§3.A1 要求本文整份重写。本次重写按核签清单执行；被撤的旧文以「原文…已撤」形式留痕，不静默覆盖。
判决与外审原文：`.artifacts/gpt_pro_review_batch_20260807/verdict/fen4/`（核签 `ADJUDICATION_fen4.md` + 外审逐字存档 `REPLY_VERBATIM.md`）。

## 读这个目录的顺序

| 文件 | 是什么 | 给谁 |
|---|---|---|
| `OWNER_DECISION_SUMMARY.md` | 一页决策摘要：结论 + 要 owner 定的事 | **先读这个** |
| `P2_0_SPECIALIZED_DESIGN_V1.md` | 完整设计稿（10 节 + 附录），承重文本 | 实现者 / 审查席 |
| `refute_round1/REJUDGE_REPORT.md` | 第一轮独立 refute 席的重判报告（撤销六例中的四例、撤销甲案族空死刑） | 审查席 / 实现者 |
| `refute_round1/GAME_RULE_IMPACT_AUDIT.md` | 游戏规则欠账清点（M-1..M-7 判例、T-4/T-5/T-6、N-1） | 审查席 |
| `refute_round1/external_round2/` | 第二轮外部审查（GPT Pro 份4）自产的独立复核脚本 + 本地核签席的两个验算 | 审查席 / 复跑验证 |
| `rate_table.py` + `_receipt.json` + `_stdout.log` | 速率常数表（表 A/B/C/D/E） | 复跑验证 |
| `split_free_probe.py` + 收据 + 日志 | 前件族是否为空的探针（**v1，均摊硬编码，已被 v2 取代，保留为历史**） | 复跑验证 |
| `refute_round1/split_free_probe_v2.py` + 收据 + 日志 | 放开占空后的重判探针（Part A–G） | 复跑验证 |
| `maxmin_segment_probe.py` + 收据 + 日志 | 细流段厚度与**速率兼容对**的探针（**同染 v1 的均摊硬编码**；其输出里的「混流窗口」按勘误二轮一律读作「速率兼容对」——速率算术只说装得下，不说装没装） | 复跑验证 |

## 一句话结论

「目标钉死 ⇒ 速率是常数 ⇒ 流量谓词退化成常数系数线性账」这个立项命题，**前半段成立、后半段不成立**。

前半段：每种商品的稳态**总**流量确实是可精确复算的有理常数（`F_route = 9,135` 件/分钟，三线互证）。但**逐台占空不是常数**——目标只钉死每个 operation 的聚合活动 `x_op`，台间怎么分是布局的自由度，构成一个 42 维多胞形。

后半段：**原稿的六例「必然分流」判决是均摊硬编码制造出来的，已越界**。连续计数（不依赖求解器、不依赖占空约定）只证明 **buckwheat 与 sandleaf 两种商品必然分支**，前件是**当前 mandatory counts + 当前直连路由语义 + warehouse-bridge 排除**，占路由流量 **10.5%**。另四例（steel_block / buckwheat_seed / sandleaf_seed / sandleaf_powder）在阶梯占空下有**速率算术层**的 split-free 见证，但该见证的**游戏稳态可达性、70×70 几何可实现性、官方 binding/routing 模型可表达性均未验证**——只能说「原必然性证明已失效」，不能说「游戏合法反例已存在」。

> 原文（已撤）：「网络级纯流被本批两个探针证伪（6 种商品、占 37% 路由流量，在任何最小车道分配下都必然分流；由此产生 15 对不同中间品的合法混流窗口）」。撤销依据 `refute_round1/REJUDGE_REPORT.md` §2；「6 种 / 37% / 15 对」全部是均摊约定下的数字。另按外审份4 D-05 与核签 §2 D-05：速率算术只证明「速率排除不了共道」（`RC`），**不构造几何共址、不推出任何布局违反 P1**，不得写成「网络级纯流恒假」。

真正的塌缩在**求解结构**，但**它带前件**：在 P1 固定了商品归属、或 master 显式固定了每商品的容量预留 `y[h,k]` 之后，多商品流才能条件分解成「逐商品单商品流 + 格位打包」，单商品流的不可行证书是**最小割**（组合对象），省掉 v2 §4.3 那套有理 Farkas 基建。**无 P1 的上界侧仍是共享容量的多商品流问题，不能直接分解**（勘误二轮，外审 D-09 / 核签 ACCEPT；原文「这个好处不依赖任何前件」已撤）。

**推荐路线**：双侧夹逼——上界侧用与车道分配无关的松弛（flowbound 线的 `A ≤ 1167` 现成可用，**这是面积坐标的上界；`min_side` 上界从未立过**，见下），见证侧用受限族；两边相遇即闭合，不需要支配引理。

> **lex 第二坐标未闭合（勘误二轮，外审 D-11 / 核签 ACCEPT，我方文档自证）**：`docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md:296` 原文写「`min_side 维度本文未触碰。`」。所以「上界 = 下界 ⇒ 闭合」必须拆成两阶段（先面积、再在 `area = U_A` 层上证 `min_side ≤ U_S`），且两边必须同语义。设计稿 §4 丙案的闭合判据已按此改写。

## 复跑

```bash
cd /home/zhuran24/zmd-pj
./.venv/bin/python docs/research/p2_0_specialized_20260807/rate_table.py
./.venv/bin/python docs/research/p2_0_specialized_20260807/split_free_probe.py
./.venv/bin/python docs/research/p2_0_specialized_20260807/maxmin_segment_probe.py
./.venv/bin/python docs/research/p2_0_specialized_20260807/refute_round1/split_free_probe_v2.py
```

后三个需 `ortools`（走 `.venv`）。`maxmin_segment_probe.py` 与 `split_free_probe_v2.py` 都复用 `split_free_probe.py` 的 `solve_duty()`，须保持相对位置。全部脚本 `Fraction` 精确、零浮点；`rate_table.py` 内含与 `.artifacts/p2_0_refresh_20260805/area_bound_work/ob1_flow_caliber_receipt.json` 的逐字符互证断言与 266 实例普查断言，断言不过直接抛错。

`maxmin_segment_probe.py` 跑约数分钟；`split_free_probe_v2.py` 约 3 分钟墙钟（24 核）。

**复跑需要完整仓库 checkout**：`rules/canonical_rules.json`、`data/preprocessed/*`、OB1 输入与原目录结构都要在。外发的证据摘录包**不是**自包含复跑包（外审份4 D-14；核签判为包装欠账——仓内 `rate_table.py` 复跑逐字节相同，见 `ADJUDICATION_fen4.md` §1.2）。

`refute_round1/external_round2/` 里的六个脚本是例外：它们零依赖（纯 `fractions` + `math`），任何 Python 3 环境直接可跑。

## 已知欠账

1. **refute 第一轮已完成**（`refute_round1/REJUDGE_REPORT.md`，2026-08-07）；**该报告本身的独立复审也已完成**——2026-08-07 由 GPT Pro 作为外审份4 执行，本地核签见 `.artifacts/gpt_pro_review_batch_20260807/verdict/fen4/ADJUDICATION_fen4.md`（24 条中 ACCEPT 21 条、PARTIAL 1 条、DOWNGRADED-IN-REPO 2 条）。**外审总判「订正后的设计稿仍不能作为 P2.0 的实现基线」经核签成立**，主要缺口：①设计稿 §3 不是一个可判定 P7 的模型（缺守恒 / 终端 / 配方耦合行族）；②lex 第二坐标从未开工；③勘误一轮的完成度声明不实（本次二轮修）；④重判报告 §5.2 的「零有理变量」被我方自己的 Part C 见证证伪。
   > 原文（已撤）：「**未过独立 refute 席**。本批是起草席自产的承重推理文书，按仓库家规入库前应过一道对抗审查。」——两轮审查均已完成。

2. **§3 不是完整的 P7 模型**（外审 D-08 / 核签 ACCEPT）。现有 P1–P4 只有容量片段，缺流守恒（T1）、终端供需（T3）、机器配方耦合（T2）、duty 聚合（D1/D2）四族。设计稿 §3 已补齐行族清单，但**未实现、未实测**。

3. **生产规模行数未实测**（设计稿 Q1）。所有「行数可接受」的工程判断在它闭合前是【假设】。Q1 已按外审 D-08 扩成「三模型 A/B/C × 14 指标」实验。

4. **多胞形任意点的游戏可实现性未证**（外审 D-04 / 核签 ACCEPT 标签级）。当前材料只证明单向包含「游戏可实现稳态 ⊆ `U_rate`」，反向包含未证。相关欠账（A7 无「长期吞吐 = 供料率」等号、同侧多出口可加性、作物环初态与吸引子、三进汇流器仲裁、零模拟器判例、官方 binding/routing 可表达性）**全部已在 `refute_round1/GAME_RULE_IMPACT_AUDIT.md` 立案**（N-1 / T-4 / T-5 / T-6 / D-5 / §7 诚实边界 + 判例 M-2..M-6）。

## 对外部线的两条净输入

- **给 flowbound 线一条禁令**：`L ≥ Σ_k ceil(F_k/C) = 308`（比现役聚合的 305 紧）**依赖「每格单商品」这个限制**，不可进无条件上界链；只能记进「受限族内上界」台账。详见设计稿 §4 末与 §8。
- **给 flowbound 线一条互证**：`F_route = 9,135` / `F_target = 9,169.5` 本批第三次独立复算通过（flow_account → OB1 → 本批）。
- **给 mixflow / U-01 线**：无条件成立的只剩一句——**速率算术恒能找到一对不同中间品的段，其速率之和 ≤ 带容量**（因为被劈开的产道速率恰为 1，最细一段必 ≤ 1/2）。这既**不构造物理共道**，也**不把窗口限定在细流段**（阶梯算术点的兼容残道出现在**端口侧**）。`item_admission_port_exclusion` 的裁决结论不受影响——它靠独立的理由 (b)(c)，不依赖速率算术；但理由 (a) 的措辞要加占空条件。详见设计稿 §7。
  > 原文（已撤）：「混流只可能发生在分流细流段（不在主干），这对需防的场景是一条收窄」。撤销依据 `refute_round1/REJUDGE_REPORT.md` §5.1 + 外审份4 D-05 / 核签 ACCEPT——该收窄只在均摊约定下成立，且「窗口存在」不等于「混流会发生」。
