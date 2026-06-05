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
**(2026-06-04 现状)** F2 / F3 / F4 generator **已在 Phase 1.2 落地**（F3 special-case commit `c768806`；F2 `cutset_oracle` Dinic max-flow；F4 `component_reach_oracle` BFS edge-only）。Phase 1.5+ 待补的是 **production 增强**（F2 node-split 模式 + LP dual witness / F3 `active_port_witness` / F4 cell-flow capacity），不是整个 generator。下列是这些增强的设计预留：

- **F2 cutset**: 复用 PCR-CUT `patch_routing_core.run()` (Phase 0-1 GO 但 Phase
  5 multi-anchor verdict NOT GO — 仍可作 generator 模板, paradigm 死的部分是
  跨 anchor 收敛, 单 cut 生成本身 OK)
- **F3 port_exposure**: 直接遍历 `state.cell_owner` + `candidate_placements`
  pose ports, 找 front_cell 被占的 case
- **F4 component_reach**: 复用 `src/search/d2_separator.py` BFS components +
  find_separator
- **F5 pattern_nogood**: deletion / QuickXplain 复用 L16 artifact `src/cuts/helpers/bounded_core_minimizer.py`
- **F6 / F8 / F9**: 各自 spec §5 generator pseudocode

### 13.4 F3 active_port_witness verify (production-前置 risk)

**严重度**: production-前置 risk for F3 default-enable (per GPT pro v17 四审
Reviewer A M1 + Reviewer B A3).

- spec `03_port_exposure.md:144-147` 要求 verify `active_port_witness_b64`
- 当前 Phase 1.2 F3 generator stage 1 写 `active_port_witness_b64=None`
  (`src/cuts/oracles/port_exposure_oracle.py`，搜符号 `active_port_witness_b64`；硬编码行号随文件增长漂，不写死)
- 当前 validator 没查此字段 (src/cuts/families/port_exposure.py)
- Phase 1.1 v1.0 假设 "all listed ports active"
- Phase 1.5+ 真 production data 时可能有 port 被 binding boundary_constraints
  LP disable; F3 的 cut `(facility A pose pA) ∧ (B pose pB) ⇒ ⊥` 假设 port 必
  active. 若 binding 选 optional port subset, 没接的 port front 被堵不构成
  infeasibility (历史 dead path: B1 Phase 5 cell-cut 死路记录在 `docs/research/` 的
  `paradigm_search_review_v12*` 归档 + `docs/lever_verdicts.md` 已证过强 cut 会误剪).

**GPT v17 reviewer 共识**: F3 special-case phase fixture / env-gated stage 1
可 GO_WITH_MINOR (`EXACT_F3_GENERATOR_ENABLED=1` default-off), 但**生产默认开启
前必须**二选一:
  - 选 1: validator 真验 `active_port_witness_b64` (cand C
    boundary_constraints LP solution wrap, 见 §13.5 F2 类似路径)
  - 选 2: P1.3A / P1.5 把 port-active 决策上收到 master, 让 literal 本身带
    active port 条件

不做此 fix 前, F3 不应被描述为 "完整生产 cut family 已关闭". Phase 1.5+ 启动
production F3 前 hard gate.

Reviewer 报告 archive: `docs/research/p1_2b_f3_gemini_round{1,2}_20260526/`
+ GPT v17 zip review 在 main 对话 archive.

### 13.5 F2 max_flow_LP algebraic witness
- spec `02_cutset.md:156-159` 要求 verify max-flow LP dual
- 当前 defer Phase 1.5+
- 接真 commodity routes + LP solver 后实施

---

