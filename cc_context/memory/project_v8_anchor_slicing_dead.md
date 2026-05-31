---
name: v8-anchor-slicing-dead
description: "2026-05-16: GPT-5.5 Pro v8 ghost-anchor slicing patch (Path 8) 实测死路. Build wall -92% 漂亮但 solve 不动, 单 anchor 5 min UNKNOWN 5.5M branches, 跟 trial7 1h UNKNOWN 同 quality. 错估同 v3 — 关注 build 没量 solve."
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

**2026-05-16 v8 anchor slicing 实测 verdict**:

GPT Pro 收到 v7 review 包后, 针对 Path 8 给出完整 v8 patch (`zmd_anchor_slicing_delivery_v8.zip`, 9.4 MB, 9 文件改动). 我们实测**死路**.

## 包验证 (3 项全过)

1. SHA256 校验: `e435404d...` ✓ 跟 GPT 给的对得上
2. Patch clean apply: HEAD `2ec6b32` worktree → 9 文件改动 0 hunk fuzz
3. 全套 pytest: **2211 passed / 60 skipped / 0 failed** (4 分 9 秒, baseline 2207 多 4 新测试)

## Build 阶段实测 (真实有效)

`build_exact_core → from_exact_core` 27×15 ghost (power_coverage=on):

| 指标 | Full overlay | Single slice@(22,28) | Δ |
|---|---|---|---|
| from_exact_core wall | 53.7 s | 4.5 s | **-92%** |
| proto vars | 19406 | 16943 | -13% |
| proto cons | 56452 | 38578 | -32% |
| build RAM | 1.86 GiB | 0.52 GiB | -72% |

## Solve 阶段实测 (打死)

跟 trial7 同 candidate (27×15) + community hint 注入 + `MAX_ANCHORS=5` + 30 min 预算, 但 process 实际跑 **5 分 7 秒**就退 — `EXACT_MASTER_GHOST_ANCHOR_SLICE_CANDIDATE_SECONDS` 默认 = master_seconds = 300, candidate deadline 切断 + `EXACT_OUTER_SKIP_UNKNOWN=1` terminal stop.

第 1 个 anchor (0,0) 数据:
- elapsed: 307.76 s
- status: **UNKNOWN**
- branches: **5,510,114** (真在搜)
- conflicts: 811
- binary_propagations: 293,533,133
- integer_propagations: 295,507,413
- deterministic_time: 746.28
- master_hinted_literals: 798 (= 266 × 3, hint 完美注入)
- `mandatory_pose_literal_count`: **3,853,132** (跟 full overlay 一致 — 锁 ghost anchor 不减 mandatory placement search space)
- ghost_anchor_count (post-slice): 1

## 跟 GPT v3 错估同源

| 项目 | v3 (5/13) | v8 (今天) |
|---|---|---|
| 关注瓶颈 | "build 慢" | "anchor choice 撑开搜索树" |
| 改完效果 | build 加速 | build wall -92% |
| solve 阶段 | 没改善 | 没改善 (5 min UNKNOWN, 5.5M branches) |
| 失败原因 | 错把 build 当瓶颈 | 错把 anchor choice 当搜索主导 |
| 严格性兼容 | ❌ (自己 audit 推翻) | ✓ (fail-closed + PROJECT_LOCK 兼容) |

工程上 v8 比 v3 干净 (没破 exactness, 没做 unsafe), 但 **ROI 仍为负**.

## 根因

锁 ghost anchor 后 master 仍有 **385 万 mandatory pose literal**. 搜索难度的主体来自 266 个 facility 几何摆放, 不是 ghost anchor choice. 锁 anchor 只剪掉搜索树最外层一层, 底下 facility placement 层没动.

## Path 计算 (3 个 path 全死)

| Strategy | 算账 | Status |
|---|---|---|
| 早命中 | 单 anchor 5 min 没结论, 后续 2463 anchor 没机会 | ❌ |
| 完整 partition | 单 anchor 5 min × 2464 = 205 小时, 物理不可行 | ❌ |
| 锁 anchor 加速单 slice | 单 slice 5 min UNKNOWN 跟原 master 1h UNKNOWN 同 quality | ❌ |

## 归档位置

- `docs/research/v8_anchor_slicing_smoke_20260516/` (8 文件 + README.md)
- v8 patch 不进 main src — worktree `~/claude-pj/zmd_v8_test/zmd` 留作 reference
- `docs/lever_verdicts.md` 加 L12 ❌

## 全 lever verdict 累积

L1-L10 + L12 = **10 条算法层面 lever 全 verdict 死路**. L6 (AI sidecar) 搁置 long-term. L11 (hard constraint) 未试 — 牺牲严格性, 用户拒绝.

**严格性兼容 + 算法层面的 algorithmic lever 全部穷尽**. v8 是穷尽证据.

## 链

- [[v7-review-package-landed]] — v7 包送出去前的 8 path 状态
- [[d-step2-hint-landed]] — D step 2 / trial7 baseline 1h UNKNOWN
- [[gpt-anchor-slicing-proposal]] — Path 8 历史背景 (v1/v2/v3 download 全过期, 这次 v8 是 GPT 重新生成)
- [[rewrite-path-exhausted]] — 其他 paradigm 路径死路
- [[external-review-reproducibility]] — GPT 全量审查 reproducibility 不足 + 错估同类型
