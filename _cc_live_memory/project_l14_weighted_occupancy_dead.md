---
name: l14-weighted-occupancy-dead
description: "2026-05-16: GPT 加料后给出 proof-carrying weighted-occupancy blocker oracle (Farkas 整数证书). PoC 70 min 实测 + 数学推理: interior anchor LP=1.000 exact 永远不可 cert. 是 GPT 第一次方向没错估的方案 — 实测如他自己 caveat #1 预言 fail (weighted occupancy 数学能力不够). L14 ❌ 死路 (mathematical capability bound). 12 条 lever 全 verdict."
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

**2026-05-16 L14 weighted occupancy blocker oracle PoC verdict**:

我们在 v10 死路后给 GPT 强化版 prompt — 要求对准 upper-bound INFEASIBLE 排除 + 不准 anecdotal "不可达" + 必须形式化证明. GPT 给出 proof-carrying weighted-occupancy blocker oracle 方案 (Farkas-style 整数证书). PoC 70 min 实测 → 死路, 但**第一次 GPT 没错估方向**.

## GPT 方案核心 (重述)

对固定 ghost forbidden mask B 找整数权重 λ 满足:

```
lhs(λ, B) = sum_g d_g * m_g^B(λ) > cap_B(λ) = rhs(λ, B)
```

其中 d_g = group g 需求, m_g^B(λ) = group g 不碰 B 的 pose 加权占用最小值, cap_B = 可用 cell 加权和.

dominance: B ⊆ G ⇒ G infeasible. PROJECT_LOCK 兼容, fail-closed 正确, 引用 Clautiaux generalized energetic reasoning 真文献.

## PoC 实测 (worktree zmd_l14_poc, ~70 min Claude pace)

3 个 script (poc_weighted_occupancy_oracle.py / poc_lp_separation.py / poc_lp_scan_antichain.py).

5 个 LP separation 数据点:

| Candidate | Anchor | Ghost-Boundary 重叠 | LP optimum | Cert |
|---|---|---|---|---|
| 6×68 | (0,0) corner | 73 | 2.190 | ✓ |
| 27×15 | (22,28) interior | 0 | **1.000** exact | ❌ |
| 27×15 | (0,0) corner | 41 | 1.4375 | ✓ |
| 28×15 | (0,0) corner | 41 | 1.4375 | ✓ |
| 28×15 | (21,0) top edge | 28 | 1.2778 | ✓ |
| 28×15 | (21,27) **interior** | 0 | **1.000** exact | ❌ |

**规律**: LP > 1 当且仅当 ghost 切棋盘 boundary. **Interior anchor LP = 1.000 严格永远**.

LP optimum 完全来自 boundary_storage_port (μ_0 ~ 0.022, 其他 μ_g = 0). 18/19 free group 自由摆对 LP 不贡献.

## 数学 verdict

GPT antichain 30 shape:
```
6×68, 7×58, 8×51, 9×46, 10×41, 11×37, 12×34, 13×32, 14×29, 15×28,
16×26, 17×24, 18×23, 19×22, 20×21, 21×20, 22×19, 23×18, 24×17, 26×16,
28×15, 29×14, 32×13, 34×12, 37×11, 41×10, 46×9, 51×8, 58×7, 68×6
```

每 candidate W×H 总 anchor = (70-W+1)(70-H+1), interior anchor = (70-W-1)(70-H-1) (~90%+ 比例).

candidate-level INFEASIBLE 证明需 100% anchor cert → interior anchor LP=1.0 不可 cert → **数学不可达**.

Dominance 也救不了 interior anchor: B 也必须 touch boundary 才 LP > 1; 但 B ⊆ G interior, B 不 touch boundary → 链断.

## 跟 GPT failure mode 对照

GPT 在 doc 自己列了 3 个 caveat:
1. "真实不可行性依赖高阶组合结构, 不是 cell-weight capacity cut" ← **实测正好 hit**
2. "Routing/flow 才是某些 candidate infeasibility 来源" (这次不相关)
3. "19-group aggregation 太弱" (相关; 18 free group 不贡献是核心)

GPT 没掩盖 caveat. **PoC 实测 confirm GPT 自己的预言**.

## 这次 GPT 没错估

跟 v3/v8/v10 区分:
| | v3 | v8 | v10 | **L14** |
|---|---|---|---|---|
| 错估类型 | 算法错估 | 算法错估 | 前提错估 | **没错估** |
| 关注瓶颈 | build | anchor choice | hint 缺 | upper-bound INFEASIBLE 排除 ✓ |
| 死的原因 | build 不是瓶颈 | facility placement 才是搜索主体 | data 不满足前提 | 数学 family 能力不够 (GPT 自己预言) |

**L14 是 GPT 第一次方向 sound + 诚实 caveat + 实测 hit caveat 的方案**. 死的不是 GPT 推理错, 是数学能力上限. 这是好事 — GPT 加料起作用.

## 升级路径 (paradigm-level)

GPT 推荐: **set-packing branch-and-bound prover** 用 weighted LP 作 dual bound, 直接在 (x_{g,p}) 整数变量上搜. 估 1-2 个月工作. 不是 light-weight lever, 是 paradigm-level investment.

## 累积 lever verdict

L1-L10 + L12 (v8) + L13 (v10) + **L14 (本次)** = **12 条算法/工程层 lever 全 verdict 死路**.

GPT 已在 3 个不同方向尝试: 算法 (v8) → 数据 (v10) → 数学 family (L14), 都未能破局.

**严格性 + 算法层面 algorithmic lever 全部穷尽**. 剩下:
- L11 牺牲严格性 (用户拒绝)
- L6 AI sidecar (long term)
- Set-packing prover (1-2 月)
- Paradigm shift (换 framework)
- 改数据 (扩 blueprint 到 266 + 改 greedy)

## 归档位置

- `docs/research/l14_weighted_occupancy_poc_20260516/` (3 PoC script + sweep log + README)
- worktree `~/claude-pj/zmd_l14_poc/zmd` 留 reference, 不进 main src

## 链

- [[v10-witness-preflight-dead]]
- [[v8-anchor-slicing-dead]]
- [[external-review-reproducibility]]
- [lever verdicts](docs/lever_verdicts.md) L14 加入 ❌
