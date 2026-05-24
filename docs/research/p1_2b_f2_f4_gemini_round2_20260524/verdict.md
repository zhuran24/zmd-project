# F2/F4 Gemini Round 2 verdict (2026-05-24)

Round 2 cross-check on commit `01d368a` (post round 1 fix).

## Gemini verdict: GO_WITH_MINOR

R1 fix CORRECT (both R1#1 iterative DFS + R1#3 bitset padding). 3 new finding +
3 disproved sanity hypotheses + clean F4 deep review.

## R1 fix verify (Gemini round 2)

- **R1#1 iterative DFS**: CORRECT. "完美模拟了递归调用栈". stack/pushed/path_edges
  入栈出栈逻辑等价 recursive fall-through. iter_ptr advance on dead-end +
  return d on sink-found 都对应 recursive 两 path.
- **R1#3 bitset padding**: CORRECT. `_decode_bitset` 公式统一; `extra_bits` 越界
  校验严密. 8 的非整数倍 grid_size latent bug 解.

## Round 2 new findings

### F1 [HIGH] cutset_oracle.py:118 — Phase 1.5+ node-split cell-cap cross-check 会静默 drop

跟 round 1 R1#2 重复 — Phase 1.5+ cell-cap 模式下 internal v_in→v_out 切 →
side_a/side_b 划分但 `_cross_partition_edges` recompute miss → cross-check fail
→ 静默 drop cut. **Phase 1.5+ defer** (与 R1#2 同 root cause).

### F2 [MEDIUM] families/cutset.py:149 — `cut_size` 命名 misleading + edge_capacity>1 假设

Validator 用 `len(current_cut_edges) != cert_cut_size`. Phase 1.2 `edge_capacity=1`
所以 `cut_capacity == |edges|`, OK. Phase 1.5+ 非 1 weighted edge 时, `cut_capacity ≠ |edges|`
→ validator 误杀合法 cut. **Phase 1.5+ defer** (重命名 cert schema `cut_size →
cut_capacity` + validator 累加 capacity 而非 len).

### F3 [LOW] component_reach_oracle.py:136 — F4 cert 漏 `blocking_facilities` 字段 (FIXED this round)

Spec 04_component_reach.md §3 列 `blocking_facilities` 为必填 (非 Optional).
v1.1 validator (Gemini round 16 A1) 不依赖具体 pose ID 但 spec contract 仍要求
cert carry 此字段. Generator 完全 omit 这个 key.

**Fix landed**: `component_reach_oracle.py:_build_component_reach_cut` cert
payload 加 `"blocking_facilities": []` + 注释解释 v1.1 留空 contract, Phase 1.5+
causation split 时填真值 `(group_id, slot_index, pose_id)`.

## F4 component_reach deep review (Gemini)

- BFS connectivity / boundary: 无懈可击, validator `_validate_recomputed_components`
  对 src/sink component 严格 cert-vs-recomputed equality, free_cells 扩 → 自然
  unsound 出局.
- Separator extraction: `extract_frontier_separator` 通过 `blocked_for_separator`
  过滤只取 `cell_owner ∪ ghost_cells`, 故意 exclude `exterior_blocks` —
  validator `_validate_separator_cells` 严格对齐.
- Cert schema soundness: v1.1 剥离 `blocking_facilities` ID 校验是架构进步,
  evaluator (hot path) 容忍 component 膨胀 + validator full check 严格 cert
  匹配 — 性能 / soundness 双层平衡.

## Sanity disproved (Gemini, 3 个)

1. Iterative DFS 残差图死循环 → disproved (level monotone increasing + iter_ptr
   保证 phase 内每边最多 1 次).
2. `_has_patch_escape` 网格边界误报 → disproved (outside_free 定义).
3. F4 hot path component 扩大但仍未连通返 True → disproved (geometric cut 哲学,
   连通状态 = 几何 infeasible, separator ID 不依赖).

## Gate state (post-F3 fix, commit pending)

- pytest cuts: 292 passed (Round 2 fix 加 cert key 不破 test, 因 validator 不
  check 此 key)
- mypy --strict 28 src 0 errors
- ruff clean

## Decision: 进 Round 3 还是 close?

按 v3 协议 stop 条件: "GO 或只剩 nice-to-have / Phase 1.5+ defer 的 minor".

Round 2:
- F1 HIGH + F2 MEDIUM 都明确 Phase 1.5+ defer (与 spec 设计一致)
- F3 LOW 已 fix this round

**剩下符合 stop 条件** → close round 2 +  跑 round 3 快 verify F3 fix + 真没新
finding 后 close.

Round 3 简短 prompt (verify F3 + 找最后第 4 finding).
