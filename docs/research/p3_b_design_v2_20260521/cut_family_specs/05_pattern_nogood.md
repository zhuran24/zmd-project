# Cut Family 5 — pattern_nogood (完整 spec, 复用 L16 deletion minimizer)

> **Status**: Day 17a v1.0 (2026-05-21)
> **Mode**: literal (_FAMILY_MODE_MAP)
> **Family_version**: v1.0
> **复用**: L16 deletion-based core minimizer + PCR-CUT QuickXplain helper
> **⚠️ 已知 Class C 风险**: 132 个 mfg_3x3 cluster 时退化 full no-good (paradigm_death_timeline.md Issue 3). **Family 9 density_envelope 是真正解** (Gemini round 15 推).

## 1. 数学定义

最一般的 cut 形式: 一组 facility pose 组合 (specific assignment) 被 sub-problem
oracle 验证 INFEASIBLE → 学 cut:

```
not (slot_1 = pose_1 ∧ slot_2 = pose_2 ∧ ... ∧ slot_n = pose_n)
                              ⇒ INFEASIBLE
```

literal-based, 走 §5 multiset evaluate (跨 group permutation sound).

## 2. Soundness proof

sub-problem oracle (binding / routing / PCR-CUT) 给定 full assignment 验证
INFEASIBLE → no-good cut 学 specific pose 组合不可. minimal core via L16
deletion-based minimization 缩 cut size.

scope: 全跟 source-of-truth, ghost (oracle 在 ghost 下验), assumption (binding
v3 / routing v2 / pcr_cut v1 abstraction version).

## 3. ⚠️ Class C 退化风险 (Gemini round 15 finding)

132 个 mfg_3x3 cluster 几何 trap 场景: full no-good cut 表示
"facility A pose pA + facility B pose pB + ... + facility N pose pN" full
assignment. cluster 内 132! permutation, anonymous slot ref multiset 包含 cover
**逻辑对称性** 但**不 cover 几何对称性** — pose pA 在 (10, 10) 不合法, pose
pA' 在 (10, 11) 大概率也不合法, full no-good 不能跨 translation lift.

**估**: 168h campaign 内, pattern_nogood >50% 累积 = stop-ship signal
(v14 review verdict). **解**: Family 9 density_envelope geometric cut 替代.
v1.0 Family 5 留 fallback (sub-problem oracle 没拿到 geometric witness 时使用).

## 4. Cert payload schema

```python
@dataclass(frozen=True)
class PatternNogoodCert:
    """cert_kind = "deletion_minimal_core" | "quickxplain_core" """
    sub_problem_oracle_name: Literal["binding_v3", "routing_v2", "pcr_cut_v1", "d2_separator_v1"]
    oracle_cert_hash: Hash                # sub-problem oracle 的 cert hash
    forbidden_pose_pattern: Tuple[Tuple[GroupId, int, PoseId], ...]
                                          # (group, slot, pose_id) 三元组
                                          # = cut.literals canonical form
    minimization_audit: Dict[str, int]    # size_before / size_after / qx_calls
    sub_oracle_witness_blob_b64: bytes    # oracle 的 infeasibility witness
                                          # (binding: ports + slots; routing:
                                          # cut paths; PCR-CUT: patch min-cut)
```

## 4b. Cut object 构造 (literal mode)

```python
cut = Cut(
    family="pattern_nogood",
    literals=tuple(
        CutLiteral(slot_ref=AnonymousSlotRef(g, s), pose_id=p)
        for g, s, p in forbidden_pose_pattern
    ),
    geometric_payload=None,
    scope=CutScope(
        ghost_rect_id=compute_ghost_rect_id(state.ghost_rect),
        blocked_cells_hash=compute_blocked_cells_hash(state),
        ...,
        oracle_abstraction_version=sub_oracle_name,
    ),
    cert=OracleCert(cert_kind="deletion_minimal_core", ...),
)
```

## 5. Generator (复用 L16 deletion minimizer)

