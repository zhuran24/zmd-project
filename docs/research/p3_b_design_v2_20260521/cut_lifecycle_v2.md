# B Design v2 — Cut Lifecycle v2

Phase 0 Day 3-9 Dev B deliverable. v14 baseline 6/7 步 lifecycle 经 GPT pro +
Gemini round 12 + Gemini round 13 cross-check 后 NO-GO; 本 doc 给完整 10 步
lifecycle (其中 dominance/expiry/demotion **defer to Phase 2** per Gemini
round 13), 配套 cut object schema / scope-aware replay / group-state contract /
per-family validator / watcher index / quarantine 政策.

不动 `src/`. Phase 1 (实施) 单开 task.

## Changelog

- **v2 (Phase 0 Day 3-9, commit 64c5317)**: 初版 10 步 lifecycle + cut object
  schema + group-state contract
- **v3 (Phase 0 Day 14, 本 commit)**: 接 `schema_update_v3.md` 5 gap 解:
  - §3 Cut schema: `literals` 改 Optional + 加 `geometric_payload` field
    (互斥契约), `CutFamily` enum 加 `shape_packing_hall` + `power_hitting_set`,
    `_FAMILY_MODE_MAP` 一致性检查, `GHOST_AGNOSTIC` sentinel
  - §4 replay step 2: `GHOST_AGNOSTIC` 跳过 ghost 比对; 加 `compute_ghost_rect_id`
    canonical hash + `ASSUMPTION_VERIFIERS` dispatch
  - §5 `evaluate_cut_as_multiset` 改名 `evaluate_cut_literal_based` + 加
    `evaluate_cut` family-dispatch entry
  - §6 `CutValidator` Protocol 加 `evaluate_geometric` method; Family 1/2/4/6
    标 geometric, Family 3/5/7 标 literal; 加 Family 7 power_hitting_set spec
- **v3.1 (Phase 0 Day 16c)**: 修 Gemini round 14 finding #4 schema 漏:
  - §4 replay step 加 `blocked_cells_hash` 校验 (v3 schema 有此 field 但 v3
    algorithm 未读 → cross-session exterior block 变化导致旧 cut 错误 attach).
    新 step 3.bis 在 source_digest + ghost_rect_id 通过后, artifact_hashes 之前
    验 `cut.scope.blocked_cells_hash == compute_blocked_cells_hash(state)`,
    不 match → quarantine.
- **v3.2 (Phase 0 Day 17d)**: §7 加 6 维 by_ghost_watcher:
  - Family 6/7/8/9 全 ghost-bound, ghost_rect change 是 critical state
    transition. by_ghost_watcher 让 ghost change 直接 invalidate affected
    cut set (从 active 移 held), 不需扫全 store
  - Watcher 添加规则表加 Family 2/3/4/5/7/8/9 (v3 加 7/8/9 新 family)
  - GHOST_AGNOSTIC cut (F1) 不入 by_ghost_watcher
  - by_blocked_cells 7 维 watcher defer Phase 1
- **v3.2.1 (Phase 0 Day 17e)**: 修 Gemini round 16 finding A2 —
  watcher 表移除 Family 3 from `by_ghost_watcher`. F3 (port_exposure) spec §5
  明定 "ghost 占 front 不发 cut", 只 cell_owner causation 触发 cut, 跟 ghost
  完全无关. Watcher 误加导致每次 ghost change 引发大量无用 F3 replay.
- **v3.2.2 (Phase 0 Day 17j, 本 commit)**: 修 Gemini round 21 finding B1
  CutScope 加 `exterior_blocks_hash` field + Step 3 dispatch:
  - v3.1 §4 Step 3 强制验 `blocked_cells_hash` (含 ghost), 但 GHOST_AGNOSTIC
    cut 在 ghost 改时 hash 必变 → 永远 quarantine, 跨 ghost 存活率 = 0
  - v3.2.2 dispatch: GHOST_AGNOSTIC cut 验 `exterior_blocks_hash` (ghost-
    independent), 绑 ghost cut 验全量 `blocked_cells_hash`. F1 cut 跨 ghost
    存活率 0 → 100%.

## 1. TL;DR

v14 原 lifecycle 缺 canonicalize / attach-scope check / quarantine + 反例
clear: G1 ghost 下 cut `not(A=pA ∧ B=pB)` 在 G2 ghost 下若按 pose-id-only
replay 会**误剪合法解**. 本 doc 把 scope (ghost / blocked cells / source
digest / artifact / oracle abstraction / active assumptions) 焊进 cut object,
replay 时 5 步 verify; 失败入 quarantine 不删. Cut literal 用 anonymous slot
ref (group_id + slot_index) 跟 group state 对齐, 跨 group permutation 仍
sound. Cut store 5 维 watcher index 避免每轮扫全表.

## 2. Lifecycle 10 步详解

每步独立可测, 失败模式明确, runtime 全跑通 (v4 教训: schema landed ≠
runtime correct).

### Step 0: Canonicalize (Gemini round 12 新增)

把 oracle 返的 raw cut payload 规范化, 防同一 cut 被生成多次不同表示.

- 输入: raw oracle cert (无序 list / 任意 id 顺序)
- 处理:
  - cells / ports / edges 排序为 canonical tuple
  - bitset 转 dense canonical form (low-bit-first, 固定 grid 宽度)
  - pose id 不规范化 (pose_data 全局唯一), group id 不规范化
  - literal list 按 (group_id, slot_index, pose_id) 三元组 lexicographic 排
- 输出: 规范化后的 raw cut spec, 跟同源不同顺序的 raw spec 哈希一致
- 失败处理: 输入 schema 错 → reject (`CanonicalizeError`), 不入 store

### Step 1: Generate (含 typed cert + source_digest + ghost_scope attach)

sub-problem oracle 在 master OPTIMAL 后被调用, 产 cut + 全套 scope metadata.

- 输入: master state snapshot + sub-problem oracle 返的 typed cert
- 处理:
  - 从当前 candidate / state 拉 ghost_rect_id / blocked_cells_hash
  - 计算 source_digest (canonical_rules + candidate_placements + mandatory_instances)
  - oracle 自报 abstraction version (`binding_v3`, `routing_v2`, `pcr_cut_v1`)
  - oracle 自报 active_assumptions (e.g. "left+bottom baseline saturation = 100%")
  - 附 oracle_cert_hash (cert 内容 sha256, replay 时验)
