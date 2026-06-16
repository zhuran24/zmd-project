# B Design v2 Phase 0 Close

> **Status**: Phase 0 ABSOLUTE FINAL CLOSE (2026-05-22)
> **Final verdict (Gemini round 22)**: 🟢 "**带着这份无懈可击的设计, 去开启 Phase 1 吧!**"
> **Total 22 rounds Gemini cross-check (round 14-22) + 9 family + 5 fixture + PoC 14/14 PASS**

## 1. Phase 0 全部 commit (28 个)

按 Day 编号:

| Day | Commit | 内容 |
|---|---|---|
| 1-2 | 976bc10 | boundary source-of-truth 冻结 + double-count bug 修 |
| 3-9 | 64c5317 | state_machine_v2 + cut_lifecycle_v2 双线 design doc |
| 10-12 | 4da7e30 | F1-F4 red fixtures |
| 13 | 3dd3d63 | schema_update_v3 propose 5 gap |
| 14 | f861ba7 | cut_lifecycle v3 land 5 gap |
| 15 | 925157e | Family 1 region_capacity 完整 spec |
| 16a | 30b0a2d | Family 6 shape_packing_hall (v3 新) |
| 16b | 824c9b6 | Family 7 power_hitting_set v1.0 |
| 16c-1 | 75e5f18 | round 14 修 (3 致命 sound + 2 schema 漏) |
| 16c-2 | 1f1e051 | paradigm_death_timeline 27 lever 归档 |
| 16c-3 | cdfbdcb | Gemini round 15 cross-check 带 timeline |
| 16c-4 | edecbd7 | B core PoC (cut lifecycle 9 步 + Family 1 runtime) ✅ 14/14 |
| 17a | 83d3242 | Family 2/3/4/5 spec (复用 PCR-CUT/D2/boundary/L16) |
| 17b | 1c757ff | Family 8 power_grid_reach (F5 反例 owner) |
| 17c | 98daa07 | Family 9 density_envelope (Class C mitigation) |
| 17d | b1ff909 | F1-F4 sweep + F5 fixture + by_ghost watcher v3.2 |
| 17e | 1ece80a | round 16 修 (4 finding) |
| 17f | ab921b1 | round 17 修 (2 finding) |
| 17g | fb2dcb4 | round 18 修 (2 致命) |
| 17h | 260f860 | round 19 修 (F9 致命 + paradigm 降级) |
| 17i | 4be39d0 | round 20 修 (F9 v1.4 area-based) |
| 17j | 7f38842 | round 21 修 (2 False Quarantine) |
| 17k | TBD | round 22 修 (1 行 watcher 漏) + 本 doc |

## 2. 9 大 Cut Family 矩阵 (final state)

| # | Family | Mode | Final version | 来源 | 处理 |
|---|---|---|---|---|---|
| 1 | region_capacity | geometric | v1.2 | F1 反例 | 全局/局部容量 (静态 cap) |
| 2 | cutset | geometric | v1.0 | PCR-CUT 复用 | Menger min-cut |
| 3 | port_exposure | literal | v1.0 | boundary_constraints | port-front blocked |
| 4 | component_reach | geometric | v1.1 | D2 separator | belt BFS disconnect |
| 5 | pattern_nogood | literal | v1.0 | L16 deletion | full no-good (fallback, monitor Class C) |
| 6 | shape_packing_hall | geometric | v1.1 | F2 反例 (v3 新) | Hall interval scheduling |
| 7 | power_hitting_set | literal | v1.1 | F3 + L16 | local CoverSet 空 (causation split) |
| 8 | power_grid_reach | geometric | v1.1 | F5 反例 (v3 新) | global power network disconnect (Liang-Barsky) |
| 9 | density_envelope | geometric | v1.5 | Gemini round 15 (v3 新) | area_capacity_overflow only (paradigm 降级) |

## 3. cut_lifecycle 演进 (v2 → v3.2.2)

- **v2 (Day 3-9)**: 初版 10 步 + AnonymousSlotRef
- **v3 (Day 14)**: literals Optional + geometric_payload 互斥 + _FAMILY_MODE_MAP + GHOST_AGNOSTIC + assumption dispatch
- **v3.1 (Day 16c-1)**: §4 加 blocked_cells_hash 校验 (5→6 步)
- **v3.2 (Day 17d)**: §7 加 6 维 by_ghost_watcher + on_ghost_rect_changed
- **v3.2.1 (Day 17e)**: F3 移出 by_ghost_watcher
- **v3.2.2 (Day 17j)**: CutScope 加 exterior_blocks_hash + Step 3 dispatch (GHOST_AGNOSTIC vs 绑 ghost)

## 4. F1-F5 反例 + F10/F13/F14/F15/F16 反例 verdict

5 red fixture (F1-F5) 都有 owner family. 在 Gemini round 14-22 cross-check 中发现 F10-F16 反例:

