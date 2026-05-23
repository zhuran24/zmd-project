# 08 — Phase 1.2 plan (P1.11 入门 + P1.11-P1.15 五 family)

进 F5-F9 实施前必清这几项. 全是 schema / spec / static hygiene, 不动 paradigm.
GO 标准见 §8.1.

### 10.1 strict registration gate default ON
- 文件: `src/cuts/replay.py:122`
- 改: `EXACT_FAMILY_VALIDATOR_STRICT` default `"0"` → `"1"`
- 影响: 未注册 family 进 replay → `NotImplementedError` 不 silent attach
- F1-F4 已注册, 切换不影响当前
- F5-F9 实施时每加 1 个必 register, 测试覆盖
- **风险**: 若任何调用方依赖默认非 strict (e.g. 半实施 fixture), 切换会破.
  mitigation: grep 现 codebase 看 strict env 使用; 切换前 dev env 显式
  `EXACT_FAMILY_VALIDATOR_STRICT=0` override

### 10.2 spec docs align (必修 #7)
- `state_machine_v2.md:42-45`: PoseId 改 `str` (src `lifecycle.py:42-49` 已是 str)
- `cut_lifecycle_v2.md:225-241 / 365-374 / 740-747`: 删 `symmetry_lift`, 加
  `power_grid_reach` / `density_envelope`
- `cut_family_specs/03_port_exposure.md:39-44`: direction 改 `N / S / E / W`
- `cut_family_specs/01_region_capacity.md:139-145`: region_kind 加 `left_or_bottom_union`
- `cut_family_specs/02_cutset.md:64-77 / 156-159`: cert schema 加 `contributing_commodities`
  集合语义 + cross-partition route 描述 (Step M+N)
- `cut_family_specs/04_component_reach.md:48-77 / 145-150`: commodity_id /
  commodity_route assumption 改 registry require, separator in-grid + ∈
  owner∪ghost 描述
- **风险**: spec 改完未跟 src 跨同步则下次 audit 反复触发 spec drift finding.
  mitigation: 每 spec 改加单元 test grep spec line vs src 值

### 10.3 source_digest 真 hash
- 当前 `lifecycle.py:635-637` + `oracles/region_capacity_oracle.py:179-186`
  写死 `"poc_source_digest"`
- 改: hash `canonical_rules.json + candidate_placements.json + mandatory_exact_instances.json
  + generic_io_requirements.json + oracle_versions` 内容
- spec 已 require: `cut_lifecycle_v2.md:881-903 / 80-86 / 146-154`
- 不修则 replay 不能识别 data source 轮换, 跨 session cert 可信度差
- **风险**: hash 函数选错 (e.g. mtime instead of content) 导致 cert 跨 session
  失效. mitigation: 内容 sha256, 不用 mtime

### 10.4 ghost_rect tuple 语义 lock
- 当前 `lifecycle.py:216` 注释 `(x, y, h, w)`, `helpers/ghost_geometry.py:108-116`
  返回 `(x, y, x+h, y+w)` — h/w 跟常规 (x+w, y+h) 反
- F8 power_grid_reach 实施前必锁:
  - 写明 schema: `(x, y, height, width)` 或改 object `{"x", "y", "height", "width"}`
  - 加非方形 fixture, e.g. `(10, 20, 3, 7)` verify AABB
- 否则 F8 接真 ghost_rect 时横竖反
- **风险**: 改 object schema 影响多处 helper + 测试; 改名 `x_span/y_span`
  减名 confusion 但仍是 tuple. mitigation: 倾向 object schema, 一次性改清

### 10.5 mypy strict 收尾
- 37 errors / 10 files, 主要泛型缺参 + Any return + unused ignore
- 重点收: `lifecycle.py` (`BState`) + `replay.py` + 4 family validator
- 让 schema 类型契约真在 type system 内 enforce
- **风险**: 收 strict 时改 type signature 影响 callers. mitigation: 小步 commit
  每次改 1 file mypy clean

### 10.6 拆 validator helper (radon D 级降)
- `validate_cutset D(27)` 拆: parse_cert / partition_disjoint / partition_subset_free /
  enclosure / cut_edges / commodity_registry / cross_partition / witness