- 输出: `Cut(literals, family, scope, cert, ...)` (见 §3)
- 失败处理: oracle cert schema 错 → reject + log; cert 内 algebraic check (LP/Farkas) fail → reject

### Step 2: Minimize / Normalize (QuickXplain + 只固定 core 其余放开模型重验)

把 cut literal set 缩到 minimal infeasibility core, 再独立重验.

- 输入: canonicalized cut
- 处理:
  1. QuickXplain (或 deletion-based) 在 sub-problem oracle 上跑 core 提取
  2. **关键** (Gemini round 12): 不在原 full assignment 上验; 用"只固定
     core literal 其余放开"的模型重 solve → 若仍 INFEASIBLE → core sound
  3. 否则 → 回退原 cut 不 minimize (保 sound 不保 minimal)
- 输出: minimized cut + minimization_audit (size_before/after, 重验 status)
- 失败处理: QuickXplain oracle 调用 cap 超 (default 32 call) → keep
  non-minimal; 重验 FEASIBLE → core 不 sound → quarantine

### Step 3: Serialize (含 scope + family_version + validator_version + payload_schema_version + oracle_cert_hash)

cut → JSON bytes 写 `data/cuts/{cut_id}.json`.

- 输入: minimized cut object
- 处理:
  - literals / scope / cert 用 family-specific serializer (bitset base64)
  - 顶层 envelope 加 `family_version` (cut family 数学定义版本) +
    `validator_version` (validator 实现版本) + `payload_schema_version` +
    `oracle_cert_hash`
- 输出: bytes (JSON, git diffable, 人类可读)
- 失败处理: 序列化报错 → log + skip 写盘, in-memory cut 仍 attach

### Step 4: Deserialize

JSON bytes → cut object. Schema 校验.

- 输入: bytes from disk
- 处理:
  - jsonschema 校验 envelope (4 个 version + cut_id + family)
  - 跑 family-specific deserializer
  - 不重建 oracle cert (cert 是 cert; replay 时算 hash 比对)
- 输出: standalone Cut object (未 attach)
- 失败处理: schema mismatch → quarantine + log; version mismatch (e.g.
  family_version old) → quarantine (不 auto-migrate)

### Step 5: Validate (独立 checker, 不信 oracle, 重算 cert)

最关键 sound 性 second line of defense. 不信 oracle 给的 cert.

- 输入: deserialize 后 cut object + 当前 BState (master state)
- 处理:
  - 按 cut.family 取 validator (`CutValidator` protocol, §6)
  - validator 独立重算 cert (LP/Farkas algebraic / port-resource 重算 / shape
    packing 重算 / connectivity 重算)
  - timeout 1s (Quarantine 政策见 §8)
- 输出: `ValidationResult(ok | timeout | unsound | schema_err)`
- 失败处理: unsound → quarantine + log `false_negative_pending`; timeout →
  quarantine + log

### Step 6: Attach-scope check (Gemini round 12 新增)

validate 在新 ghost / new source / new domain 下仍 sound 才 attach.

- 输入: validated cut + 当前 BState
- 处理: 5 步 verify (见 §4 详解):
  1. source_digest 比对 → 不一致 → quarantine
  2. ghost_scope match 当前 candidate → 不 match → 不 attach (保留)
  3. artifact_hashes 比对 → 不一致 → quarantine
  4. oracle_abstraction_version 当前可用 → 不可用 → 不 attach
  5. active_assumptions 在当前 state 仍 hold → 不 hold → 不 attach
- 输出: `AttachDecision(attach | hold | quarantine)`
- 失败处理: hold = retain cut 不 active (留下个 candidate 试)

### Step 7: Resolve (group state 映射 + anonymous slot ref expansion)

cut attach 后, 跑 propagation on BState.

- 输入: attached cut + BState (group enumeration order known)
- 处理:
  - cut literal (group_id, slot_index, pose_id) → 拿 BState
    `selected_pose_assignments[group_id][slot_index]` (见 §5)
  - 按 family-specific resolve 算 propagation (infeasible / domain_change /
    no_change)
- 输出: `ResolveOutcome(kind, conflict_set | removed_poses)`
- 失败处理: group enumeration order undefined (group state 未初始化) →
  defer to next iter

### Step 8: Activation index update (cell / group / pose / commodity / region watcher)

每次 state change 仅 trigger 对应 watcher 里的 cut 重 evaluate, 不扫全表.

- 输入: cut attached + watcher index
- 处理:
  - 按 cut.family + cut.literals 推 watchers (e.g. region_capacity cut 入
    `by_cell_watcher[cell]` 每个 cell ∈ region; pattern_nogood cut 入
    `by_group_watcher[group_id]` + `by_pose_watcher[(group_id, pose_id)]`)
- 输出: 5 维 watcher index update (§7)
- 失败处理: watcher key 冲突 → 不可能 (watcher 是 Set); index 写错 → log
  inconsistency + 跳过 (cut 仍 active 只是 propagation 会扫多)

### Step 9: Replay / Regression (失败入 quarantine 不 active 不删)

跨 candidate / 跨 session 时 store load 完, 对每个 cut 跑 Step 4-8 链路.

- 输入: cut store (disk) + 新 BState
- 处理:
  - 每个 cut 跑 deserialize → validate → attach-scope check →
    (attach 则) resolve / index update
  - Regression sweep: 周期性 (e.g. campaign hour boundary) 对 store 内全部
    cut 跑 dry-run replay 验仍 sound (不 attach 只 validate)
- 输出: replay_report (attached_count / held_count / quarantined_count /
  unsound_count) + regression_report
- 失败处理: quarantine 不删; regression 失败 cut 全部 quarantine + 通报
  audit log

### Step 10 (DEFER): Dominance / expiry / demotion (Gemini round 13 推 defer to Phase 2)

不在本 doc 实施. 简记当前**故意不做**:

- dominance: cut C1 蕴含 cut C2 时 demote C2 (subsumption check)
- expiry: cut 未 hit N candidate 时 age-out
- demotion: false-negative stats 累积时降级

理由 (round 13): 9 步链路 runtime correctness 先稳; subsumption / hit-count /
age 加进 store 不当会埋 bug. Phase 2 单独 stress test 后实施.

## 3. Cut object schema

完整 dataclass. 全部 frozen (immutability 防 replay 时被改坏).

