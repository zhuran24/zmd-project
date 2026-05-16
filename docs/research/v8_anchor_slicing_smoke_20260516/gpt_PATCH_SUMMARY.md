# Patch summary

## 要解决的瓶颈

原模型把所有 ghost anchor 作为同一个 master 中的 optional overlay 一次性展开。搜索树最先被 anchor 选择本身撑开，之后才进入布局、binding、routing 的精确证明。这个补丁把 ghost anchor 析取拆成逐 anchor exact partition:

```text
candidate feasible  <=>  exists anchor a: fixed-anchor slice(a) feasible
candidate infeasible <=>  all anchors a: fixed-anchor slice(a) infeasible
```

这样每个 slice 只保留一个 ghost anchor，去掉 master 内对同一 ghost rectangle 的大规模 anchor-choice branching。

## 精确性不变

- slice 内仍走原 `certified_exact` Benders 流程。
- 每个 slice 只通过 `EXACT_MASTER_GHOST_ANCHOR_FILTER=x,y` 固定一个析取分支。
- 任意一个 slice CERTIFIED，父 candidate CERTIFIED。
- 只有完整 anchor partition 全部 terminal INFEASIBLE，父 candidate 才 INFEASIBLE。
- 时间、cap、UNKNOWN、UNPROVEN、manifest 不完整都不会升级成 INFEASIBLE。

## 时间约束不扩张

默认 `EXACT_MASTER_GHOST_ANCHOR_SLICE_CANDIDATE_SECONDS` 等于原传入的 `master_seconds`。slice loop 在每个 anchor 前检查 candidate wall-clock deadline 和 campaign remaining time。到点后返回 UNKNOWN/UNPROVEN，并写 manifest 供下次继续。

## 关键实现

- `src/search/benders_loop.py`
  - 新增 `EXACT_MASTER_GHOST_ANCHOR_SLICE_MODE` / `EXACT_GHOST_ANCHOR_SLICING` dispatcher。
  - 新增 manifest resume、signature invalidation、atomic save。
  - 新增 per-anchor env 注入和 hint suffix，避免不同 anchor hint 互相污染。
  - 新增 parent proof summary 的 `anchor_slicing` 字段。
  - 修复 filtered overlay 下 ghost-conditioned cut replay 的 original/local anchor 解析。
- `src/models/master_model.py`
  - ghost domain 增加 `original_anchor_idx` 和 `local_anchor_idx`。
  - build stats 增加 `total_unfiltered_placements` 和 `filtered_original_anchor_indices`。
- `src/models/exact_coordinate_master.py`
  - 与 legacy master 保持同样 anchor metadata。
- `scripts/preflight_gate.py`
  - preflight 单测前剥离 slicing runtime env，避免 shell 环境污染测试默认行为。
- `docs/env_variable_index.md`
  - 增加所有 slicing env 索引。
- `docs/phase3c_ghost_anchor_slicing_breakthrough_20260516.md`
  - 记录算法、运行方式、manifest、安全边界。
- `CHANGELOG.md`
  - 增加 Phase 3C ghost anchor slicing 记录。
- `src/tests/test_ghost_anchor_filter.py`
  - 覆盖 original anchor index 稳定性和 sliced cut replay fail-closed。
- `src/tests/test_anchor_slice_resume_manifest.py`
  - 覆盖 capped UNKNOWN 后从 manifest 续跑到完整 INFEASIBLE。

## 新环境变量

| Name | Default | 作用 |
|---|---:|---|
| `EXACT_MASTER_GHOST_ANCHOR_SLICE_MODE` | 0 | 启用逐 anchor 精确分区 |
| `EXACT_GHOST_ANCHOR_SLICING` | 0 | 短别名 |
| `EXACT_MASTER_GHOST_ANCHOR_SLICE_CANDIDATE_SECONDS` | `master_seconds` | 单 candidate slicing 总墙钟预算 |
| `EXACT_MASTER_GHOST_ANCHOR_SLICE_MAX_ANCHORS` | 0 | 单次最多新评估 anchor 数，0 表示不限 |
| `EXACT_MASTER_GHOST_ANCHOR_SLICE_RESUME` | 1 | 是否续写 manifest |
| `EXACT_MASTER_GHOST_ANCHOR_SLICE_MANIFEST_PATH` | `data/checkpoints/anchor_slice_manifests/<candidate>.json` | manifest 文件或目录 |
| `EXACT_MASTER_GHOST_ANCHOR_FILTER` | empty | 单 master ghost anchor 白名单，格式 `x,y;x,y` |
