# Cut Family 4 — component_reach (完整 spec, 复用 D2 separator)

> **Status**: Day 17e v1.1 (2026-05-21) — Gemini round 16 finding A1 修
> **Mode**: geometric (_FAMILY_MODE_MAP)
> **Family_version**: v1.1 (geometric mode 不校验 blocking_facility 具体 pose ID)
> **复用**: `src/search/d2_separator.py` (D2 commodity flow BFS/Tarjan helper, Path 17 死路 留下)

## Changelog

- **v1.0** (Day 17a, commit 83d3242): 初版 spec
- **v1.1** (Day 17e): 修 Gemini round 16 finding A1 — Validator §7 step 4 删
  对 `blocking_facilities` 具体 pose ID 的校验. Geometric 哲学 "只认空间, 不
  认 ID", 强行校验 ID 破坏跨排列 (permutation) soundness 误杀合法 cut. Causation
  split 是 literal-based cut (F3/F7) 专利, geometric cut 不需要. cert 仍 carry
  `blocking_facilities` 字段作 debug/audit 用, validator 不依赖它判 sound.

## 1. 数学定义

belt routing 要求 commodity flow 从 src 流到 sink, free_cells 上必须存在
belt-traversable path. Family 4 拦截:

```
∃ (commodity c, src_c, sink_c) s.t.
    BFS on state.free_cells from src_c 不可达 sink_c
    ⇒ INFEASIBLE (component disconnect)
```

跟 Family 2 cutset 区别:
- Family 4: 单一 commodity 不连通 (binary reachability)
- Family 2: multi-commodity 共享 cut, 总 demand > min-cut capacity (quantitative)

Family 4 更弱 (cap inferred 单一 commodity 即可), Family 2 更强 (覆盖 capacity).

## 2. Soundness proof

state.free_cells 上 BFS connected component 唯一. 若 src ∈ comp_A, sink ∈ comp_B,
A ≠ B → 没有 belt path → flow infeasible.

scope: state.free_cells 跟 ghost + cell_owner 一起单调缩. cell_owner change
可破连通, 必带 multi-literal carry blocking facility.

## 3. Cert payload schema

```python
@dataclass(frozen=True)
class ComponentReachCert:
    """cert_kind = "bfs_disconnect_witness"."""
    src_cell: Tuple[int, int]
    sink_cell: Tuple[int, int]
    commodity_id: str
    src_component_bitset_b64: str            # base64 src 所在连通分量 bitset
    sink_component_bitset_b64: str            # sink 所在分量
    separator_cells: Tuple[Tuple[int, int], ...]  # disconnect 的 boundary cells
    blocking_facilities: Tuple[Tuple[GroupId, int, PoseId], ...]
                                              # 占 separator_cells 的 facility (causation)
    witness_path_attempt: Optional[Tuple[Tuple[int, int], ...]]
                                              # BFS partial path 至 boundary (debug)
```

## 4. Cut object 构造

geometric mode. 但 cell_owner causation 通过 cert.blocking_facilities 表达
(非空 → 多 cause). v1.0 单 cert kind ("bfs_disconnect_witness"), Phase 1 可分
ghost-cause vs cell_owner-cause sub-kind (类似 F7).

```python
cut = Cut(
    family="component_reach", literals=None,
    geometric_payload=canonical_bytes(ComponentReachCert.asdict()),
    scope=CutScope(
        ghost_rect_id=compute_ghost_rect_id(state.ghost_rect),
        blocked_cells_hash=compute_blocked_cells_hash(state),
        ...,
        oracle_abstraction_version="component_reach_v1",
        active_assumptions=(
            Assumption("commodity_route", value=f"{commodity_id}:src={src},sink={sink}"),
        ),
    ),
    cert=OracleCert(cert_kind="bfs_disconnect_witness", ...),
)
```

## 5. Generator (复用 D2 separator)