| 反例 | round | 应对 |
|---|---|---|
| F5 Power Grid Disconnect | r14 | Family 8 owner ✅ |
| F10 Kinematic Belt Knot (U-turn) | r16 | Family 4 升级 Kinematic Reachability (Phase 1) |
| F13 Planar Crossing Deadlock | r18 | Routing Oracle → Family 5 fallback ✅ |
| F14 Port-Vector Cutset (3x3 270°) | r20 | F9 降级 + Family 5 fallback ✅ |
| F15 Port-Vector Cutset | r21 | Family 5 fallback ✅ |
| F16 Global Algebraic Overload | r22 | **不需 Cut** — Master CP-SAT 1 行线性约束 (`sum(is_placed * power) <= MAX`); **代数归 Master, 几何归 Cut, 架构分工完美** |

## 5. Phase 0 关键 invariant (Phase 1 实施保持)

- **Exactness (精确性)**: FP = 0, 任何 cut 都不能误剪合法解
- **Symmetry (对称性消)**: Group/orbit-count state + AnonymousSlotRef, 消除 10^134 label symmetry
- **Class B/C 兜底**: F5 monitor + 168h campaign exit criteria 第 7 (pattern_nogood >50% = stop-ship)
- **Soundness 双保**: Validator 独立重算 cert + replay 6 步 verify (含 v3.2.2 dispatch)
- **Schema-first 不 retrofit**: B core PoC (14/14) 跨 Phase 1 boundary 验过
- **Scope-aware HOLD vs quarantine**: ghost mismatch HOLD 不删, 真不一致才 quarantine

## 6. Phase 1 起步清单 (defer to Phase 1)

Cross-check 提及但 defer 项:

1. **F4 Kinematic Reachability 升级** (Gemini round 16 F10): cert 加 port_directions field, Stateful BFS A* 寻路
2. **F8 cell_owner causation split v2.0** (Gemini round 16 B3): 类 F7 v1.1, 防 cell_owner 挤压 power network 误剪
3. **F8 watcher BoundingBox 改 PoolPole ∩ BB** (Gemini round 17 B1): 已在 spec 改, Phase 1 实施
4. **F1 §8 add_watchers 加 by_ghost_watcher** (Gemini round 22): 已在 spec 改, 1 行
5. **F9 paradigm 降级 monitor** (Gemini round 19): 168h ratio (F5 vs F9) telemetry
6. **PROJECT_LOCK update**: Phase 0 close 后改 lock — cut object 一等公民边界

## 7. 22 轮 Gemini cross-check 总结 (round 14-22)

| Round | Day | Key finding (新 bug 数) |
|---|---|---|
| 14 | 16b 后 | 3 致命 sound bug + 2 schema 漏 + F5 反例 |
| 15 | 16c-2 后 (带 timeline) | round 14 修对 ✅ + 2 风险 + F9 推荐 |
| 16 | 17d 后 | 3 sound + 1 watcher 误入 + F10 反例 |
| 17 | 17e 后 | round 16 修对 ✅ + 2 新 bug (F8 watcher / F9 slot) |
| 18 | 17f 后 | round 17 修对 ✅ + 2 致命 (F1 AGNOSTIC / F9 partial) + F13 反例 |
| 19 | 17g 后 | F1 修对 + **F9 v1.2 修错** + F9 paradigm 降级 |
| 20 | 17h 后 | F9 v1.3 修对 + **F9 v1.3 FN** + F14 反例 + GO ALL CLEAR |
| 21 | 17i 后 | F9 v1.4 ✅ + 2 False Quarantine bug + F15 反例 |
| 22 | 17j 后 | 2 修对 ✅ + **仅 1 行 watcher 漏** + F16 反例 → **不需 Cut** |

**总计**: 22 round, ~15 个 finding 修, 0 个 paradigm-level unsolved.

## 8. 进 Phase 1 (代码实施) 前 ready checklist

- [x] state_machine_v2 + cut_lifecycle_v2 v3.2.2 spec
- [x] 9 family 完整 spec (v1.0+ 全 final)
- [x] 5 red fixture (F1-F5)
- [x] paradigm_death_timeline 27 lever consolidated
- [x] B core PoC 14/14 PASS (cut lifecycle 9 步)
- [x] 22 round Gemini cross-check 完整 trace
- [x] Phase 0 close summary (本 doc)
- [ ] PROJECT_LOCK update (Day 18-21 or Phase 1 起步)
- [ ] 168h campaign exit criteria 8 条 checklist (Day 18-21 or Phase 1)

## 9. 用户授权检查

**Phase 0 close 后下一步是 Phase 1 编码** (按 [[phase0-b-prep-progress]] memory plan v3 Day 18-21 集成 + exit criteria + PROJECT_LOCK update, 或者直接进 Phase 1). 用户决定走法.

Gemini round 22 verdict 原话: "**你已经准备好进入 Phase 1 (代码实施) 了**".

---

**Refs**: cut_family_specs/01-09 + cut_lifecycle_v2 v3.2.2 + state_machine_v2 + red_fixtures/F1-F5 + cross_check/round_14-22 + poc/b_core_lifecycle_poc + paradigm_death_timeline