```python
from dataclasses import dataclass, field
from typing import Tuple, Dict, FrozenSet, Literal, Optional
from datetime import datetime
import uuid

# === Identifier types ===

CutId = str                       # UUID4 hex
GroupId = str                     # e.g. "crusher_blue_iron"
PoseId = int                      # global pose data idx (从 pose registry)
GhostRectId = str                 # candidate.ghost_rect canonical hash
Hash = str                        # sha256 hex digest
SourceDigestStr = str             # canonical bytes digest (见 below)

CutFamily = Literal[
    "region_capacity",
    "cutset",
    "port_exposure",
    "component_reach",
    "pattern_nogood",
    "shape_packing_hall",   # v3 新 (F2 反例 owner)
    "power_hitting_set",     # v3 新 (F3 反例 owner)
    "symmetry_lift",         # 不是新 family, 是 1-7 的 lift; 此 field 标 "已 lifted"
]

# Sentinel for ghost-agnostic cuts (F1 boundary saturation 这种不依赖 ghost 的 cut).
# Replay step 2 见到此值跳过 ghost_rect_id 比对, 直接进 step 3.
GHOST_AGNOSTIC: GhostRectId = "__ghost_agnostic__"

# === Anonymous slot ref (§5) ===

@dataclass(frozen=True)
class AnonymousSlotRef:
    """Cut literal 指向 group 内 anonymous slot, 不绑 instance id.

    跨 group permutation 仍 sound: anonymous slot 在 group 内 interchangeable.
    """
    group_id: GroupId
    slot_index: int               # 0..(group_demand - 1), group 内顺序由
                                  # BState selected_pose_assignments 决定

@dataclass(frozen=True)
class CutLiteral:
    """Cut 的单条 literal: not (slot_ref = pose_id) 等价表示."""
    slot_ref: AnonymousSlotRef
    pose_id: PoseId

# === Scope (§4) ===

@dataclass(frozen=True)
class Assumption:
    """Oracle 在 generate 时报的 active assumption (replay 时验)."""
    key: str                      # e.g. "left_baseline_saturation"
    value: str                    # canonical str repr, replay 时 verbatim 比

@dataclass(frozen=True)
class CutScope:
    """Cut 跟 candidate / state / data / oracle 的强绑定."""
    ghost_rect_id: GhostRectId
    blocked_cells_hash: Hash      # ghost ∪ exterior block ∪ mandatory_pre_block
                                  # (含 ghost, ghost change 必变)
    exterior_blocks_hash: Hash    # v3.2.2 (Gemini round 21 B1): 拆出 ghost-
                                  # independent 部分. = sha256(sorted(exterior_blocks
                                  # ∪ mandatory_pre_block)) (不含 ghost cells)
                                  # GHOST_AGNOSTIC cut 校验此字段 (跨 ghost 仍 sound)
    source_digest: SourceDigestStr  # SourceDigest 全 hash (见下)
    artifact_hashes: Dict[str, Hash] = field(default_factory=dict)
                                  # canonical_rules / candidate_placements /
                                  # mandatory_instances 各自 file hash
    oracle_abstraction_version: str = ""    # e.g. "binding_v3", "routing_v2"
    active_assumptions: Tuple[Assumption, ...] = ()

@dataclass(frozen=True)
class SourceDigest:
    """全套 source-of-truth 的 hash bundle, scope.source_digest 等于其规范化 hash."""
    canonical_rules_hash: Hash
    candidate_placements_hash: Hash
    mandatory_instances_hash: Hash
    oracle_versions: Dict[str, str] = field(default_factory=dict)

# === Cut object ===

@dataclass(frozen=True)
class OracleCert:
    """Oracle 给的 cert payload + family-specific. validate 时独立重算."""
    cert_kind: str                # e.g. "farkas_dual_ray", "menger_min_cut",
                                  # "deletion_minimal_core", "shape_packing"
    cert_payload: bytes           # canonical bytes, family validator 解
    cert_hash: Hash               # sha256(cert_payload)

@dataclass(frozen=True)
class Cut:
    """First-class cut object. 跨 session 持久化.

    v3 (Day 14): cut 主体二分 — `literals` (literal-based families: port_exposure,
    pattern_nogood, power_hitting_set) 与 `geometric_payload` (geometric families:
    region_capacity, cutset, component_reach, shape_packing_hall) 互斥.
    """
    cut_id: CutId
    family: CutFamily

    # === Cut 主体: literal-based OR geometric, 必有且只有一个非空 (v3) ===
    # literal-based: families 3 / 5 / 7 — cut 反例可表达成 "(group,slot)=pose" 组合
    literals: Optional[Tuple[CutLiteral, ...]] = None
    # geometric/algebraic: families 1 / 2 / 4 / 6 — cut 通过 cert 的 region /
    # graph / bitset / interval 信息约束, 不指向具体 (group,slot,pose)
    geometric_payload: Optional[bytes] = None

    scope: CutScope = None  # type: ignore[assignment]
    cert: OracleCert = None  # type: ignore[assignment]

    # versions (replay 时 strict match)
    family_version: str = ""      # cut family 数学定义版本 (e.g. "v1.0")
    validator_version: str = ""   # validator 实现版本
    payload_schema_version: int = 1  # JSON envelope schema 版本

    # provenance
    oracle_name: str = ""         # e.g. "PCR-CUT", "D2-separator", "SAC-Hull"
    oracle_cert_hash: Hash = ""   # = cert.cert_hash, 顶层冗余便于 lookup
    minimization_audit: Dict[str, int] = field(default_factory=dict)
                                  # size_before/after, qx_calls, etc.
    created_at: str = ""          # ISO 8601 datetime
    iter_index: int = -1          # 生成时 iter idx (debug only, replay 不依赖)

    # quarantine / demotion (Step 10 defer, 现 frozen 占位)
    is_quarantined: bool = False
    quarantine_reason: str = ""

    def __post_init__(self) -> None:
        # v3 互斥契约: literals 非空 XOR geometric_payload 非空
        has_lit = self.literals is not None and len(self.literals) > 0
        has_geo = self.geometric_payload is not None
        if has_lit == has_geo:
            raise ValueError(
                f"Cut {self.cut_id}: literals 和 geometric_payload 必有且只有一个非空 "
                f"(literals={'set' if has_lit else 'empty/None'}, "
                f"geometric_payload={'set' if has_geo else 'None'})"
            )
        # family ↔ mode 一致性 (防 region_capacity 走 literal-based 之类的错误组合)
        _family_mode = _FAMILY_MODE_MAP.get(self.family)
        if _family_mode == "literal" and not has_lit:
            raise ValueError(f"Cut {self.cut_id}: family={self.family} 要求 literal-based, 但 literals 空")
        if _family_mode == "geometric" and not has_geo:
            raise ValueError(f"Cut {self.cut_id}: family={self.family} 要求 geometric, 但 geometric_payload 空")


# Family ↔ cut-body mode 映射 (post_init 一致性检查用)
_FAMILY_MODE_MAP: Dict[CutFamily, Literal["literal", "geometric"]] = {
    "region_capacity":      "geometric",
    "cutset":                "geometric",
    "port_exposure":         "literal",
    "component_reach":       "geometric",
    "pattern_nogood":        "literal",
    "shape_packing_hall":    "geometric",
    "power_hitting_set":     "literal",
    "symmetry_lift":         "literal",   # 跟 underlying lifted family 一致, 默 literal
}
```

