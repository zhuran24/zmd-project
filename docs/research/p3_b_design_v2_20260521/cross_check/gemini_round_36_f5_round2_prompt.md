# F5 pattern_nogood — Round 2 Gemini cross-check (修复 verify + 新 finding push)

## 上下文

这是**第二轮**审查. Round 1 你 (Gemini 3 Pro) 给了 NOT_GO + 6 findings. Main Claude 已经修了其中 4 个 (Fix #1/#3/#4/#5), 另外 2 个 (#2 deletion vs QuickXplain / #6 module-level registry vs multi-process) defer 到 Phase 1.5+ — 因为 Phase 1.2 是 dummy oracle 单进程, defer 不影响当下 soundness.

修后状态: pytest 243 pass, ruff clean, mypy strict 25 source files 0 errors, vulture clean, bandit clean, radon avg complexity A 4.31, exit_criteria 0 FAIL.

**Round 2 任务**:
1. **Verify fix 正确性** — Main Claude 的每个 fix 是不是真解决问题? 引入新 gap 吗?
2. **Round 1 漏 finding** — round 1 是黑盒看 spec, round 2 看实际 src 代码, 应该能 catch round 1 漏的 algorithm/data/前提 bug.
3. **不接受 GO 章 ritual** — round 1 你给了 6 finding, round 2 不可能全无问题. 你要 push find. design 全 clean 这种 verdict 默认 reject — 必须列具体 file:line + 反例 + reproduce.

## Round 1 finding 回顾 + Main Claude 修复方案

### Finding #1 [BLOCKER] cert_payload 含 sub_problem_witness_hash 跨 worker 不复现

**Round 1 问题**: cert_payload 把 sub_problem_witness_hash 当 deterministic 字段 sha256 进 cert_hash, 但底层 binding/routing CP-SAT 在不同 worker 上可能返回不同的 INFEASIBLE witness (不同 IIS / 不同 conflict reason / 不同 unsat core). 这让 cert_hash 跨 worker 不稳定, 同一 cut 在不同 worker 上有不同 cert_hash → CutStore 去重失败 / replay 跨 worker fail.

**Main Claude 修法 (Fix #1)**:
- cert_payload 移除 sub_problem_witness_hash 字段
- Validator 不再 schema-check witness hash
- Validator 唯一 soundness check 改为: re-query adapter on `forbidden_pose_pattern`, 必须返 INFEASIBLE
- Witness bytes 仍由 generator 收到, 但**不进 cert** (单纯丢弃)

**你要 review**:
- (a) 这真解决跨 worker 复现吗? cert_payload 现在还有 non-deterministic 字段吗?
- (b) Validator 不再有 witness identity binding, 仅靠 re-query INFEASIBLE — 这够 sound 吗? 攻击场景: 攻击者伪造一个 fake `forbidden_pose_pattern`, 但 adapter 恰好在那个 core 上也独立 INFEASIBLE (不是因为同一个 binding 死法). validator 接受这个 cert — 这是 false positive 吗? F5 cut 语义是不是只是"这个 literal 组合 sub-problem INFEASIBLE" 就够? 不需要 binding 到具体 IIS?
- (c) Witness bytes 收到但丢弃 — generator 现在收 witness 干嘛? 不应该完全去掉吗?

### Finding #3 [HIGH] Validator 5s deadline < Generator 10s budget

**Round 1 问题**: `_VALIDATOR_REVERIFY_DEADLINE_SECONDS = 5.0` 但 `MinimizerBudget.max_seconds = 10.0`. 如果 generator 用 9.5s solve 出来 INFEASIBLE 加 cut, validator 重 query 限 5s 必 TIMEOUT, cut 被 quarantine. 合法 cut 系统性丢失.

**Main Claude 修法 (Fix #3)**: `_VALIDATOR_REVERIFY_DEADLINE_SECONDS = 5.0 → 10.0` match generator default.

**你要 review**:
- (a) 10s == 10s 是不是边界刚刚好? generator 在 wall=10s 边界返 INFEASIBLE, validator 也按 wall=10s 走 — 如果 adapter 内部 wall-clock 测量有 ε 抖动 (e.g. 一个 worker 测 9.99s, 另一个测 10.01s) validator TIMEOUT, 边界条件不稳. 应该 validator > generator (e.g. 15s) 留 buffer 吗?
- (b) Phase 1.5+ 真接 binding/routing CP-SAT, sub-problem solve 可能分钟级. Validator 10s deadline 必 TIMEOUT, 所有 cut quarantine. 这个 fix 撑得到 Phase 1.5 吗? 还是 Phase 1.5 入口必须重做 deadline 策略?
- (c) Generator 用 MinimizerBudget(max_seconds=X), validator hardcode 10s — 这俩应该用同一个 budget config 而非各自硬编码吗?

### Finding #4 [HIGH] oracle_cb deadline_seconds=budget.max_seconds — deadline leak

**Round 1 问题**: 原 oracle_cb 每次调 adapter.query 都传 `deadline_seconds=budget.max_seconds`. 累积 N 次 query, wall-clock 总开销可达 N×max_seconds (e.g. 64 calls × 10s = 640s), 远超 budget. budget 形同虚设.

**Main Claude 修法 (Fix #4)**:
```python
gen_t0 = _time.monotonic()
def oracle_cb(core):
    remaining = max(0.1, budget.max_seconds - (_time.monotonic() - gen_t0))
    verdict, _blob = sub_problem_oracle.query(core, state, deadline_seconds=remaining)
    return verdict
```

**你要 review**:
- (a) `max(0.1, ...)` 0.1s minimum — 这意味着 budget 到期后 adapter 仍被 query 一次 (limit 0.1s). 0.1s 在 CP-SAT 几乎必 TIMEOUT (presolve 都不止 0.1s). 这是 oracle 系统 1 次 spurious TIMEOUT response 吗? deletion loop 把它当 inconclusive, `had_inconclusive=True`, `is_minimal=False`. 但 budget exhaustion 本来应该走 stopped_reason=TIMEOUT/MAX_CALLS 路径 — 现在 oracle_cb 把 budget exhaustion 转化为 oracle TIMEOUT verdict. 两条路径并存乱不乱?
- (b) Deletion loop 自己也 check `time.monotonic() - t0 >= budget.max_seconds`, 在 query 前 short-circuit. oracle_cb 内的 remaining-deadline 计算和 loop 内的 budget check 是 redundant 还是必要? (Round 1 用 budget.max_seconds 也只是为防止累积超 budget; 现在 loop 内 check 已经防累积超时, oracle_cb 内是否冗余?)
- (c) `gen_t0` 是 closure capture — 多次调 generate_pattern_nogood_cuts (不同 master iter), gen_t0 每次 fresh. 在并发场景 (虽然 Phase 1.2 单进程) gen_t0 是不是 thread-safe? closure 是 per-call 还是 share?

### Finding #5 [MEDIUM] duplicate triple 浪费 oracle call

**Round 1 问题**: 如果 caller 误传含重复 triple 的 assignment, canonical_sort 不 dedup, deletion loop 看到 `lit not in current_core` 假阳性 skip — 但 trial_core 包含 dup 的副本被独立 oracle query, 浪费 call.

**Main Claude 修法 (Fix #5)**: `canonical_sort_assignment` 入口 dedup via `tuple(dict.fromkeys(sorted_tuple))`.

**你要 review**:
- (a) `size_before = len(sorted_assignment)` (line 143) 现在是 **dedup 后** size. 但用户调用 `deletion_minimize_core(raw_assignment, ...)`, raw_assignment 可能有 dup. size_before 应该报 raw size 还是 dedup 后 size? cert 里 `size_before` 字段含义是什么 — pre-minimization size 还是 input size?
  - 攻击场景: 攻击者传 [(g,0,p), (g,0,p), (g,0,p)] (3 dup), dedup 后 1, 0 deletion iter, size_before=1, size_after=1, calls=1, INFEASIBLE_VERIFIED. cert 看起来"minimal 1-literal core". validator schema 接受. 但实际用户给 3-literal "core", 误导?
- (b) `dict.fromkeys` 保 sorted 顺序 — Python 3.7+ dict 保插入顺序, sorted_tuple 顺序, dict.fromkeys 保 sorted → dedup. 这个不变量在 Python 跨版本稳定吗? (你应该知道 3.7+ 是 language spec 不是 CPython 实现, 但 mypy strict 不查这种)
- (c) 文件 line 176-179 有个 comment "canonical sort doesn't dedupe" — 但现在 dedupe 了. comment 和 code 矛盾, 这是 stale comment 还是逻辑残留?

```python
# Line 176-179 (bounded_core_minimizer.py):
if lit not in current_core:
    # Defensive: literal already removed in a prior iter (only possible
    # if the input has dup triples — canonical sort doesn't dedupe).
    continue
```

## F5 现版本 src 代码 (Round 2 复审)

### `src/cuts/helpers/bounded_core_minimizer.py` (复审用)

```python
"""Bounded deletion-based core minimizer (Phase 1.2 P1.2B-F5 F5 pattern_nogood).

Deletion-based bounded MUS minimizer with paranoid fail-closed contract:

- Input: full literal assignment (canonical-sortable triple), oracle callable
  returning a 4-value verdict, budget (max calls + max seconds).
- Output: ``CoreMinimizeResult`` with last-verified-INFEASIBLE core + audit.

Hard rules (per docs/项目说明/12_go_criteria.md §8.1.x acceptance A):

1. Full assignment must first verify INFEASIBLE; FEASIBLE/UNKNOWN/TIMEOUT
   responses raise ``ValueError`` (caller contract violation — caller already
   has an INFEASIBLE sub-problem result before invoking).
2. Each deletion trial: only ``INFEASIBLE`` shrinks the core.
3. ``FEASIBLE`` keeps the literal (essential) and continues.
4. ``UNKNOWN`` / ``TIMEOUT`` (oracle's own response) keeps the literal and
   continues — spec "fail-closed (保留旧 core)" means do not shrink, not stop.
   ``is_minimal`` reports ``False`` whenever any inconclusive reply occurred.
5. Oracle ``raise`` ends the loop early with ``EXCEPTION_FAIL_CLOSED``;
   never propagate the exception.
6. Budget exhaustion (calls or seconds) ends the loop early; return last
   verified core. Never return an unverified partial.

The minimizer's contract assumes the oracle is **untrusted** — sub-problem
adapters in ``src/cuts/oracles/pattern_nogood_oracle.py`` wrap the real
binding / routing / pcr_cut solvers behind a uniform ``OracleCallback``
interface.

Refs:
- docs/项目说明/08_phase_1_2_plan.md §P1.2B-F5
- docs/项目说明/12_go_criteria.md §8.1.x acceptance A
- docs/research/p3_b_design_v2_20260521/cut_family_specs/05_pattern_nogood.md
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Literal, Tuple

from src.cuts.lifecycle import GroupId, PoseId


class CoreStoppedReason(str, Enum):
    """4-value closed set. Validator membership-checks at deserialize time."""

    INFEASIBLE_VERIFIED = "INFEASIBLE_VERIFIED"
    TIMEOUT = "TIMEOUT"
    MAX_CALLS = "MAX_CALLS"
    EXCEPTION_FAIL_CLOSED = "EXCEPTION_FAIL_CLOSED"


VALID_STOPPED_REASONS: frozenset[str] = frozenset(r.value for r in CoreStoppedReason)


OracleVerdict = Literal["INFEASIBLE", "FEASIBLE", "UNKNOWN", "TIMEOUT"]
VALID_ORACLE_VERDICTS: frozenset[str] = frozenset(("INFEASIBLE", "FEASIBLE", "UNKNOWN", "TIMEOUT"))


LiteralAssignment = Tuple[GroupId, int, PoseId]
"""Canonical sortable triple: (group_id, slot_index, pose_id).

slot_index participates in canonical sort for deterministic cert_hash but does
NOT participate in soundness binding (state_machine_v2 §5 multiset anonymity).
"""


OracleCallback = Callable[[Tuple[LiteralAssignment, ...]], OracleVerdict]


@dataclass(frozen=True)
class MinimizerBudget:
    """Hard-cap pair. Either threshold first ends the loop early."""

    max_calls: int = 64
    max_seconds: float = 10.0

    def __post_init__(self) -> None:
        if not isinstance(self.max_calls, int) or isinstance(self.max_calls, bool):
            raise ValueError(
                f"max_calls must be strict int, got {type(self.max_calls).__name__}"
            )
        if self.max_calls < 1:
            raise ValueError(f"max_calls must be >= 1, got {self.max_calls}")
        if isinstance(self.max_seconds, bool) or not isinstance(
            self.max_seconds, (int, float)
        ):
            raise ValueError(
                f"max_seconds must be float, got {type(self.max_seconds).__name__}"
            )
        if self.max_seconds <= 0.0:
            raise ValueError(f"max_seconds must be > 0.0, got {self.max_seconds}")


@dataclass(frozen=True)
class CoreMinimizeResult:
    """Last-verified-INFEASIBLE core + audit fields.

    Invariant: ``core`` is always derived from an INFEASIBLE oracle verdict —
    either the initial full-assignment verify or a strictly later shrink.
    ``is_verified_infeasible`` is True under every stopped_reason; the explicit
    field is schema-level paranoia (validator rejects ``False``).
    """

    core: Tuple[LiteralAssignment, ...]
    is_minimal: bool
    is_verified_infeasible: bool  # invariant True; validator rejects False
    calls: int
    elapsed_seconds: float
    stopped_reason: CoreStoppedReason
    size_before: int
    size_after: int


def canonical_sort_assignment(
    assignment: Tuple[LiteralAssignment, ...],
) -> Tuple[LiteralAssignment, ...]:
    """Sort by (group_id, slot_index, pose_id) lex + dedup.

    Dedup is defense-in-depth: caller may pass duplicates by accident; without
    dedup the minimizer's deletion loop would waste oracle calls re-evaluating
    the same trial_core after a FEASIBLE response (per Gemini F5 review #5).
    """
    sorted_tuple = tuple(sorted(assignment, key=lambda lit: (lit[0], lit[1], lit[2])))
    return tuple(dict.fromkeys(sorted_tuple))


def deletion_minimize_core(
    assignment: Tuple[LiteralAssignment, ...],
    oracle: OracleCallback,
    budget: MinimizerBudget = MinimizerBudget(),
) -> CoreMinimizeResult:
    """Deletion-based bounded MUS minimizer with paranoid fail-closed.

    Raises:
        ValueError: assignment empty, or the initial full-assignment oracle
            call returns anything other than INFEASIBLE (caller contract).
    """
    if not assignment:
        raise ValueError("deletion_minimize_core: assignment must be non-empty")

    sorted_assignment = canonical_sort_assignment(assignment)
    size_before = len(sorted_assignment)

    t0 = time.monotonic()
    initial_verdict = oracle(sorted_assignment)
    if initial_verdict != "INFEASIBLE":
        raise ValueError(
            f"deletion_minimize_core: initial verify returned {initial_verdict!r}, "
            f"expected INFEASIBLE (caller contract violated)"
        )

    current_core: Tuple[LiteralAssignment, ...] = sorted_assignment
    calls = 1
    had_inconclusive = False

    for lit in reversed(sorted_assignment):
        if calls >= budget.max_calls:
            return _build_result(
                current_core,
                is_minimal=False,
                calls=calls,
                t0=t0,
                stopped_reason=CoreStoppedReason.MAX_CALLS,
                size_before=size_before,
            )
        if time.monotonic() - t0 >= budget.max_seconds:
            return _build_result(
                current_core,
                is_minimal=False,
                calls=calls,
                t0=t0,
                stopped_reason=CoreStoppedReason.TIMEOUT,
                size_before=size_before,
            )
        if lit not in current_core:
            # Defensive: literal already removed in a prior iter (only possible
            # if the input has dup triples — canonical sort doesn't dedupe).
            continue
        trial_core = tuple(x for x in current_core if x != lit)
        if not trial_core:
            # Keep at least one literal (empty core has no meaning as a nogood).
            continue
        try:
            verdict = oracle(trial_core)
        except Exception:  # noqa: BLE001 — fail-closed: oracle is untrusted
            return _build_result(
                current_core,
                is_minimal=False,
                calls=calls + 1,
                t0=t0,
                stopped_reason=CoreStoppedReason.EXCEPTION_FAIL_CLOSED,
                size_before=size_before,
            )
        calls += 1
        if verdict == "INFEASIBLE":
            current_core = trial_core
        elif verdict in ("UNKNOWN", "TIMEOUT"):
            had_inconclusive = True
        # FEASIBLE keeps literal silently; INFEASIBLE/FEASIBLE both are
        # decisive responses, only UNKNOWN/TIMEOUT lower is_minimal at end.

    return _build_result(
        current_core,
        is_minimal=not had_inconclusive,
        calls=calls,
        t0=t0,
        stopped_reason=CoreStoppedReason.INFEASIBLE_VERIFIED,
        size_before=size_before,
    )


def _build_result(
    core: Tuple[LiteralAssignment, ...],
    *,
    is_minimal: bool,
    calls: int,
    t0: float,
    stopped_reason: CoreStoppedReason,
    size_before: int,
) -> CoreMinimizeResult:
    return CoreMinimizeResult(
        core=core,
        is_minimal=is_minimal,
        is_verified_infeasible=True,
        calls=calls,
        elapsed_seconds=time.monotonic() - t0,
        stopped_reason=stopped_reason,
        size_before=size_before,
        size_after=len(core),
    )

```

### `src/cuts/oracles/pattern_nogood_oracle.py` (复审用)

```python
"""F5 pattern_nogood generator + sub-problem oracle adapter contract (P1.2B-F5).

Phase 1.2 P1.2B-F5 scope:
- ``SubProblemOracleAdapter`` Protocol — uniform contract for binding /
  routing / pcr_cut / d2_separator adapters (Phase 1.5+ wires real ones).
- ``_REGISTERED_SUB_PROBLEM_ORACLES`` module-level registry (closed-set).
  Phase 1.2 default empty; tests register fakes via ``register_sub_problem_oracle``.
- ``generate_pattern_nogood_cuts`` — wraps ``deletion_minimize_core`` over an
  adapter's ``query`` method and produces 0 or 1 F5 Cut object.

Fail-closed: any caller-contract violation, registry miss, version mismatch,
or generator-internal exception returns ``[]`` (never partial / unverified cut).

Refs:
- docs/项目说明/08_phase_1_2_plan.md §P1.2B-F5
- docs/项目说明/12_go_criteria.md §8.1.x acceptance A
- docs/research/p3_b_design_v2_20260521/cut_family_specs/05_pattern_nogood.md
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Protocol, Tuple

from src.cuts.helpers.bounded_core_minimizer import (
    CoreMinimizeResult,
    LiteralAssignment,
    MinimizerBudget,
    OracleVerdict,
    canonical_sort_assignment,
    deletion_minimize_core,
)
from src.cuts.lifecycle import (
    AnonymousSlotRef,
    BState,
    Cut,
    CutLiteral,
    CutScope,
    OracleCert,
    compute_blocked_cells_hash,
    compute_exterior_blocks_hash,
    compute_ghost_rect_id,
    compute_source_digest,
)


# ============================================================================
# Module-level constants (F1-F4 oracle 风格一致)
# ============================================================================

ORACLE_NAME: str = "pattern_nogood_v1"
FAMILY_VERSION: str = "v1.0"
VALIDATOR_VERSION: str = "v1.0"
CERT_KIND: str = "bounded_deletion_core"


# ============================================================================
# SubProblemOracleAdapter — Protocol + registry
# ============================================================================


class SubProblemOracleAdapter(Protocol):
    """Sub-problem oracle adapter contract.

    Phase 1.5+ binding_subproblem / routing_subproblem / pcr_cut / d2_separator
    each implement this protocol so the F5 generator and validator can re-verify
    via a uniform API. Phase 1.2: no real implementations; tests inject fakes.
    """

    name: str  # registry key (e.g. "binding_v1"); validator membership-checks
    version: str  # validator strict-equals at re-verify time

    def query(
        self,
        core: Tuple[LiteralAssignment, ...],
        state: BState,
        *,
        deadline_seconds: float,
    ) -> Tuple[OracleVerdict, bytes]:
        """Return (verdict, witness_blob). witness_blob non-empty only on INFEASIBLE."""
        ...


_REGISTERED_SUB_PROBLEM_ORACLES: Dict[str, SubProblemOracleAdapter] = {}


def register_sub_problem_oracle(adapter: SubProblemOracleAdapter) -> None:
    """Register an adapter under its self-reported name. Idempotent on same name."""
    if not isinstance(adapter.name, str) or not adapter.name:
        raise ValueError(f"adapter.name must be non-empty str, got {adapter.name!r}")
    if not isinstance(adapter.version, str) or not adapter.version:
        raise ValueError(
            f"adapter.version must be non-empty str, got {adapter.version!r}"
        )
    _REGISTERED_SUB_PROBLEM_ORACLES[adapter.name] = adapter


def lookup_sub_problem_oracle(name: str) -> Optional[SubProblemOracleAdapter]:
    """Closed-set lookup. Returns None for unregistered name (caller fail-closed)."""
    return _REGISTERED_SUB_PROBLEM_ORACLES.get(name)


def clear_sub_problem_oracle_registry() -> None:
    """Test-only — reset registry to empty between cases."""
    _REGISTERED_SUB_PROBLEM_ORACLES.clear()


def registered_sub_problem_oracle_names() -> Tuple[str, ...]:
    """Return current registry keys (sorted, for stable test/audit output)."""
    return tuple(sorted(_REGISTERED_SUB_PROBLEM_ORACLES.keys()))


# ============================================================================
# Generator
# ============================================================================


def generate_pattern_nogood_cuts(
    state: BState,
    *,
    sub_problem_oracle: SubProblemOracleAdapter,
    full_assignment_literals: Tuple[CutLiteral, ...],
    budget: MinimizerBudget = MinimizerBudget(),
    iter_index: int = -1,
) -> List[Cut]:
    """Produce 0 or 1 F5 cut from a known-INFEASIBLE sub-problem assignment.

    Fail-closed returns ``[]`` when:
    - sub_problem_oracle.name not in registry, or version mismatch
    - full_assignment_literals empty
    - initial verify of full assignment is not INFEASIBLE
    - any internal exception during cert build

    Caller responsibility (benders_loop / Phase 1.5+):
    - sub_problem_oracle is the same adapter that just returned INFEASIBLE on
      the current master assignment.
    - full_assignment_literals are the literals from the master assignment
      that fed the sub-problem.
    """
    if not full_assignment_literals:
        return []

    registered = lookup_sub_problem_oracle(sub_problem_oracle.name)
    if registered is None or registered.version != sub_problem_oracle.version:
        return []

    assignment_triples: Tuple[LiteralAssignment, ...] = tuple(
        (lit.slot_ref.group_id, lit.slot_ref.slot_index, lit.pose_id)
        for lit in full_assignment_literals
    )

    # Wall-clock tracking for the whole generate call: each adapter.query
    # gets the *remaining* deadline (per Gemini F5 review #4 deadline leak fix),
    # not the full budget. Otherwise multiple oracle calls compound wall time.
    import time as _time

    gen_t0 = _time.monotonic()

    def oracle_cb(core: Tuple[LiteralAssignment, ...]) -> OracleVerdict:
        remaining = max(0.1, budget.max_seconds - (_time.monotonic() - gen_t0))
        verdict, _blob = sub_problem_oracle.query(
            core, state, deadline_seconds=remaining
        )
        # witness_blob no longer used: per Gemini F5 review #1, the sub-problem
        # witness hash is non-deterministic across workers and was breaking the
        # cert_hash invariant. Validator re-queries the oracle for INFEASIBLE
        # confirmation; that is the soundness guarantee, not the witness bytes.
        return verdict

    try:
        result = deletion_minimize_core(assignment_triples, oracle_cb, budget)
    except ValueError:
        return []
    except Exception:  # noqa: BLE001 — fail-closed against any adapter bug
        return []

    try:
        cut = _build_pattern_nogood_cut(
            state=state,
            sub_problem_oracle=sub_problem_oracle,
            result=result,
            iter_index=iter_index,
        )
    except Exception:  # noqa: BLE001 — fail-closed
        return []
    return [cut]


def _build_pattern_nogood_cut(
    *,
    state: BState,
    sub_problem_oracle: SubProblemOracleAdapter,
    result: CoreMinimizeResult,
    iter_index: int,
) -> Cut:
    """Construct F5 Cut from minimize result.

    Cert payload structure (canonical JSON, sorted keys, only
    deterministic-across-worker fields — per Gemini F5 review #1, sub-problem
    witness bytes are NOT deterministic so are excluded from cert_payload):

        cert_kind: "bounded_deletion_core"
        sub_problem_oracle_name: str (∈ registry)
        sub_problem_oracle_version: str (strict-equals registry value)
        forbidden_pose_pattern: list of [group_id, slot_index, pose_id]
        core_minimization: {size_before, size_after, calls, stopped_reason,
                            is_verified_infeasible}

    Cut top-level fields satisfy R3 ``validate_cut_integrity``:
    - ``cut.cert.cert_hash`` = sha256(cert_payload_bytes)
    - ``cut.oracle_cert_hash`` = cert.cert_hash (R3 invariant).

    Soundness is preserved by the validator's re-query of the oracle on
    ``forbidden_pose_pattern`` — the sub-problem solver must independently
    return INFEASIBLE on the cert literals, regardless of what witness bytes
    it emits.
    """
    canonical_core = canonical_sort_assignment(result.core)
    # canonical_sort_assignment now dedups; this remains explicit for clarity.
    deduped_core: Tuple[LiteralAssignment, ...] = canonical_core

    cert_payload_dict: Dict[str, Any] = {
        "cert_kind": CERT_KIND,
        "sub_problem_oracle_name": sub_problem_oracle.name,
        "sub_problem_oracle_version": sub_problem_oracle.version,
        "forbidden_pose_pattern": [[g, s, p] for (g, s, p) in deduped_core],
        "core_minimization": {
            "size_before": int(result.size_before),
            "size_after": int(result.size_after),
            "calls": int(result.calls),
            "stopped_reason": result.stopped_reason.value,
            "is_verified_infeasible": bool(result.is_verified_infeasible),
        },
    }
    cert_payload_bytes = json.dumps(
        cert_payload_dict, sort_keys=True, ensure_ascii=False
    ).encode("utf-8")
    cert_hash = hashlib.sha256(cert_payload_bytes).hexdigest()

    cut_literals: Tuple[CutLiteral, ...] = tuple(
        CutLiteral(
            slot_ref=AnonymousSlotRef(group_id=g, slot_index=s),
            pose_id=p,
        )
        for (g, s, p) in deduped_core
    )

    source_digest = state.source_digest or compute_source_digest(state)

    scope = CutScope(
        ghost_rect_id=compute_ghost_rect_id(state.ghost_rect),
        blocked_cells_hash=compute_blocked_cells_hash(state),
        exterior_blocks_hash=compute_exterior_blocks_hash(state),
        source_digest=source_digest,
        oracle_abstraction_version=sub_problem_oracle.name,
        artifact_hashes=dict(state.artifact_hashes),
    )

    cut = Cut(
        cut_id=f"f5_{iter_index}_{cert_hash[:12]}",
        family="pattern_nogood",
        literals=cut_literals,
        geometric_payload=None,
        scope=scope,
        cert=OracleCert(
            cert_kind=CERT_KIND,
            cert_payload=cert_payload_bytes,
            cert_hash=cert_hash,
        ),
        family_version=FAMILY_VERSION,
        validator_version=VALIDATOR_VERSION,
        oracle_name=ORACLE_NAME,
        oracle_cert_hash=cert_hash,  # R3 invariant: == cert.cert_hash
        minimization_audit={
            "size_before": int(result.size_before),
            "size_after": int(result.size_after),
            "calls": int(result.calls),
        },
        iter_index=iter_index,
    )
    return cut

```

### `src/cuts/families/pattern_nogood.py` (复审用)

```python
"""Family 5 pattern_nogood — production validator (P1.2B-F5).

Validator re-verifies F5 cuts as the trust boundary: oracle responses are
treated as untrusted, every cert field is schema-checked, and the sub-problem
oracle is re-queried on the forbidden core to confirm INFEASIBLE.

Cert payload contract (canonical JSON, per
``src/cuts/oracles/pattern_nogood_oracle._build_pattern_nogood_cut``):

    cert_kind: "bounded_deletion_core"
    sub_problem_oracle_name: str (∈ _REGISTERED_SUB_PROBLEM_ORACLES)
    sub_problem_oracle_version: str (strict-equals registry value)
    forbidden_pose_pattern: list of [group_id, slot_index, pose_id], dedup
    core_minimization:
        size_before, size_after, calls: strict int >= 0
        stopped_reason: ∈ {INFEASIBLE_VERIFIED, TIMEOUT, MAX_CALLS,
                          EXCEPTION_FAIL_CLOSED}
        is_verified_infeasible: True (rejected otherwise)

Note: Sub-problem witness bytes are NOT included in cert_payload (per Gemini
F5 review #1 BLOCKER fix). Witness bytes can be non-deterministic across
workers, which would break cert_hash cross-worker reproducibility. Validator
re-queries the oracle on forbidden_pose_pattern as its soundness check —
identity of the witness bytes is irrelevant, only the INFEASIBLE verdict matters.

Re-verify budget is conservative — Phase 1.2 default 5s wall. TIMEOUT → ValidationResult("timeout") so CutStore can quarantine without classifying as unsound.

Evaluator: F5 is literal-based, delegated to ``lifecycle.evaluate_literal_multiset``
via ``step_7_evaluate_cut`` dispatch (no F5-specific evaluator).

Refs:
- docs/项目说明/08_phase_1_2_plan.md §P1.2B-F5
- docs/项目说明/12_go_criteria.md §8.1.x acceptance A
- docs/research/p3_b_design_v2_20260521/cut_family_specs/05_pattern_nogood.md
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Literal, Optional, Tuple, cast

from src.cuts.helpers.bounded_core_minimizer import (
    VALID_STOPPED_REASONS,
)
from src.cuts.lifecycle import BState, Cut, ValidationResult
from src.cuts.oracles.pattern_nogood_oracle import (
    SubProblemOracleAdapter,
    lookup_sub_problem_oracle,
)


ValidationKind = Literal["ok", "unsound", "timeout", "schema_err"]


# Validator re-verify deadline. Per Gemini F5 review #3, must be >= the
# generator's MinimizerBudget.max_seconds (default 10.0s) so a cut whose final
# oracle call fits the generator budget does not get quarantined by the
# validator running with a tighter timeout. Phase 1.5+ may tune.
_VALIDATOR_REVERIFY_DEADLINE_SECONDS: float = 10.0

def _vr(kind: ValidationKind, t0: float, detail: str = "") -> ValidationResult:
    return ValidationResult(
        kind=kind, elapsed_seconds=time.monotonic() - t0, detail=detail or None
    )


def _is_strict_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_non_empty_str(value: object) -> bool:
    return isinstance(value, str) and value != ""


def _parse_cert_payload(cert_payload: bytes) -> Dict[str, Any]:
    """Parse cert payload JSON. Raises ValueError on malformed input."""
    if not isinstance(cert_payload, bytes):
        raise ValueError("cert_payload must be bytes")
    try:
        loaded = json.loads(cert_payload)
    except Exception as e:
        raise ValueError(f"cert_payload JSON decode failed: {e}") from e
    if not isinstance(loaded, dict):
        raise ValueError(f"cert_payload must decode to dict, got {type(loaded).__name__}")
    return cast(Dict[str, Any], loaded)


def _validate_cert_kind(cert_dict: Dict[str, Any], t0: float) -> Optional[ValidationResult]:
    cert_kind = cert_dict.get("cert_kind")
    if cert_kind != "bounded_deletion_core":
        return _vr(
            "schema_err",
            t0,
            f"cert_kind must be 'bounded_deletion_core', got {cert_kind!r}",
        )
    return None


def _validate_sub_problem_oracle(
    cert_dict: Dict[str, Any], t0: float
) -> Tuple[Optional[ValidationResult], Optional[SubProblemOracleAdapter]]:
    name = cert_dict.get("sub_problem_oracle_name")
    version = cert_dict.get("sub_problem_oracle_version")
    if not _is_non_empty_str(name):
        return (
            _vr("schema_err", t0, f"sub_problem_oracle_name must be non-empty str, got {name!r}"),
            None,
        )
    if not _is_non_empty_str(version):
        return (
            _vr(
                "schema_err",
                t0,
                f"sub_problem_oracle_version must be non-empty str, got {version!r}",
            ),
            None,
        )
    adapter = lookup_sub_problem_oracle(cast(str, name))
    if adapter is None:
        return (
            _vr(
                "schema_err",
                t0,
                f"sub_problem_oracle_name {name!r} not in registry (fail-closed)",
            ),
            None,
        )
    if adapter.version != version:
        return (
            _vr(
                "unsound",
                t0,
                f"sub_problem_oracle_version mismatch: cert={version!r}, registry={adapter.version!r}",
            ),
            None,
        )
    return None, adapter


# Witness hash validation removed (Gemini F5 review #1 fix): witness bytes
# are not deterministic across workers; soundness comes from oracle re-query,
# not byte-equal witness identity.


def _validate_core_minimization(
    cert_dict: Dict[str, Any], t0: float
) -> Optional[ValidationResult]:
    cm = cert_dict.get("core_minimization")
    if not isinstance(cm, dict):
        return _vr("schema_err", t0, f"core_minimization must be dict, got {type(cm).__name__}")
    for field in ("size_before", "size_after", "calls"):
        v = cm.get(field)
        if not _is_strict_int(v):
            return _vr(
                "schema_err",
                t0,
                f"core_minimization.{field} must be strict int, got {v!r}",
            )
        if cast(int, v) < 0:
            return _vr("schema_err", t0, f"core_minimization.{field} must be >= 0, got {v}")
    if cast(int, cm["size_after"]) > cast(int, cm["size_before"]):
        return _vr(
            "schema_err",
            t0,
            f"size_after ({cm['size_after']}) > size_before ({cm['size_before']})",
        )
    reason = cm.get("stopped_reason")
    if not isinstance(reason, str) or reason not in VALID_STOPPED_REASONS:
        return _vr(
            "schema_err",
            t0,
            f"core_minimization.stopped_reason {reason!r} not in {sorted(VALID_STOPPED_REASONS)}",
        )
    verified = cm.get("is_verified_infeasible")
    if not isinstance(verified, bool):
        return _vr(
            "schema_err",
            t0,
            f"core_minimization.is_verified_infeasible must be bool, got {type(verified).__name__}",
        )
    if verified is not True:
        return _vr(
            "unsound",
            t0,
            "core_minimization.is_verified_infeasible is False (cert self-declares unverified)",
        )
    return None


def _validate_forbidden_pose_pattern(
    cert_dict: Dict[str, Any], state: BState, t0: float
) -> Tuple[Optional[ValidationResult], Optional[Tuple[Tuple[str, int, str], ...]]]:
    raw = cert_dict.get("forbidden_pose_pattern")
    if not isinstance(raw, list) or not raw:
        return (
            _vr("schema_err", t0, "forbidden_pose_pattern must be non-empty list"),
            None,
        )
    triples: List[Tuple[str, int, str]] = []
    seen: set[Tuple[str, int, str]] = set()
    for idx, entry in enumerate(raw):
        if not isinstance(entry, list) or len(entry) != 3:
            return (
                _vr(
                    "schema_err",
                    t0,
                    f"forbidden_pose_pattern[{idx}] must be 3-element list",
                ),
                None,
            )
        g, s, p = entry
        if not _is_non_empty_str(g):
            return (
                _vr("schema_err", t0, f"forbidden_pose_pattern[{idx}].group_id must be non-empty str, got {g!r}"),
                None,
            )
        if not _is_strict_int(s) or cast(int, s) < 0:
            return (
                _vr("schema_err", t0, f"forbidden_pose_pattern[{idx}].slot_index must be strict int >= 0, got {s!r}"),
                None,
            )
        if not _is_non_empty_str(p):
            return (
                _vr("schema_err", t0, f"forbidden_pose_pattern[{idx}].pose_id must be non-empty str, got {p!r}"),
                None,
            )
        triple = (cast(str, g), cast(int, s), cast(str, p))
        if triple in seen:
            return (
                _vr("schema_err", t0, f"forbidden_pose_pattern duplicate triple {triple!r}"),
                None,
            )
        seen.add(triple)
        triples.append(triple)
        # pose ∈ state.groups[g].pose_domain check (defense-in-depth)
        group_state = state.groups.get(triple[0])
        if group_state is None:
            return (
                _vr(
                    "unsound",
                    t0,
                    f"forbidden_pose_pattern[{idx}] references unknown group_id {triple[0]!r}",
                ),
                None,
            )
        if triple[2] not in group_state.pose_domain:
            return (
                _vr(
                    "unsound",
                    t0,
                    f"forbidden_pose_pattern[{idx}] pose_id {triple[2]!r} not in group {triple[0]!r} pose_domain",
                ),
                None,
            )
    return None, tuple(triples)


def _validate_cert_literals_match(
    cut: Cut,
    cert_triples: Tuple[Tuple[str, int, str], ...],
    t0: float,
) -> Optional[ValidationResult]:
    if cut.literals is None or len(cut.literals) != len(cert_triples):
        cut_len = 0 if cut.literals is None else len(cut.literals)
        return _vr(
            "unsound",
            t0,
            f"cut.literals length {cut_len} != forbidden_pose_pattern length {len(cert_triples)}",
        )
    literal_triples = tuple(
        (lit.slot_ref.group_id, lit.slot_ref.slot_index, lit.pose_id)
        for lit in cut.literals
    )
    if literal_triples != cert_triples:
        return _vr(
            "unsound",
            t0,
            "cut.literals triples do not match cert.forbidden_pose_pattern (must be 1:1 in canonical order)",
        )
    return None


def _reverify_sub_problem_oracle(
    adapter: SubProblemOracleAdapter,
    cert_triples: Tuple[Tuple[str, int, str], ...],
    state: BState,
    t0: float,
) -> Optional[ValidationResult]:
    """Re-query the sub-problem oracle on the forbidden core. Must return INFEASIBLE.

    Per Gemini F5 review #1 BLOCKER fix: witness bytes are non-deterministic
    across workers; we no longer compare witness hash against cert. The
    soundness contract is the INFEASIBLE verdict alone.
    """
    try:
        verdict, _witness_blob = adapter.query(
            cert_triples,
            state,
            deadline_seconds=_VALIDATOR_REVERIFY_DEADLINE_SECONDS,
        )
    except Exception as e:  # noqa: BLE001 — oracle is untrusted
        return _vr(
            "unsound",
            t0,
            f"sub-problem oracle re-verify raised {type(e).__name__}: {e}",
        )
    if verdict == "TIMEOUT":
        return _vr(
            "timeout",
            t0,
            f"sub-problem oracle re-verify TIMEOUT (deadline={_VALIDATOR_REVERIFY_DEADLINE_SECONDS}s)",
        )
    if verdict != "INFEASIBLE":
        return _vr(
            "unsound",
            t0,
            f"sub-problem oracle re-verify returned {verdict!r}, expected INFEASIBLE",
        )
    return None


def validate_pattern_nogood(
    cut: Cut,
    state: BState,
    canonical_rules: Dict[str, Any],
) -> ValidationResult:
    """Re-validate F5 pattern_nogood cut. Trust boundary: oracle is untrusted.

    7-phase validation:
    1. cert payload JSON parse
    2. cert_kind == 'bounded_deletion_core'
    3. sub_problem_oracle_name in registry + version strict-equal
    4. sub_problem_witness_hash hex sha256 schema
    5. core_minimization fields schema (strict int / closed-set stopped_reason
       / is_verified_infeasible True)
    6. forbidden_pose_pattern dedup + each entry schema + pose ∈ pose_domain +
       1:1 match with cut.literals in canonical order
    7. sub-problem oracle re-verify on forbidden core (TIMEOUT → quarantine)
    """
    t0 = time.monotonic()
    del canonical_rules

    if cut.cert is None or cut.literals is None or len(cut.literals) == 0:
        return _vr(
            "schema_err",
            t0,
            "F5 requires non-empty cert + literals (cut_lifecycle_v2 §3)",
        )

    try:
        cert_dict = _parse_cert_payload(cut.cert.cert_payload)
    except ValueError as e:
        return _vr("schema_err", t0, str(e))

    for error in (
        _validate_cert_kind(cert_dict, t0),
        _validate_core_minimization(cert_dict, t0),
    ):
        if error is not None:
            return error

    oracle_err, adapter = _validate_sub_problem_oracle(cert_dict, t0)
    if oracle_err is not None:
        return oracle_err
    if adapter is None:  # belt-and-suspenders (None implies oracle_err non-None)
        return _vr("schema_err", t0, "sub-problem oracle adapter resolution failed")

    pattern_err, cert_triples = _validate_forbidden_pose_pattern(cert_dict, state, t0)
    if pattern_err is not None:
        return pattern_err
    if cert_triples is None:
        return _vr("schema_err", t0, "forbidden_pose_pattern parse returned None")

    literal_err = _validate_cert_literals_match(cut, cert_triples, t0)
    if literal_err is not None:
        return literal_err

    reverify_err = _reverify_sub_problem_oracle(
        adapter,
        cert_triples,
        state,
        t0,
    )
    if reverify_err is not None:
        return reverify_err

    return _vr("ok", t0)


def watcher_keys_pattern_nogood(cut: Cut) -> Dict[str, List[Any]]:
    """Return watcher keys for CutStore.add_cut (cut_lifecycle_v2 §7 table).

    F5 walls by group + pose (per spec — slot/cell anonymity).
    by_ghost is auto-added by store from cut.scope.ghost_rect_id.
    """
    if cut.literals is None:
        return {"group_keys": [], "pose_keys": []}
    group_keys = sorted({lit.slot_ref.group_id for lit in cut.literals})
    pose_keys = sorted({(lit.slot_ref.group_id, lit.pose_id) for lit in cut.literals})
    return {"group_keys": group_keys, "pose_keys": pose_keys}



```

## Round 2 强制 push 类别 (per gemini-prompt-audit-mode 反 GO ritual)

请按以下顺序输出, 严禁先总结 design good. 必须先列 finding.

### A. 算法错估 (Algorithm errors)
Claude 修法的算法选择是否错? Reproduce/反例? File:line.

### B. 前提错估 (Premise errors)
Claude 修法依赖的隐含前提 (e.g. "oracle 跨 worker 在同一 core 上必给同一 verdict") 是否成立? Spec/data 是否实际满足? File:line + 反例 input.

### C. 数学能力上限 (Math capability ceiling)
Soundness 上, 修后 paradigm 是否仍有数学层 hole? 例如 sub-problem oracle re-query INFEASIBLE 是 F5 soundness 必要+充分 条件吗? 是否有 spec/lifecycle 不变量 (cut_lifecycle_v2 / state_machine_v2) 被违反?

### D. 修复 verify 表格
对 4 个 fix 各给 verdict in {CORRECT, PARTIAL, WRONG, NEW_GAP}, 一句话理由.

### E. Round 1 漏掉的 finding (黑盒看 src 才能 catch 的)
不少于 2 个, 否则你没认真读 src.

### F. Overall verdict
GO / CONCERN / NOT_GO, 一句话.

## 报告 format

```markdown
## Round 2 Verdict (一句话)
NOT_GO | CONCERN | GO

## A. 算法错估
- [SEVERITY] file:line — 问题 / reproduce / 修建议

## B. 前提错估
- ...

## C. 数学能力上限
- ...

## D. 修复 verify 表格
| Fix | Verdict | 理由 |
|---|---|---|
| #1 cert_payload witness 移除 | CORRECT/PARTIAL/WRONG/NEW_GAP | ... |
| #3 deadline 10s match | ... | ... |
| #4 remaining deadline closure | ... | ... |
| #5 input dedup canonical_sort | ... | ... |

## E. Round 1 漏 finding (新发现, >= 2 个)
- ...

## F. Overall verdict
NOT_GO / CONCERN / GO — reasoning.
```

**最后强调**: 你 round 1 列了 6 finding 给 NOT_GO. Round 2 src 实际代码层, 修复有交易 (witness 丢 = soundness model 改变, dedup = size_before 语义改变, remaining deadline = 0.1s 边界引入 spurious TIMEOUT). 一定有新 finding. **列出来**, 不要 design good ritual.