```python
class PatternNogoodOracle:
    name = "pattern_nogood_v1"

    def generate(self, state, master_solution, sub_problem_result) -> List[Cut]:
        """sub_problem_result 是 binding / routing / PCR-CUT 的 INFEASIBLE 返."""
        from src.cuts.l16_deletion_minimizer import deletion_minimize_core
        # L16 deletion-based: 缩 cut size 通过 repeated sub-problem oracle 调用
        full_assignment = master_solution.to_pose_pattern()  # full pose pattern
        minimal_core = deletion_minimize_core(
            assignment=full_assignment,
            oracle=sub_problem_result.oracle_callable,
            timeout=10.0,
        )
        cert = PatternNogoodCert(
            sub_problem_oracle_name=sub_problem_result.oracle_name,
            oracle_cert_hash=sub_problem_result.cert_hash,
            forbidden_pose_pattern=tuple(minimal_core),
            minimization_audit={
                "size_before": len(full_assignment),
                "size_after": len(minimal_core),
                "qx_calls": deletion_minimize_core.last_call_count,
            },
            sub_oracle_witness_blob_b64=sub_problem_result.witness_blob,
        )
        return [construct_pattern_nogood_cut(state, cert)]
```

## 6. evaluate_cut (literal-based 走 §5 multiset)

```python
# cut_lifecycle_v2 v3 §5 multiset evaluate:
def evaluate_cut_literal_based(cut, state) -> bool:
    cut_demand_by_group = group_by(cut.literals, key=lambda l: l.slot_ref.group_id)
    state_by_group = {gid: Counter(g.selected_pose_assignments)
                      for gid, g in state.groups.items()}
    for gid, demand in cut_demand_by_group.items():
        demand_counter = Counter(l.pose_id for l in demand)
        if not (demand_counter <= state_by_group.get(gid, Counter())):
            return False
    return True
```

## 7. Validator

```python
class PatternNogoodValidator(CutValidator):
    family = "pattern_nogood"
    validator_version = "v1.0"

    def validate(self, cut, state) -> ValidationResult:
        cert = decode_pattern_nogood_cert(cut.cert.cert_payload)
        # 1. 重跑 sub-problem oracle 在 forbidden_pose_pattern 验仍 INFEASIBLE
        oracle = lookup_oracle(cert.sub_problem_oracle_name)
        if not oracle.verify_infeasibility(
            assignment=cert.forbidden_pose_pattern,
            witness=cert.sub_oracle_witness_blob_b64,
            state=state,
        ):
            # sub-problem 在 forbidden_pose_pattern 上 FEASIBLE → cert 不 sound
            return ValidationResult("unsound", ..., "sub-problem oracle re-verification FEASIBLE")
        # 2. 验 cert oracle_cert_hash 跟 witness 一致
        if hashlib.sha256(cert.sub_oracle_witness_blob_b64).hexdigest() != cert.oracle_cert_hash:
            return ValidationResult("unsound", ..., "oracle_cert_hash mismatch")
        return ValidationResult("ok", ...)

    def evaluate_geometric(self, cut, state):
        raise NotImplementedError("Family 5 is literal-based")
```

## 8. Replay + watcher

watcher:
- by_group_watcher (forbidden_pose_pattern 涉及每 group)
- by_pose_watcher ((group, pose_id) tuples)
- by_ghost_watcher (Day 17d 加, sub-problem oracle 跟 ghost 绑)

## 9. ⚠️ Class C accumulation 监控 (Phase 1 必加)

168h campaign 启动 8 exit criteria 第 7 项 (memory v14-review-findings):
"pattern no-good 平均 core size 受控 + 非主力 cut source". 实施:
- 每 candidate / 每 small iteration 报 Family 5 cuts ratio
- ratio > 50% → telemetry alarm
- Phase 1 加监控 src/cuts/families/pattern_nogood.py 内

## 10. Open questions

1. **Translation lift** (Gemini round 15 推): 几何对称的 pose 组合学一条 cut
   多扰动场景命中. Phase 1 / Phase 2 generalize.
2. **Sub-problem oracle abstraction version**: cert.sub_problem_oracle_name
   绑 v1, oracle 升 v2 时全部 quarantine. Phase 1 加 oracle compat matrix.
3. **跟 Family 7 cell_owner causation 重复**: F7 v1.1 多 literal 跟 F5 类似.
   F7 严格优于 F5 (Gemini round 15 verdict — 白盒 vs 黑盒). cut store dedup
   政策 Phase 1 政策.

## 11. 验收

- ✅ 数学 + soundness + literal-based 走 multiset
- ✅ Cert + cut 构造 + generator (L16 复用) + evaluate + validator
- ⚠️ Class C 退化风险 acknowledged, Family 9 是真正解, Family 5 作 fallback
- ⏸ Phase 1 实施 src/cuts/families/pattern_nogood.py + monitor + L16 import
