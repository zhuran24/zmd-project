# Path 17 — D2 Commodity Cell-Flow (sub-problem 路径)

## 当前项目情况

Path 16 (全图 owner-optional) Phase 0 资源爆死后. 5 paradigm 死. GPT v7 review.

## 为什么走这条路

GPT v7 Candidate D 完整版: **commodity cell-flow + virtual terminal + conditional flow conservation**. 数学最丰富 paradigm:
- u[k, c] BoolVar — commodity k 用 cell c
- e[k, arc] BoolVar — directed arc within free cells
- cell capacity sum_k u[k,c] ≤ 1
- channeling e ⇒ u
- flow conservation per (k, c) — output port +1 / input port -1
- per-owner assumption literal 控 port adherence
- SufficientAssumptionsForInfeasibility 抽 minimal owner core → master no-good

跟 Path 16 区别: Path 16 是**全图 model 进 master**, Path 17 D2 是**全图 model 当 sub-problem** (master 不变).

## 实验过程

5 个 Phase:
- Phase 0 D1 (轻版本 u + cell capacity): 5/7 anchor FEASIBLE, paradigm 太松 NO-GO
- Phase 0b D2 (+ e arc + flow conservation): **7/7 INFEASIBLE in 0.05-0.15s GO ✅** (第一次 Phase 0 真 GO 在 D family)
- Phase 1 production class + LBBD wiring: 5/5 iter cut_added master OPTIMAL 持续
- Phase 2 multi-anchor max_iter=10: 8 anchor 实测

## 实验结果

### Phase 0b GO ✅
- 7/7 eligible INFEASIBLE 0.05-0.15s
- u_vars 23,389 + e_vars 78,318 = 101K total
- 资源全 fit cap

### Phase 1 ✅ (端到端 land)
- 5/5 iter cut_added=True
- master.solve 全 OPTIMAL — no UNKNOWN
- core size 全 = 1 (D2 找最 minimal sufficient — single owner)

### Phase 2 verdict
| anchor | status | wall |
|---|---|---|
| interior_22_28 | UNPROVEN | 611.5s |
| interior_10_10 | UNPROVEN | 658.8s |
| interior_44_30 | UNPROVEN | 608.2s |
| interior_15_40 | UNPROVEN | 610.8s |
| corner_0_0_NEGATIVE | INFEASIBLE | 57.6s (sound, no D2 entry) |
| small_10x10 | UNPROVEN | 664.0s |
| small_15x10 | UNPROVEN | 690.9s |
| small_15x15 | UNPROVEN | 631.7s |

**0/8 CERTIFIED, 7/7 non-corner UNPROVEN**. 同 Path 12-14 同质死法.

## 经验跟教训 (含瓶颈理解更新)

- **paradigm 数学最丰富但 cut form 退化** instance-pose no-good (跟 RAB-SEP 同):
  ```
  sum_{(i, p_i) in core} x_{i, p_i} <= |core| - 1
  ```
- D2 sub-problem 真识别的信息 (具体 connectivity / flow 信息) **不能在 master pose-bool 维度上表达**. 只能翻译成 owner-pose no-good.
- **瓶颈理解更新**: 6 paradigm 撞同墙 evidence. 用户 hypothesis: pose-bool master 表达力 limits 是隐含原因. 这次实测**进一步 confirm** — paradigm 数学复杂度无关, cut form 必落 master pose-bool 维度.
- 用户 sharp 抓出此 Path 17 是 **sub-problem 路径**, 不是 augmented master. 600s wall 完全没用上 (master 仍 pose-bool 100s OK, D2 0.15s 完). → 后续 L23 实施 augmented master 真验.

## code/

- `code/` 含 src/models/d2_commodity_flow_core.py (281 LOC) + src/search/d2_separator.py (215 LOC) + Phase 0/0b/1/2 trial scripts + stats JSON + 2 verdict.md
