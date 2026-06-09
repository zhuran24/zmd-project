"""
Exact campaign state manager（精确战役状态管理器）.

职责：
1. 计算 certified exact（严格认证精确）输入工件哈希。
2. 管理最长 168 小时级 campaign state（战役状态）持久化。
3. 只有在 schema / mode / artifact hash / required fields 一致时才允许恢复。
4. 为每个候选空地保存 strictly valid evidence（严格有效证据）与 exact-safe cuts（精确安全 cuts）。
"""

from __future__ import annotations

import calendar
import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from src.models.cut_manager import BendersCut, _parse_ghost_anchor_condition_key

DEFAULT_CAMPAIGN_FILENAME = "exact_campaign_state.json"
CAMPAIGN_SCHEMA_VERSION = 3
PROOF_SUMMARY_SCHEMA_VERSION = 1
VALID_CANDIDATE_STATUSES = {
    "RUNNING",
    "CERTIFIED",
    "INFEASIBLE",
    "UNKNOWN",
    "UNPROVEN",
    # P1 #7a prep: ε-Certified status. status="EPSILON_CERTIFIED" 表示 candidate
    # 求到 ε-bound 内但未 ε=0 完整 certified。bound_state.epsilon_target 记录
    # 是哪个 ε 阶段（0.05/0.01/0.0）。final_status 同样可以是 EPSILON_CERTIFIED。
    "EPSILON_CERTIFIED",
}
REQUIRED_STATE_FIELDS = {
    "schema_version",
    "solve_mode",
    "campaign_hours",
    "created_at",
    "updated_at",
    "artifact_hashes",
    "proof_summary_schema_version",
    "reset_reason",
    "final_result",
    "final_status",
    "last_stop_reason",
    "candidates",
}
REQUIRED_CANDIDATE_FIELDS = {
    "ghost_rect",
    "attempts",
    "started_at",
    "updated_at",
    "finished_at",
    "status",
    "proof_summary",
    "exact_safe_cuts",
    "loaded_exact_safe_cut_count",
    "generated_exact_safe_cut_count",
}

EXACT_HASH_FILES = {
    "mandatory_exact_instances": "data/preprocessed/mandatory_exact_instances.json",
    "candidate_placements": "data/preprocessed/candidate_placements.json",
    "canonical_rules": "rules/canonical_rules.json",
    "generic_io_requirements": "data/preprocessed/generic_io_requirements.json",
}


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _loads_strict_json_object(text: str) -> Any:
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_json_constant,
    )


def now_ts() -> float:
    return time.time()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts()))


def iso_to_ts(iso_text: str) -> float:
    try:
        return float(calendar.timegm(time.strptime(iso_text, "%Y-%m-%dT%H:%M:%SZ")))
    except Exception:
        return now_ts()


def sha256_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def compute_exact_artifact_hashes(project_root: Path) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    for key, relative_path in EXACT_HASH_FILES.items():
        hashes[key] = sha256_file(project_root / relative_path)
    return hashes


def _strict_resume_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return int(value)


