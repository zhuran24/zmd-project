# L14 — Weighted Occupancy Blocker Oracle (GPT 加料 prompt)

## 当时项目情况

v8 + v10 双死后, 项目给 GPT 加料 prompt — 要求**形式化证明** unsolvability, 不准 "I believe" / 直觉.

## 为什么走这条路

GPT 给出 **proof-carrying weighted-occupancy blocker oracle** (Farkas-style 整数证书):

```
lhs(λ, B) = sum_g d_g × m_g^B(λ) > cap_B(λ) = rhs(λ, B)
```

其中 d_g = group g 需求, m_g^B(λ) = group g 不碰 B 的 pose 加权占用最小值, cap_B = 可用 cell 加权和. dominance: B ⊆ G ⇒ G infeasible. PROJECT_LOCK 兼容 + 引用 Clautiaux generalized energetic reasoning 真文献.

## 实验过程

worktree zmd_l14_poc, 70 min Claude pace. 3 个 script (poc_weighted_occupancy_oracle.py / poc_lp_separation.py / poc_lp_scan_antichain.py). 5 LP separation datapoints.

## 实验结果

| Candidate | Anchor | LP optimum | Cert |
|---|---|---|---|
| 6×68 | (0,0) corner | 2.190 | ✓ |
| 27×15 | (22,28) interior | **1.000** exact | ❌ |
| 27×15 | (0,0) corner | 1.4375 | ✓ |
| 28×15 | (21,27) **interior** | **1.000** exact | ❌ |

**规律**: LP > 1 当且仅当 ghost 切棋盘 boundary. **Interior anchor LP = 1.000 严格永远**.

LP optimum 完全来自 boundary_storage_port (μ_0 ~ 0.022), 其他 18 free group μ_g = 0. interior anchor 不 touch boundary → LP=1 → 数学不可 cert.

## 经验跟教训 (含瓶颈理解更新)

- **GPT 第一次方向没错估** — paper 自己列了 3 个 caveat, 实测 hit caveat #1 ("真实不可行性依赖高阶组合结构, 不是 cell-weight capacity cut"). 加料 prompt 起作用.
- **新错估类型: 数学能力上限** — paradigm 数学方法 family (weighted occupancy / linear cell-weight cut) 自身不够强表达 problem 的高阶组合结构.
- **瓶颈理解更新**: routing/flow 才是某些 candidate infeasibility 来源, 不是 cell-weight cut 维度.

GPT 推荐升级: **set-packing branch-and-bound prover** (1-2 月 paradigm investment) → 后续 L15.

## code/

- `code/` 含 3 个 PoC script + LP separation sweep log + README
- 详 `code/README.md`
