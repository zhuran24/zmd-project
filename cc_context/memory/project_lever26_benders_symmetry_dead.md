---
name: lever26-benders-symmetry-dead
description: "GPT v12 lever 26 (Benders symmetry cut-orbit lifting) Phase 0 实测 NO-GO: 总 group >10^308 但 nontrivial orbit 仅 8, m5 multiplier=1, symmetry 被 ghost/boundary/port_dir 打碎"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-20 commit 2c5d400: GPT v12 review 包给的 4 个 alive 候选之一. typed automorphism graph (pose × cell × dir-cell) + nauty/bliss orbit detection + cut-orbit lifting. Phase 0 cheap gate Probe 用 pynauty 2.8.8.1.

## Phase 0 实测 (typed graph build + automorphism)

| metric | 实测 | threshold | 判定 |
|---|---|---|---|
| m1 graph build seconds | 1.09s | (combined m1+m2) | ✓ |
| m2 automorphism seconds | **194.46s** | combined ≤ 60s | ❌ |
| m3 graph RSS GB | 6.28 | ≤ 8 GB | ✓ |
| m4 nontrivial orbit count | **8** | ≥ 10 | ❌ |
| m5 effective multiplier (avg) | **1.0** | min ≥ 2, avg ≥ 5 | ❌ |
| m6 orbit image replay soundness | 100% (trivial orbits, vacuous sound) | = 100% | ✓ vacuous |

Graph: 106,295 node + 2,485,100 edge. Group size > 10^308 (overflow). Top nontrivial orbit sizes: [204, 204, 137, 137, 76, 76, 76, 76].

## Core finding

总 symmetry group 极巨 (>10^308) **但只有 8 个 nontrivial orbit**. 5 个 synthetic core 全落 trivial orbit (size=1, m5=1.0). 意味着: **graph 总 automorphism 大, 但跟 cut-relevant pose 无相关 orbit** — ghost anchor + boundary port + port direction + pose-cell incidence 已把 cut-relevant pose 的 symmetry 完全打碎.

这正是 GPT v12 lever 26 README 自己 self-flag 的 Failure mode 1 ("真实 symmetry 被项目语义打碎"). **应验**.

automorphism 194s 也超 budget (cap 60s combined), 即使 m4/m5 通过 Phase 1 也跑不动.

## probe bug fixes (2 个)

1. `group_size = float(grpsize1) * 10.0**grpsize2` → 用 `log10` + mantissa/exponent 存避免 float overflow
2. `lift_core_to_orbit(..., None)` buggy call → inline 重写 orbit lookup, build vertex→rep map once O(n)

## Verdict

**第 26 lever 死**. GPT v12 lever 26 进 dead lever list. infrastructure (TypedSymmetryGraph + pynauty wrapper + orbit lookup) 留作 future reference (e.g. 若日后 ghost anchor / port direction 编码改变).

跟 [[path18-layout-invariant-cert-dead]] 同 day 同 1 day 杀完, cheap gate workflow 自身成功 — 数学上花 1 day 排除一条, Phase 1 (~1 周) 投资省了.

## 跟 LIC ❌ verdict 的差异

LIC 是独立 Claude opus brainstorm 方向 (cut lift cell-front pattern). Benders symm 是 GPT v12 推荐. **两条独立选出来的方向 Phase 0 都死**, 但死因不同:
- LIC: cell-front 几乎决定 pose, lift 不动
- Benders symm: graph automorphism 总 group 大但 cut-relevant pose 无 orbit

共同 root cause: **项目 facility/port/cell 几何 high-resolution 已经把 sub-pose-level 等价性打碎**. Cut 强度 amplification 在这个 problem geometry 下没 free lunch.

## Next: GPT v12 剩 3 个候选

- cand C **Column generation / branch-and-price** (3-6 月 paradigm-level 投资, 唯一真换 master variable basis)
- lever 25 **IHS Implicit Hitting Set** (1-2 周, 但 core size=1 退化风险 = Path 17 D2 同质)
- cand A **CDCL warm-start** (1 周, hint source 替换不改 proof bottleneck, GPT 自评低优先级)

或 27 lever / paradigm shift / scope reset. 用户决策.