def _load_exact_grid_dimensions(project_root: Optional[Path]) -> Optional[Tuple[int, int]]:
    if project_root is None:
        return None
    rules_path = project_root / EXACT_HASH_FILES["canonical_rules"]
    payload = _loads_strict_json_object(rules_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("canonical_rules must be a JSON object")
    globals_payload = payload.get("globals")
    if not isinstance(globals_payload, Mapping):
        raise ValueError("canonical_rules.globals must be a mapping")
    grid = globals_payload.get("grid")
    if not isinstance(grid, Mapping):
        raise ValueError("canonical_rules.globals.grid must be a mapping")
    grid_w = _strict_resume_int(grid.get("width"), "canonical_rules.globals.grid.width")
    grid_h = _strict_resume_int(grid.get("height"), "canonical_rules.globals.grid.height")
    if grid_w <= 0 or grid_h <= 0:
        raise ValueError("canonical_rules grid dimensions must be positive")
    return grid_w, grid_h


def _strict_candidate_ghost_rect(record: Mapping[str, Any]) -> Tuple[int, int]:
    ghost_rect = record.get("ghost_rect")
    if not isinstance(ghost_rect, Mapping):
        raise ValueError("candidate ghost_rect must be a mapping")
    ghost_w = _strict_resume_int(ghost_rect.get("w"), "candidate.ghost_rect.w")
    ghost_h = _strict_resume_int(ghost_rect.get("h"), "candidate.ghost_rect.h")
    area = _strict_resume_int(ghost_rect.get("area"), "candidate.ghost_rect.area")
    if ghost_w <= 0 or ghost_h <= 0 or area != ghost_w * ghost_h:
        raise ValueError("candidate ghost_rect dimensions must be positive and area-consistent")
    return ghost_w, ghost_h


def _expected_unfiltered_ghost_anchor_index(
    *,
    grid_w: int,
    grid_h: int,
    ghost_w: int,
    ghost_h: int,
    anchor_x: int,
    anchor_y: int,
) -> Optional[int]:
    if ghost_w <= 0 or ghost_h <= 0 or ghost_w > grid_w or ghost_h > grid_h:
        return None
    if anchor_x < 0 or anchor_y < 0:
        return None
    y_count = grid_h - ghost_h + 1
    if anchor_x > grid_w - ghost_w or anchor_y > grid_h - ghost_h:
        return None
    return int(anchor_x) * int(y_count) + int(anchor_y)


def _validate_cut_condition_domain(
    *,
    record: Mapping[str, Any],
    cut: BendersCut,
    grid_dimensions: Optional[Tuple[int, int]],
) -> None:
    if not cut.condition_set:
        return
    if grid_dimensions is None:
        raise ValueError("condition_set domain validation requires canonical grid dimensions")
    grid_w, grid_h = grid_dimensions
    ghost_w, ghost_h = _strict_candidate_ghost_rect(record)
    for key, rect_idx in cut.condition_set.items():
        parsed_anchor = _parse_ghost_anchor_condition_key(str(key))
        if parsed_anchor is None:
            raise ValueError(f"unsupported condition_set key: {key}")
        expected_rect_idx = _expected_unfiltered_ghost_anchor_index(
            grid_w=int(grid_w),
            grid_h=int(grid_h),
            ghost_w=int(ghost_w),
            ghost_h=int(ghost_h),
            anchor_x=int(parsed_anchor[0]),
            anchor_y=int(parsed_anchor[1]),
        )
        if expected_rect_idx is None:
            raise ValueError(f"condition_set ghost anchor is outside the candidate domain: {key}")
        if int(rect_idx) != expected_rect_idx:
            raise ValueError(
                "condition_set ghost anchor index does not match the current "
                f"candidate domain for key {key}"
            )


def candidate_key(ghost_w: int, ghost_h: int) -> str:
    return f"{ghost_w}x{ghost_h}"


def _candidate_objective_from_rect(ghost_w: int, ghost_h: int) -> Tuple[int, int]:
    return (int(ghost_w) * int(ghost_h), min(int(ghost_w), int(ghost_h)))


def _final_result_objective(result: Mapping[str, Any]) -> Tuple[int, int]:
    ghost_rect = result.get("ghost_rect")
    if not isinstance(ghost_rect, Mapping):
        return (0, 0)
    try:
        ghost_w = int(ghost_rect.get("w", 0))
        ghost_h = int(ghost_rect.get("h", 0))
    except Exception:
        return (0, 0)
    return _candidate_objective_from_rect(ghost_w, ghost_h)


def _has_certified_final_result(state: Mapping[str, Any]) -> bool:
    return isinstance(state.get("final_result"), Mapping)


def _fsync_directory(path: Path) -> None:
    try:
        dir_fd = os.open(str(path), os.O_RDONLY)
    except Exception:
        return
    try:
        os.fsync(dir_fd)
    except Exception:
        pass
    finally:
        os.close(dir_fd)


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_tmp_path = tempfile.mkstemp(
        prefix=f".{path.name}.tmp-",
        suffix=".json",
        dir=str(path.parent),
    )
    tmp_path = Path(raw_tmp_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(tmp_path), str(path))
        _fsync_directory(path.parent)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass


def _bound_state_defaults() -> Dict[str, Any]:
    """P1 #7a prep: optional bound_state block per candidate.

    All fields default None. Filled in when master writes back lb/ub/gap
    after a wave (P1 #7 主体阶段集成). schema_version 不 bump — 这个 block
    是可选扩展, 旧 v3 reader 见到忽略, 新 reader 见缺失给默认。
    """
    return {
        "lb": None,            # int | None  : best dual lower bound
        "ub": None,            # int | None  : best primal incumbent
        "gap": None,           # float | None: (ub - lb) / max(|ub|, 1)
        "epsilon_target": None,  # float | None: 0.05/0.01/0.0 三阶段
        "prover": None,          # str | None: "master_cpsat" / "binding_lbbd" / etc.
        "observed_at": None,     # iso str | None
        "model_hash": None,      # str | None: 跨 wave 一致性校验
    }


def _candidate_defaults(ghost_w: int, ghost_h: int) -> Dict[str, Any]:
    return {
        "ghost_rect": {"w": int(ghost_w), "h": int(ghost_h), "area": int(ghost_w) * int(ghost_h)},
        "attempts": 0,
        "started_at": None,
        "updated_at": None,
        "finished_at": None,
        "status": "UNKNOWN",
        "proof_summary": {},
        "exact_safe_cuts": [],
        "loaded_exact_safe_cut_count": 0,
        "generated_exact_safe_cut_count": 0,
        # P1 #7a prep: optional. 旧 v3 checkpoint 缺这个字段, reader 给默认。
        "bound_state": _bound_state_defaults(),
    }


def _build_initial_state(
    *,
    current_hashes: Mapping[str, str],
    campaign_hours: float,
    reset_reason: Optional[str],
) -> Dict[str, Any]:
    timestamp = now_iso()
    return {
        "schema_version": CAMPAIGN_SCHEMA_VERSION,
        "solve_mode": "certified_exact",
        "campaign_hours": float(campaign_hours),
        "created_at": timestamp,
        "updated_at": timestamp,
        "artifact_hashes": {str(k): str(v) for k, v in current_hashes.items()},
        "proof_summary_schema_version": PROOF_SUMMARY_SCHEMA_VERSION,
        "reset_reason": reset_reason,
        "final_result": None,
        "final_status": None,
        "last_stop_reason": None,
        # P2 #14 数据收集 audit: A 方案 (EXACT_OUTER_SKIP_UNKNOWN) 让 UNKNOWN
        # candidate 跳过 frontier → declare 出的 "最优" 可能漏 UNKNOWN 实际为
        # FEASIBLE, 违反 max_lex 严格证明. 此字段标记 campaign declare 严格度:
        #   "strict" (default) — declare 是真 max_lex 最优 (严格证明)
        #   "best_effort"      — campaign 含 UNKNOWN gap, declare 仅"算清范围内最优"
        # outer_search 启动时若 EXACT_OUTER_SKIP_UNKNOWN env on, 把此字段升 best_effort.
        "declare_mode": "strict",
        "candidates": {},
    }


def _validate_candidate_record(
    record_key: str,
    record: Mapping[str, Any],
    *,
    grid_dimensions: Optional[Tuple[int, int]] = None,
) -> Optional[str]:
    missing = sorted(REQUIRED_CANDIDATE_FIELDS.difference(record.keys()))
    if missing:
        return f"candidate_missing_field:{record_key}:{missing[0]}"

    ghost_rect = record.get("ghost_rect")
    if not isinstance(ghost_rect, Mapping):
        return f"candidate_invalid_ghost_rect:{record_key}"
    for field in ("w", "h", "area"):
        if field not in ghost_rect:
            return f"candidate_missing_ghost_rect_field:{record_key}:{field}"
    try:
        _strict_candidate_ghost_rect(record)
    except Exception:
        return f"candidate_invalid_ghost_rect:{record_key}"

    try:
        int(record.get("attempts", 0))
        int(record.get("loaded_exact_safe_cut_count", 0))
        int(record.get("generated_exact_safe_cut_count", 0))
    except Exception:
        return f"candidate_invalid_count:{record_key}"

    status = str(record.get("status", ""))
    if status not in VALID_CANDIDATE_STATUSES:
        return f"candidate_invalid_status:{record_key}:{status}"

    if not isinstance(record.get("proof_summary"), Mapping):
        return f"candidate_invalid_proof_summary:{record_key}"
    exact_safe_cuts = record.get("exact_safe_cuts")
    if not isinstance(exact_safe_cuts, list):
        return f"candidate_invalid_exact_safe_cuts:{record_key}"
    for index, raw_cut in enumerate(exact_safe_cuts):
        if not isinstance(raw_cut, Mapping):
            return f"candidate_invalid_exact_safe_cut:{record_key}:{index}"
        try:
            cut = BendersCut.from_dict(raw_cut)
        except Exception:
            return f"candidate_invalid_exact_safe_cut:{record_key}:{index}"
        if cut.source_mode != "certified_exact" or cut.exact_safe is not True:
            return f"candidate_invalid_exact_safe_cut:{record_key}:{index}"
        try:
            _validate_cut_condition_domain(
                record=record,
                cut=cut,
                grid_dimensions=grid_dimensions,
            )
        except Exception:
            return f"candidate_invalid_exact_safe_cut:{record_key}:{index}"

    for field in ("started_at", "updated_at"):
        if record.get(field) is None:
            return f"candidate_missing_timestamp:{record_key}:{field}"
    if status == "RUNNING" and record.get("finished_at") is not None:
        return f"candidate_running_has_finished_at:{record_key}"
    if status != "RUNNING" and record.get("finished_at") is None:
        return f"candidate_terminal_missing_finished_at:{record_key}"
    return None


def _validate_resume_state(
    state: Mapping[str, Any],
    *,
    current_hashes: Mapping[str, str],
    project_root: Optional[Path] = None,
) -> Optional[str]:
    missing = sorted(REQUIRED_STATE_FIELDS.difference(state.keys()))
    if missing:
        return f"missing_state_field:{missing[0]}"
    if int(state.get("schema_version", -1)) != CAMPAIGN_SCHEMA_VERSION:
        return "schema_version_mismatch"
    if str(state.get("solve_mode")) != "certified_exact":
        return "solve_mode_mismatch"
    if int(state.get("proof_summary_schema_version", -1)) != PROOF_SUMMARY_SCHEMA_VERSION:
        return "proof_summary_schema_version_mismatch"
    if not isinstance(state.get("artifact_hashes"), Mapping):
        return "artifact_hashes_invalid"
    if dict(state.get("artifact_hashes", {})) != dict(current_hashes):
        return "artifact_hash_mismatch"
    if not isinstance(state.get("candidates"), Mapping):
        return "candidates_invalid"
    if state.get("last_stop_reason") is not None:
        stop_reason = state.get("last_stop_reason")
        if not isinstance(stop_reason, Mapping) or "reason" not in stop_reason:
            return "last_stop_reason_invalid"
    final_result = state.get("final_result")
    final_status = state.get("final_status")
    if final_result is not None and not isinstance(final_result, Mapping):
        return "final_result_invalid"
    if final_status is not None and not isinstance(final_status, str):
        return "final_status_invalid"
    if final_result is not None and final_status != "CERTIFIED":
        return "final_status_mismatch"

    try:
        grid_dimensions = _load_exact_grid_dimensions(project_root)
    except Exception:
        return "canonical_grid_invalid"

    for record_key, record in dict(state.get("candidates", {})).items():
        if not isinstance(record, Mapping):
            return f"candidate_invalid:{record_key}"
        reason = _validate_candidate_record(
            str(record_key),
            record,
            grid_dimensions=grid_dimensions,
        )
        if reason is not None:
            return reason
    return None


def validate_exact_campaign_resume_state(
    state: Mapping[str, Any],
    current_hashes: Mapping[str, str],
    *,
    project_root: Optional[Path] = None,
) -> Optional[str]:
    return _validate_resume_state(
        state,
        current_hashes=current_hashes,
        project_root=project_root,
    )


@dataclass
class ExactCampaign:
    project_root: Path
    path: Path
    state: Dict[str, Any]
    resumed: bool
    compatible_hashes: bool

    @classmethod
    def load_or_create(
        cls,
        project_root: Path,
        campaign_hours: float = 168.0,
        resume: bool = False,
        filename: str = DEFAULT_CAMPAIGN_FILENAME,
    ) -> "ExactCampaign":
        checkpoints_dir = project_root / "data" / "checkpoints"
        checkpoints_dir.mkdir(parents=True, exist_ok=True)
        path = checkpoints_dir / filename
        current_hashes = compute_exact_artifact_hashes(project_root)

        reset_reason: Optional[str] = None
        if resume and path.exists():
            try:
                loaded_state = _loads_strict_json_object(path.read_text(encoding="utf-8"))
            except Exception:
                reset_reason = "state_json_invalid"
            else:
                if isinstance(loaded_state, Mapping):
                    reset_reason = _validate_resume_state(
                        loaded_state,
                        current_hashes=current_hashes,
                        project_root=project_root,
                    )
                    if reset_reason is None:
                        state = dict(loaded_state)
                        state["updated_at"] = now_iso()
                        state["reset_reason"] = None
                        # Allow extending campaign budget on resume
                        if campaign_hours > float(state.get("campaign_hours", 0)):
                            state["campaign_hours"] = float(campaign_hours)
                        # Clear time-budget-exhausted stop so campaign can continue
                        stop = state.get("last_stop_reason")
                        if (
                            isinstance(stop, Mapping)
                            and stop.get("reason") == "campaign_time_budget_exhausted"
                        ):
                            state["last_stop_reason"] = None
                            state["final_status"] = None
                        return cls(
                            project_root=project_root,
                            path=path,
                            state=state,
                            resumed=True,
                            compatible_hashes=True,
                        )
                else:
                    reset_reason = "state_payload_invalid"

        state = _build_initial_state(
            current_hashes=current_hashes,
            campaign_hours=campaign_hours,
            reset_reason=reset_reason,
        )
        return cls(
            project_root=project_root,
            path=path,
            state=state,
            resumed=False,
            compatible_hashes=(reset_reason is None),
        )

    @property
    def artifact_hashes(self) -> Dict[str, str]:
        return dict(self.state.get("artifact_hashes", {}))

    @property
    def campaign_hours(self) -> float:
        return float(self.state.get("campaign_hours", 168.0))

    @property
    def reset_reason(self) -> Optional[str]:
        value = self.state.get("reset_reason")
        return None if value is None else str(value)

    def remaining_seconds(self) -> float:
        created_at = str(self.state.get("created_at", now_iso()))
        elapsed = max(0.0, now_ts() - iso_to_ts(created_at))
        return max(0.0, self.campaign_hours * 3600.0 - elapsed)

    def elapsed_seconds(self) -> float:
        """P1 #7 main: 给 outer_search 三阶段 ε 调度算当前 elapsed 用."""
        created_at = str(self.state.get("created_at", now_iso()))
        return max(0.0, now_ts() - iso_to_ts(created_at))

    def is_compatible_with_current_hashes(self) -> bool:
        return self.state.get("artifact_hashes") == compute_exact_artifact_hashes(self.project_root)

    def get_candidate_record(self, ghost_w: int, ghost_h: int) -> Optional[Dict[str, Any]]:
        record = self.state.get("candidates", {}).get(candidate_key(ghost_w, ghost_h))
        return dict(record) if isinstance(record, dict) else None

    def get_candidate_cuts(self, ghost_w: int, ghost_h: int) -> list[Dict[str, Any]]:
        record = self.get_candidate_record(ghost_w, ghost_h) or {}
        return list(record.get("exact_safe_cuts", []))

    # P1 #7a prep: bound_state read/write helpers (P1 #7d guard 也用这俩).
    def get_candidate_bound_state(
        self, ghost_w: int, ghost_h: int
    ) -> Dict[str, Any]:
        """Return current bound_state dict (default-filled if missing)."""
        record = self.get_candidate_record(ghost_w, ghost_h) or {}
        bound = record.get("bound_state")
        if isinstance(bound, Mapping):
            # Merge with defaults so新增字段也有 default
            merged = _bound_state_defaults()
            merged.update(dict(bound))
            return merged
        return _bound_state_defaults()

    def update_candidate_bound_state(
        self,
        ghost_w: int,
        ghost_h: int,
        *,
        lb: Optional[int] = None,
        ub: Optional[int] = None,
        gap: Optional[float] = None,
        epsilon_target: Optional[float] = None,
        prover: Optional[str] = None,
        model_hash: Optional[str] = None,
        regression_tolerance: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """Update bound_state for the given candidate. None args 留旧值不变.

        P1 #7d guard: 如果 new_lb < old_lb - regression_tolerance 触发
        BOUND_REGRESSION audit event (append 到 state['audit_log']) 但不
        阻塞 — model_hash 可能合法变化, 需人审。

        Returns: 触发的 audit entry (dict) 或 None.
        """
        key = candidate_key(ghost_w, ghost_h)
        candidates = self.state.setdefault("candidates", {})
        record = candidates.get(key)
        if not isinstance(record, dict):
            record = _candidate_defaults(ghost_w, ghost_h)
            record["started_at"] = now_iso()
            record["updated_at"] = now_iso()
            candidates[key] = record
        bound = record.get("bound_state")
        if not isinstance(bound, dict):
            bound = _bound_state_defaults()

        old_lb = bound.get("lb")
        old_model_hash = bound.get("model_hash")

        if lb is not None:
            bound["lb"] = int(lb)
        if ub is not None:
            bound["ub"] = int(ub)
        if gap is not None:
            bound["gap"] = float(gap)
        if epsilon_target is not None:
            bound["epsilon_target"] = float(epsilon_target)
        if prover is not None:
            bound["prover"] = str(prover)
        if model_hash is not None:
            bound["model_hash"] = str(model_hash)
        bound["observed_at"] = now_iso()
        record["bound_state"] = bound
        record["updated_at"] = now_iso()
        self.state["updated_at"] = now_iso()

        # P1 #7d bound regression guard: 检测 lb 是否退化。
        audit_entry: Optional[Dict[str, Any]] = None
        if (
            lb is not None
            and isinstance(old_lb, int)
            and int(lb) < int(old_lb) - int(regression_tolerance)
        ):
            audit_entry = {
                "ts": now_iso(),
                "candidate_key": key,
                "event": "BOUND_REGRESSION",
                "old_lb": int(old_lb),
                "new_lb": int(lb),
                "tolerance": int(regression_tolerance),
                "model_hash_old": old_model_hash,
                "model_hash_new": bound.get("model_hash"),
                "prover": bound.get("prover"),
            }
            audit_log = self.state.setdefault("audit_log", [])
            if isinstance(audit_log, list):
                audit_log.append(audit_entry)
        return audit_entry

    def get_audit_log(self) -> list[Dict[str, Any]]:
        """P1 #7d: read accumulated audit events (BOUND_REGRESSION 等)."""
        log = self.state.get("audit_log", [])
        return list(log) if isinstance(log, list) else []

    def mark_candidate_started(self, ghost_w: int, ghost_h: int) -> None:
        key = candidate_key(ghost_w, ghost_h)
        candidates = self.state.setdefault("candidates", {})
        existing = candidates.get(key, {})
        record = _candidate_defaults(ghost_w, ghost_h)
        if isinstance(existing, Mapping):
            record.update(dict(existing))

        timestamp = now_iso()
        record["status"] = "RUNNING"
        record["attempts"] = int(record.get("attempts", 0)) + 1
        record["started_at"] = timestamp
        record["updated_at"] = timestamp
        record["finished_at"] = None

        candidates[key] = record
        self.state["last_stop_reason"] = None
        if self.state.get("final_result") is None:
            self.state["final_status"] = None
        self.state["updated_at"] = timestamp

    def mark_candidate_result(
        self,
        ghost_w: int,
        ghost_h: int,
        status: str,
        *,
        exact_safe_cuts: Optional[list[Mapping[str, Any]]] = None,
        solution: Optional[Mapping[str, Any]] = None,
        proof_summary: Optional[Mapping[str, Any]] = None,
        loaded_exact_safe_cut_count: Optional[int] = None,
        generated_exact_safe_cut_count: Optional[int] = None,
    ) -> None:
        key = candidate_key(ghost_w, ghost_h)
        candidates = self.state.setdefault("candidates", {})
        existing = candidates.get(key, {})
        record = _candidate_defaults(ghost_w, ghost_h)
        if isinstance(existing, Mapping):
            record.update(dict(existing))

        timestamp = now_iso()
        record["status"] = str(status)
        record["updated_at"] = timestamp
        record["finished_at"] = timestamp
        if record.get("started_at") is None:
            record["started_at"] = timestamp
        record["proof_summary"] = dict(proof_summary or {})

        if exact_safe_cuts is not None:
            record["exact_safe_cuts"] = [dict(cut) for cut in exact_safe_cuts]
        else:
            record["exact_safe_cuts"] = list(record.get("exact_safe_cuts", []))

        if loaded_exact_safe_cut_count is not None:
            record["loaded_exact_safe_cut_count"] = int(loaded_exact_safe_cut_count)
        else:
            record["loaded_exact_safe_cut_count"] = int(record.get("loaded_exact_safe_cut_count", 0))

        if generated_exact_safe_cut_count is not None:
            record["generated_exact_safe_cut_count"] = int(generated_exact_safe_cut_count)
        else:
            record["generated_exact_safe_cut_count"] = int(
                record.get("generated_exact_safe_cut_count", 0)
            )

        if solution is not None and status == "CERTIFIED":
            record["solution"] = dict(solution)
            candidate_result = {
                "ghost_rect": {"w": ghost_w, "h": ghost_h, "area": ghost_w * ghost_h},
                "placement_solution": dict(solution),
                "search_status": status,
                "search_stats": {
                    "campaign_resumed": self.resumed,
                    "timestamp": timestamp,
                },
            }
            existing_result = self.state.get("final_result")
            if not isinstance(existing_result, Mapping) or _candidate_objective_from_rect(
                ghost_w,
                ghost_h,
            ) >= _final_result_objective(existing_result):
                self.state["final_result"] = candidate_result
                self.state["final_status"] = "CERTIFIED"
                self.state["last_stop_reason"] = None
        elif status != "CERTIFIED":
            record.pop("solution", None)

        candidates[key] = record
        self.state["updated_at"] = timestamp

    def update_candidate_running_proof_summary(
        self,
        ghost_w: int,
        ghost_h: int,
        proof_summary: Mapping[str, Any],
    ) -> None:
        key = candidate_key(ghost_w, ghost_h)
        candidates = self.state.setdefault("candidates", {})
        existing = candidates.get(key, {})
        record = _candidate_defaults(ghost_w, ghost_h)
        if isinstance(existing, Mapping):
            record.update(dict(existing))

        if str(record.get("status")) != "RUNNING":
            return

        timestamp = now_iso()
        existing_summary = record.get("proof_summary")
        merged_summary = dict(existing_summary) if isinstance(existing_summary, Mapping) else {}
        merged_summary.update(dict(proof_summary or {}))
        record["proof_summary"] = merged_summary
        record["updated_at"] = timestamp
        candidates[key] = record
        self.state["updated_at"] = timestamp

    def mark_campaign_stopped(self, reason: str, status: Optional[str] = None) -> None:
        timestamp = now_iso()
        stop_record = {
            "reason": str(reason),
            "status": None if status is None else str(status),
            "updated_at": timestamp,
        }
        self.state["last_stop_reason"] = stop_record
        if status is not None:
            if _has_certified_final_result(self.state) and str(status) != "CERTIFIED":
                self.state["final_status"] = "CERTIFIED"
            else:
                self.state["final_status"] = str(status)
        self.state["updated_at"] = timestamp

    def best_certified_result(self) -> Optional[Dict[str, Any]]:
        result = self.state.get("final_result")
        if not isinstance(result, dict):
            return None
        result_copy = dict(result)
        result_copy["search_status"] = "CERTIFIED"
        self.state["final_result"] = dict(result_copy)
        self.state["final_status"] = "CERTIFIED"
        return result_copy

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state["updated_at"] = now_iso()
        atomic_write_json(self.path, self.state)
