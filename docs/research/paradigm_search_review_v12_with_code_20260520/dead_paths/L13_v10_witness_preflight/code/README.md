# v10 witness preflight 实测归档 — 2026-05-16

GPT Pro 在 v9 review 包基础上 (注: v9 已记录 v8 anchor slicing 失败), 提出 **witness-only mandatory-placement preflight** 方案. 本目录归档 patch + 实测数据 + verdict 数据点.

**verdict**: ❌ 死路, **不同来源的错估** — v10 不是算法错估, 是**前提错估 + data 不匹配**. v10 算法本身比 v8 更可能有用, 但在我们当前 hint 数据下永远不 trigger forced clone solve.

---

## 文件清单

| 文件 | 内容 |
|---|---|
| `gpt_CORE_ANALYSIS.md` | GPT 自己解释 "为啥 v8 没用 + v10 新思路" |
| `gpt_phase3c_witness_preflight.md` | GPT 写的算法 + exactness contract 文档 |
| `gpt_README_DELIVERY.md` | GPT 自己写的 delivery 说明 |
| `gpt_validation.log` | GPT 自己跑过的验证 (8 targeted 测试 + py_compile + ruff) |
| `zmd_witness_preflight_v10.patch` | 完整 patch (1013 行, +782/-39, 7 文件) |
| `v10_pytest_2212_pass.log` | 我本地全套 pytest 结果 (2212 passed / 60 skipped / 0 failed) |
| `smoke_master_iter1.log` | 30 min smoke 跑出来的 main.py stdout |
| `exact_campaign_state.json` | smoke 跑完 campaign 终态 (含 master_witness_preflight telemetry) |
| `exact_campaign_telemetry.json` | smoke wave telemetry |

---

## 关键数据点

### Patch 整合验证

- 外层 SHA256 跟 GPT 给的对得上: `a909097b0cc5275b9e8cb36a0e0ddca03f99a7af39ba1a538556eadd9d0e28b7`
- 直接 `git apply -p1` 到 HEAD `634c0bd` clean apply
- 全套 pytest: **2212 passed / 60 skipped / 0 failed** (比 baseline 2207 多 5 个新测试)
- GPT 自己只跑 8 个 targeted 测试, 我们项目全套 2212 是兜底

### 算法核心 (复述 GPT 文档)

```text
已有完整 mandatory hint
=> 计算 mandatory 占用格
=> 找出与该占用格不相交的 compatible ghost anchors
=> clone 当前 master 模型 (含已 replay 的 Benders cuts)
=> 固定 mandatory slot 的 x / y / mode
=> 固定一个 compatible ghost anchor literal == 1
=> residual optional 仍然自由
=> clone FEASIBLE 且能 extract solution
=> 作为普通 master FEASIBLE incumbent 进 binding/routing
```

fail-closed 设计 (sound):
- `forced clone INFEASIBLE/UNKNOWN/timeout/incomplete` → 不证 parent INFEASIBLE, 回退 normal master
- `preflight 吃完 budget 仍无 witness` → parent UNKNOWN, 不伪造 INFEASIBLE

### Hint 完整性 — 实战路径触发 OK, 但 compatible anchor = 0

实战 `_run_certified_exact` 合并 hint 流程:
1. `build_exact_candidate_warm_start()` → greedy hint **266 个 mandatory**
2. 加载 community blueprint hint (225 个 mandatory)
3. Community 用相同 instance_id override greedy → **`+0 additions, 224 overrides, total 266`**

v10 `candidate_witness_compatible_ghost_anchors(merged_hint, max_anchors=32)` 实测:

| 字段 | 值 |
|---|---|
| `complete_hint` | True (266 hint 全)|
| `mandatory_hint_pose_count` | 266 |
| `mandatory_hint_occupied_cell_count` | **3122 格** (70×70=4900 的 64%) |
| `ghost_anchor_total_count` | 2464 |
| `compatible_anchor_count` | **0** |
| `reason` | `no_compatible_ghost_anchor` |

**266 facility 摆出来的 3122 格占用, 跟所有 2464 个 27×15 ghost anchor 候选位置都有 cell overlap. 0 个不冲突的 anchor.**

### Smoke 实测 telemetry

```bash
EXACT_MASTER_WITNESS_PREFLIGHT=1 \
EXACT_MASTER_WITNESS_PREFLIGHT_SECONDS=30 \
EXACT_MASTER_WITNESS_PREFLIGHT_MAX_ANCHORS=32 \
EXACT_COMMUNITY_BLUEPRINT_HINT_PATH=data/hints/blueprint_2026_05_13_master_hint.json \
.venv/bin/python main.py --campaign-hours 0.5 --master-seconds 300 ... \
    --start-area 410 --min-side 15 --max-aspect-ratio 1.9 --parallel-processes 1
```

#### Preflight 阶段

