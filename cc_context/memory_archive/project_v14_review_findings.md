---
name: v14-review-findings
description: "2026-05-21 GPT pro + Gemini 两份独立 v14 architecture stress test review verdict: B direction GO, v14 spec NO-GO. 必修 4 件事 (boundary source-of-truth / 3 类新 cut / state schema / lifecycle scope-aware) 才能进 implementation"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-21 v14 包 (commit e57f95a) 发 GPT pro + Gemini round 12 两份独立 review. high robustness 共识 verdict:

```
B direction:      GO ✓
v14 cut set:      NO-GO as written ❌
v14 state schema: NO-GO as written ❌
v14 lifecycle:    NO-GO as written ❌
```

## 必修 4 件事 (Phase 0 preparation 扩到 ~3 week)

### 1. Boundary source-of-truth 冻结 (Phase 0 第一件)

v14 包写 "46 × 3 = 138 cells / perimeter 276 / 占 50%". 但源码:
- `rules/canonical_rules.json` `"placement_rule": "left_or_bottom_boundary"`
- `candidate_placements.json` 只 134 boundary pose (left 67 + bottom 67)
- 真实: 46 × 3 = 138 cells 必须 **100% 铺满 left+bottom 138 allowed cells**
- 每条边 23 port, 唯一无重叠铺法 start=1,4,7,...,67

修法 (team 二选一):
- A. 改 generator + canonical_rules: 左+底 → 四边 perimeter (如果游戏真实是四边)
- B. 改文档 + 所有 perimeter cut 重写: 接受 left+bottom 100% saturation 模型

不修这个所有 cut family 在错误几何上验证 sound, 后面全 wasted.

### 2. 加 3-4 类新 cut family (1 week)

v14 5 类 cut 全部漏掉 critical infeasibility 类型. 两份各自构造反例:

**反例 A (GPT)**: q-cell (58,35) 两 commodity forced output port 撞同一 front cell, routing `AddAtMostOne((cell,layer))` + exact port adherence → UNSAT. 5 cut family 全静默, 退化 pattern no-good.

**反例 B (Gemini)**: 长度 10 boundary 被 ghost 切 [1,2,3,4]+[6,7,8,9,10], cell 数 9 = demand 9 pass region capacity, 但 length-3 interval `⌊4/3⌋+⌊5/3⌋=2 < 3` infeasible.

**反例 C (Gemini)**: 十字 corridor 三 commodity 都强制经过 center cell, per-commodity cutset pass, 但 routing node/layer capacity 不够.

必加 4 类新 cut:
1. **Port-front terminal resource cut** (GPT): `(cell, layer)` cap=1, forced terminal 撞同一 front 即 UNSAT
2. **Shape packing / pose-domain Hall cut** (Gemini): `α(P_U) < demand(U)` interval/footprint scheduling
3. **Multi-commodity node/layer capacity cut** (Gemini): vertex split graph + node capacity demand
4. **Power support hitting-set cut** (GPT): pose covered by optional power_pole set, hitting-set infeasible → forbid

每类 schema: 数学定义 + soundness 证明 + generator + resolve + validator + replay.

### 3. State schema 重写 (1 week)

v14 schema 只有 placement/cell_owner/free_cells/pose_domain/ghost/active_cuts/trail. 缺:
- binding_domain_summary + forced_terminal_resources
- power_cover_domain (residual optional pole)
- front_resource_load Counter[(cell, layer)]
- routing capacity projection

不放 full routing CP-SAT vars (重蹈 L23 = 32GB), 只放 cut 解释所需轻量 resource state.

**Critical bug** (Gemini 抓): `resolve_region_capacity` 伪代码 double-count placed pose:
```
used = sum(|cells(placement[i]) ∩ R|) ...
for i, poses in pose_domain.items():
    for p in poses:
        if used + |cells(p) ∩ R| > cap_R:  # placed i 的 p 被加两次!
            remove p
```
直接把 placed pose 从 domain 删 → state invariant 破坏. 必须只过滤 unplaced i 的 pose, 或对 placed i 用 delta.

**对称性灾难** (Gemini): per-instance schema (`Dict[InstanceId, Optional[Pose]]`) 重新引入 34! × 34! × 46! ≈ 10^134 标签对称性. 源码 pose-bool master 是 group-demand (`sum(group_pose_vars) == demand`). B 必须 group/orbit-count state 而非 per-instance.

Trail 改 reversible delta log (`TrailEvent = DomainRemove/Assign/CellOwnerSet/CutAttach` w/ decision_level + reason). 不靠"last cause_decision_id" 回滚.

### 4. Cut lifecycle 扩到 ~10 步 + scope-aware replay (1 week)

v14 lifecycle 6/7 步缺关键 step. 合并 GPT + Gemini 推荐:
- 0. canonicalize (payload 排序, bitset 规范化, pose/group id 规范化)
- 1. generate (含 typed cert + source_digest + ghost_scope attach)
- 2. minimize/normalize (QuickXplain core 必须用 "只固定 core 其余释放" 模型 revalidate)
- 3. serialize (含 scope + family_version + validator_version + payload_schema_version + oracle_cert_hash)
- 4. deserialize
- 5. validate (独立 checker, 不信 oracle, 重算 cert)
- 6. attach-scope check (validate 在新 ghost / new source / new domain 下仍 sound 才 attach)
- 7. resolve (修 double-count bug, 用 group state 而非 per-instance)
- 8. dominance/subsumption + activation index/watchers
- 9. replay/regression (失败入 quarantine 不 active 不删)

