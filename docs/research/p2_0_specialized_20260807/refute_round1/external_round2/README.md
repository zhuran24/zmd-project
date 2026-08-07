# 第二轮（外部）审查的独立复核件

**来源**：2026-08-07 GPT Pro 外审份4 回件（`independent_*.py` 三件）+ 本地核签席自产的验算（`aggregate_reading_check.py`、`true_min_lanes.py`）。
外审原文逐字存档与核签判决在 `.artifacts/gpt_pro_review_batch_20260807/verdict/fen4/`（`REPLY_VERBATIM.md` + `ADJUDICATION_fen4.md`）。

**复跑状态**：五个脚本**全部在本地复跑，与归档 stdout 逐字节相同**（核签席一次、勘误二轮施工席再一次）。

**依赖**：**零依赖**——纯 `fractions` + `math`，不用 OR-Tools、不读项目数据、不需要仓库 checkout。任何 Python 3 直接可跑：

```bash
cd docs/research/p2_0_specialized_20260807/refute_round1/external_round2
python3 independent_handcheck.py
python3 independent_staircase_check.py
python3 independent_part_f_continuous_proof.py
python3 aggregate_reading_check.py
python3 true_min_lanes.py
```

## 五个脚本各自证明什么

| 脚本 | 出处 | 承担的结论 | 引用它的地方 |
|---|---|---|---|
| `independent_handcheck.py` | 外审自产 | ①两条作物的鸽巢手算（buckwheat 11 产道 vs 12 耗道、sandleaf 21 vs 22，`forced_split=True`）；②**660 不是自由占空域公分母**的反例（`13/14, 19/21, 11/12 ×4` 和恰为 `11/2`，乘 660 得 `4290/7`、`4180/7` 非整数） | `REJUDGE_REPORT.md` §3 定理 1；`../../P2_0_SPECIALIZED_DESIGN_V1.md` §3 的 P2 有理化段（D-07） |
| `independent_staircase_check.py` | 外审自产 | 阶梯占空下 19 种商品的**独立重建**：17/19 split-free、`not_split_free = buckwheat, sandleaf`、**逐商品速率集**（含 `qiaoyu_capsule 3/20,1/5,11/20` 与 `valley_battery 1/5,3/5`）、以及**全网端点车道数 622** | `REJUDGE_REPORT.md` §2 的 17/19 上确界；**§5.2 的整体替换**（这份输出就是「`{1,1/2}` 两档」被证伪的直接证据） |
| `independent_part_f_continuous_proof.py` | 外审自产 | **Part F 的连续域精确证明**——对每个自由 operation 枚举 `residual > t` 的精确 duty 区间，证明 `strict_improvement_feasible=False`；七个 operation 的连续最优与我方格点数字**全等** | `REJUDGE_REPORT.md` §4「均摊是残道最优」段的**正式附录**（R-05 指出原 Part F 是 1/660 格点却被写成连续域，同时把补丁给了） |
| `aggregate_reading_check.py` | **核签席自产** | **「616」对任何合法占空分配都不可达**：`qiaoyu_capsule` / `valley_battery` 各 3 台机器、每台占空必 > 0、各自独立出口 ⇒ 产侧至少 3 条道，而聚合下界 `⌈F_k/C⌉` 只给 1 条 | `REJUDGE_REPORT.md` §4 的 616→622 反转；`../../P2_0_SPECIALIZED_DESIGN_V1.md` §2.5；`../../OWNER_DECISION_SUMMARY.md` |
| `true_min_lanes.py` | **核签席自产** | **622 是可达最小值，阶梯是它的最小化解**：逐 (op, port) 下界 `max(n_op, ⌈c_p·x_op⌉)`，制造端口 568 + 52 源口 + 2 终品汇口 = 622，`阶梯是否处处达到逐项下界: True`；均摊多用的 6 条逐口列出 | 同上 |

## 为什么后两个是承重件

外审份4 的 D-06 是一条 **BLOCK**，它据「理论下确界 616」断言「均摊 628 与阶梯 622 都高于 616，因此**两者都不满足**前件 (ii)」。核签对这条判 **PARTIAL：诊断成立、关键论据 REFUTE**——诊断（我方在同一段论证里切换了量化单位）成立并已订正；但 616 这个数**我方原文也在用**，而这两个脚本证明它是**任何合法分配都够不到的数**，所以拿它当门槛的推论两边都不成立。

**净效果**：外审在这条上判错，但它逼出了我方自己那处更老的错（原文「理论下确界 616」+「前件与结论互斥」），这两处已在勘误二轮撤销。

## 收编状态

- `independent_part_f_continuous_proof.py` 已收作 **Part F 连续域证明的正式附录**（`REJUDGE_REPORT.md` §4、§9 欠账 2）。
- 其余四件作为**交叉验证件**入库，不重复造轮子（核签结论：「这批脚本可以直接当我方的交叉验证件收下，不必另写」）。
- 本目录的脚本**不修改**——它们是外部与核签席的原件，改了就失去独立性。
