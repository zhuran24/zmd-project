"""
Exact port-binding subproblem（精确端口绑定子问题）.

职责：
1. 对固定摆放解选择 exact pose-level binding（精确位姿级端口绑定）。
2. 从预处理工件 generic_io_requirements.json（通用 I/O 需求工件）读取默认需求，
   不再在模型内部长期硬编码默认值。
3. 识别 pose_optional::...（位姿级可选设施）合成实例，尤其是
   protocol_storage_box（协议储存箱）与 power_pole（供电桩）。
4. 输出可持久化的 conflict summary（冲突摘要），供 exact campaign（精确战役）写盘。
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set

from ortools.sat.python import cp_model

from src.io.strict_json import load_strict_json, loads_strict_json
from src.models.cp_sat_worker_config import (
    DEFAULT_BINDING_CP_SAT_WORKERS,
    apply_subproblem_memory_cap,
    resolve_cp_sat_worker_count,
)
from src.models._cpsat_compat import search_branching_name
from src.models.port_binding import (
    enumerate_pose_level_port_bindings_with_cache_info,
    supports_exact_pose_level_binding,
)
from src.preprocess.operation_profiles import (
    OPERATION_PORT_PROFILES,
    get_operation_port_profile,
)
from src.search.commodity_throughput import (
    classify_commodity_flow,
    compute_commodity_throughput,
)

# P2 #14 production: env-gated binding state dumper. 默认 off, 主路径不影响.
# 启用后每次 solve() 入口把 binding 输入 dump 到 jsonl, 给后续 cut evolve
# evaluator 当 fixture 用. 见 docs/research/profiles/p2_14_alphaevolve_poc_*.
EXACT_BINDING_DUMP_STATE_ENV = "EXACT_BINDING_DUMP_STATE"
_BINDING_DUMP_RELATIVE_PATH = "data/telemetry/binding_dumps.jsonl"

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GENERIC_IO_REQUIREMENTS_PATH = (
    PROJECT_ROOT / "data" / "preprocessed" / "generic_io_requirements.json"
)
PREPROCESS_PLAN_PATH = PROJECT_ROOT / "rules" / "preprocess_plan.json"

POSE_OPTIONAL_OPERATION_BY_TEMPLATE = {
    "protocol_storage_box": "wireless_sink",
    "power_pole": "power_supply",
}
NON_FACILITY_PLACEMENT_MARKER_IDS = {"ghost_pick"}
CANONICAL_PROFILE_FACILITY_TYPES = {
    str(profile.facility_type) for profile in OPERATION_PORT_PROFILES.values()
}


def _is_non_facility_placement_marker(instance_id: str) -> bool:
    return str(instance_id) in NON_FACILITY_PLACEMENT_MARKER_IDS


def _loads_strict_json(text: str) -> Any:
    return loads_strict_json(text)


def _load_strict_json(path: Path) -> Any:
    return load_strict_json(path)


def _normalize_wireless_sink_generic_input_slots(
    raw_slot_count: Any,
    *,
    field: str = "wireless_sink.generic_input_slots",
) -> int:
    if isinstance(raw_slot_count, bool) or not isinstance(raw_slot_count, int):
        raise TypeError(
            f"{field} must be an integer "
            "（无线消费槽位数必须是整数）"
        )
    slot_count = int(raw_slot_count)
    if slot_count < 0:
        raise ValueError(
            f"{field} must be non-negative "
            f"（无线消费槽位数不能为负）: {slot_count}"
        )
    return slot_count


def load_wireless_sink_generic_input_slots(
    *,
    project_root: Optional[Path] = None,
    path: Optional[Path] = None,
) -> int:
    """Load the canonical wireless-sink generic input slot count.

    protocol_storage_box is declared as ``omni_wireless`` in canonical rules and as
    ``wireless_sink`` in preprocess_plan.json. The binding model therefore
    accounts for generic input capacity without requiring a physical port cell.
    """

    if path is None:
        path = (
            PREPROCESS_PLAN_PATH
            if project_root is None
            else project_root / "rules" / "preprocess_plan.json"
        )

    if not path.exists():
        raise FileNotFoundError(
            f"Missing preprocess_plan artifact（缺少预处理计划工件）: {path}"
        )

    payload = _load_strict_json(path)
    if not isinstance(payload, Mapping):
        raise TypeError(
            "preprocess_plan must be a JSON object "
            "（预处理计划工件顶层必须是对象）"
        )
    utility_operations = payload.get("utility_operations")
    if not isinstance(utility_operations, Mapping):
        raise KeyError(
            "preprocess_plan.utility_operations is required for wireless sink binding "
            "（预处理计划缺少 utility_operations）"
        )
    wireless_sink = utility_operations.get("wireless_sink")
    if not isinstance(wireless_sink, Mapping):
        raise KeyError(
            "preprocess_plan.utility_operations.wireless_sink is required for "
            "wireless sink binding（预处理计划缺少 wireless_sink）"
        )
    if "generic_input_slots" not in wireless_sink:
        raise KeyError(
            "preprocess_plan utility_operations.wireless_sink.generic_input_slots "
            "is required for wireless sink binding（无线消费槽位数缺失）"
        )

    return _normalize_wireless_sink_generic_input_slots(
        wireless_sink["generic_input_slots"],
        field="wireless_sink.generic_input_slots",
    )


def load_wireless_sink_generic_input_slots_from_text(*, text: str) -> int:
    """Atomic-snapshot variant of load_wireless_sink_generic_input_slots (P1.2-FIX-5).

    Parses the preprocess_plan slot count from a pre-snapshotted artifact text so the
    bytes build consumes are the bytes the session hashed (no second disk read).
    """

    payload = _loads_strict_json(text)
    if not isinstance(payload, Mapping):
        raise TypeError(
            "preprocess_plan must be a JSON object "
            "（预处理计划工件顶层必须是对象）"
        )
    utility_operations = payload.get("utility_operations")
    if not isinstance(utility_operations, Mapping):
        raise KeyError(
            "preprocess_plan.utility_operations is required for wireless sink binding "
            "（预处理计划缺少 utility_operations）"
        )
    wireless_sink = utility_operations.get("wireless_sink")
    if not isinstance(wireless_sink, Mapping):
        raise KeyError(
            "preprocess_plan.utility_operations.wireless_sink is required for "
            "wireless sink binding（预处理计划缺少 wireless_sink）"
        )
    if "generic_input_slots" not in wireless_sink:
        raise KeyError(
            "preprocess_plan utility_operations.wireless_sink.generic_input_slots "
            "is required for wireless sink binding（无线消费槽位数缺失）"
        )
    return _normalize_wireless_sink_generic_input_slots(
        wireless_sink["generic_input_slots"],
        field="wireless_sink.generic_input_slots",
    )


def load_generic_io_requirements(
    *,
    project_root: Optional[Path] = None,
    path: Optional[Path] = None,
    validate_against_canonical: bool = True,
) -> Dict[str, Dict[str, int]]:
    """Load generic I/O requirements（加载通用 I/O 需求）.

    Returns:
        {
            "required_generic_outputs": {...},
            "required_generic_inputs": {...},
        }
    """

    if path is None:
        root = project_root or PROJECT_ROOT
        path = root / "data" / "preprocessed" / "generic_io_requirements.json"

    if not path.exists():
        raise FileNotFoundError(
            f"Missing generic_io_requirements artifact（缺少通用 I/O 需求工件）: {path}"
        )

    payload = _load_strict_json(path)
    if not isinstance(payload, Mapping):
        raise TypeError(
            "generic_io_requirements must be a JSON object "
            "（通用 I/O 需求工件顶层必须是对象）"
        )

    requirements = {
        "required_generic_outputs": _load_generic_io_requirement_section(
            payload,
            "required_generic_outputs",
        ),
        "required_generic_inputs": _load_generic_io_requirement_section(
            payload,
            "required_generic_inputs",
        ),
    }
    if validate_against_canonical:
        _validate_generic_io_requirement_roles(
            requirements,
            project_root=project_root or PROJECT_ROOT,
        )
    return requirements


def load_generic_io_requirements_from_text(
    *,
    text: str,
    project_root: Optional[Path] = None,
    canonical_rules_text: Optional[str] = None,
    canonical_rules_payload: Optional[Mapping[str, Any]] = None,
    canonical_commodity_metadata: Optional[Mapping[str, Any]] = None,
    validate_against_canonical: bool = True,
) -> Dict[str, Dict[str, int]]:
    """Atomic-snapshot variant of load_generic_io_requirements (P1.2-FIX-5).

    Parses the generic IO requirements from a pre-snapshotted artifact text so the
    bytes build consumes are the bytes the session hashed (no second disk read).
    Certified callers must pass the matching snapshot canonical_rules payload/text
    so role validation consumes the same canonical bytes as the master build.
    """

    payload = _loads_strict_json(text)
    if not isinstance(payload, Mapping):
        raise TypeError(
            "generic_io_requirements must be a JSON object "
            "（通用 I/O 需求工件顶层必须是对象）"
        )
    requirements = {
        "required_generic_outputs": _load_generic_io_requirement_section(
            payload,
            "required_generic_outputs",
        ),
        "required_generic_inputs": _load_generic_io_requirement_section(
            payload,
            "required_generic_inputs",
        ),
    }
    if validate_against_canonical:
        if canonical_rules_payload is None and canonical_rules_text is not None:
            loaded_canonical = _loads_strict_json(canonical_rules_text)
            if not isinstance(loaded_canonical, Mapping):
                raise TypeError(
                    "canonical_rules must be a JSON object for generic I/O validation"
                )
            canonical_rules_payload = loaded_canonical
        _validate_generic_io_requirement_roles(
            requirements,
            project_root=project_root or PROJECT_ROOT,
            canonical_rules_payload=canonical_rules_payload,
            canonical_commodity_metadata=canonical_commodity_metadata,
        )
    return requirements


def _load_generic_io_requirement_section(
    payload: Mapping[str, Any],
    section_name: str,
) -> Dict[str, int]:
    if section_name not in payload:
        raise KeyError(
            f"generic_io_requirements.{section_name} is required "
            f"（通用 I/O 需求工件缺少 {section_name}）"
        )

    raw_section = payload[section_name]
    if not isinstance(raw_section, Mapping):
        raise TypeError(
            f"generic_io_requirements.{section_name} must be an object "
            f"（{section_name} 必须是对象）"
        )
    return _normalize_generic_io_requirement_mapping(raw_section, section_name)


def _normalize_generic_io_requirement_mapping(
    raw_section: Mapping[str, Any],
    section_name: str,
) -> Dict[str, int]:
    section: Dict[str, int] = {}
    for raw_commodity, raw_count in raw_section.items():
        commodity = str(raw_commodity)
        if commodity == "__unused__":
            raise ValueError(
                f"generic_io_requirements.{section_name}.__unused__ is reserved "
                "for the binding model sentinel "
                f"（{section_name}.__unused__ 是 binding 未使用槽哨兵，不能作为商品）"
            )
        if isinstance(raw_count, bool) or not isinstance(raw_count, int):
            raise TypeError(
                f"generic_io_requirements.{section_name}.{commodity} must be an integer "
                f"（{section_name}.{commodity} 必须是整数槽数）"
            )
        if raw_count < 0:
            raise ValueError(
                f"generic_io_requirements.{section_name}.{commodity} must be non-negative "
                f"（{section_name}.{commodity} 不能为负）: {raw_count}"
            )
        section[commodity] = int(raw_count)
    return section


def _validate_generic_io_requirement_roles(
    requirements: Mapping[str, Mapping[str, int]],
    *,
    project_root: Optional[Path] = None,
    canonical_rules_payload: Optional[Mapping[str, Any]] = None,
    canonical_commodity_metadata: Optional[Mapping[str, Any]] = None,
) -> None:
    output_commodities = tuple(requirements.get("required_generic_outputs", {}))
    input_commodities = tuple(requirements.get("required_generic_inputs", {}))
    if not output_commodities and not input_commodities:
        return

    if canonical_commodity_metadata is not None:
        commodity_metadata = canonical_commodity_metadata
    else:
        if canonical_rules_payload is None:
            root = project_root or PROJECT_ROOT
            canonical_path = root / "rules" / "canonical_rules.json"
            if not canonical_path.exists():
                raise FileNotFoundError(
                    f"Missing canonical_rules artifact for generic I/O validation "
                    f"（缺少 canonical_rules 以校验通用 I/O）: {canonical_path}"
                )

            canonical = _load_strict_json(canonical_path)
        else:
            canonical = canonical_rules_payload
        if not isinstance(canonical, Mapping):
            raise TypeError(
                "canonical_rules must be a JSON object for generic I/O validation"
            )
        commodity_metadata = canonical.get("commodity_metadata")
    if not isinstance(commodity_metadata, Mapping):
        raise KeyError(
            "canonical_rules.commodity_metadata is required for generic I/O validation "
            "（canonical_rules 缺少 commodity_metadata）"
        )

    for commodity in output_commodities:
        metadata = commodity_metadata.get(commodity)
        if not isinstance(metadata, Mapping):
            raise KeyError(
                f"generic output commodity {commodity!r} is absent from "
                "canonical_rules.commodity_metadata "
                f"（通用输出商品 {commodity!r} 未登记在 canonical commodity_metadata）"
            )
        if metadata.get("source_kind") != "external_boundary":
            raise ValueError(
                f"generic output commodity {commodity!r} must have "
                "source_kind=external_boundary in canonical_rules "
                f"（通用输出商品 {commodity!r} 必须是外部边界源）"
            )

    for commodity in input_commodities:
        metadata = commodity_metadata.get(commodity)
        if not isinstance(metadata, Mapping):
            raise KeyError(
                f"generic input commodity {commodity!r} is absent from "
                "canonical_rules.commodity_metadata "
                f"（通用输入商品 {commodity!r} 未登记在 canonical commodity_metadata）"
            )
        if metadata.get("sink_kind") != "generic_input":
            raise ValueError(
                f"generic input commodity {commodity!r} must have "
                "sink_kind=generic_input in canonical_rules "
                f"（通用输入商品 {commodity!r} 必须是通用输入终端商品）"
            )

    # F-BIND-R8-02（owner-channel, LOW availability hardening）: 一旦声明了非空
    # generic I/O 需求工件, 它必须以正槽数覆盖所有 canonical sink_kind=generic_input
    # 终品. 漏声明或零槽数会悄悄缩小 binding capacity, 并把该终品移出 routing-free
    # sink 集合, 使其 producer 的无线终品输出变成孤儿 routing terminal（spurious
    # front_blocked / false-INFEASIBLE）. 只有 output+input 双空才是合法退化态
    #（上方 early return 已处理）; output-only 工件不是空需求, 也必须接受完备性校验.
    canonical_generic_inputs = sorted(
        str(commodity)
        for commodity, metadata in commodity_metadata.items()
        if isinstance(metadata, Mapping)
        and metadata.get("sink_kind") == "generic_input"
    )
    input_requirements = requirements.get("required_generic_inputs", {})
    missing_generic_inputs = [
        commodity
        for commodity in canonical_generic_inputs
        if commodity not in input_requirements
    ]
    non_positive_generic_inputs = [
        commodity
        for commodity in canonical_generic_inputs
        if commodity in input_requirements
        and int(input_requirements[commodity]) <= 0
    ]
    if missing_generic_inputs or non_positive_generic_inputs:
        details = []
        if missing_generic_inputs:
            details.append("missing=" + ",".join(missing_generic_inputs))
        if non_positive_generic_inputs:
            details.append("non_positive=" + ",".join(non_positive_generic_inputs))
        raise ValueError(
            "generic_io_requirements.required_generic_inputs must include every "
            "canonical sink_kind=generic_input commodity with a positive slot count "
            "（非空 generic I/O 需求工件必须以正槽数覆盖所有 canonical generic_input 终品）: "
            + "; ".join(details)
        )


class PortBindingModel:
    """CP-SAT model（CP-SAT 模型）for exact port binding（精确端口绑定）."""

    def __init__(
        self,
        placement_solution: Mapping[str, Mapping[str, Any]],
        facility_pools: Mapping[str, List[Dict[str, Any]]],
        instances: Sequence[Mapping[str, Any]],
        required_generic_outputs: Optional[Mapping[str, int]] = None,
        required_generic_inputs: Optional[Mapping[str, int]] = None,
        project_root: Optional[Path] = None,
        io_requirements_path: Optional[Path] = None,
        wireless_sink_generic_input_slots: Optional[int] = None,
        routing_context: Optional[Any] = None,  # RAB-SEP Phase 1: routing-aware filter
        canonical_rules_payload: Optional[Mapping[str, Any]] = None,
        canonical_commodity_metadata: Optional[Mapping[str, Any]] = None,
    ):
        self.project_root = project_root or PROJECT_ROOT
        self.io_requirements_path = io_requirements_path
        if canonical_rules_payload is not None and not isinstance(
            canonical_rules_payload,
            Mapping,
        ):
            raise TypeError("canonical_rules_payload must be a mapping")
        if canonical_commodity_metadata is not None and not isinstance(
            canonical_commodity_metadata,
            Mapping,
        ):
            raise TypeError("canonical_commodity_metadata must be a mapping")
        self._canonical_rules_payload = canonical_rules_payload
        self._canonical_commodity_metadata = canonical_commodity_metadata
        self._wireless_sink_generic_input_slots: Optional[int] = (
            None
            if wireless_sink_generic_input_slots is None
            else _normalize_wireless_sink_generic_input_slots(
                wireless_sink_generic_input_slots,
                field="wireless_sink_generic_input_slots",
            )
        )
        self.placement_solution = {
            str(instance_id): dict(sol)
            for instance_id, sol in placement_solution.items()
        }
        self.facility_pools = {tpl: list(pool) for tpl, pool in facility_pools.items()}
        self.instances_by_id = {
            str(inst["instance_id"]): dict(inst)
            for inst in instances
        }

        if required_generic_outputs is None or required_generic_inputs is None:
            io_requirements = load_generic_io_requirements(
                project_root=self.project_root,
                path=self.io_requirements_path,
                validate_against_canonical=False,
            )
        else:
            io_requirements = {
                "required_generic_outputs": {},
                "required_generic_inputs": {},
            }

        self.required_generic_outputs = _normalize_generic_io_requirement_mapping(
            (
                required_generic_outputs
                if required_generic_outputs is not None
                else io_requirements["required_generic_outputs"]
            ),
            "required_generic_outputs",
        )
        self.required_generic_inputs = _normalize_generic_io_requirement_mapping(
            (
                required_generic_inputs
                if required_generic_inputs is not None
                else io_requirements["required_generic_inputs"]
            ),
            "required_generic_inputs",
        )
        _validate_generic_io_requirement_roles(
            {
                "required_generic_outputs": self.required_generic_outputs,
                "required_generic_inputs": self.required_generic_inputs,
            },
            project_root=self.project_root,
            canonical_rules_payload=self._canonical_rules_payload,
            canonical_commodity_metadata=self._canonical_commodity_metadata,
        )
        self.routing_free_sink_commodities = {
            str(commodity)
            for commodity, required in self.required_generic_inputs.items()
            if int(required) > 0
        }

        self.model = cp_model.CpModel()
        self._solver: Optional[cp_model.CpSolver] = None
        self._status: Optional[int] = None
        self._conflict_summary: Dict[str, Any] = {
            "placement_instances": sorted(self.placement_solution.keys()),
            "synthesized_instances": [],
            "missing_instance_ids": [],
            "ignored_placement_marker_ids": [],
            "invalid_instance_metadata": [],
            "invalid_binding_input_reasons": [],
            "binding_domains": {},
            "empty_binding_domain_instances": [],
            "binding_domain_cache_hits": 0,
            "binding_domain_cache_misses": 0,
            "binding_domain_reused_instances": [],
            "required_generic_outputs": dict(self.required_generic_outputs),
            "required_generic_inputs": dict(self.required_generic_inputs),
            "routing_free_sink_commodities": sorted(self.routing_free_sink_commodities),
        }

        self.binding_domains: Dict[str, List[Dict[str, List[Dict[str, Any]]]]] = {}
        self.binding_vars: Dict[str, Dict[int, Any]] = {}
        self.fixed_binding_choice: Dict[str, int] = {}
        self.empty_binding_domain_instances: List[Dict[str, Any]] = []
        self.generic_output_slots: List[Dict[str, Any]] = []
        self.generic_output_vars: Dict[str, Dict[str, Any]] = {}
        self.generic_input_slots: List[Dict[str, Any]] = []
        self.generic_input_vars: Dict[str, Dict[str, Any]] = {}
        self.binding_domain_cache_hits = 0
        self.binding_domain_cache_misses = 0
        self.binding_domain_reused_instances: List[str] = []
        self._ignored_placement_marker_ids: List[str] = []

        # RAB-SEP Phase 1: routing-aware filter context (None when disabled)
        self.routing_context = routing_context
        self.routing_aware_filter_stats: Dict[str, Any] = {
            "enabled": routing_context is not None,
            "raw_patterns_total": 0,
            "filtered_patterns_total": 0,
            "front_blocked_patterns_pruned": 0,
            "empty_filtered_owners": [],
            "generic_output_slots_pre_filter": 0,
            "generic_output_slots_post_filter": 0,
            "generic_input_slots_pre_filter": 0,
            "generic_input_slots_post_filter": 0,
        }
        # RAB-SEP Phase 3: per-owner blocker info for cert generation
        # key: instance_id -> set of blocker instance_ids
        self.routing_aware_blockers_by_owner: Dict[str, Set[str]] = {}

        self._materialize_pose_optional_instances()
        self._validate_placement_instance_metadata()

    def _materialize_pose_optional_instances(self) -> None:
        synthesized: List[str] = []

        for instance_id, sol in self.placement_solution.items():
            if instance_id in self.instances_by_id:
                continue
            if _is_non_facility_placement_marker(instance_id):
                self._record_ignored_placement_marker(instance_id)
                continue

            facility_type = str(sol.get("facility_type", ""))
            operation_type = POSE_OPTIONAL_OPERATION_BY_TEMPLATE.get(facility_type)
            if operation_type is None and instance_id.startswith("pose_optional::"):
                _, inferred_tpl, *_rest = instance_id.split("::")
                operation_type = POSE_OPTIONAL_OPERATION_BY_TEMPLATE.get(inferred_tpl)
                if operation_type is not None:
                    facility_type = inferred_tpl

            if operation_type is None:
                self._record_missing_instance_id(instance_id)
                continue

            self.instances_by_id[instance_id] = {
                "instance_id": instance_id,
                "facility_type": facility_type,
                "operation_type": operation_type,
                "is_mandatory": False,
                "bound_type": str(sol.get("bound_type", "exact_pose_optional")),
                "solve_mode": str(sol.get("solve_mode", "unknown")),
            }
            synthesized.append(instance_id)

        self._conflict_summary["synthesized_instances"] = synthesized
        self._conflict_summary["ignored_placement_marker_ids"] = list(
            self._ignored_placement_marker_ids
        )

    def _record_ignored_placement_marker(self, instance_id: str) -> None:
        marker_id = str(instance_id)
        if marker_id not in self._ignored_placement_marker_ids:
            self._ignored_placement_marker_ids.append(marker_id)

    def _record_missing_instance_id(self, instance_id: str) -> None:
        missing_id = str(instance_id)
        missing = self._conflict_summary.setdefault("missing_instance_ids", [])
        if missing_id not in missing:
            missing.append(missing_id)

    def _record_invalid_instance_metadata(
        self,
        instance_id: str,
        reason: str,
        **details: Any,
    ) -> None:
        record = {
            "instance_id": str(instance_id),
            "reason": str(reason),
            **{str(key): value for key, value in details.items()},
        }
        records = self._conflict_summary.setdefault("invalid_instance_metadata", [])
        if not any(
            existing.get("instance_id") == record["instance_id"]
            and existing.get("reason") == record["reason"]
            for existing in records
        ):
            records.append(record)

    def _validate_placement_instance_metadata(self) -> None:
        for instance_id, sol in self.placement_solution.items():
            if _is_non_facility_placement_marker(instance_id):
                continue
            inst = self.instances_by_id.get(instance_id)
            if inst is None:
                continue
            self._validate_instance_metadata_consistency(instance_id, sol, inst)

    def _validate_instance_metadata_consistency(
        self,
        instance_id: str,
        sol: Mapping[str, Any],
        inst: Mapping[str, Any],
    ) -> None:
        raw_solution_facility_type = sol.get("facility_type")
        solution_facility_type = str(raw_solution_facility_type or "")
        if not solution_facility_type:
            self._record_invalid_instance_metadata(
                instance_id,
                "missing_solution_facility_type",
            )

        raw_pose_idx = sol.get("pose_idx")
        pose_idx: Optional[int]
        if isinstance(raw_pose_idx, bool) or raw_pose_idx is None:
            pose_idx = None
            self._record_invalid_instance_metadata(
                instance_id,
                "invalid_solution_pose_idx",
                pose_idx=raw_pose_idx,
            )
        else:
            try:
                pose_idx = int(raw_pose_idx)
            except (TypeError, ValueError):
                pose_idx = None
                self._record_invalid_instance_metadata(
                    instance_id,
                    "invalid_solution_pose_idx",
                    pose_idx=raw_pose_idx,
                )
        if solution_facility_type and pose_idx is not None:
            pool = self.facility_pools.get(solution_facility_type, [])
            if pose_idx < 0 or pose_idx >= len(pool):
                self._record_invalid_instance_metadata(
                    instance_id,
                    "solution_pose_idx_out_of_range",
                    facility_type=solution_facility_type,
                    pose_idx=pose_idx,
                )

        raw_instance_facility_type = inst.get("facility_type")
        instance_facility_type = str(raw_instance_facility_type or "")
        if not instance_facility_type:
            self._record_invalid_instance_metadata(
                instance_id,
                "missing_instance_facility_type",
            )
        elif solution_facility_type and instance_facility_type != solution_facility_type:
            self._record_invalid_instance_metadata(
                instance_id,
                "instance_facility_type_mismatch",
                instance_facility_type=instance_facility_type,
                solution_facility_type=solution_facility_type,
            )

        is_canonical_solution_facility = (
            solution_facility_type in CANONICAL_PROFILE_FACILITY_TYPES
        )

        raw_operation_type = inst.get("operation_type")
        operation_type = str(raw_operation_type or "")
        if not operation_type:
            if is_canonical_solution_facility:
                self._record_invalid_instance_metadata(
                    instance_id,
                    "missing_operation_type",
                )
            return

        try:
            profile = get_operation_port_profile(operation_type)
        except KeyError:
            if is_canonical_solution_facility:
                self._record_invalid_instance_metadata(
                    instance_id,
                    "unknown_operation_type",
                    operation_type=operation_type,
                )
            return

        expected_facility_type = str(profile.facility_type)
        if (
            is_canonical_solution_facility
            and expected_facility_type != solution_facility_type
        ):
            self._record_invalid_instance_metadata(
                instance_id,
                "operation_facility_type_mismatch",
                operation_type=operation_type,
                expected_facility_type=expected_facility_type,
                solution_facility_type=solution_facility_type,
            )

    def _has_invalid_binding_input(self) -> bool:
        return bool(
            self._conflict_summary.get("missing_instance_ids")
            or self._conflict_summary.get("invalid_instance_metadata")
        )

    def _mark_invalid_binding_input_summary(self) -> None:
        reasons: List[str] = []
        if self._conflict_summary.get("missing_instance_ids"):
            reasons.append("missing_instance_metadata")
        invalid_metadata_reasons = sorted(
            {
                str(record.get("reason"))
                for record in self._conflict_summary.get("invalid_instance_metadata", [])
                if record.get("reason")
            }
        )
        reasons.extend(invalid_metadata_reasons)
        self._conflict_summary["invalid_binding_input_reasons"] = reasons

    def build(self, *, use_overload_separation: Optional[bool] = None) -> None:
        self._build_fixed_operation_domains()
        self._build_generic_input_domains()
        self._build_generic_output_domains()
        self._add_generic_input_requirements()
        self._add_generic_output_requirements()
        self._mark_invalid_binding_input_summary()
        if self.empty_binding_domain_instances:
            self.model.Add(0 == 1)
        self._add_search_guidance()
        self._conflict_summary["generic_output_slot_count"] = len(self.generic_output_slots)
        self._conflict_summary["generic_input_slot_count"] = len(self.generic_input_slots)
        # Phase 3C P1 #9 hint 2 stage 2 (env-gated): forbid pairing
        # high-prod-low-demand and low-prod-high-demand commodities in the
        # same storage box. Default OFF — requires caller-side fallback
        # ladder when enabled (handle INFEASIBLE by retrying without nogood).
        # use_overload_separation overrides the env when not None: I1 independent
        # reverify passes False to force this heuristic OFF regardless of env, so
        # the independent binding model never carries a feasible-solution-cutting
        # nogood (depth-defense — the reverifier must not inherit a heuristic that
        # could turn a feasible layout into a heuristic-INFEASIBLE sealed as a cut).
        if use_overload_separation is None:
            overload_env = os.environ.get(
                "EXACT_BINDING_USE_OVERLOAD_SEPARATION", ""
            ).strip().lower()
            enabled = overload_env in {"1", "true", "yes", "on"}
        else:
            enabled = bool(use_overload_separation)
        if enabled:
            nogood_count = self._add_storage_box_overload_nogoods()
            self._conflict_summary["overload_separation_enabled"] = True
            self._conflict_summary["overload_nogoods_added"] = int(nogood_count)
        else:
            self._conflict_summary["overload_separation_enabled"] = False
            self._conflict_summary["overload_nogoods_added"] = 0

    def _load_overload_classification(self) -> Dict[str, str]:
        """Lazy-load commodity classification. Uses the caller-provided
        canonical snapshot when present, otherwise reads canonical_rules.json from
        project_root, then classifies each commodity as high_prod_low_demand /
        low_prod_high_demand / balanced.
        """
        if getattr(self, "_overload_classification_cache", None) is not None:
            return self._overload_classification_cache
        if self._canonical_rules_payload is not None:
            rules = self._canonical_rules_payload
        else:
            rules_path = self.project_root / "rules" / "canonical_rules.json"
            rules = _load_strict_json(rules_path)
        instances = list(self.instances_by_id.values())
        throughput = compute_commodity_throughput(rules, instances)
        self._overload_classification_cache = classify_commodity_flow(
            throughput, threshold_ratio=0.1
        )
        return self._overload_classification_cache

    def _add_storage_box_overload_nogoods(self) -> int:
        """P1 #9 hint 2 stage 2: forbid high+low commodity pair in same storage box.

        For every protocol_storage_box instance (operation_type=wireless_sink),
        for every (c_high, c_low) pair where c_high is high_prod_low_demand and
        c_low is low_prod_high_demand, add CP-SAT clause:
            NOT (h_lit AND l_lit) ≡ AddBoolOr([h_lit.Not(), l_lit.Not()])
        for every input-slot literal pair (h_lit, l_lit) on that box.

        This is a HARD nogood — it can cut feasible solutions when the
        commodity supply structurally forces high+low colocation. Caller
        MUST implement a fallback ladder: detect INFEASIBLE while
        overload_separation_enabled and retry with env unset.

        Returns: number of nogood clauses added (for logging / A-B test).
        """
        classification = self._load_overload_classification()
        high_set = {c for c, k in classification.items() if k == "high_prod_low_demand"}
        low_set = {c for c, k in classification.items() if k == "low_prod_high_demand"}
        if not high_set or not low_set:
            return 0

        # Group input slots by storage-box instance.
        slots_by_instance: Dict[str, List[str]] = {}
        for slot in self.generic_input_slots:
            instance_id = str(slot.get("instance_id", ""))
            if not instance_id:
                continue
            slots_by_instance.setdefault(instance_id, []).append(str(slot["slot_id"]))

        nogood_count = 0
        for instance_id, slot_ids in slots_by_instance.items():
            inst = self.instances_by_id.get(instance_id)
            if not inst or str(inst.get("operation_type", "")) != "wireless_sink":
                continue
            for c_high in high_set:
                high_lits = [
                    self.generic_input_vars[s][c_high]
                    for s in slot_ids
                    if c_high in self.generic_input_vars.get(s, {})
                ]
                if not high_lits:
                    continue
                for c_low in low_set:
                    low_lits = [
                        self.generic_input_vars[s][c_low]
                        for s in slot_ids
                        if c_low in self.generic_input_vars.get(s, {})
                    ]
                    if not low_lits:
                        continue
                    for h in high_lits:
                        for low_lit in low_lits:
                            self.model.AddBoolOr([h.Not(), low_lit.Not()])
                            nogood_count += 1
        return nogood_count

    def _resolve_instance(self, instance_id: str) -> Optional[Dict[str, Any]]:
        inst = self.instances_by_id.get(instance_id)
        if inst is not None:
            return inst
        if _is_non_facility_placement_marker(instance_id):
            self._record_ignored_placement_marker(instance_id)
            self._conflict_summary["ignored_placement_marker_ids"] = list(
                self._ignored_placement_marker_ids
            )
            return None
        self._record_missing_instance_id(instance_id)
        return None

    def _filter_pose_binding_domain(
        self,
        raw_patterns: List[Dict[str, List[Dict[str, Any]]]],
        owner_instance_id: str,
    ) -> List[Dict[str, List[Dict[str, Any]]]]:
        """RAB-SEP Phase 1: layout-local front-free filter on raw binding patterns.

        Returns NEW list (raw cache not polluted). Pattern is kept iff every
        routing-visible active port has front cell in-grid and free. Routing-free
        wireless final commodities are excluded on the producer-output side here,
        matching extract_port_specs(): their output ports are binding choices only,
        not routing terminals.

        Phase 3 side effect: collect blocker instance_ids for cert generation
        — every blocker that occupies a routing-visible active port front cell
        across any raw pattern is recorded. Used by
        extract_routing_aware_certificates().
        """
        if self.routing_context is None:
            return list(raw_patterns)
        from src.models.routing_binding_context import port_front_status
        kept: List[Dict[str, List[Dict[str, Any]]]] = []
        blockers: Set[str] = set()
        for pattern in raw_patterns:
            ok = True
            routing_visible_ports = list(pattern.get("input_ports", []))
            routing_visible_ports.extend(
                port
                for port in pattern.get("output_ports", [])
                if str(port.get("commodity", "")) not in self.routing_free_sink_commodities
            )
            for port in routing_visible_ports:
                status = port_front_status(port, self.routing_context, owner_instance_id)
                if not (status.in_grid and status.is_free):
                    ok = False
                    if status.blocker_instance_id is not None:
                        blockers.add(status.blocker_instance_id)
                    # 不 break — 继续 collect 该 pattern 中所有 blocker
            if ok:
                kept.append(pattern)
        if blockers:
            self.routing_aware_blockers_by_owner[owner_instance_id] = blockers
        return kept

    def extract_routing_aware_certificates(self) -> List[Dict[str, Any]]:
        """RAB-SEP Phase 3: generate clear-deficit certificates for empty filtered owners.

        Each cert = owner_pose + minimal blocker_poses (instance_id, pose_idx) —
        禁止该 owner_pose 跟该 blocker_poses 同时出现.

        Returns list of certs sorted by core size (smallest first), to feed
        master add_benders_cut().
        """
        certs: List[Dict[str, Any]] = []
        for owner_id in self.routing_aware_filter_stats.get("empty_filtered_owners", []):
            owner_sol = self.placement_solution.get(str(owner_id), {})
            owner_pose_idx = int(owner_sol.get("pose_idx", -1))
            if owner_pose_idx < 0:
                continue
            blockers = self.routing_aware_blockers_by_owner.get(str(owner_id), set())
            conflict_set: Dict[str, int] = {str(owner_id): owner_pose_idx}
            for blocker_id in blockers:
                b_sol = self.placement_solution.get(blocker_id, {})
                b_pose_idx = int(b_sol.get("pose_idx", -1))
                if b_pose_idx >= 0:
                    conflict_set[blocker_id] = b_pose_idx
            certs.append({
                "owner_instance_id": str(owner_id),
                "owner_pose_idx": owner_pose_idx,
                "blocker_instance_ids": sorted(blockers),
                "conflict_set": conflict_set,
                "core_size": len(conflict_set),
            })
        certs.sort(key=lambda c: c["core_size"])
        return certs

    def _resolve_pose(self, facility_type: str, pose_idx: int) -> Dict[str, Any]:
        pool = self.facility_pools.get(facility_type, [])
        if pose_idx < 0 or pose_idx >= len(pool):
            raise IndexError(
                f"Pose index（位姿索引） out of range（越界）: {facility_type}[{pose_idx}]"
            )
        return pool[pose_idx]

    def _build_fixed_operation_domains(self) -> None:
        for instance_id, sol in self.placement_solution.items():
            inst = self._resolve_instance(instance_id)
            if not inst:
                continue

            operation_type = str(inst.get("operation_type", ""))
            if not operation_type or not supports_exact_pose_level_binding(operation_type):
                continue

            tpl = str(sol["facility_type"])
            pose = self._resolve_pose(tpl, int(sol["pose_idx"]))
            domains, cache_hit = enumerate_pose_level_port_bindings_with_cache_info(
                operation_type,
                pose,
            )
            if cache_hit:
                self.binding_domain_cache_hits += 1
                self.binding_domain_reused_instances.append(instance_id)
            else:
                self.binding_domain_cache_misses += 1

            # RAB-SEP Phase 1: filter raw patterns to front-free ones (layout-local, not cached)
            if self.routing_context is not None and domains:
                raw_count = len(domains)
                domains = self._filter_pose_binding_domain(domains, instance_id)
                self.routing_aware_filter_stats["raw_patterns_total"] += raw_count
                self.routing_aware_filter_stats["filtered_patterns_total"] += len(domains)
                self.routing_aware_filter_stats["front_blocked_patterns_pruned"] += (raw_count - len(domains))

            if not domains:
                empty_domain = {
                    "instance_id": instance_id,
                    "facility_type": tpl,
                    "operation_type": operation_type,
                    "pose_idx": int(sol["pose_idx"]),
                    "pose_id": str(pose.get("pose_id", "")),
                }
                self.empty_binding_domain_instances.append(empty_domain)
                self._conflict_summary["binding_domains"][instance_id] = 0
                if self.routing_context is not None:
                    self.routing_aware_filter_stats["empty_filtered_owners"].append(instance_id)
                continue

            self.binding_domains[instance_id] = domains
            self._conflict_summary["binding_domains"][instance_id] = len(domains)
            if len(domains) == 1:
                self.fixed_binding_choice[instance_id] = 0
                continue

            self.binding_vars[instance_id] = {}
            for idx in range(len(domains)):
                self.binding_vars[instance_id][idx] = self.model.NewBoolVar(
                    f"bind_{instance_id}_{idx}"
                )
            self.model.AddExactlyOne(list(self.binding_vars[instance_id].values()))
        self._conflict_summary["binding_domain_cache_hits"] = int(self.binding_domain_cache_hits)
        self._conflict_summary["binding_domain_cache_misses"] = int(self.binding_domain_cache_misses)
        self._conflict_summary["binding_domain_reused_instances"] = list(
            self.binding_domain_reused_instances
        )

    def _build_generic_output_domains(self) -> None:
        generic_commodities = sorted(self.required_generic_outputs.keys())
        if not generic_commodities:
            return
        slot_commodities = generic_commodities + ["__unused__"]

        for instance_id, sol in self.placement_solution.items():
            inst = self._resolve_instance(instance_id)
            if not inst:
                continue
            operation_type = str(inst.get("operation_type", ""))
            if operation_type not in {"boundary_io", "protocol_core"}:
                continue

            tpl = str(sol["facility_type"])
            pose = self._resolve_pose(tpl, int(sol["pose_idx"]))
            for local_idx, port in enumerate(pose.get("output_port_cells", [])):
                self.routing_aware_filter_stats["generic_output_slots_pre_filter"] += 1
                # RAB-SEP Phase 1: skip front-blocked generic output slot
                if self.routing_context is not None:
                    from src.models.routing_binding_context import is_port_front_usable
                    if not is_port_front_usable(port, self.routing_context, instance_id):
                        continue
                self.routing_aware_filter_stats["generic_output_slots_post_filter"] += 1
                slot_id = f"{instance_id}:out:{local_idx}"
                slot = {
                    "slot_id": slot_id,
                    "instance_id": instance_id,
                    "x": int(port["x"]),
                    "y": int(port["y"]),
                    "dir": str(port["dir"]),
                    "type": "out",
                }
                self.generic_output_slots.append(slot)
                self.generic_output_vars[slot_id] = {}
                for commodity in slot_commodities:
                    self.generic_output_vars[slot_id][commodity] = self.model.NewBoolVar(
                        f"slot_{slot_id}_{commodity}"
                    )
                self.model.AddExactlyOne(list(self.generic_output_vars[slot_id].values()))

    def _wireless_sink_input_slot_count(self) -> int:
        if self._wireless_sink_generic_input_slots is None:
            self._wireless_sink_generic_input_slots = load_wireless_sink_generic_input_slots(
                project_root=self.project_root
            )
        return self._wireless_sink_generic_input_slots

    def _build_generic_input_domains(self) -> None:
        generic_commodities = sorted(self.required_generic_inputs.keys())
        if not generic_commodities:
            return
        slot_commodities = generic_commodities + ["__unused__"]

        for instance_id, _sol in self.placement_solution.items():
            inst = self._resolve_instance(instance_id)
            if not inst:
                continue
            operation_type = str(inst.get("operation_type", ""))
            if operation_type != "wireless_sink":
                continue

            # ``wireless_sink`` is intentionally routing-free: protocol storage
            # boxes have no physical input port cells under the canonical
            # ``omni_wireless`` rule. Binding still needs the capacity rows, so
            # materialize virtual generic-input slots from preprocess_plan.json
            # and do not pass them through routing-front filtering.
            for local_idx in range(self._wireless_sink_input_slot_count()):
                self.routing_aware_filter_stats["generic_input_slots_pre_filter"] += 1
                self.routing_aware_filter_stats["generic_input_slots_post_filter"] += 1
                slot_id = f"{instance_id}:in:{local_idx}"
                slot = {
                    "slot_id": slot_id,
                    "instance_id": instance_id,
                    "type": "in",
                    "operation_type": "wireless_sink",
                    "routing_free": True,
                    "virtual": True,
                }
                self.generic_input_slots.append(slot)
                self.generic_input_vars[slot_id] = {}
                for commodity in slot_commodities:
                    self.generic_input_vars[slot_id][commodity] = self.model.NewBoolVar(
                        f"slot_{slot_id}_{commodity}"
                    )
                self.model.AddExactlyOne(list(self.generic_input_vars[slot_id].values()))

    def _add_generic_input_requirements(self) -> None:
        for commodity, required in self.required_generic_inputs.items():
            vars_for_commodity = [
                commodity_vars[commodity]
                for commodity_vars in self.generic_input_vars.values()
                if commodity in commodity_vars
            ]
            if required == 0:
                for var in vars_for_commodity:
                    self.model.Add(var == 0)
                continue
            self.model.Add(sum(vars_for_commodity) == required)

    def _add_generic_output_requirements(self) -> None:
        for commodity, required in self.required_generic_outputs.items():
            vars_for_commodity = [
                commodity_vars[commodity]
                for commodity_vars in self.generic_output_vars.values()
                if commodity in commodity_vars
            ]
            if required == 0:
                for var in vars_for_commodity:
                    self.model.Add(var == 0)
                continue
            self.model.Add(sum(vars_for_commodity) == required)

    def _ordered_generic_slot_commodities(
        self,
        commodity_vars: Mapping[str, Any],
    ) -> List[str]:
        return sorted(
            commodity_vars,
            key=lambda commodity: (
                str(commodity) == "__unused__",
                str(commodity),
            ),
        )

    def _add_search_guidance(self) -> None:
        binding_literals = 0
        generic_input_literals = 0
        generic_output_literals = 0

        for instance_id in sorted(self.binding_vars):
            ordered_vars = [
                self.binding_vars[instance_id][idx]
                for idx in sorted(self.binding_vars[instance_id])
            ]
            if not ordered_vars:
                continue
            self.model.AddDecisionStrategy(
                ordered_vars,
                cp_model.CHOOSE_FIRST,
                cp_model.SELECT_MAX_VALUE,
            )
            binding_literals += len(ordered_vars)

        for slot_id in sorted(self.generic_input_vars):
            ordered_vars = [
                self.generic_input_vars[slot_id][commodity]
                for commodity in self._ordered_generic_slot_commodities(
                    self.generic_input_vars[slot_id]
                )
            ]
            if not ordered_vars:
                continue
            self.model.AddDecisionStrategy(
                ordered_vars,
                cp_model.CHOOSE_FIRST,
                cp_model.SELECT_MAX_VALUE,
            )
            generic_input_literals += len(ordered_vars)

        for slot_id in sorted(self.generic_output_vars):
            ordered_vars = [
                self.generic_output_vars[slot_id][commodity]
                for commodity in self._ordered_generic_slot_commodities(
                    self.generic_output_vars[slot_id]
                )
            ]
            if not ordered_vars:
                continue
            self.model.AddDecisionStrategy(
                ordered_vars,
                cp_model.CHOOSE_FIRST,
                cp_model.SELECT_MAX_VALUE,
            )
            generic_output_literals += len(ordered_vars)

        self._conflict_summary["search_guidance"] = {
            "applied": bool(
                binding_literals or generic_input_literals or generic_output_literals
            ),
            "profile": "exact_binding_guided_branching_v1",
            "search_branching": "FIXED_SEARCH",
            "binding_literals": int(binding_literals),
            "generic_input_literals": int(generic_input_literals),
            "generic_output_literals": int(generic_output_literals),
        }

    def _maybe_dump_state(self, time_limit_seconds: float) -> None:
        """P2 #14 production: env-gated dump binding inputs as evaluator fixture.

        EXACT_BINDING_DUMP_STATE 启用后, 每次 solve() 入口把 binding 输入
        (placement_solution / instances / io requirements / time_limit) append
        到 data/telemetry/binding_dumps.jsonl. 给 P2 #14 cut-evolution evaluator
        用作 fixture (跑 baseline vs +hint wall-clock).

        失败 silent (try/except pass), 主路径绝不能因 dumper 异常崩.
        """
        if not os.environ.get(EXACT_BINDING_DUMP_STATE_ENV):
            return
        try:
            project_root = self.project_root or PROJECT_ROOT
            dump_path = Path(project_root) / _BINDING_DUMP_RELATIVE_PATH
            dump_path.parent.mkdir(parents=True, exist_ok=True)
            # schema v2: 加 facility_pools_signature 兜底, evaluator 重建
            # PortBindingModel 时若 facility_pools 漂移可 detect (虽然 evaluator
            # 用同 project_root 通常 OK, signature 作为 audit cross-check).
            # signature 用 canonical JSON dump 的 sha256 前 16 chars.
            fp_canonical = json.dumps(
                self.facility_pools, sort_keys=True, ensure_ascii=True, default=str
            )
            fp_signature = hashlib.sha256(fp_canonical.encode("utf-8")).hexdigest()[:16]
            record = {
                "schema_version": 2,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "placement_solution": self.placement_solution,
                "instances": list(self.instances_by_id.values()),
                "required_generic_outputs": dict(self.required_generic_outputs),
                "required_generic_inputs": dict(self.required_generic_inputs),
                "time_limit_seconds": float(time_limit_seconds),
                "facility_pools_signature": fp_signature,
            }
            with dump_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass

    def solve(self, time_limit_seconds: float = 30.0) -> str:
        self._maybe_dump_state(time_limit_seconds)
        self._mark_invalid_binding_input_summary()
        if self._has_invalid_binding_input():
            self._solver = None
            self._status = None
            self._conflict_summary["solver_status"] = "INVALID_INPUT"
            self._conflict_summary["wall_time"] = 0.0
            self._conflict_summary["search_profile"] = str(
                self._conflict_summary.get("search_guidance", {}).get(
                    "profile",
                    "exact_binding_guided_branching_v1",
                )
            )
            self._conflict_summary["search_branching"] = "NOT_SOLVED_INVALID_INPUT"
            return "INVALID_INPUT"

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(time_limit_seconds)
        solver.parameters.num_workers = resolve_cp_sat_worker_count(
            env_name="EXACT_BINDING_CP_SAT_WORKERS",
            default=DEFAULT_BINDING_CP_SAT_WORKERS,
        )
        solver.parameters.search_branching = cp_model.FIXED_SEARCH
        solver.parameters.symmetry_level = max(int(solver.parameters.symmetry_level), 3)
        solver.parameters.cp_model_probing_level = max(
            int(solver.parameters.cp_model_probing_level),
            3,
        )
        # 显式 env 注入必须最后应用: EXACT_SUBPROBLEM_PARAMS 的契约是 sweep 时
        # 显式指定的参数为最终值; 放在内置 profile 之前会被上面的硬编码静默覆盖
        # (search_branching 即因此曾不可覆盖)。缺省无 env 时此调用是 no-op,
        # 上面的 guided-branching profile 不变。
        apply_subproblem_memory_cap(solver)
        status = solver.Solve(self.model)
        self._solver = solver
        self._status = status

        self._conflict_summary["solver_status"] = solver.StatusName(status)
        self._conflict_summary["wall_time"] = solver.WallTime()
        self._conflict_summary["search_profile"] = str(
            self._conflict_summary.get("search_guidance", {}).get(
                "profile",
                "exact_binding_guided_branching_v1",
            )
        )
        self._conflict_summary["search_branching"] = search_branching_name(
            solver.parameters.search_branching
        )

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return "FEASIBLE"
        if status == cp_model.INFEASIBLE:
            return "INFEASIBLE"
        return "TIMEOUT"

    def extract_selection(self) -> Dict[str, Any]:
        if self._status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return {}

        selection = {
            "binding_choice": {},
            "generic_inputs": {},
            "generic_outputs": {},
        }

        for instance_id, choice in self.fixed_binding_choice.items():
            selection["binding_choice"][instance_id] = choice

        for instance_id, vars_by_idx in self.binding_vars.items():
            for idx, var in vars_by_idx.items():
                if self._solver is not None and self._solver.Value(var) == 1:
                    selection["binding_choice"][instance_id] = idx
                    break

        for slot in self.generic_input_slots:
            slot_id = slot["slot_id"]
            for commodity, var in self.generic_input_vars[slot_id].items():
                if self._solver is not None and self._solver.Value(var) == 1:
                    selection["generic_inputs"][slot_id] = commodity
                    break

        for slot in self.generic_output_slots:
            slot_id = slot["slot_id"]
            for commodity, var in self.generic_output_vars[slot_id].items():
                if self._solver is not None and self._solver.Value(var) == 1:
                    selection["generic_outputs"][slot_id] = commodity
                    break

        return selection

    def extract_port_specs(self) -> List[Dict[str, Any]]:
        if self._status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return []

        selection = self.extract_selection()
        port_specs: List[Dict[str, Any]] = []

        for instance_id, binding_idx in selection.get("binding_choice", {}).items():
            domain = self.binding_domains.get(instance_id, [])
            if binding_idx < 0 or binding_idx >= len(domain):
                continue
            for side_key in ("input_ports", "output_ports"):
                for port in domain[binding_idx][side_key]:
                    commodity = str(port["commodity"])
                    if (
                        side_key == "output_ports"
                        and commodity in self.routing_free_sink_commodities
                    ):
                        continue
                    port_specs.append(
                        {
                            "instance_id": instance_id,
                            "x": int(port["x"]),
                            "y": int(port["y"]),
                            "dir": str(port["dir"]),
                            "type": "in" if side_key == "input_ports" else "out",
                            "commodity": commodity,
                        }
                    )

        for slot in self.generic_input_slots:
            slot_id = slot["slot_id"]
            commodity = selection["generic_inputs"].get(slot_id)
            if commodity in (None, "__unused__"):
                continue
            if slot.get("routing_free") or slot.get("virtual"):
                continue
            port_specs.append(
                {
                    "instance_id": slot["instance_id"],
                    "x": slot["x"],
                    "y": slot["y"],
                    "dir": slot["dir"],
                    "type": slot["type"],
                    "commodity": commodity,
                }
            )

        for slot in self.generic_output_slots:
            slot_id = slot["slot_id"]
            commodity = selection["generic_outputs"].get(slot_id)
            if commodity in (None, "__unused__"):
                continue
            if str(commodity) in self.routing_free_sink_commodities:
                continue
            port_specs.append(
                {
                    "instance_id": slot["instance_id"],
                    "x": slot["x"],
                    "y": slot["y"],
                    "dir": slot["dir"],
                    "type": slot["type"],
                    "commodity": commodity,
                }
            )

        return port_specs

    def extract_conflict_summary(self) -> Dict[str, Any]:
        self._mark_invalid_binding_input_summary()
        empty_binding_domain_instances = self.extract_empty_binding_domain_instances()
        summary = dict(self._conflict_summary)
        summary["binding_domain_count"] = sum(len(v) for v in self.binding_domains.values())
        summary["binding_instance_count"] = len(self.binding_domains)
        summary["empty_binding_domain_count"] = len(empty_binding_domain_instances)
        summary["empty_binding_domain_instances"] = empty_binding_domain_instances
        summary["binding_domain_cache_hits"] = int(self.binding_domain_cache_hits)
        summary["binding_domain_cache_misses"] = int(self.binding_domain_cache_misses)
        summary["binding_domain_reused_instances"] = list(self.binding_domain_reused_instances)
        summary["selection"] = self.extract_selection() if self._status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else {}
        return summary

    def extract_empty_binding_domain_instances(self) -> List[Dict[str, Any]]:
        if self._has_invalid_binding_input():
            return []
        return [dict(item) for item in self.empty_binding_domain_instances]

    def add_nogood_cut(self, selection: Mapping[str, Any]) -> None:
        literals = []

        for instance_id, binding_idx in selection.get("binding_choice", {}).items():
            if instance_id in self.binding_vars and binding_idx in self.binding_vars[instance_id]:
                literals.append(self.binding_vars[instance_id][binding_idx])

        for slot_id, commodity in selection.get("generic_inputs", {}).items():
            if slot_id in self.generic_input_vars and commodity in self.generic_input_vars[slot_id]:
                literals.append(self.generic_input_vars[slot_id][commodity])

        for slot_id, commodity in selection.get("generic_outputs", {}).items():
            if slot_id in self.generic_output_vars and commodity in self.generic_output_vars[slot_id]:
                literals.append(self.generic_output_vars[slot_id][commodity])

        if literals:
            self.model.Add(sum(literals) <= len(literals) - 1)