**Replay scope-aware critical**: G1 ghost 挡 A B routing infeasible 学 `not(A=pA∧B=pB)`, G2 ghost 移开后 feasible. v14 replay 只查 pose id valid → 直接误剪合法解. 每个 cut 必须带 (ghost_rect_id + blocked_cells_hash + source_digest + artifact_hashes + active rule version + oracle abstraction version + assumptions). replay 时 validate 必须在新 scope 重新证 sound.

## Pattern no-good 完备性是空洞

5 cut family + pattern no-good 数学完备 (任何 infeasible full assignment 都能学一条 full no-good). 但 `Π_i |pose_domain(i)|` 至少 `3^266 ≈ 10^126`, 168h / 12GB worker budget 内不可能枚举.

**Acceptance criterion**: full-assignment no-good 只能 debug fallback. 真正成功标准 = oracle cut 比 full assignment 小至少一数量级 + 跨对称实例 / 相邻 ghost candidate / 同类 region 泛化. 任一 ramp >50% cuts 是 full no-good = stop-ship signal.

## 复用 contract-first

可复用作 oracle (但必须签 input scope + output verdict + minimal core + independent validation + 禁止 UNKNOWN→cut):
- B1 pose-bool master → placement oracle
- PCR-CUT patch_routing_core → routing cutset oracle (patch 边界写 payload)
- D2 commodity flow → component reachability oracle
- SAC-Hull → 必要 capacity cut, **不能** sufficient
- L16 lazy power completion → typed power-cover cut (ghost-conditioned, `benders_loop.py:4219-4268` 已对)
- highspy Farkas → 纯 LP relax algebraic cert, **不能**证 integer infeasibility

不能 certified prune (只能 order-only / debug):
- cand C v3 RMP / RF λ-space branching / set-covering relaxation logic
- routing_aware_pricing / feasibility_bootstrap / alternative_blueprint_generator
- SMT-MT outer pruning (除非输出 certified upper bound)

## Phase 0 preparation plan v3 (Gemini round 13 cross-check 微调后)

Day 1-2 串行: boundary semantics freeze + **double-count bug Day 1 修** (Gemini round 13: 纯代码 bug 不修后面 fixtures 全错)
Day 3-9 **双线并行** (Gemini round 13 推, 省工时 ~30%):
  - Dev A: State Machine v2 (group/orbit-count + reversible delta trail)
  - Dev B: Cut Lifecycle v2 (scope-aware + DB schema + 10 步)
Day 10-12 集成点: F1-F4 fixtures (boundary saturation / shape packing / power no-cover / ghost-scoped replay false-positive) 接进新框架
Day 13-17: 新 4 cut family schema (port-front terminal resource + shape packing Hall + multi-commodity vertex capacity + power support hitting-set, GPT power 跟 Gemini power 合并一类)
Day 18-21: 集成 + 168h campaign 8 条 exit criteria checklist Go/No-Go gate

## Gemini round 13 cross-check 调整 (3 处)

1. **Day 1 提前修 double-count bug**: 我原计划 Day 6-12 跟 state 一起改, Gemini 推 Day 1-2 跟 boundary 同时. 不修 fixtures 全错.

2. **Cut Lifecycle 砍 Subsumption/Dominance defer**: 10 步先砍这一步, implementation 后期再加.

3. **Rust/pyo3 重写 defer to Phase 2**: 当前最大风险是数学模型 + 状态机 bug 不是常数性能. Python + numpy bitset 先跑通 168h, 证明 B 能解题后再优化.

## Gemini round 13 新发现 Critical 接口冲突 (cross-check 才暴露)

**Group/Orbit State (Gemini Round 12 要求) vs. Port-binding Cut (GPT 要求) 接口冲突**

- Gemini 推 state group-based: "在区域 R 放了 3 个蓝铁粉碎机"
- GPT 推 cut reference 具体 instance ID: `not(crusher_blue_iron_001 = p1 ∧ refinery_steel_001 = p2)`
- 冲突: state 不 carry instance ID, cut 需要 instance ID resolve

候选方案 (Phase 0 必须解决, 不能 defer):
- state group-based, cut object 含 "anonymous instance slot" 引用
- Resolve 时 anonymous slot → group state 映射
- 具体 design phase 详细, prep phase 必须意识到这个 contract 不解决会撞墙

## Gemini round 13 同意 (不调整)

- 4 类新 cut family 覆盖完美
- 3 week right-sized 不是 over-conservative
- CDCL(T) defer Q3/Q4 future architecture doc
- Boundary interval screen partial 复用 (`master_model.py` CP-SAT interval packing 包 Oracle contract-first)
- 168h campaign 8 条作 Day 21 exit criteria checklist Go/No-Go gate

168h campaign 启动 8 硬条件 (GPT):
1. boundary 语义冻结 + 源码文档一致
2. q-front overload synthetic test 被 port-resource cut 剪 (不靠 full no-good)
3. power no-cover test ghost-conditioned typed cert
4. replay suite 27+ ghost anchors 无 false positive
5. 80-inst 无 UNKNOWN→cut
6. 160-inst cut store < 12GB/worker
7. pattern no-good 平均 core size 受控 + 非主力 cut source
8. 所有 persisted cuts deserialize+validate+attach-scope 通过

## Refs
- v14 包: `~/linwin_share/p3_b_design_review_v14_20260521.zip` SHA 6852d256
- GPT 答复: 用户 paste 完整内容到 transcript (2026-05-21)
- Gemini round 12 答复: 用户 paste 完整内容到 transcript (2026-05-21)
- 跟 [[gpt-v13-cut-language-thesis]] 互相 confirm (cut language 升级方向)
- 跟 [[cand-c-phase1-go]] 实测数据 align (cand C Phase 2 无 memory, 见 git commit history)
