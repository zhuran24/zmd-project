# Cut Family 9 — density_envelope (完整 spec, v3 新 family, Class C mitigation)

> **Status**: Day 17c v1.0 (2026-05-21)
> **Cross-refs**: `../cut_lifecycle_v2.md` v3.1 + `../paradigm_death_timeline.md` Issue 3 + `../cross_check/gemini_round_15_followup.md`
> **Mode**: geometric (_FAMILY_MODE_MAP)
> **Family_version**: v1.0
> **来源**: Gemini round 15 Class C mitigation 推荐
> **解决 paradigm_death_timeline Issue 3**: manufacturing cluster trap (132 个 mfg_3x3) Family 5 pattern_nogood 退化 full no-good

## 0. Changelog

- **v1.0** (Day 17c, commit 98daa07): Gemini round 15 推荐. Class C (cut
  family abstraction 不够 / full no-good 退化) mitigation. 把 oracle 反馈的
  局部 routing INFEASIBLE 翻译成**几何 density** cut, 不绑具体 pose ID, 跨
  几何扰动命中.
- **v1.1** (Day 17f): 修 Gemini round 17 B2 schema state-dependency:
  `oracle_assignment_witness` v1.0 含 `(GroupId, int slot, PoseId)`, slot 是
  master 内部 enumeration order (state-dependent). 跨 candidate replay 时
  slot 改 → validator 死板验 slot 让合法 witness 失败 quarantine. v1.1 改
  `(GroupId, PoseId)` (state-independent), validator 只看 "K+1 pose 同时存在"
  即可验 INFEASIBLE.
- **v1.2** (Day 17g): 修 Gemini round 18 partial intersection — 改 Reference
  Cell 计数. **但 v1.2 修错** (Gemini round 19 verdict): facility origin 贴
  window 边内但身躯外仍算 → False Positive 误剪. **deprecated**.
- **v1.3** (Day 17h): 修 Gemini round 19 **2 致命 bug**:
  1. **计数严苛化**: §6 改 `all(c in W for c in pose_cells)` 全包含计数 —
     只有 facility 所有 cells 都在 window 内才 +1. Certified exact 宁可 False
     Negative 漏剪, **绝不可** False Positive 误剪.
  2. **Paradigm 降级** (Gemini round 19 B critical): F9 v1.0-v1.2 把
     Oracle Routing/Binding 拓扑死锁泛化"几何密度" 数学 **Unsound** —
     Oracle INFEASIBLE 来自特定端口朝向 / 相对位置 routing 死锁不是密度.
     Master 回溯后整齐排列 routing 可行, F9 单按数量秒杀误剪. v1.3:
     - F9 只能用于 Oracle 抛 `AreaCapacityOverflow` 凭证场景 (面积容量
       绝对溢出: K+1 facility 需 90 cells + belt 30 = 120 > W=100)
     - binding/routing/pcr INFEASIBLE 必 **Fallback Family 5 pattern_nogood**
       (接受 Class C 代价, 不强行 lift F9)
     - witness_kind enum 改: 仅留 `"area_capacity_overflow"`, deprecate
       `binding_overflow / routing_overflow / pcr_cut_overflow`
- **v1.4** (Day 17i, 本 commit): 修 Gemini round 20 B2 **严重 False Negative**:
  v1.3 全包含计数对面积溢出**漏剪** — Master 在 W 内全包 10 个 3x3 (90 cells)
  + 边缘半身 5 个 3x3 (15 cells in W) = 105 > 100 cells 真溢出, 但全包含计数
  只算 10 ≤ K=10 → 静默 (FN). v1.4 改: F9 既降级"面积溢出", evaluator **直接
  数占用格子数** `sum(|pose_cells ∩ W|)` vs `cert.max_allowed_area`, **不数
  facility 个数**. 既 sound 又防边缘漏剪. cert 加 `max_allowed_area` field
  替代 `density_K` (deprecated).

## 1. 数学定义

### 1a. Cut 形式

设 window `W` ⊆ grid (e.g. 15×15 矩形). facility group `g` (e.g.
`manufacturing_3x3`). density bound `K`:

```
∃ window W, group g, density bound K s.t.
    sum_{i ∈ g.instances} 1[placement[i] ∩ W ≠ ∅] > K
    ⇒  INFEASIBLE (W 内 g 密度超 K 必 INFEASIBLE)
```

cut 表达: "Window `W` 内 group `g` 的 placed instance 数 ≤ K-1".

### 1b. 解决 manufacturing cluster trap (Issue 3)

132 个 mfg_3x3 cluster 几何 trap. Family 5 pattern_nogood full no-good 退化:
- pose pA @(10,10) infeasible + pose pA' @(10,11) 也 infeasible
- F5 学的 cut 绑 pose_id, 几何扰动跨数量级失效 → C(132, K) permutation 都
  各自 cut → cut store 爆 / accumulation 慢

Family 9 几何 lift: 把 Oracle 反馈 "10 mfg_3x3 在 15×15 window 必 INFEASIBLE"
学成 1 条 geometric cut "Window W 内 mfg_3x3 ≤ 9", 一条秒杀
`C(N, 10) ≈ N^10` permutation 扰动. **Lift cut 表达力数量级**.

### 1c. 跟 Family 1 区别 (Gemini round 15)

|  | Family 1 region_capacity | Family 9 density_envelope |
|---|---|---|
| Region 来源 | 全局 baseline / interior_rect (canonical) | Oracle 反馈动态 window |
| Cap 来源 | static (ghost + exterior) | dynamic (Oracle 推导 K) |
| Demand | source-of-truth 决定 | 当前 master selected 数 |
| 数学定理 | demand_R > cap_R | density > K bound |
| 触发 | source-of-truth + ghost | sub-problem oracle 推导 |

Family 1 是几何**容量**, Family 9 是几何**密度** — 不同 axis.

## 2. Soundness proof

### 2a. Oracle 推导 K bound

K bound 由 sub-problem oracle 推导: 假设 W 内放 m 个 group g 的 instance,
oracle (binding/routing/PCR-CUT/D2) 跑 INFEASIBLE → m > K. K = m - 1 是 sound
upper bound (再放 K+1 个必 INFEASIBLE).

### 2b. 跨几何扰动 sound

cut "Window W 内 group g ≤ K" 跟 group instance 的**具体 pose ID 无关** —
只看 placement 是否 ∩ W 非空. 任何几何 permutation (translation / rotation
之内) 满足 "数量 ≤ K" 即 sound, 数量 > K 即 violate. 跨 pose_id 扰动 sound.

### 2c. Scope 限定

K bound 由 oracle 在特定 ghost 下推. ghost 变 → window/cap 都可能变 →
scope 必绑 ghost_rect_id (非 GHOST_AGNOSTIC) + active_assumption sub_problem_oracle
abstraction version.

## 3. Cert payload schema

```python
@dataclass(frozen=True)
class DensityEnvelopeCert:
    """cert_kind = "oracle_density_witness"."""
    window_rect: Tuple[int, int, int, int]    # (x, y, h, w) — window 矩形
    group_id: GroupId                          # 受 density bound 限制的 group
    # v1.4 (Gemini round 20 B2): F9 降级面积 cut 后, max_allowed_area 替代 density_K
    max_allowed_area: int                      # W 内 group 可占最大 cells 数
                                               # = |W| - belt_cells_needed - other_facility_cells
                                               # 由 Oracle area_capacity_overflow 凭证给出
    density_K: int                              # **deprecated v1.4** — kept for back-compat,
                                               # but evaluator 不再用; 旧 K=floor(max_allowed_area/cells_per_pose)
    oracle_witness_kind: Literal[
        # v1.3 (Gemini round 19): 仅留 area_capacity_overflow, 其他 deprecate
        "area_capacity_overflow",              # K+1 facility cells + belt cells > W cells
        #
        # DEPRECATED v1.0-v1.2 (paradigm Unsound — 拓扑死锁泛化几何密度 unsound):
        # "binding_overflow",                  # → Fallback Family 5 pattern_nogood
        # "routing_overflow",                  # → Fallback Family 5 pattern_nogood
        # "pcr_cut_overflow",                  # → Fallback Family 5 pattern_nogood
    ]
    oracle_cert_hash: Hash                     # sub-problem oracle 的 INFEASIBLE 证书 hash

    # v1.1 (Gemini round 17 B2): 去 slot ID (state-dependent), 改 (group, pose) 只
    oracle_assignment_witness: Tuple[Tuple[GroupId, PoseId], ...]
                                                # K+1 具体 (group, pose) 对触发 oracle INFEASIBLE
                                                # slot 不在 cert (state-dependent),
                                                # validator 只验 "K+1 pose 同时存在" sound
    ghost_rect_repr: Tuple[int, int, int, int]
```

