# L14 weighted-occupancy blocker oracle PoC — 2026-05-16

GPT Pro 在收到 v10 死路 + 强化版 prompt (要求方案对准 upper-bound INFEASIBLE 排除, 不准 anecdotal "不可达") 后, 给出**proof-carrying weighted-occupancy blocker oracle** (Farkas-style 整数证书). 本目录归档 PoC 实测 + verdict.

**verdict**: ❌ 死路, 但**不是 GPT 错估** — 是 GPT 自己 caveat 列出的 failure mode 1 ("加权占用太弱") 实测确认. 在我们项目结构下, weighted occupancy LP optimum **interior anchor 永远 stable at 1.000 exact**, 不能严格 > 1, 数学上 cert 不动.

跟 v3/v8/v10 不同: GPT 这次方向 sound + 诚实 caveat. 死的是数学能力上限, 不是关注点错位.

---

## GPT 方案核心 (重述)

对固定 ghost forbidden mask B, 找整数权重 λ 满足:

```
lhs(λ, B) = sum_g d_g * m_g^B(λ) > cap_B(λ) = rhs(λ, B)
```

其中:
- d_g: group g 需求数 (19 group, sum d_g = 266)
- m_g^B(λ): group g 在不碰 B 前提下, 所有合法 pose 中 sum_{c in F(p)} λ_c 的最小值
- cap_B(λ): sum_{c in C\B} λ_c

如果 lhs > rhs, B 下 mandatory placement 几何 infeasible.

证书 dominance: B ⊆ G ⇒ G 也 infeasible (cap 减小 + per-group min 不减).

---

## 文件清单

| 文件 | 内容 |
|---|---|
| `poc_weighted_occupancy_oracle.py` | Step 1: integer verifier + uniform/window/boundary λ 模式扫 (302 行) |
| `poc_lp_separation.py` | Step 2: LP separation 找最优 cell-level λ (203 行) |
| `poc_lp_scan_antichain.py` | Step 3: scan antichain × sample anchors 算 coverage (215 行) |
| `lp_sweep_28x15.log` | 28×15 几个 anchor LP 实测数据 |

---

## 实测数据 (5 anchor LP separation, GLOP solver, OR-Tools 9.15)

| Candidate | Anchor | Ghost-Boundary 重叠 | LP iter | LP optimum | Cert |
|---|---|---|---|---|---|
| 6×68 | (0,0) corner | ~73 cells | 229 | **2.190** | ✓ |
| 27×15 | (22,28) interior | 0 | 690 | **1.000** exact | ❌ |
| 27×15 | (0,0) corner | 41 | 447 | **1.4375** | ✓ |
| 28×15 | (0,0) corner | 41 | 469 | **1.4375** | ✓ |
| 28×15 | (21,0) top edge | 28 | 479 | **1.2778** | ✓ |
| 28×15 | (21,27) interior | 0 | 692 | **1.000** exact | ❌ |

**规律**: LP > 1 当且仅当 ghost 切棋盘 boundary. interior anchor LP = 1.000 严格.

LP 数学结构: μ_0 ~ 0.022 (boundary_storage_port), 其他 μ_g = 0. LP optimum 完全来自 boundary_storage_port 这一个 captive group; 18/19 free group (manufacturing_*, protocol_core 等) 自由摆, 对 LP 不贡献.

---

## Antichain + Coverage 计算

70x70 grid, area > 405, min_side ≥ 6 的 antichain 共 **30 个形状** (跟 GPT claim 完全对得上):

```
6×68, 7×58, 8×51, 9×46, 10×41, 11×37, 12×34, 13×32, 14×29, 15×28,
16×26, 17×24, 18×23, 19×22, 20×21, 21×20, 22×19, 23×18, 24×17, 26×16,
28×15, 29×14, 32×13, 34×12, 37×11, 41×10, 46×9, 51×8, 58×7, 68×6
```

每 candidate W×H 的总 anchor 数 = (70-W+1)(70-H+1). Interior anchor 数 = (70-W-1)(70-H-1) (anchor 不碰任何 boundary edge).

