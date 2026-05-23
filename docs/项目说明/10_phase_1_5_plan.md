# 10 — Phase 1.5+ plan (production integration)

Phase 1.3 framework 跑通后接真生产 data + 真 oracle. GO 标准见 §8.4.

### 13.1 commodity registry production inject
- 当前 `BState.commodity_demands` / `commodity_routes` Phase 1.1 mock 注入
- Phase 1.5+ 真 inject 路径: 从 `data/preprocessed/commodity_demands.json` +
  routing planner output + master_solution.commodities 真 build
- 设计 `build_bstate_from_production_inputs()` 统一入口, 覆盖:
  - canonical_rules + facility_templates
  - mandatory_exact_instances + instance_to_facility_type
  - candidate_placements
  - commodity demand / routes (从 production data)
  - source_digest 真 hash

### 13.2 registry schema 评估 (route_id vs commodity_id)
GPT v5 / v6 提出: 当前 `{commodity_id: {"src", "sink", "demand"}}` 只支撑
"一 commodity 一 route". 真生产同 commodity 可能多 src/sink pair (e.g.
`blue_iron_ore` 多 mining tile → 多 refinery).

候选 schema:
```python
commodity_routes: {
    route_id: {
        "commodity_type": str,
        "src": (x, y),
        "sink": (x, y),
        "demand": int,
    }
}
```

cert 改用 `contributing_route_ids` 不是 `contributing_commodities`.

**决策点**: Phase 1.5+ 真生产 commodity registry data 设计时定. 不提前 refactor
— 当前 Phase 1.1 / 1.2 / 1.3 不需要多 route 语义, 提前改 schema 风险 over-engineer.

### 13.3 各 family oracle 真实施
当前 F2 / F3 / F4 oracle 是 stub `return []`. Phase 1.5+ 接真 generator:

- **F2 cutset**: 复用 PCR-CUT `patch_routing_core.run()` (Phase 0-1 GO 但 Phase
  5 multi-anchor verdict NOT GO — 仍可作 generator 模板, paradigm 死的部分是
  跨 anchor 收敛, 单 cut 生成本身 OK)
- **F3 port_exposure**: 直接遍历 `state.cell_owner` + `candidate_placements`
  pose ports, 找 front_cell 被占的 case
- **F4 component_reach**: 复用 `src/search/d2_separator.py` BFS components +
  find_separator
- **F5 pattern_nogood**: deletion / QuickXplain 复用 L16 `core_minimizer.py`
- **F6 / F8 / F9**: 各自 spec §5 generator pseudocode

### 13.4 F3 active_port_witness verify
- spec `03_port_exposure.md:144-147` 要求 verify `active_port_witness_b64`
- 当前 validator 没查 (Phase 1.1 v1.0 假设 "all listed ports active")
- Phase 1.5+ 真 production data 时可能有 port 被 boundary_constraints LP
  disable, 必加 witness 验

### 13.5 F2 max_flow_LP algebraic witness
- spec `02_cutset.md:156-159` 要求 verify max-flow LP dual
- 当前 defer Phase 1.5+
- 接真 commodity routes + LP solver 后实施

---