## 4. Cut object 构造

```python
cut = Cut(
    family="density_envelope", literals=None,
    geometric_payload=canonical_bytes(DensityEnvelopeCert.asdict()),
    scope=CutScope(
        ghost_rect_id=compute_ghost_rect_id(state.ghost_rect),
        blocked_cells_hash=compute_blocked_cells_hash(state),
        ...,
        oracle_abstraction_version=cert.oracle_witness_kind,  # binding_v3 / routing_v2 / pcr_cut_v1
        active_assumptions=(
            Assumption("sub_oracle_abstraction", value=cert.oracle_witness_kind),
        ),
    ),
    cert=OracleCert(cert_kind="oracle_density_witness", ...),
)
```

## 5. Generator

### 5a. Density extraction from sub-problem oracle

Oracle 在 master OPTIMAL 后跑, 若 INFEASIBLE 给一个 witness assignment (具体
K+1 facility 在某 window 不可绑/不可路由/不可 cut). 把这个 K+1 assignment lift
成几何 envelope:

```python
class DensityEnvelopeOracle:
    name = "density_envelope_v1.3"  # v1.3 (Gemini round 19): paradigm 降级

    def generate(self, state, master_solution, sub_problem_result) -> List[Cut]:
        """v1.3 (Gemini round 19 critical paradigm): **仅 area_capacity_overflow
        触发**, 不再 lift binding/routing/PCR-CUT INFEASIBLE.

        why: 拓扑死锁 (端口对冲 / 相对位置 routing 死锁) 泛化"几何密度" 数学
        Unsound — master 整齐排列后 routing 可行但 F9 仍秒杀.

        binding/routing/PCR-CUT INFEASIBLE → Family 5 pattern_nogood Fallback
        (接受 Class C 代价, 不强行 lift F9).
        """
        cuts = []
        # v1.3: 仅当 sub_problem_result 是面积容量绝对溢出才 trigger
        if sub_problem_result.kind != "area_capacity_overflow":
            return cuts  # → Fallback Family 5

        # area_capacity_overflow witness: K+1 facility cells + belt cells > W cells
        witness_assignment = sub_problem_result.infeasibility_witness  # K+1 (group, pose_id)
        if not witness_assignment:
            return cuts

        # Group by group_id (density 是 per-group)
        by_group = {}
        for g, s, p in witness_assignment:
            by_group.setdefault(g, []).append((s, p))

        for group_id, members in by_group.items():
            # 计算 minimal window 包含 members 所有 cells
            all_cells = [c for s, p in members for c in canonical_rules_pose_cells(group_id, p)]
            window_rect = compute_bounding_rect(all_cells)
            density_K = len(members) - 1  # K+1 INFEASIBLE → K = len - 1

            cert = DensityEnvelopeCert(
                window_rect=window_rect,
                group_id=group_id,
                density_K=density_K,
                oracle_witness_kind=infer_witness_kind(sub_problem_result),
                oracle_cert_hash=sub_problem_result.cert_hash,
                oracle_assignment_witness=tuple(witness_assignment),
                ghost_rect_repr=tuple(state.ghost_rect),
            )
            cuts.append(construct_density_envelope_cut(state, cert))
        return cuts
```

### 5b. Minimize (Step 2)

Window 缩到 minimal: bounding rect 含 K+1 facility cells, 但 minimal 是
**最小 window 仍触发 oracle INFEASIBLE**. 走 QuickXplain on window expansion:

