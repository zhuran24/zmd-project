# B Component 2: Cut object 6-step lifecycle

## 为什么需要完整 lifecycle

27 lever 死法 B (cut 表达力被 master 维度锁) 的一个根因是: cut 在 CP-SAT
solver 内是 lazy clause, **不能跨 session 持久化 + 跨 candidate 复用**.

每次重启 / 切 anchor / 切 candidate, cut 全部丢失. sub-problem 重新跑出
新 cert, master 重新加 cut, 同质 cut 重复加 N 次浪费.

Design B 把 cut 当独立 object, 6 步 lifecycle:

```
generate → serialize → deserialize → validate → resolve → replay → regression
```

每步独立可测 + 跨 session 持久化, 解决 cut 重用问题 + 增强 audit/debug.

## Step 1: Generate

sub-problem oracle 返回 cert + cut spec:

```python
@dataclass
class CutSpec:
    family: Literal["region_capacity", "cutset", "port_exposure",
                    "component_reach", "pattern_nogood", "symmetry_lift"]
    payload: Dict[str, Any]                 # family-specific data
    causal_state_snapshot: StateSnapshot    # cut 是基于哪个 state 生成的
    sub_problem_cert: SubProblemCert        # sub-problem oracle 返回的 cert
    timestamp: datetime
    cut_id: UUID                            # globally unique
```

`payload` 是 family-dependent. 比如:
- region_capacity: `{"region_bitset": Bitset, "max_cells": int}`
- cutset: `{"side_a_bitset": Bitset, "side_b_bitset": Bitset, "min_cut": int}`
- port_exposure: `{"port_cell": Cell, "dir": Direction, "required_clear": List[Cell]}`
- component_reach: `{"required_component_edges": List[Edge]}`
- pattern_nogood: `{"forbidden_assignment": Dict[InstanceId, PoseId]}`
- symmetry_lift: `{"orbit": List[InstanceId], "rep_cut": CutId}`

## Step 2: Serialize

```python
def serialize(cut: CutSpec) -> bytes:
    """Cut → JSON bytes. bitset 转 base64."""
    payload = {
        "cut_id": str(cut.cut_id),
        "family": cut.family,
        "payload": serialize_payload(cut.payload),  # family-specific
        "causal_state_snapshot_hash": state_hash(cut.causal_state_snapshot),
        "timestamp": cut.timestamp.isoformat(),
    }
    return json.dumps(payload).encode()
```

写入 `data/cuts/{cut_id}.json`. JSON + bitset base64 保证人类可读 + git
可 diff.

state_snapshot 只存 hash, 不存完整 snapshot — snapshot 可重新构造 (state
machine 是 deterministic).

## Step 3: Deserialize

```python
def deserialize(blob: bytes) -> CutSpec:
    """JSON bytes → Cut. validate schema."""
    payload = json.loads(blob)
    family = payload["family"]
    deserialized_payload = deserialize_payload(family, payload["payload"])
    return CutSpec(
        cut_id=UUID(payload["cut_id"]),
        family=family,
        payload=deserialized_payload,
        # state snapshot 不 reconstruct, 只 hash
        causal_state_snapshot=StateSnapshotRef(payload["causal_state_snapshot_hash"]),
        ...
    )
```

deserialize 后 cut 还没 attach 到 state machine, 是 standalone object.

## Step 4: Validate

```python
def validate(cut: CutSpec) -> ValidationResult:
    """Cut 是否 sound. 数学论证检查."""
    if cut.family == "region_capacity":
        # 验证 sum of cells_used in region ≤ region_cap 是 sound
        # i.e. 任何 layout 在 region 内 facility 占用总 cell ≥ region_cap + 1 都不可行
        return validate_region_capacity(cut.payload, cut.sub_problem_cert)
    elif cut.family == "cutset":
        # 验证 min-cut ≥ k 是 routing infeasibility cert
        return validate_cutset(cut.payload, cut.sub_problem_cert)
    # ... 各 family 自有 validate
```

validate 跑独立验证 logic, **不**信任 sub-problem oracle 的 cert. 即使 cert
有 bug, validate 仍要数学论证 cut 是 sound.

→ 这是 sound 性 second line of defense. PROJECT_LOCK 要求 certified exact,
任何 sound cut 都要可独立验证.

## Step 5: Resolve

attach cut 到 state machine, propagate:

```python
def resolve(cut: CutSpec, state: MasterState) -> ResolveOutcome:
    """对当前 state 推理 cut 的 implication."""
    if cut.family == "region_capacity":
        # 看 state 在 region 内已 placement 的 cell 数
        used = sum(p.cells_in(cut.payload.region_bitset) for p in state.placement.values() if p)
        if used > cut.payload.max_cells:
            return ResolveOutcome("infeasible", conflict_set=...)
        # 看哪些 pose 加入会让 used 超 cap → 缩 pose_domain
        removed = {}
        for i, poses in state.pose_domain.items():
            for p in poses:
                if used + p.cells_in(cut.payload.region_bitset) > cut.payload.max_cells:
                    removed.setdefault(i, set()).add(p)
        return ResolveOutcome("domain_change", removed_poses=removed)
    # ... 各 family 自有 resolve
```

resolve 是 cut 的核心运行时. propagation loop 在 Step 5 调每个 active cut.

## Step 6: Replay

跨 candidate / 跨 session 时 cut store load 完, 每个 cut 需要在新 state
下 replay:

```python
def replay(cut: CutSpec, new_state: MasterState) -> ReplayOutcome:
    """Cut 在 new_state 是否仍 sound + 仍 attach-able."""
    # 验证 cut.causal_state_snapshot 跟 new_state 兼容
    # e.g. cut 在 ghost (22,28,15,27) 下生成, 当前 candidate 是 ghost (10, 15, 20, 20)
    # — 多数 cut family 跟 ghost 形状无关 (pattern_nogood 跟 ghost 强耦合)
    
    if cut.family == "pattern_nogood":
        # pattern 是 specific (instance, pose) tuple list
        # 验 instance.pose 在 new state 仍 valid pose_data_count
        for (i, p) in cut.payload.forbidden_assignment.items():
            if p not in new_state.pose_domain.get(i, set()):
                return ReplayOutcome("pose_not_valid_in_new_candidate", attach=False)
        return ReplayOutcome("ok", attach=True)
    
    elif cut.family == "region_capacity":
        # region 跟 ghost 关系: 若 cut 区域跟新 ghost 重叠, 调整 max_cells
        # 通常 sound (减小 max_cells 不破坏 soundness)
        return ReplayOutcome("ok", attach=True)
    # ...
```

replay 关键 invariant: **cut 跨 candidate 不允许 false positive** (即不能
切掉新 candidate 的合法 layout). false negative 允许 (即 cut 不再 useful
就 detach).

→ 替不可 attach 的 cut 标 inactive, 不删 disk (保留 audit trail).

## 额外 Step 7: Regression

```python
def regression_test(cut_store: CutStore) -> List[CutId]:
    """跨 candidate sweep, 验所有 cut 仍 sound + replay 正确."""
    failed = []
    for cut in cut_store:
        for candidate in test_candidates:
            new_state = build_state_for_candidate(candidate)
            outcome = replay(cut, new_state)
            if not outcome.is_sound():
                failed.append(cut.cut_id)
    return failed
```

Regression sweep 在 disk 上 cut store 持久化的优势 — 任意时刻可重跑全
sweep 验所有历史 cut 仍 sound. 这是 audit/debug 的核心 tool.

## 项目历史的 cut lifecycle 设计 (实测教训)

项目方曾在 v4 GPT review 给出 6 步 lifecycle schema, 实现了 generate +
serialize + deserialize 但**没**完整跑 validate / replay / regression. v4
follow-up 8 commit 留下 schema, **runtime correct 没**: schema landed ≠
runtime correct (项目 memory 内 [[feedback-proof-object-lifecycle]] 提醒).

→ B 设计要把 6 步**全 runtime 跑通**, 不是只 schema landed.

## 现 cand C 跟 B lifecycle 的对比

cand C 在 Phase 2 v3 内 RF branching node 有 trace + serializable, 但
cut 仍是 RMP / pricing LP 内部 implicit (Σ_k λ_k 形式), 没独立 cut object
+ 没跨 session 持久化.

B 设计的 cut object 是显式 first-class object, lifecycle 全 6 步独立可测.

## Stress test 视角

- 6 步 lifecycle 是否完整? 哪步缺?
  - 比如: cut promotion / cut demotion 跨 candidate 时是否需要单独 step?
  - cut conflict (两个 cut 互相 contradict 时) 怎么处理?
- validate step 数学论证是否能 cover 所有 5 cut family?
  - 哪些 family 的 validate logic 难 (e.g. component reachability 跟
    routing 强耦合, validate 需要跑 oracle)
- replay 在 false positive 上是否 sound?
  - cross-candidate replay 在 ghost rect 变化时, cut 是否可能 incorrectly
    prune
- regression 测试在 168h campaign 长 sweep 中的实施成本?