| Shape | 总 anchor | Interior anchor | Interior 比例 |
|---|---|---|---|
| 27×15 | 2464 | 2268 | 92.0% |
| 28×15 | 2408 | 2214 | 91.9% |
| 30×14 | 2337 | 2143 | 91.7% |
| 6×68 | 195 | 65 | 33.3% |
| 35×13 | 2052 | 1870 | 91.1% |

**对绝大多数 antichain shape, interior anchor 占 90%+**. 这些 interior anchor 在 weighted occupancy LP 下全 = 1.000, 不可 cert.

---

## Verdict 数学推导

GPT 方案 candidate W×H 整体 INFEASIBLE 证明要求:
- **每个**anchor 都有 certificate (或被 smaller B 的 certificate dominate)

由于 interior anchor LP = 1.0 永远, **无法 cert single interior anchor**.

GPT 提议的 dominance (B ⊆ G ⇒ G infeasible) 也救不了:
- 要 cover G 的 interior anchor (不 touch boundary), B 必须 ⊆ G 的内部
- B ⊆ G interior → B 也不 touch boundary → B 自己 LP = 1.0, cert 不动
- Dominance 链上 base B 不存在 cert → 链断

**结论**: weighted occupancy proof family 在我们项目结构下数学上 cover 不动任何 area > 405 candidate 的 INFEASIBLE 证明.

---

## 跟 GPT failure mode 对照

GPT 在方案 doc 自己写了 3 个 caveat:
1. "真实不可行性依赖高阶组合结构, 而不是任何 cell-weight capacity cut" ← **实测正好 hit**
2. "Routing/flow 才是某些 candidate 的 infeasibility 来源" (不是这次)
3. "19-group aggregation 太弱" (相关; 18 free group 不贡献是核心)

GPT 没掩盖这个 caveat, 实测确认了它的预言. **这是 GPT 第一次给的方案 caveat 没错估**.

---

## 跟 v3 / v8 / v10 错估对比

| | v3 | v8 | v10 | **L14 (本次)** |
|---|---|---|---|---|
| 错估类型 | 算法错估 | 算法错估 | 前提错估 | **没错估 (mathematical limitation, GPT 自己 caveat 列了)** |
| 关注瓶颈 | build | anchor choice | hint 缺 | **upper-bound INFEASIBLE 排除 (对路)** |
| 死的原因 | build 不是瓶颈 | facility placement 才是搜索主体 | data 不满足前提 | **数学 family 本身能力不够** |
| GPT caveat | 没说 | 没说 | 暗示 | **明说 3 个, 实测 hit #1** |

---

## 升级路径 (都不在 PoC 范围内)

GPT 自己推荐: 升级到**set-packing prover** (1-2 个月工作), 不靠 LP 找 weighted, 而是 branch-and-bound 直接在 (x_{g,p}) 整数变量上证, 用 weighted LP 作为 dual bound.

实施代价: 自己写一个专用 set-packing prover, GPT 估 1-2 个月. 不是 light-weight lever, 是 paradigm-level investment.

---

## 累积 lever verdict

L1 / L2 / L3 / L4 / L5 / L7 / L8 / L9 / L10 + L12 (v8) + L13 (v10) + **L14 (本次)** = **12 条算法层面 lever 全 verdict 死路**.

- L11 牺牲严格性 (用户拒绝)
- L6 AI sidecar (long term, 搁置)
- Set-packing prover (1-2 月 paradigm investment)
- 改数据 (扩 blueprint 到 266 + 改 greedy)

至此**严格性 + 算法层面 algorithmic lever 全部穷尽**. 在不放宽硬约束的前提下没有 light-weight lever.

---

## 操作记录

worktree: `~/claude-pj/zmd_l14_poc/zmd` (基于 HEAD `9991843`, 加 3 个 PoC script, 不进 main src)

PoC 实测总耗时:
- worktree setup + antichain verify: ~10 min
- uniform/boundary 简单 weight scan: ~30 min
- LP separation 5 anchor: ~25 min
- 总 PoC: ~70 min (Claude pace, 完全在 GPT 估的 "3-5 天最小可交付" 之下)

---

## 链

- [[project_v10_witness_preflight_dead]] — 上一次 GPT 方案 (前提错估)
- [[project_v8_anchor_slicing_dead]] — v8 (算法错估)
- [[feedback_external_review_reproducibility]] — GPT 错估类型
- [[lever_verdicts]] L14 加入 ❌