```python
def minimize_window(cert: DensityEnvelopeCert, oracle) -> DensityEnvelopeCert:
    """Shrink window 直到 K+1 facility 不被 oracle 拒.
    缩 axis 1 cell 一次, 重跑 oracle (in shrunk window) verify INFEASIBLE.
    """
    # PoC scope: 不实施 minimize, v1.0 用 bounding rect
    return cert
```

v1.0 不 minimize (bounding rect 已 sound). v1.1 加 minimize 缩 window scope.

### 5c. Tighten K (advanced minimize)

给定 window W 固定, K 可以 binary search 缩到 minimal:
- 二分 K: 在 W 内放 K' facility (K' < K+1) → oracle 是否 INFEASIBLE
- 找最小 K_min s.t. K_min+1 INFEASIBLE → cert.density_K = K_min

v1.0 直接用 oracle witness 的 K+1 - 1 = K. v1.1 binary search 紧化.

## 6. evaluate_geometric (hot path)

```python
def evaluate_geometric_density_envelope(cut: Cut, state: BState) -> bool:
    """Window W 内 group g 的 placed instance 数 > K → violate.

    v1.4 (Gemini round 20 B2): F9 降级面积溢出 paradigm 后, **直接数占用
    格子数** `sum(|pose_cells ∩ W|)` vs `cert.max_allowed_area`, **不数
    facility 个数**. 既 sound 又防 v1.3 边缘 facility 半身 in W 漏剪 (FN).
    """
    cert = decode_density_envelope_cert(cut.geometric_payload)
    wx, wy, wh, ww = cert.window_rect
    W = {(x, y) for x in range(wx, wx + wh) for y in range(wy, wy + ww)}

    # v1.4: 数 W 内被 cert.group_id facility 占的总格子数 (不数 facility 个数)
    occupied_in_window = 0
    for cell, (owner_group, _) in state.cell_owner.items():
        if owner_group == cert.group_id and cell in W:
            occupied_in_window += 1

    return occupied_in_window > cert.max_allowed_area
```

Hot path 重算, 跟 Family 4/8 同 pattern. **v1.4 关键**: F9 降级面积 cut 后,
evaluator 数 cells 不数 facilities. 边缘 facility 半身 in W 仍贡献其 in-W
cells, 防 v1.3 FN.

> 历史:
> v1.0 over-count (任 cell 沾 W 算整 facility) → FP
> v1.2 origin-in-W 才算 → FP (Gemini round 19)
> v1.3 all-in-W 才算 → FN (Gemini round 20 — 边缘溢出漏)
> v1.4 数占用 cells 直接 → 唯一 sound (无 FP 无 FN)

## 7. Validator

```python
class DensityEnvelopeValidator(CutValidator):
    family = "density_envelope"
    validator_version = "v1.0"

    def validate(self, cut, state) -> ValidationResult:
        cert = decode_density_envelope_cert(cut.cert.cert_payload)
        # 1. 验 ghost_rect_repr match
        if cert.ghost_rect_repr != tuple(state.ghost_rect):
            return ValidationResult("unsound", ..., "ghost_rect mismatch")
        # 2. 验 oracle witness 重跑仍 INFEASIBLE (Sub-problem oracle 调用)
        sub_oracle = lookup_oracle(cert.oracle_witness_kind)
        verified = sub_oracle.verify_infeasibility(
            assignment=cert.oracle_assignment_witness,
            state=state,
            window=cert.window_rect,
        )
        if not verified:
            return ValidationResult(
                "unsound", ...,
                "sub-problem oracle re-verification not INFEASIBLE",
            )
        # 3. 验 oracle_assignment_witness 是 K+1 (group, pose) in window of group_id
        # v1.1 (Gemini round 17 B2): witness 不 carry slot, 验只看 K+1 pose 存在
        in_window_count = 0
        for g, p in cert.oracle_assignment_witness:
            if g != cert.group_id:
                return ValidationResult("unsound", ..., f"witness group {g} != cert {cert.group_id}")
            pose_cells = canonical_rules_pose_cells(g, p)
            wx, wy, wh, ww = cert.window_rect
            if any(wx <= c[0] < wx + wh and wy <= c[1] < wy + ww for c in pose_cells):
                in_window_count += 1
        if in_window_count != cert.density_K + 1:
            return ValidationResult(
                "unsound", ...,
                f"witness count {in_window_count} != K+1 = {cert.density_K + 1}",
            )
        return ValidationResult("ok", ...)

    def evaluate_geometric(self, cut, state):
        return evaluate_geometric_density_envelope(cut, state)
```

