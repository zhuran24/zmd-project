---
name: v10-witness-preflight-dead
description: "2026-05-16: GPT v10 witness-only mandatory-placement preflight 实测死路, 但跟 v8 错估不同源 — v10 是前提错估 (要求 complete witness, 我们 community blueprint 缺 41 mandatory + greedy 填充破坏 27×15 空地) + candidate-size 依赖 (大 candidate 永远 0 compatible anchor). 算法本身 sound."
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

**2026-05-16 v10 witness preflight 实测 verdict**:

GPT Pro 在 v9 包基础上 (我们 v9 已记录 v8 anchor slicing 失败), 重新出 v10 witness-only mandatory-placement preflight 方案 (`zmd_witness_preflight_delivery_v10.zip`, 5.4 MB, 7 文件改动, +782/-39 行, SHA `a909097b...`). 我们 worktree 实测 → 死路, 但**跟 v8 错估不同源**.

## 包验证 (3 项全过)

1. SHA256 校验 ✓
2. `git apply -p1` clean apply 到 HEAD `634c0bd`, 0 hunk fuzz
3. 全套 pytest: **2212 passed / 60 skipped / 0 failed** (4 分 5 秒, baseline 2207 多 5 新测试)

## 算法核心

```text
已有完整 mandatory hint
=> 计算 mandatory 占用格
=> 找出与该占用格不相交的 compatible ghost anchors
=> clone 当前 master (含已 replay Benders cuts)
=> 固定 mandatory slot 的 x / y / mode
=> 固定一个 compatible ghost anchor literal == 1
=> residual optional 仍自由
=> clone FEASIBLE 且能 extract solution
=> 作为普通 master FEASIBLE incumbent 进 binding/routing
```

fail-closed 设计: clone INFEASIBLE/UNKNOWN/timeout/incomplete → 不证 parent INFEASIBLE, 回退 normal master. **逻辑上 sound + PROJECT_LOCK 兼容**.

## 实测 verdict — preflight 在我们 data 下永不 trigger

**实战路径 hint 合并** (smoke log 验证):
- `build_exact_candidate_warm_start()` → greedy hint **266 个**
- 加 community blueprint hint (225 个) → `+0 additions, 224 overrides, total 266`

**Witness compatibility 检查实测**:

| 字段 | 值 |
|---|---|
| `complete_hint` | **True** ✓ (266 hint 全) |
| `mandatory_hint_pose_count` | 266 |
| `mandatory_hint_occupied_cell_count` | **3122 格** (70×70=4900 的 64%) |
| `ghost_anchor_total_count` | 2464 (27×15 candidate) |
| `compatible_anchor_count` | **0** |
| `reason` | `no_compatible_ghost_anchor` |

**Smoke 实战 telemetry** (跟 trial7 同 candidate + slicing on + 30 min budget):

Preflight 阶段:
- `enabled: True, attempted: True, accepted: False, status: skipped`
- `anchor_attempt_count: 0` (没跑 1 次 forced clone solve)
- `elapsed_seconds: 0.0` (preflight 几乎瞬间 fail)

Fallback normal master (回退 trial7-style):
- wall: 302.12s, status UNKNOWN
- branches: 5,574,230, conflicts: 15,380
- binary_propagations: 799,437,315

跟 trial7 / v8 同 quality, master fallback 没改善.

## Candidate-size 依赖 (新发现)

Greedy hint 套到不同 ghost rect 大小测 compatible anchor count:

| Ghost (w×h) | Compatible / Total | 比例 |
|---|---|---|
| 8×8 | 611/3969 | 15.4% |
| 10×10 | 469/3721 | 12.6% |
| 12×8 | 363/3717 | 9.8% |
| 15×15 | 149/3136 | 4.8% |
| 20×15 | 0/2856 | **0.0%** |
| 27×15 | 0/2464 | **0.0%** |

**v10 preflight 在小 candidate (area ≤ 225) 上能 trigger, 在 area ≥ 300 大 candidate 上永远 0**. 项目目标是大面积 `max_lex`, preflight 对真目标无效.

## 错估根因 — 跟 v8 不同源

v8 错估 = **算法错估** (anchor choice 撑搜索树假设跟实测不符)
v10 错估 = **前提错估 + data 不匹配**

具体:
- v10 假设 "complete 266-facility witness 跟 blueprint align"
- 实际我们 community blueprint 只 225 mandatory (用户手调 blueprint 只摆 225 个)
- 缺 41 个 mandatory (3 boundary_port + 3 grinder_fine_buckwheat + 3 packaging_battery + 1 protocol_core_001 + 31 其他) 由 greedy heuristic 填
- Greedy 不知道 blueprint 留 27×15 空地, 这 41 个填进了 blueprint 留空区域
- Merge 后 266 facility 占 3122 格, 把 blueprint 的 27×15 空地破坏掉

v10 **算法本身比 v8 更可能有用** — 如果 data 满足前提 (266/266 align blueprint), forced clone solve 至少能 trigger. 但当前 data 不满足, 无法验 forced clone solve 是否能 FEASIBLE.

## 错估总表 (v3 / v8 / v10)

| | v3 (5/13) | v8 (5/16 早) | v10 (5/16 晚) |
|---|---|---|---|
| 类型 | 算法错估 | 算法错估 | **前提错估** |
| 关注瓶颈 | "build 慢" | "anchor choice 撑搜索树" | "有 complete witness 假设" |
| 真相 | solve 才是瓶颈 | facility placement 是瓶颈 | 我们 blueprint 缺 41 mandatory + greedy 不 align |
| 改完真效果 | build 加速 | build 加速 -92% (solve 不变) | preflight 在大 candidate 永不 trigger |
| 严格性 | ❌ (5h 自己推翻) | ✓ (fail-closed) | ✓ (fail-closed) |
| 实测 verdict | ❌ | ❌ | ❌ (data-bound) |

## 破解 v10 的可能路径 (都不在 patch 范围内)

1. **扩展用户 blueprint 到 266 facility 全 align** — 用户手加 41 个 facility 进 blueprint (几小时人工 + schema match)
2. **改 greedy heuristic 尊重 blueprint 空地** — greedy 跑时把 blueprint 留空区域 mask 掉 (改 heuristic 代码, 工作量大)
3. **v10 加 partial witness mode** — 允许 incomplete hint + missing 部分让 CP-SAT 搜 (但这就回到原 master 搜索难度, 失去 v10 价值)

这 3 条都是 data/heuristic 工程侧, 不是 v10 patch 算法侧.

## 累积 lever verdict

L1-L10 + L12 (v8) + **L13 (v10)** = **11 条算法/工程层 lever 全 verdict 死路**.

GPT 在两个不同方向都未能破局: 算法侧 (v8) 跟 data 侧 (v10) 都试过, 都失败.

## 归档位置

- `docs/research/v10_witness_preflight_smoke_20260516/` (9 文件 + README.md)
- v10 patch 不进 main src — worktree `~/claude-pj/zmd_v10_test/zmd` 留作 reference
- `docs/lever_verdicts.md` 加 L13 ❌

## 链

- [[v8-anchor-slicing-dead]] — v8 错估 (算法错估)
- [[v7-review-package-landed]] — v7 包 (送 GPT 前的 8 path 状态)
- [[d-step2-hint-landed]] — D step 2 trial7 baseline (community hint 225 facility)
- [[external-review-reproducibility]] — GPT 外部审查错估类型
- [lever verdicts](docs/lever_verdicts.md) — 主线 lever 总账 (L13 加入)
