# v8 anchor slicing 实测归档 — 2026-05-16

GPT Pro 在 v7 review 包基础上, 针对 Path 8 (ghost-anchor disjunctive decomposition) 给出 v8 完整 patch + 交付包. 本目录归档该 patch + 我们本地实测数据 + verdict 数据点.

**verdict**: Path 8 实测**死路**. 跟 GPT v3 错估同源 — build 阶段优化真实有效 (-92%), 但 solve 阶段没改善, 单 anchor 5 分钟仍 UNKNOWN. 跟 trial7 1h UNKNOWN 在 quality 上一致.

---

## 文件清单

| 文件 | 内容 |
|---|---|
| `gpt_PATCH_SUMMARY.md` | GPT 自己写的 patch 说明 (核心算法 + 安全边界 + 环境变量) |
| `gpt_VALIDATION.md` | GPT 自己跑过的验证 (61 测试 + py_compile + ruff) |
| `zmd_anchor_slicing_v8.patch` | 完整 patch (1620 行, +1177/-107, 9 文件) |
| `v8_pytest_2211_pass.log` | 我本地全套 pytest 结果 (2211 passed / 60 skipped / 0 failed) |
| `smoke_master_iter1.log` | 30 min smoke 跑出来的 main.py stdout (6 行) |
| `anchor_slice_manifest_27x15.json` | dispatcher 写出来的 anchor partition manifest |
| `exact_campaign_state.json` | smoke 跑完 campaign 终态 |
| `exact_campaign_telemetry.json` | smoke telemetry |

---

## 关键数据点

### Patch 整合验证

- 外层 SHA256 跟 GPT 给的对得上: `e435404d3ef5bcef5efdebfd559d1278a31123212e900e5eb7f662808ef32c27`
- 内层 SHA256SUMS 全 20 文件 ✓
- 直接 `git apply -p1` 到 HEAD `2ec6b32` clean apply (无 hunk fuzz)
- 全套 pytest: **2211 passed + 60 skipped + 0 failed** (4 分 9 秒, 比 baseline 2207 多 4 个新测试)

### Build 阶段实测 (`build_exact_core → from_exact_core`, 27×15 ghost, power_coverage=on)

| 指标 | Full overlay | Single slice@(22,28) | Δ |
|---|---|---|---|
| from_exact_core wall | 53.7 s | 4.5 s | **-92%** |
| proto vars | 19406 | 16943 | -13% |
| proto cons | 56452 | 38578 | -32% |
| RAM after build | 3.83 GiB | 2.96 GiB | -23% |
| ghost anchors | 2464 | 1 | filter 工作 |

Slicing 在 build 阶段大幅减负. **但 build 不是项目瓶颈, solve 才是**.

### Anchor 数量

70−27+1 = 44 个 x 位置, 70−15+1 = 56 个 y 位置, 总共 **2464 个 anchor**.

`signature_tightening_anchor_reductions` 只剪 44 (约束, 不是 anchor 个数). `power_capacity_screened_disabled_placements` = 0 (没有 anchor 被预筛掉). **placements 还是 2464**.

完整 partition 即使每 slice 1 min = **41 小时**, 超 1h 时间预算; 实测每 slice 5 min UNKNOWN = **205 小时**, 完全不可行.

### Smoke 实测 — Single anchor 5 分钟 UNKNOWN (跟 trial7 同 quality)

跟 trial7 同 candidate selector + community hint 注入 + slicing on (MAX_ANCHORS=5):

```bash
EXACT_MASTER_GHOST_ANCHOR_SLICE_MODE=1 \
EXACT_MASTER_GHOST_ANCHOR_SLICE_MAX_ANCHORS=5 \
EXACT_MASTER_GHOST_ANCHOR_SLICE_RESUME=1 \
EXACT_COMMUNITY_BLUEPRINT_HINT_PATH=data/hints/blueprint_2026_05_13_master_hint.json \
.venv/bin/python main.py \
  --campaign-hours 0.5 --master-seconds 300 --binding-seconds 300 --routing-seconds 300 \
  --start-area 410 --min-side 15 --max-aspect-ratio 1.9 \
  --parallel-processes 1 --skip-readiness-gate
```

Process 实际 wall: **5 分 7 秒** (非 30 min 预算). 原因: `EXACT_MASTER_GHOST_ANCHOR_SLICE_CANDIDATE_SECONDS` 默认 = `master_seconds` = 300, candidate-level deadline 切断 → 跑完第 1 个 anchor 就 退出. outer_search 看到 UNKNOWN 后 `EXACT_OUTER_SKIP_UNKNOWN=1` (production wrapper default) terminal stop.

Anchor 0 (x=0, y=0) 数据 (从 manifest 提取):

| 指标 | 值 |
|---|---|
| elapsed_seconds | 307.76 |
| status | UNKNOWN |
| `master_last_solve.branches` | 5,510,114 |
| `master_last_solve.conflicts` | 811 |
| `master_last_solve.binary_propagations` | 293,533,133 |
| `master_last_solve.integer_propagations` | 295,507,413 |
| `master_last_solve.deterministic_time` | 746.28 |
| `master_hinted_literals` | 798 (= 266 × 3, 完整注入) |
| `mandatory_pose_literal_count` | 3,853,132 |
| `residual_optional_pose_literal_count` | 13,398,531 |
| `master_interval_count` | 3148 |
| `ghost_anchor_count` (after slicing) | 1 |

也就是说 — CP-SAT 真在搜 (5.5M branches), 不是 0 秒 trivial INFEASIBLE (跟 isolated 测试不一致, 证实 LBBD 整链路径跟 isolated build 不同 model). 但 5 分钟搜了 5.5M branches + 8 亿 propagation 还是 UNKNOWN.

### 根因分析

锁 ghost anchor 后, master 内部的 mandatory pose literal 还有 **3,853,132 个候选**. 即使 ghost anchor 只剩 1 个, 266 个 mandatory facility 的几何摆放 search space 没变小. **搜索难度的主体来自 facility placement, 不是 ghost anchor choice**.

Path 8 的核心假设 "anchor choice 撑开搜索树" 跟实测数据冲突. 实测说: 撑开搜索树的是 facility placement, anchor choice 只是搜索树最外层的一层.

### 跟 GPT v3 错估对比

| 项目 | GPT v3 (5/13) | GPT v8 (今天) |
|---|---|---|
| 关注的瓶颈 | "build 慢" (300s 沙盒不完) | "anchor choice 撑开搜索树" |
| 改完真效果 | build 加速 | build wall -92% |
| solve 阶段 | 没改善 | 没改善 (5 min UNKNOWN, 5.5M branches) |
| 失败原因 | 错把 build 当瓶颈 | 错把 anchor choice 当搜索主导因素 |
| 严格性兼容 | 不兼容 (自己 audit 推翻) | 兼容 (fail-closed 设计正确) |

工程上 v8 比 v3 干净 (没破 exactness, 没做 unsafe). 但 **ROI 是负的**, 改完不破局.

---

## 操作记录

worktree: `~/claude-pj/zmd_v8_test/zmd` (基于 HEAD `2ec6b32`, 应用 v8 patch)

主 tree 没接受 v8 patch — 实测确认死路, 改动留在 worktree + patch 归档, 不进 src.

---

## 相关文档

- `docs/lever_verdicts.md` — Path 8 verdict 更新 ❌
- 主 memory `project_v8_anchor_slicing_dead.md` — 整 session 状态
- v7 review 包 `~/linwin_share/zmd_code_v7.zip` — 历史