**Field 总数** (Cut object + 嵌套 dataclass 不重计): 14 顶层 (v3: +`geometric_payload` +
postinit 验) + AnonymousSlotRef 2 + CutLiteral 2 + Assumption 2 + CutScope 6 +
SourceDigest 4 + OracleCert 3 **= 33 fields**.

## 4. Scope-aware replay 算法

Critical bug fix on v14 (pose-id-only replay false positive 反例已 cover 在
§5 prompt 内).

v3.1 (Gemini round 14 finding #4): step 加 blocked_cells_hash 校验 → 6 步.

```python
def replay_cut(cut: Cut, state: BState, store: CutStore) -> AttachDecision:
    # === 6 步 verify (v3.1) ===

    # 1. Source digest 比对
    current_digest = compute_source_digest(state)
    if cut.scope.source_digest != current_digest.canonical_hash():
        store.quarantine(cut, reason="source_digest_mismatch")
        return AttachDecision.QUARANTINE

    # 2. Ghost scope match 当前 candidate (v3: GHOST_AGNOSTIC sentinel 跳过比对)
    if cut.scope.ghost_rect_id != GHOST_AGNOSTIC and \
       cut.scope.ghost_rect_id != state.candidate.ghost_rect_id:
        # 不 quarantine — 不同 candidate 用不同 ghost 是正常
        return AttachDecision.HOLD     # 保留, 下个 matching candidate 再试

    # 3. Blocked cells hash 比对 (v3.2.2 — Gemini round 21 B1 dispatch by ghost_rect_id)
    # GHOST_AGNOSTIC cut 容量只受 exterior_blocks 影响, 跨 ghost 仍 sound — 验
    # exterior_blocks_hash. 绑 ghost cut 验全量 blocked_cells_hash.
    # 修法源: round 21 finding B1 — F1 GHOST_AGNOSTIC cut 在 ghost 改时 step 3
    # 必死结. 拆 hash dispatch 后跨 ghost 存活率从 0 → 100%.
    if cut.scope.ghost_rect_id == GHOST_AGNOSTIC:
        if cut.scope.exterior_blocks_hash != compute_exterior_blocks_hash(state):
            store.quarantine(cut, reason="exterior_blocks_hash_changed")
            return AttachDecision.QUARANTINE
    else:
        if cut.scope.blocked_cells_hash != compute_blocked_cells_hash(state):
            store.quarantine(cut, reason="blocked_cells_hash_changed")
            return AttachDecision.QUARANTINE

    # 4. Artifact hashes 比对 (原 step 3, 重编号 v3.1)
    for fname, h in cut.scope.artifact_hashes.items():
        if state.artifact_hashes.get(fname) != h:
            store.quarantine(cut, reason=f"artifact_{fname}_changed")
            return AttachDecision.QUARANTINE

    # 5. Oracle abstraction version 当前可用 (原 step 4, 重编号 v3.1)
    if cut.scope.oracle_abstraction_version not in state.available_oracle_versions:
        return AttachDecision.HOLD     # 不 quarantine, oracle 升级后可能 OK

    # 6. Active assumptions 在当前 state 仍 hold (v3: 走 ASSUMPTION_VERIFIERS dispatch, v3.1 重编号)
    for assumption in cut.scope.active_assumptions:
        if not assumption_holds(state, assumption):
            return AttachDecision.HOLD

    # === 通过 6 步 → 跑 validate (Step 5 of lifecycle, 跟 6 步 verify 不混淆) 再次 sound check ===
    vr = state.get_validator(cut.family).validate(cut, state)
    if vr.kind == "unsound":
        store.quarantine(cut, reason="post_attach_validation_unsound")
        return AttachDecision.QUARANTINE
    if vr.kind == "timeout":
        store.quarantine(cut, reason="validate_timeout")
        return AttachDecision.QUARANTINE

    return AttachDecision.ATTACH
```

**关键不变量** (Gemini round 12 + 13 共同):
- `HOLD` 不删 cut — 等下个 candidate matching 再试
- `QUARANTINE` 不删 cut — 留 audit trail, 不参与 active resolve
- `ATTACH` 后续按 family resolve algorithm (§6) propagate

### Replay 反例 walk-through (v14 bug)

- G1 ghost 挡 A 和 B 间路径 → routing infeasible → cut
  `not(crusher_blue_iron[slot=0] = pA ∧ shop_blue_iron[slot=0] = pB)`
- G2 ghost 移开此挡 → A=pA + B=pB feasible
- v14 replay: 只查 `pA ∈ pose_domain[A]` + `pB ∈ pose_domain[B]` → both true →
  attach → **误剪合法解**
- v2 replay step 2: `cut.scope.ghost_rect_id = G1_id`, 当前 candidate
  `ghost_rect_id = G2_id`, 不 match → `HOLD` (不 attach, 保留)
- 当 candidate 再次 ghost = G1 时, 5 步全 pass + validate 仍 sound → attach

### v3 — Ghost-rect id canonical hash (Gap 4)

```python
def compute_ghost_rect_id(rect: Optional[Rect]) -> GhostRectId:
    """Canonical 16-char hash. 跨 session 稳定, 跨 exterior_block / candidate
    enumeration order 同 ghost rectangle 返同 id.

    不含 blocked_cells_hash: blocked_cells = ghost ∪ exterior ∪ pre_block 是
    derived, 单独走 CutScope.blocked_cells_hash field 在 replay step 3 比对.
    """
    if rect is None:
        return GHOST_AGNOSTIC
    blob = f"{rect.x},{rect.y},{rect.h},{rect.w}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]
```

### v3 — Active assumption dispatch (Gap 5)

```python
ASSUMPTION_KEYS = Literal[
    # F1 source-of-truth assumption
    "left_or_bottom_boundary_saturation",
    # F2 source-of-truth + state-conditioned
    "boundary_pose_shape",
    "boundary_region",
    # F3 source-of-truth assumption
    "power_pole_radius",
    "power_pole_shape",
    # F4 state-conditioned assumption
    "g1_blocks_AB_path",
    # Day 15-17 各 cut family 自加 (per cut_family_spec.md)
]

# Verifier 函数签名: (BState, value_str) -> bool
ASSUMPTION_VERIFIERS: Dict[str, Callable[[BState, str], bool]] = {
    "left_or_bottom_boundary_saturation": _verify_boundary_saturation,
    "boundary_pose_shape":                _verify_pose_shape_constraint,
    "boundary_region":                    _verify_region_membership,
    "power_pole_radius":                  _verify_power_pole_radius,
    "power_pole_shape":                   _verify_power_pole_shape,
    "g1_blocks_AB_path":                  _verify_ghost_blocks_path,
    # Day 15-17 扩展
}

def assumption_holds(state: BState, assumption: Assumption) -> bool:
    """Replay step 5 dispatch. 未知 key → fail-closed (HOLD), 不 quarantine.

    两类 assumption (Day 15-17 每 key 标 source-of-truth / state-conditioned):
    - source-of-truth: 验 `canonical_rules.json` 等 file hash, 全 source rotated
      时变, 否则 always hold
    - state-conditioned: 在特定 ghost / state 下成立, 重跑 oracle
    """
    verifier = ASSUMPTION_VERIFIERS.get(assumption.key)
    if verifier is None:
        # PROJECT_LOCK fail-closed: 未知 assumption 不 attach (silent recovery 禁)
        return False
    return verifier(state, assumption.value)
```

## 5. Group state ↔ Port-binding cut 接口 contract

(跟 Dev A state_machine_v2 doc 共识界面; 本 doc 只写 cut object 端 contract.)

### 问题

Group state 把 132 manufacturing_3x3 同质 facility 合并为 group, group 内
无 instance ID (state 只 carry `selected_pose_assignments: List[PoseId]`).
但 cut 必须 reference 具体 instance 给 port-binding 检查 (binding 关心
instance level 的 port direction).

### 解 (anonymous slot ref)

cut literal 用 `(group_id, slot_index, pose_id)` 三元组, 而不是
`(instance_id, pose_id)`.

```python
# Cut 例:
literals = (
    CutLiteral(AnonymousSlotRef("crusher_blue_iron", 0), 17),
    CutLiteral(AnonymousSlotRef("crusher_blue_iron", 1), 23),
    CutLiteral(AnonymousSlotRef("shop_blue_iron", 0), 42),
)
# 语义: not (group "crusher_blue_iron" 内 slot=0 pose=17 ∧ slot=1 pose=23 ∧
#            group "shop_blue_iron" 内 slot=0 pose=42)
```

### Resolve 映射 (Step 7)

BState 内每 group carry:

```python
@dataclass
class GroupState:
    group_id: GroupId
    selected_pose_assignments: List[PoseId]   # group 内 enumeration order
                                              # (master 决定后 frozen)
    # slot_index 对应位置 → selected_pose_assignments[slot_index]
```

Validator (per family) 收 cut + BState 后:

```python
def evaluate_literals(cut: Cut, state: BState) -> bool:
    """全 literal match 则 cut violated."""
    for lit in cut.literals:
        group = state.groups[lit.slot_ref.group_id]
        if lit.slot_ref.slot_index >= len(group.selected_pose_assignments):
            return False  # group 还没填满, cut 暂不 violate
        if group.selected_pose_assignments[lit.slot_ref.slot_index] != lit.pose_id:
            return False
    return True  # 全 match → violate
```

### Cross-group permutation soundness

anonymous slot 是 group 内 interchangeable 的, 任何 permutation
σ: slots → slots 都 sound. 但**enumeration order**是 BState 内部决定; cut
学完的 slot 顺序在下一 candidate 内会不同 order. 这是 sound bug 风险.

**修法**: enumeration order 不参与 cut soundness 推理. 替代是把 cut 当
"set of (group_id, pose_id) multiset" — 即 cut violates 当且仅当 group 内
存在某种 slot assignment 使 literals 全 match. 这等价 multiset 包含关系:

```python
def evaluate_cut_literal_based(cut: Cut, state: BState) -> bool:
    """Multiset 包含语义跟 slot enumeration order 无关 → 跨 candidate replay sound.

    仅适用 literal-based cut (Cut.literals 非空, family ∈ {port_exposure,
    pattern_nogood, power_hitting_set, symmetry_lift}).
    """
    assert cut.literals is not None, "literal-based evaluate 要求 cut.literals 非 None"
    # 按 group_id group cut 的 literals
    cut_demand_by_group: Dict[GroupId, List[CutLiteral]] = group_by(
        cut.literals, key=lambda l: l.slot_ref.group_id
    )
    # 当前 state 内 group 的 multiset
    state_by_group: Dict[GroupId, Counter[PoseId]] = {
        gid: Counter(g.selected_pose_assignments) for gid, g in state.groups.items()
    }
    # 每 group cut_demand multiset ⊆ state multiset 都成立 → violate
    for gid, demand in cut_demand_by_group.items():
        demand_counter = Counter(l.pose_id for l in demand)
        if not (demand_counter <= state_by_group.get(gid, Counter())):
            return False
    return True
```

multiset 包含语义跟 slot enumeration order 无关 → 跨 candidate replay sound.

> 注: slot_index 只为 **debug / serialization stability** 保留 (cut object
> JSON repr 顺序固定). Resolve / validate 不用它做 soundness 判定.

### v3 — Family-dispatch evaluate (Gap 3)

cut object 上加 family-dispatch 入口, 走 literal-based 或 geometric 两个 path:

```python
def evaluate_cut(cut: Cut, state: BState) -> bool:
    """Cut 是否在当前 state 上 violate. v3 family-dispatch entry.

    根据 Cut.literals / Cut.geometric_payload 互斥 contract (§3 _FAMILY_MODE_MAP)
    走 literal-based multiset evaluate 或 geometric validator.evaluate_geometric.
    """
    if cut.literals is not None:
        # Literal-based path (Family 3 port_exposure / 5 pattern_nogood / 7 power_hitting_set / lift)
        return evaluate_cut_literal_based(cut, state)
    elif cut.geometric_payload is not None:
        # Geometric path (Family 1 region_capacity / 2 cutset / 4 component_reach / 6 shape_hall)
        validator = state.get_validator(cut.family)
        return validator.evaluate_geometric(cut, state)
    else:
        # __post_init__ 已保证不会到此, 保 defensive
        raise ValueError(f"Cut {cut.cut_id}: both literals and geometric_payload are None")
```

`evaluate_cut` 是 propagation hot path (每次 state change 经 watcher hit 后调用).
跟 §6 `validate` 区分:
- `evaluate_cut(cut, state) -> bool` — 快速 violate 检查, 不重算 cert
- `validate(cut, state) -> ValidationResult` — sound 性 second line of defense,
  独立重算 cert, 走 timeout-bounded budget

## 6. Validator contract per cut family

每 family 自己 validator + version. cut object 内带 `validator_version`,
replay 时 version match 才 attach.

```python
class CutValidator(Protocol):
    family: CutFamily
    validator_version: str

    def validate(self, cut: Cut, state: BState) -> ValidationResult:
        """Sound 性 second line of defense — 不信 oracle cert, 独立重算.

        timeout-bounded (default 1s, Quarantine 政策见 §8). 走 replay step 5.
        """

    def evaluate_geometric(self, cut: Cut, state: BState) -> bool:
        """v3 propagation hot path — 几何/代数 cut 是否在当前 state 上 violate.

        仅 geometric family 必实 (region_capacity / cutset / component_reach /
        shape_packing_hall); literal-based family 实现可 raise NotImplementedError.

        不重算 cert; 只解 cut.geometric_payload 跟当前 state 的 free_cells /
        cell_owner / groups / ghost 检查 violate 条件.
        """
```

> v3: 每 family 下面 "Validator" 段是 `validate` 实现要点; v3 加 family
> evaluate_geometric 草拟在每 family 下补一行 (Day 15-17 完整数学定义).

### Family 1: region_capacity (geometric)

- Validator: 取 `cut.cert.cert_payload` 含 `(region_bitset, cap_R, LP_dual)`.
  独立重算: region 内 free_cells 数 |R|; 验 cap_R ≤ |R| (sound 下界).
  若 cert 带 Farkas dual (LP relaxation lower bound), 跑 algebraic check
  `yᵀ A ≤ 0 ∧ yᵀ b > 0`.
- v3 evaluate_geometric: 解 `geometric_payload` 含 `(region_cells_bitset,
  cap_R, demand_R)`; 算当前 state 内 region 已占 demand
  (`placed_demand_in_region(state, region)`); 若 `placed_demand > cap_R` → True.
- 复用: cand C `farkas_certificate.py` HiGHS dual ray extract logic (见 §9).

### Family 2: cutset (geometric)

- Validator: cert 含 `(side_a_bitset, side_b_bitset, k_AB, Menger_witness)`.
  独立跑 max-flow min-cut on `state.belt_routing_graph` 取 partition (A, B)
  上的 belt-usable edge count, 验 ≥ k_AB.
- v3 evaluate_geometric: 解 `geometric_payload` 含 `(side_a, side_b, k_AB)`;
  算当前 state.free_cells 上 boundary cut size; 若 < k_AB → True.
- 复用: PCR-CUT `patch_routing_core.py` min-cut helper.

### Family 3: port_exposure (literal)

- Validator: cert 含 `(facility_instance_or_slot, port_cell, direction,
  active_witness)`. 重算 front_cell, 验 `state.cell_owner[front_cell]` 非
  conflicting facility; 验 active_witness (binding 端给的 port active cert)
  在 state 当前 binding selection 下仍 hold.
- v3 evaluate_geometric: 不实现 (literal-based, 走 §5 multiset evaluate).
- 复用: cand C `boundary_constraints.py` per-(cell, dir) net flow equality
  逻辑 (作为 active port set 一致性 sanity).

### Family 4: component_reach (geometric)

- Validator: cert 含 `(src_cell, sink_cell, free_cells_at_gen, witness_path)`.
  独立 BFS on `state.free_cells` 验 src→sink 连通; 若 cert 携 witness_path,
  逐边验所有 edge 在当前 free_cells 上 belt-usable.
- v3 evaluate_geometric: 解 `geometric_payload` 含 `(src, sink, witness_path)`;
  跑 BFS 在 `state.free_cells` 上验 src→sink **不可达** → True.
- 复用: D2 `d2_separator.py` BFS / Tarjan helper.

### Family 5: pattern_nogood (literal)

- Validator: cert 含 `(forbidden_pose_pattern, sub_problem_oracle_name,
  oracle_cert_hash)`. 重算: 对 cut.literals 跑 §5 multiset 检查; 若 state
  现状满足 literals 全 match → 验 sub-problem oracle 在 forbidden_pose_pattern
  上重跑给 INFEASIBLE.
- v3 evaluate_geometric: 不实现 (literal-based, 走 §5 multiset evaluate).
- 复用: L16 deletion-based core minimizer + PCR-CUT QuickXplain (sub-problem
  oracle 复用).

### Family 6: shape_packing_hall (geometric, v3 新)

- Validator: cert 含 `(region, partition_lens, pose_length, max_packable,
  demand, witness)`. 独立重算: 取当前 state.free_cells 在 region 上, 按 ghost
  切 maximal-free-interval; 算 `sum(⌊len(I_k) / pose_length⌋)`; 验 < demand
  (Hall infeasibility witness).
- v3 evaluate_geometric: 同 validator 路径, 不重 oracle cert (oracle 端 cert
  已在 attach 时验过), 只算当前 partition. F2 反例 owner.
- 复用: 暂无, Day 15-17 写新 helper `compute_baseline_partition_lens`.

### Family 7: power_hitting_set (literal, v3 新)

- Validator: cert 含 `(facility_pose, facility_cells, pole_radius,
  candidate_pole_poses_before_ghost, candidate_pole_poses_after_ghost,
  ghost_blocked_pole_cells, witness)`. 独立重算: 在当前 ghost 下重算 candidate
  pole 候选; 验空 set (hitting-set INFEASIBLE).
- v3 evaluate_geometric: 不实现 (literal-based, 走 §5 multiset evaluate).
- 复用: `src/search/benders_loop.py:4219-4268` L16 lazy power completion logic.

### Family 8 (variant): symmetry_lift

- 不是新 family, 是 1-7 的 lifted version. Validator 跟 underlying family
  一致, 额外验 `cut.cert.cert_payload` 里的 orbit + permutation 跟当前
  `state.symmetry_groups` 一致 (orbit detection 来源
  `mandatory_exact_instances.json`).
- v3 evaluate_geometric: dispatch 到 underlying family 的 evaluate_geometric
  (若 underlying 是 geometric); literal 同 §5 multiset.

### ValidationResult

```python
@dataclass(frozen=True)
class ValidationResult:
    kind: Literal["ok", "unsound", "timeout", "schema_err"]
    elapsed_seconds: float
    detail: Optional[str] = None
    # ok: cut sound; unsound: 重算 cert fail; timeout: > 1s budget;
    # schema_err: cert payload schema 错
```

## 7. Cut store + watcher index

cut store 是中央数据结构, 5 维 watcher index 避免每轮扫全表.

```python
@dataclass
class CutStore:
    cuts: Dict[CutId, Cut] = field(default_factory=dict)

    # 6 维 watcher (v3.2 Day 17d 加 by_ghost — Family 6/7/8/9 ghost-bound 必需)
    by_cell_watcher: Dict[Cell, Set[CutId]] = field(default_factory=lambda: defaultdict(set))
    by_group_watcher: Dict[GroupId, Set[CutId]] = field(default_factory=lambda: defaultdict(set))
    by_pose_watcher: Dict[Tuple[GroupId, PoseId], Set[CutId]] = field(default_factory=lambda: defaultdict(set))
    by_commodity_watcher: Dict[CommodityId, Set[CutId]] = field(default_factory=lambda: defaultdict(set))
    by_region_watcher: Dict[RegionId, Set[CutId]] = field(default_factory=lambda: defaultdict(set))
    by_ghost_watcher: Dict[GhostRectId, Set[CutId]] = field(default_factory=lambda: defaultdict(set))
                                                # v3.2 — ghost_rect 变直接 invalidate
                                                # by ghost_rect_id; ghost_rect_id =
                                                # GHOST_AGNOSTIC 的 cut 不入此 watcher

    # Quarantine (Step 9)
    quarantined: Dict[CutId, "QuarantineReason"] = field(default_factory=dict)

    # Hold (HOLD decision retention)
    held: Set[CutId] = field(default_factory=set)
```

### Watcher 添加规则 (Step 8)

每 family attach 时按规则添 (v3.2 Day 17d 加 7/8/9 + 6 维 by_ghost):

| Family | watcher domain |
|---|---|
| 1 region_capacity | `by_cell_watcher` (每 cell ∈ region) + `by_region_watcher[region_id]` |
| 2 cutset | `by_cell_watcher` (cut_edges 端点) + `by_commodity_watcher` + `by_ghost_watcher` |
| 3 port_exposure | `by_cell_watcher[port_cell, front_cell]` + `by_group_watcher` + `by_pose_watcher` (v3.2.1 Gemini round 16 A2: 不入 by_ghost — F3 spec §5 明定 ghost-blocked front 不发 cut, 跟 ghost 无关) |
| 4 component_reach | `by_cell_watcher` (separator_cells) + `by_commodity_watcher` + `by_ghost_watcher` |
| 5 pattern_nogood | `by_group_watcher` (每 group 涉及) + `by_pose_watcher[(group, pose)]` + `by_ghost_watcher` (oracle 跟 ghost 绑) |
| 6 shape_packing_hall (v3) | `by_cell_watcher` (region cells) + `by_region_watcher` + `by_group_watcher` + **`by_ghost_watcher`** |
| 7 power_hitting_set (v3) | `by_cell_watcher` (facility + ghost_blocked) + `by_group_watcher` + `by_pose_watcher` + **`by_ghost_watcher`** |
| 8 power_grid_reach (v3) | `by_cell_watcher` (facility + candidate poles) + `by_pose_watcher` + **`by_ghost_watcher`** |
| 9 density_envelope (v3) | `by_cell_watcher` (window 内 cell) + `by_group_watcher` + **`by_ghost_watcher`** |
| symmetry_lift | underlying family 同 + 全 orbit groups |

state change → 只看对应 watcher 内 cut 重 evaluate. Big-O 从 O(全 cut)
降到 O(影响 cut).

### v3.2 by_ghost_watcher 工作流

ghost_rect change 是 critical state transition — 几乎所有 geometric/literal
ghost-bound cut 都需要重 attach-scope check. by_ghost_watcher 加速:

```python
def on_ghost_rect_changed(state: BState, new_ghost_id: GhostRectId, store: CutStore) -> None:
    """ghost change 触发 affected cut 重 replay."""
    # 旧 ghost_id 关联的 cut 全 hold (不 attach, 不 quarantine — 等下次 match)
    old_ghost_id = state.previous_ghost_rect_id
    affected = store.by_ghost_watcher.get(old_ghost_id, set())
    for cut_id in affected:
        cut = store.cuts[cut_id]
        # 已 attach 的 cut: hold (从 active 移到 held set)
        store.held.add(cut_id)
        # 不删 cut, 不 quarantine (下次 ghost 回 old_id 时 re-attach OK)

    # 新 ghost_id 关联的 cut 重跑 replay (5/6 步 verify)
    candidates = store.by_ghost_watcher.get(new_ghost_id, set())
    for cut_id in candidates:
        cut = store.cuts[cut_id]
        decision = replay_cut(cut, state, store)  # v3.1 6 步 verify
        if decision == "ATTACH":
            store.held.discard(cut_id)  # 从 held 移回 active
```

GHOST_AGNOSTIC cut (e.g. F1 boundary saturation) 不入 by_ghost_watcher,
ghost 变不影响其 attach. blocked_cells_hash 校验 (v3.1 step 3) 仍可能让
GHOST_AGNOSTIC cut quarantine — by_blocked_cells watcher Phase 1 加 (7 维).

## 8. Quarantine + source digest 政策

### Quarantine 状态机

```
Cut state machine:
    ACTIVE → QUARANTINE: validate unsound / timeout / scope mismatch /
                         post_attach_validation_unsound / artifact_changed
    HOLD → ACTIVE: 下个 candidate scope match + validate sound
    HOLD → QUARANTINE: regression sweep 时 validate unsound
    QUARANTINE → (no transition): 不 auto-recover; 手动 audit 可 override
```

### Quarantine 政策

- **不删** cut: 保 audit trail, regression sweep 可 dry-run 跑历史 cut
- **不 active**: 不进 resolve loop, 不影响 propagation
- 写 `data/cuts/quarantine/{cut_id}.json` 跟 active store 物理分离
- log 全 reason: schema 错 / scope 不 match / validate timeout / source
  digest 变 / artifact hash 变 / post-attach unsound
- 手动 override: `EXACT_CUT_STORE_FORCE_REACTIVATE=cut_id1,cut_id2,...` env
  (debug 用, 不应 production)

### Quarantine ↔ source digest 交互

**关键 hard rule** (Gemini round 12): source change → 所有 cut 必须重 validate.

- campaign 启动时算当前 SourceDigest hash
- load cut store 时每 cut 跑 step 5/6 (validate + attach-scope check)
- 任一 source artifact hash 变 → 全 store cut quarantine + audit log "source
  rotated, store invalidated, manual review required"
- 不 auto-recover: 即使重新计算 cert / validator 在新 source 下 sound,
  仍要手动 override (PROJECT_LOCK 要求 certified exact, 不允许 silent
  recovery)

例外: oracle_versions 单一升级 (e.g. `binding_v3` → `binding_v4`) 不算
source change — oracle 是 implementation, source-of-truth 是数据.
这种 case 走 step 6 attach-scope check 的 `oracle_abstraction_version`
HOLD 路径, 不 quarantine.

### Source digest 计算

```python
def compute_source_digest(state: BState) -> SourceDigest:
    return SourceDigest(
        canonical_rules_hash=sha256_file("rules/canonical_rules.json"),
        candidate_placements_hash=sha256_file("data/preprocessed/candidate_placements.json"),
        mandatory_instances_hash=sha256_file("data/preprocessed/mandatory_exact_instances.json"),
        oracle_versions={
            "binding": "v3",
            "routing": "v2",
            "pcr_cut": "v1",
            "d2_separator": "v1",
            "sac_hull": "v1",
        },
    )

def canonical_hash(sd: SourceDigest) -> str:
    # canonical bytes: 字段名按 ASCII 字典序 + 值 verbatim + null-byte 分隔
    blob = b"\x00".join([
        b"canonical_rules", sd.canonical_rules_hash.encode(),
        b"candidate_placements", sd.candidate_placements_hash.encode(),
        b"mandatory_instances", sd.mandatory_instances_hash.encode(),
        b"oracle_versions", json.dumps(sd.oracle_versions, sort_keys=True).encode(),
    ])
    return hashlib.sha256(blob).hexdigest()
```

## 9. 复用 from cand C Phase 2 v3

cand C v3 ~3000 LOC, B Design v2 复用如下 (per `reuse_from_cand_c.md` 扩展):

### Direct reuse (Validator templates)

- **`farkas_certificate.py`** (~? LOC) →
  - LP/Farkas algebraic validator template (Family 1 region_capacity 的
    LP-dual cert validation)
  - HiGHS dual ray extract 逻辑 (presolve=off, getDualRay)
  - hotspot cell 提取 → 可作 Family 1 sound 性 second check
- **`column_grammar.BoundarySignature`** (Phase 1) →
  - 作 `CutScope.active_assumptions` 的一种 entry kind ("perimeter saturation")
  - canonical_bytes() 方法直接复用 → 保 hash 稳定
- **`integer_validator.py`** (Phase 1) →
  - `check_set_partitioning` strict validator → Family 5 pattern_nogood
    sub-problem oracle 验 cert 用

### Indirect reuse (Oracle infrastructure)

cut generation 端 (Step 1) 复用各 paradigm PoC infrastructure (在
`reuse_from_cand_c.md` 已列, 此 doc 不重复):
- PCR-CUT `patch_routing_core.py` → Family 2 cutset oracle
- D2 `d2_commodity_flow_core.py` + `d2_separator.py` → Family 4 component_reach
- SAC-Hull `sac_hull_separator.py` → Family 1 region_capacity
- L16 deletion minimizer → Family 5 pattern_nogood minimization
- B1 `pose_bool_exact_master.py` → small-candidate fallback oracle

### Drop (不复用)

- cand C RMP / RF / column generation LP logic — Design B 不在 λ-space
- `alternative_blueprint_generator.py` — LP-level 加 column, B 不用 LP

## 10. Open questions / 风险

defer to Phase 1 (实施) 解决:

1. **Group enumeration order across candidate**: §5 multiset 解 sound 但
   serialization 内 slot_index 顺序是否影响 JSON diff / git review 体验?
   defer: Phase 1 跑 1-2 demo 看 diff 噪音.
2. **Quarantine cut 累积 disk 占用**: 168h campaign quarantine 量未估.
   defer: Phase 1 / 2 加 disk quota + rotation; 暂不删但加 archive 机制.
3. **Validator version skew 在 long campaign**: campaign 中 validator 升
   级 → 全 cut quarantine 太激进. defer: 设 validator_compat_matrix (老
   validator 跑老 cut 仍 OK 的条件).
4. **Watcher index disk persist**: 5 维 index 跨 session 重建成本 (load
   全 cuts 重建 vs disk cache index)? defer: Phase 1 measure.
5. **Symmetry-lifted cut 的 cert hash 稳定性**: orbit permutation 后 cert
   hash 变, lifted cuts 之间不 dedupe → 浪费. defer: Phase 1 加 orbit
   canonical form 跟 cert_hash 一致化.

Step 10 (dominance/expiry/demotion) **defer to Phase 2** per Gemini round 13
— 9 步链路 runtime correctness 先稳, subsumption / hit-count / age 加进
store 不当会埋 bug.

---

**Doc 路径**: `docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md`
**LOC**: ~480 lines (within ≤ 700 cap)
**Phase 1 (实施) 不在本 doc scope**