```python
class ComponentReachOracle:
    name = "component_reach_v1"

    def generate(self, state, master_solution):
        from src.search.d2_separator import compute_bfs_components, find_separator
        cuts = []
        components = compute_bfs_components(state.free_cells)
        for commodity in master_solution.commodities:
            src_comp = components[commodity.src]
            sink_comp = components[commodity.sink]
            if src_comp != sink_comp:
                # disconnect
                separator = find_separator(components, commodity.src, commodity.sink, state)
                blocking = identify_blocking_facilities(separator, state.cell_owner, state.groups)
                cert = ComponentReachCert(
                    src_cell=commodity.src,
                    sink_cell=commodity.sink,
                    commodity_id=commodity.id,
                    src_component_bitset_b64=encode_bitset(src_comp),
                    sink_component_bitset_b64=encode_bitset(sink_comp),
                    separator_cells=tuple(separator),
                    blocking_facilities=tuple(blocking),
                    witness_path_attempt=None,  # debug only
                )
                cuts.append(construct_component_reach_cut(state, cert))
        return cuts
```

## 6. evaluate_geometric

```python
def evaluate_geometric_component_reach(cut: Cut, state: BState) -> bool:
    """重算当前 state.free_cells 上 src/sink BFS 是否仍 disconnected."""
    cert = decode_component_reach_cert(cut.geometric_payload)
    from src.search.d2_separator import compute_bfs_components
    components = compute_bfs_components(state.free_cells)
    return components[cert.src_cell] != components[cert.sink_cell]
```

注意: 这跟 Family 1 v1.1 "无条件 True" 不一样 — Family 4 partition 是 state-
dependent (cell_owner 改可能 reconnect). 必须 hot path 重算.

## 7. Validator

```python
class ComponentReachValidator(CutValidator):
    family = "component_reach"
    validator_version = "v1.0"

    def validate(self, cut, state) -> ValidationResult:
        cert = decode_component_reach_cert(cut.geometric_payload)
        # 独立 BFS on cur free_cells
        components = compute_bfs_components(state.free_cells)
        if components[cert.src_cell] == components[cert.sink_cell]:
            return ValidationResult("unsound", ..., "src/sink reconnected in cur state")
        # 验 cert.src_component bitset 跟 BFS 结果 match
        recomputed_src = encode_bitset(components[cert.src_cell])
        if recomputed_src != cert.src_component_bitset_b64:
            return ValidationResult("unsound", ..., "src_component bitset mismatch")
        # 验 separator_cells 全在 (cell_owner ∪ ghost) (不是 free)
        # v1.1 (Gemini round 16 finding A1): geometric mode 只验空间, 不验 ID.
        # 谁占了 separator_cell 不重要, 只要它不在 free_cells 就够 sound.
        for sep_cell in cert.separator_cells:
            if sep_cell in state.free_cells:
                return ValidationResult("unsound", ..., f"separator cell {sep_cell} is free")
        # v1.0 step 4 删除: validator 不再校验 cert.blocking_facilities 具体
        # pose ID — geometric cut 哲学是"只认空间不认 ID", 强行校验 ID 破坏跨
        # permutation soundness. cert.blocking_facilities 仍 carry 但只作
        # debug/audit, validator 不依赖.
        return ValidationResult("ok", ...)

    def evaluate_geometric(self, cut, state):
        return evaluate_geometric_component_reach(cut, state)
```

## 8. Replay + watcher

watcher:
- by_cell_watcher (separator_cells 每 cell)
- by_commodity_watcher (commodity_id)
- by_ghost_watcher (Day 17d 加 6 维)

## 9. Open questions

1. **Multi-component**: cert 只 carry src/sink 两 component. 多 commodity 共享
   separator 时, 是否合并 cut. Phase 1 evaluate.
2. **Cell_owner causation split** (类 F7): v1.0 cert.blocking_facilities carry
   但 cut 是 geometric (不进 literals). Phase 1 决定要不要拆 sub-kind.
3. **跟 Family 8 power_grid_reach 区别**: Family 4 是 belt graph (连续 free_cells),
   Family 8 是 power pole 跃迁 graph (R_conn radius). 两者 schema 分开 (Day 17b).

## 10. 验收

- ✅ 数学 (BFS disconnect) + soundness (component 唯一)
- ✅ Cert + cut + generator (D2 separator 复用) + evaluate_geometric (hot path
  重算, 跟 Family 1 简化版区别) + validator + replay
- ⏸ Phase 1 实施 src/cuts/families/component_reach.py