```json
{
  "enabled": true,
  "attempted": true,
  "accepted": false,
  "status": "skipped",
  "reason": "no_compatible_ghost_anchor",
  "anchor_attempt_count": 0,
  "compatible_anchor_count": 0,
  "mandatory_hint_pose_count": 266,
  "mandatory_hint_occupied_cell_count": 3122,
  "missing_hint_count": 0,
  "time_budget_seconds": 30.0,
  "elapsed_seconds": 0.0,
  "validation_samples": []
}
```

**preflight 0 秒 fail-closed, 0 次 forced clone solve attempt.**

#### Fallback normal master 阶段

```json
{
  "status": "UNKNOWN",
  "wall_time": 302.116,
  "deterministic_time": 673.50,
  "branches": 5574230,
  "conflicts": 15380,
  "binary_propagations": 799437315,
  "integer_propagations": 154387574,
  "hinted_literals": 798,
  "search_branching": "SearchBranching.FIXED_SEARCH"
}
```

5 分钟 5.57M branches + 8 亿 propagation, 跟 trial7 1h UNKNOWN / v8 sliced 5 min UNKNOWN 同 quality.

### Candidate-size 依赖性 (新发现)

我把 greedy hint 套到不同 ghost rect 大小测一遍 compatible anchor count:

| Ghost rect (w×h) | Total anchors | Compatible | 比例 |
|---|---|---|---|
| 8×8 | 3969 | 611 | 15.4% |
| 10×10 | 3721 | 469 | 12.6% |
| 12×8 | 3717 | 363 | 9.8% |
| 15×15 | 3136 | 149 | 4.8% |
| 20×15 | 2856 | 0 | **0.0%** |
| 27×15 | 2464 | 0 | **0.0%** |

**v10 preflight 在小 candidate (area ≤ 225) 上能 trigger, 在大 candidate (area ≥ 300) 上永远 0 compatible**. 我们项目目标是 `max_lex` 大面积, 大 candidate 上 preflight 等于 no-op.

### 错估根因

v10 假设 "我们有 complete 266-facility witness 跟 blueprint align". 实际:
- Community blueprint 只有 225 mandatory (用户手调蓝图就摆了 225 个, 缺 41 个: 3 boundary_port + 3 grinder + 3 packaging + 1 protocol_core + 31 其他)
- 缺的 41 个 mandatory 由 greedy heuristic 填充
- Greedy 不知道 blueprint 留 27×15 空地, 把这 41 个摆进了 blueprint 留空区域
- Merge 后 266 facility 占 3122 格, 破坏了 blueprint 的 27×15 空地

**v10 算法本身 sound + 严格性兼容 + 比 v8 工程更干净**. 但 **data 前提不满足** → preflight 在大 candidate 上永远不 trigger → 实测 ROI = 0.

### 跟 v8 / v3 错估对比

| | v3 (5/13) | v8 (5/16 早) | v10 (5/16 晚) |
|---|---|---|---|
| 类型 | 算法错估 | 算法错估 | **前提错估** |
| GPT 假设 | build 慢 | anchor choice 撑搜索树 | 我们有 complete blueprint witness |
| 真相 | solve 才是瓶颈 | facility placement 是瓶颈 | 我们 blueprint 缺 41 个, greedy 填的位置跟 blueprint 不 align |
| 改完真效果 | build 加速 | build 加速 -92% (solve 不变) | preflight 在 large candidate 永不 trigger |
| 严格性 | ❌ (5h 自己推翻) | ✓ | ✓ |
| 实测 verdict | ❌ | ❌ | ❌ (data-bound, 非 algorithm-bound) |

### 破解 v10 的可能路径 (都不在 v10 patch 范围内)

1. **扩展用户 blueprint 到 266 facility 全 align**: 用户手动加 41 个 facility 进 blueprint, 数据 schema match. 这是几小时人工.
2. **改 greedy heuristic 尊重 blueprint 空地**: greedy 跑时把 blueprint 留空区域 mask 掉. 改 heuristic 代码, 工作量大.
3. **给 preflight 加 partial witness mode**: 允许 incomplete hint + missing 部分让 CP-SAT 搜索. 但这就回到原 master 搜索难度.

这 3 条都不是 v10 patch 自己能解决的 — patch 是算法侧, 这些是 data/heuristic 侧.

---

## 操作记录

worktree: `~/claude-pj/zmd_v10_test/zmd` (基于 HEAD `634c0bd`, 应用 v10 patch)

主 tree 没接受 v10 patch — 实测确认在我们 data 下 ROI=0, 改动留 worktree + patch 归档, 不进 src.

---

## 相关文档

- `docs/lever_verdicts.md` — Path 8 (L12, v8) + L13 (v10) verdict 更新
- 主 memory `project_v10_witness_preflight_dead.md` — 整 session 状态
- 上一个 v8 verdict 归档: `docs/research/v8_anchor_slicing_smoke_20260516/`
- v9 review 包 `~/linwin_share/zmd_code_v9.zip` — 历史 (v8 verdict 那次给 GPT)