## 8. Replay + watcher

按 v3.1 §4 6 步 verify. watcher:
- by_cell_watcher (window_rect 内每 cell)
- by_group_watcher (group_id)
- by_ghost_watcher (Day 17d 加)

## 9. Density vs Capacity 协调 (Family 1 vs 9)

可能场景: 同 group g, region R 跟 window W 重叠. Family 1 cut "region R 内
g.demand > cap_R" 跟 Family 9 cut "window W 内 g ≤ K" 都 trigger.

不冲突: Family 1 limit 是源于 region cell capacity (geometry), Family 9 limit
是源于 sub-oracle infeasibility (interaction). 可同时 attach, 两者协同剪枝.

## 10. ⚠️ Key design choice (Gemini round 15)

**Family 9 是 Issue 3 manufacturing cluster trap 真正解** — Family 5 pattern_nogood
fallback. 但 Family 9 依赖 sub-problem oracle 给出 K+1 INFEASIBLE witness.

若 oracle 不给 density witness (只给 specific pose pattern), Family 5 fallback.

**Phase 1 实施关键**: oracle 端 generate 时优先尝试 lift 成 Family 9, 失败回退
Family 5. 168h campaign 监控 Family 9 / Family 5 ratio (memory v14-review
exit criteria 第 7).

## 11. Open questions → Phase 1 / v1.1

1. **Window 选 algorithm**: bounding rect 最 obvious 但可能太大. minimal
   shrink window 走 QuickXplain (v1.1).
2. **K binary search**: v1.0 K = witness_size - 1, v1.1 binary search 紧化.
3. **Multi-group window**: window W 内多 group 都被限. Family 9 spec 单 group.
   v1.1 加 multi-group sub_kind.
4. **Window translation lift**: 同 K bound 适用 translated window? 部分 yes
   (geometry-invariant), 但 ghost 切割让 translation 不 sound. Phase 1 评估.
5. **Family 9 跟 D2 dual lift**: D2 commodity flow 死路留下 cell-flow infrastructure.
   D2 给 INFEASIBLE 时可能 lift Family 9 (高 demand 集中). Phase 1 设 hook.

## 12. Implementation pre-decision

- `DensityEnvelopeValidator` 实现: `src/cuts/families/density_envelope.py` (Phase 1)
- `DensityEnvelopeOracle.generate`: `src/cuts/generators/density_envelope_oracle.py` (Phase 1)
- `compute_bounding_rect` helper: 新 helper, ~20 LOC (Phase 1)
- `infer_witness_kind`: dispatch sub-problem oracle 返 result 标 binding/routing/pcr_cut. Phase 1 加 lookup table.
- 测试: `src/tests/cuts/test_family_9_density_envelope.py` (Phase 1)
- 168h monitor: Family 9 / Family 5 ratio telemetry

## 13. 验收

- ✅ 数学定义 (geometric density bound, oracle-derived K)
- ✅ Soundness proof (Oracle witness K+1 INFEASIBLE → cut bound K sound,
  几何 permutation 跨 pose_id sound)
- ✅ Cert schema (DensityEnvelopeCert 含 window_rect / group_id / K /
  oracle_witness_kind / oracle_assignment_witness / ghost)
- ✅ Cut 构造 (geometric, ghost-bound)
- ✅ Generator (oracle witness lift 成 geometric envelope + minimize defer)
- ✅ evaluate_geometric (hot path: count instance in window)
- ✅ Validator 3 步 (ghost / oracle re-verify / witness count match K+1)
- ✅ Replay + watcher
- ✅ Family 1/5 协调政策
- ⚠️ 5 open question (window 缩 / K binary search / multi-group / translation lift / D2 hook)
- ⏸ Phase 1 实施 + 168h ratio monitor