- `validate_component_reach D(24)` 拆: components_disjoint / membership /
  recompute_bfs / separator / commodity_registry
- `validate_port_exposure D(23)` 拆: parse_cert / front_cell_math /
  blocking_pose_binding / literal_multiset / port_exists
- `validate_region_capacity C(20)` 顺手拆 cells_per_pose / demand /
  gap_consistency
- 不只是好看 — Step J/K/L/M/N/O 反复在最大函数里漏接线 invariant, 拆开后下次
  audit reviewer 更易定位
- **风险**: 拆后破坏现有 regression test. mitigation: 每拆一个 validator 跑
  完整 cuts test 不变

### 10.7 evaluate_literal_port_exposure 决定
- vulture 标 unused (走 generic `evaluate_literal_multiset`)
- 选项 a: 删 (统一 generic path)
- 选项 b: 接进 `step_7_evaluate_cut` literal dispatch 作 F3 specific evaluator
- 倾向 a (factual simpler, sound 不变), Phase 1.2 入门一行决定

---

## 11. Phase 1.2 P1.11-P1.15 实施 (5 new family)

入门完后进 5 family 实施. 每 family 单独 commit (≥ 5 commit), 跟 Phase 1.1
同样 cross-check rhythm. GO 标准见 §8.2.

### 11.1 P1.11 F5 pattern_nogood
- 用途: literal-based cut, 拒已知 unsat 状态. lifecycle step 2 minimize 入口
- 实施: `src/cuts/families/pattern_nogood.py` (validator + evaluator) +
  `src/cuts/oracles/pattern_nogood_oracle.py` (从 master infeasible witness 提)
- 复用: L16 `core_minimizer.py` deletion / QuickXplain helper
- spec: `cut_family_specs/05_pattern_nogood.md`
- **风险**: deletion+QuickXplain perf 是 NP-hard. mitigation: 限 ≤ N literal,
  超 N 不 minimize 直接 emit 原 cut

### 11.2 P1.12 F6 shape_packing_hall
- 用途: geometric cut, Hall's marriage theorem 推 region 内 pose 数下界
- 实施: validator (cert.required_count vs region.available_slots) + oracle
  (greedy bipartite match)
- 复用: F1 region helper (region_cells / capacity)
- spec: `cut_family_specs/06_shape_packing_hall.md`
- **风险**: Hall theorem 实施复杂. mitigation: 先 greedy 后 LP

### 11.3 P1.13 F7 power_hitting_set
- 用途: literal-based cut, 必选 power pole set
- 实施: hitting-set greedy minimize + multiset evaluate (复用 F3 path)
- 复用: F3 generic literal evaluator
- spec: `cut_family_specs/07_power_hitting_set.md`
- **风险**: hitting-set NP-hard. mitigation: LP relax 找近似 hitting set,
  validator 验 set 真覆盖

### 11.4 P1.14 F8 power_grid_reach
- 用途: geometric cut, Liang-Barsky AABB + BFS 电网可达
- 实施: `helpers/ghost_geometry.py` 已有 Liang-Barsky helper, 复用
- 前置: ghost_rect tuple 语义必先 lock (§10.4)
- 复用: F4 BFS helper
- spec: `cut_family_specs/08_power_grid_reach.md`
- **风险**: ghost_rect tuple 横竖反 bug. mitigation: §10.4 lock spec + 非方形
  fixture 必先

### 11.5 P1.15 F9 density_envelope
- 用途: geometric cut, region density 上界 (单位 cell pose count)
- 实施: validator (cert.density vs region.area × max_density) + oracle
- 复用: F6 region density helper
- spec: `cut_family_specs/09_density_envelope.md`
- **风险**: 数学 sound 边界 (max_density 怎么算). mitigation: 加 negative test
  覆盖 density 临界

### 11.6 P1.15+ test fixture 补全
- F3 direction E / W synthetic fixture (真数据只 N=273 S=257, E=W=0)
- F8 直接复用 E / W fixture
- ghost_rect 非方形 fixture
- F5-F9 各 family 7-10 test (sound case + ≥ 3 attack 反例 + schema_err +
  adversarial scope)

---

