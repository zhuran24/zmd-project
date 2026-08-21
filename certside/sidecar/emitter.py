"""binding PB sidecar — 独立 OPB emitter（设计稿 v2 §3；零 import 生产代码）.

输入: binding_sidecar_model_input_v1 JSON（合成样本直给；真实样本经前端模块
从冻结工件推导后填入——前端未落地前真实样本走 NOT_REPLAYABLE，见 v2 §3.4）。
输出: instance.opb + varmap.json + conmap.json + emit_report.json。

语义权威: ../binding_canonical_semantics_v1.md（逐条对照源码锚点）。
失败模型: 一律 raise EmitterReject(status, subcode) —— fail-closed，绝不把
输入问题编码成 UNSAT（v2 §2.2/§5.0）。
"""

from __future__ import annotations

import json
import math
from itertools import combinations
from typing import Any, Dict, List, Mapping, Sequence, Tuple

SCHEMA_INPUT = "binding_sidecar_model_input_v1"

NON_FACILITY_PLACEMENT_MARKER_IDS = {"ghost_pick"}
UNUSED = "__unused__"

# ---- 组合护栏默认上限（v2 §5.0-3）
MAX_PATTERNS_PER_INSTANCE = 200_000
MAX_TOTAL_VARIABLES = 2_000_000


class EmitterReject(Exception):
    """fail-closed 拒绝：status ∈ {INPUT_INVALID, UNKNOWN}，subcode 细分."""

    def __init__(self, status: str, subcode: str, detail: str = ""):
        super().__init__(f"{status}/{subcode}: {detail}")
        self.status = status
        self.subcode = subcode
        self.detail = detail


# ---------------------------------------------------------------- strict JSON
def _validate_utility_operation_map(
    raw: Any,
    profiles: Mapping[str, Mapping[str, Any]],
    instances_by_id: Mapping[str, Mapping[str, Any]],
) -> Dict[str, str]:
    if not isinstance(raw, Mapping):
        detail = "plan_utility_operation_by_template must be an object"
        raise EmitterReject("INPUT_INVALID", "BAD_UTILITY_OPERATION_MAP", detail)
    full_map: Dict[str, str] = {}
    for raw_template, raw_operation in raw.items():
        facility_type = str(raw_template)
        operation_type = str(raw_operation)
        if not facility_type or not operation_type:
            detail = "utility operation map contains an empty identifier"
            raise EmitterReject("INPUT_INVALID", "BAD_UTILITY_OPERATION_MAP", detail)
        profile = profiles.get(operation_type)
        if not isinstance(profile, Mapping) or str(profile.get("facility_type", "")) != facility_type:
            detail = f"utility operation map/profile mismatch: {facility_type} -> {operation_type}"
            raise EmitterReject("INPUT_INVALID", "BAD_UTILITY_OPERATION_MAP", detail)
        full_map[facility_type] = operation_type
    represented = {
        str(instance.get("operation_type", ""))
        for instance in instances_by_id.values()
        if str(instance.get("operation_type", ""))
    }
    return {
        facility_type: operation_type
        for facility_type, operation_type in sorted(full_map.items())
        if operation_type not in represented
    }


def strict_json_loads(text: str) -> Any:
    """独立实现的 strict JSON（semantics_v1 §1：拒重复 key/NaN/Inf/非有限 float）."""

    def _pairs(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError(f"duplicate JSON key: {k}")
            out[k] = v
        return out

    def _const(v):
        raise ValueError(f"invalid JSON constant: {v}")

    def _float(v):
        f = float(v)
        if not math.isfinite(f):
            raise ValueError(f"non-finite JSON number: {v}")
        return f

    return json.loads(text, object_pairs_hook=_pairs, parse_constant=_const, parse_float=_float)


# ---------------------------------------------------------------- 输入校验（v2 §2.2）
def _require_int(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EmitterReject("INPUT_INVALID", "NON_INT_FIELD", f"{field}={value!r}")
    if value < minimum:
        raise EmitterReject("INPUT_INVALID", "NEGATIVE_FIELD", f"{field}={value}")
    return int(value)


def _validate_requirements(section: Mapping[str, Any], name: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for commodity, count in section.items():
        c = str(commodity)
        if c == UNUSED:
            raise EmitterReject("INPUT_INVALID", "UNUSED_SENTINEL_IN_REQUIREMENTS", name)
        out[c] = _require_int(count, f"{name}.{c}")
    return out


def _generic_output_slot_map_from_profiles(
    profiles: Mapping[str, Mapping[str, Any]],
) -> Dict[str, int]:
    """Independently derive provider admission from plan-derived profiles."""
    result: Dict[str, int] = {}
    for operation_type, profile in profiles.items():
        count = _require_int(
            profile.get("generic_output_slots", 0),
            f"profile.{operation_type}.generic_output_slots",
        )
        if count > 0:
            result[str(operation_type)] = count
    return dict(sorted(result.items()))


def _validate_generic_input_slot_map(
    raw: Any,
    profiles: Mapping[str, Mapping[str, Any]],
) -> Dict[str, int]:
    """Validate the frozen per-operation generic-input capacity account.

    The frontend derives this map from the same preprocess-plan snapshot as the
    operation profiles.  Requiring exact agreement here prevents a caller from
    silently restoring the removed single-receiver/virtual-slot semantics.
    """
    if not isinstance(raw, Mapping):
        raise EmitterReject(
            "INPUT_INVALID", "BAD_GENERIC_INPUT_SLOT_MAP", "expected object"
        )
    normalized: Dict[str, int] = {}
    for raw_operation_type, raw_count in raw.items():
        operation_type = str(raw_operation_type)
        if not operation_type:
            raise EmitterReject(
                "INPUT_INVALID", "BAD_GENERIC_INPUT_SLOT_MAP", "empty operation type"
            )
        count = _require_int(
            raw_count,
            f"generic_input_slots_by_operation.{operation_type}",
        )
        if count <= 0:
            raise EmitterReject(
                "INPUT_INVALID",
                "BAD_GENERIC_INPUT_SLOT_MAP",
                f"{operation_type}={count}; zero-capacity entries must be omitted",
            )
        normalized[operation_type] = count

    expected: Dict[str, int] = {}
    for operation_type, profile in profiles.items():
        count = _require_int(
            profile.get("generic_input_slots", 0),
            f"profile.{operation_type}.generic_input_slots",
        )
        if count > 0:
            expected[str(operation_type)] = count
    if normalized != expected:
        raise EmitterReject(
            "INPUT_INVALID",
            "GENERIC_INPUT_SLOT_MAP_MISMATCH",
            f"map={normalized} profiles={expected}",
        )
    return normalized


def _validate_generic_roles(
    req_out: Mapping[str, int],
    req_in: Mapping[str, int],
    commodity_metadata: Mapping[str, Any],
) -> None:
    if not req_out and not req_in:
        return  # 双空 = 合法退化态（semantics_v1 §4.1）
    for c in req_out:
        meta = commodity_metadata.get(c)
        if not isinstance(meta, Mapping):
            raise EmitterReject("INPUT_INVALID", "OUTPUT_COMMODITY_UNREGISTERED", c)
        if meta.get("source_kind") != "external_boundary":
            raise EmitterReject("INPUT_INVALID", "OUTPUT_ROLE_MISMATCH", c)
    for c in req_in:
        meta = commodity_metadata.get(c)
        if not isinstance(meta, Mapping):
            raise EmitterReject("INPUT_INVALID", "INPUT_COMMODITY_UNREGISTERED", c)
        if meta.get("sink_kind") != "generic_input":
            raise EmitterReject("INPUT_INVALID", "INPUT_ROLE_MISMATCH", c)
    canonical_inputs = sorted(
        str(c)
        for c, meta in commodity_metadata.items()
        if isinstance(meta, Mapping) and meta.get("sink_kind") == "generic_input"
    )
    missing = [c for c in canonical_inputs if c not in req_in]
    non_positive = [c for c in canonical_inputs if c in req_in and req_in[c] <= 0]
    if missing or non_positive:
        raise EmitterReject(
            "INPUT_INVALID",
            "GENERIC_INPUT_COMPLETENESS",
            f"missing={missing} non_positive={non_positive}",
        )


def _synthesize_instances(
    placement: Mapping[str, Mapping[str, Any]],
    instances_by_id: Dict[str, Dict[str, Any]],
    operation_by_template: Mapping[str, str],
) -> List[str]:
    """pose_optional 合成（semantics_v1 §4.1，含 `::` 反推）。缺映射 = INPUT_INVALID."""
    synthesized: List[str] = []
    for instance_id, sol in placement.items():
        if instance_id in instances_by_id:
            continue
        if instance_id in NON_FACILITY_PLACEMENT_MARKER_IDS:
            continue
        if not instance_id.startswith("pose_optional::"):
            raise EmitterReject(
                "INPUT_INVALID", "MISSING_INSTANCE_METADATA", instance_id
            )
        parts = instance_id.split("::")
        if len(parts) < 3 or not parts[1]:
            raise EmitterReject(
                "INPUT_INVALID", "MISSING_INSTANCE_METADATA", instance_id
            )
        facility_type = parts[1]
        solution_template = str(sol.get("facility_type", ""))
        if solution_template and solution_template != facility_type:
            raise EmitterReject(
                "INPUT_INVALID",
                "POSE_OPTIONAL_TEMPLATE_IDENTITY_MISMATCH",
                f"{instance_id}: {solution_template}!={facility_type}",
            )
        operation_type = operation_by_template.get(facility_type)
        if operation_type is None:
            raise EmitterReject(
                "INPUT_INVALID", "MISSING_INSTANCE_METADATA", instance_id
            )
        instances_by_id[instance_id] = {
            "instance_id": instance_id,
            "facility_type": facility_type,
            "operation_type": operation_type,
        }
        synthesized.append(instance_id)
    return synthesized


def _validate_metadata(
    placement: Mapping[str, Mapping[str, Any]],
    instances_by_id: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Any]],
    profiles: Mapping[str, Mapping[str, Any]],
) -> None:
    """semantics_v1 §4.1 metadata 一致性 + build 期 raise 类，全归 INPUT_INVALID."""
    canonical_facility_types = {
        str(p.get("facility_type", "")) for p in profiles.values()
    }
    for instance_id, sol in placement.items():
        if instance_id in NON_FACILITY_PLACEMENT_MARKER_IDS:
            continue
        inst = instances_by_id[instance_id]
        sol_ft = str(sol.get("facility_type") or "")
        if not sol_ft:
            raise EmitterReject("INPUT_INVALID", "MISSING_SOLUTION_FACILITY_TYPE", instance_id)
        raw_pose_idx = sol.get("pose_idx")
        if isinstance(raw_pose_idx, bool) or raw_pose_idx is None:
            raise EmitterReject("INPUT_INVALID", "INVALID_POSE_IDX", instance_id)
        try:
            pose_idx = int(raw_pose_idx)
        except (TypeError, ValueError):
            raise EmitterReject("INPUT_INVALID", "INVALID_POSE_IDX", instance_id)
        pool = facility_pools.get(sol_ft, [])
        if pose_idx < 0 or pose_idx >= len(pool):
            raise EmitterReject(
                "INPUT_INVALID", "POSE_IDX_OUT_OF_RANGE", f"{instance_id}:{sol_ft}[{pose_idx}]"
            )
        inst_ft = str(inst.get("facility_type") or "")
        if not inst_ft:
            raise EmitterReject("INPUT_INVALID", "MISSING_INSTANCE_FACILITY_TYPE", instance_id)
        if inst_ft != sol_ft:
            raise EmitterReject("INPUT_INVALID", "FACILITY_TYPE_MISMATCH", instance_id)
        op = str(inst.get("operation_type") or "")
        is_canonical = sol_ft in canonical_facility_types
        if not op:
            if is_canonical:
                raise EmitterReject("INPUT_INVALID", "MISSING_OPERATION_TYPE", instance_id)
            continue
        profile = profiles.get(op)
        if profile is None:
            if is_canonical:
                raise EmitterReject("INPUT_INVALID", "UNKNOWN_OPERATION_TYPE", f"{instance_id}:{op}")
            continue
        if is_canonical and str(profile.get("facility_type", "")) != sol_ft:
            raise EmitterReject(
                "INPUT_INVALID", "OPERATION_FACILITY_MISMATCH", f"{instance_id}:{op}"
            )


# ---------------------------------------------------------------- 域枚举（semantics_v1 §3）
def _physical_port_cell(port: Any, field: str) -> Tuple[int, int, str]:
    if not isinstance(port, Mapping):
        raise EmitterReject(
            "INPUT_INVALID", "BAD_PHYSICAL_PORT_CELL", f"{field}: expected object"
        )
    if not {"x", "y", "dir"}.issubset(port):
        raise EmitterReject(
            "INPUT_INVALID", "BAD_PHYSICAL_PORT_CELL", f"{field}: missing x/y/dir"
        )
    try:
        return int(port["x"]), int(port["y"]), str(port["dir"])
    except (TypeError, ValueError) as exc:
        raise EmitterReject(
            "INPUT_INVALID", "BAD_PHYSICAL_PORT_CELL", f"{field}: {exc}"
        ) from exc


def _normalize_cells(cells: Sequence[Mapping[str, Any]]) -> List[Tuple[int, int, str]]:
    out = [_physical_port_cell(c, f"port_cells[{idx}]") for idx, c in enumerate(cells)]
    out.sort()
    return out


def _side_patterns(
    cell_count: int, slot_counts: Mapping[str, int], side: str, instance_id: str
) -> List[Tuple[Tuple[int, str], ...]]:
    required = [(c, n) for c, n in slot_counts.items() if n > 0]
    total = sum(n for _, n in required)
    if total > cell_count:
        raise EmitterReject(
            "INPUT_INVALID",
            "PRODUCTION_EXCEPTION_CLASS",
            f"{side} ports insufficient for {instance_id}: need {total}, have {cell_count}",
        )
    if not required:
        return [tuple()]
    results: List[Tuple[Tuple[int, str], ...]] = []

    def backtrack(req_idx: int, remaining: Tuple[int, ...], chosen: Dict[int, str]) -> None:
        if req_idx >= len(required):
            results.append(tuple((i, chosen[i]) for i in sorted(chosen)))
            return
        commodity, count = required[req_idx]
        for combo in combinations(remaining, count):
            nxt = dict(chosen)
            for i in combo:
                nxt[i] = commodity
            backtrack(req_idx + 1, tuple(i for i in remaining if i not in combo), nxt)

    backtrack(0, tuple(range(cell_count)), {})
    return results


def _pattern_count(cell_count: int, slot_counts: Mapping[str, int]) -> int:
    """组合规模精确预估（不物化），护栏用."""
    n = cell_count
    total = 1
    for _, k in sorted((c, k) for c, k in slot_counts.items() if k > 0):
        total *= math.comb(n, k)
        n -= k
        if total > MAX_PATTERNS_PER_INSTANCE:
            return total
    return total


# ---------------------------------------------------------------- 主流程
def emit(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """model_input → {opb, varmap, conmap, report}。raise EmitterReject = fail-closed."""
    if payload.get("schema") != SCHEMA_INPUT:
        raise EmitterReject("INPUT_INVALID", "BAD_SCHEMA", str(payload.get("schema")))

    placement = {str(k): dict(v) for k, v in dict(payload["placement_solution"]).items()}
    facility_pools = {str(k): list(v) for k, v in dict(payload["facility_pools"]).items()}
    instances_by_id = {
        str(i["instance_id"]): dict(i) for i in payload["instances"]
    }
    profiles = {str(k): dict(v) for k, v in dict(payload["operation_profiles"]).items()}
    pose_optional_operation_by_template = _validate_utility_operation_map(
        payload.get("plan_utility_operation_by_template"),
        profiles,
        instances_by_id,
    )
    commodity_metadata = dict(payload.get("commodity_metadata", {}))

    req_out = _validate_requirements(payload["required_generic_outputs"], "required_generic_outputs")
    req_in = _validate_requirements(payload["required_generic_inputs"], "required_generic_inputs")
    _validate_generic_roles(req_out, req_in, commodity_metadata)
    if "wireless_sink_generic_input_slots" in payload:
        raise EmitterReject(
            "INPUT_INVALID",
            "LEGACY_WIRELESS_SLOT_FIELD",
            "use generic_input_slots_by_operation with physical pose input ports",
        )
    generic_input_slots_by_operation = _validate_generic_input_slot_map(
        payload.get("generic_input_slots_by_operation"),
        profiles,
    )
    generic_output_slots_by_operation = _generic_output_slot_map_from_profiles(
        profiles
    )

    synthesized = _synthesize_instances(
        placement,
        instances_by_id,
        pose_optional_operation_by_template,
    )
    _validate_metadata(placement, instances_by_id, facility_pools, profiles)

    # ---- 变量分配（v2 §3.1：确定性编号 + 结构化 varmap）
    varmap: List[Dict[str, Any]] = []  # index = var number - 1
    var_of: Dict[Tuple, int] = {}

    def new_var(semantic: Dict[str, Any], key: Tuple) -> int:
        varmap.append(semantic)
        var_of[key] = len(varmap)
        if len(varmap) > MAX_TOTAL_VARIABLES:
            raise EmitterReject("UNKNOWN", "EMITTER_DOMAIN_TOO_LARGE", "total variables cap")
        return len(varmap)

    # ---- binding 域组（instance_id 字典序）
    binding_domains: Dict[str, int] = {}   # instance_id -> pattern count（>1 才有变量）
    materialized_patterns: Dict[str, List[Dict[str, Any]]] = {}
    fixed_choices: Dict[str, int] = {}
    domain_estimates: Dict[str, int] = {}
    exo_bind_rows: List[Tuple[str, List[int]]] = []

    for instance_id in sorted(placement):
        if instance_id in NON_FACILITY_PLACEMENT_MARKER_IDS:
            continue
        inst = instances_by_id[instance_id]
        op = str(inst.get("operation_type") or "")
        if not op or op not in profiles:
            continue
        profile = profiles[op]
        gi = _require_int(profile.get("generic_input_slots", 0), f"profile.{op}.generic_input_slots")
        go = _require_int(profile.get("generic_output_slots", 0), f"profile.{op}.generic_output_slots")
        if gi or go:
            continue  # supports_exact_pose_level_binding == False → 不属 binding 域组
        sol = placement[instance_id]
        pose = facility_pools[str(sol["facility_type"])][int(sol["pose_idx"])]
        in_cells = _normalize_cells(pose.get("input_port_cells", []))
        out_cells = _normalize_cells(pose.get("output_port_cells", []))
        in_counts = {str(c): _require_int(n, f"profile.{op}.input_slot_counts.{c}")
                     for c, n in dict(profile.get("input_slot_counts", {})).items()}
        out_counts = {str(c): _require_int(n, f"profile.{op}.output_slot_counts.{c}")
                      for c, n in dict(profile.get("output_slot_counts", {})).items()}
        est = _pattern_count(len(in_cells), in_counts) * _pattern_count(len(out_cells), out_counts)
        domain_estimates[instance_id] = est
        if est > MAX_PATTERNS_PER_INSTANCE:
            raise EmitterReject(
                "UNKNOWN", "EMITTER_DOMAIN_TOO_LARGE", f"{instance_id}: {est} patterns"
            )
        in_patterns = _side_patterns(len(in_cells), in_counts, "input", instance_id)
        out_patterns = _side_patterns(len(out_cells), out_counts, "output", instance_id)
        n_patterns = len(in_patterns) * len(out_patterns)
        binding_domains[instance_id] = n_patterns
        # patterns 物化（canonical witness checker 用：idx→具体分配；两侧笛卡尔积
        # 的 idx 序 = out 侧快变，与变量分配序一致）
        materialized_patterns[instance_id] = [
            {
                "input": [
                    {"x": in_cells[i][0], "y": in_cells[i][1], "dir": in_cells[i][2],
                     "commodity": c}
                    for i, c in in_pat
                ],
                "output": [
                    {"x": out_cells[i][0], "y": out_cells[i][1], "dir": out_cells[i][2],
                     "commodity": c}
                    for i, c in out_pat
                ],
            }
            for in_pat in in_patterns
            for out_pat in out_patterns
        ]
        if n_patterns == 0:
            # semantics_v1 §3 推论：纯模型不可达；防御性保留（EMPTY false row 由 conmap 标注）
            exo_bind_rows.append((instance_id, []))
            continue
        if n_patterns == 1:
            fixed_choices[instance_id] = 0
            continue
        var_ids = [
            new_var(
                {"kind": "binding_choice", "instance_id": instance_id, "binding_idx": k},
                ("b", instance_id, k),
            )
            for k in range(n_patterns)
        ]
        exo_bind_rows.append((instance_id, var_ids))

    # ---- generic 槽组
    out_commodities = sorted(req_out) + [UNUSED]
    in_commodities = sorted(req_in) + [UNUSED]
    out_slots: List[str] = []
    in_slots: List[str] = []

    if req_out:
        for instance_id in sorted(placement):
            if instance_id in NON_FACILITY_PLACEMENT_MARKER_IDS:
                continue
            inst = instances_by_id[instance_id]
            operation_type = str(inst.get("operation_type") or "")
            declared_slots = generic_output_slots_by_operation.get(operation_type)
            if declared_slots is None:
                continue
            sol = placement[instance_id]
            pose = facility_pools[str(sol["facility_type"])][int(sol["pose_idx"])]
            output_ports = list(pose.get("output_port_cells", []) or [])
            if len(output_ports) != declared_slots:
                raise EmitterReject(
                    "INPUT_INVALID",
                    "GENERIC_OUTPUT_PORT_CAPACITY_DRIFT",
                    f"{operation_type}/{instance_id}: declares {declared_slots}, "
                    f"pose has {len(output_ports)} physical output ports",
                )
            for local_idx, port in enumerate(output_ports):
                x, y, direction = _physical_port_cell(
                    port, f"{instance_id}.output_port_cells[{local_idx}]"
                )
                slot_id = f"{instance_id}:out:{local_idx}"
                out_slots.append(slot_id)
                for c in out_commodities:
                    new_var(
                        {"kind": "generic_output",
                         "slot": {"slot_id": slot_id, "instance_id": instance_id,
                                  "direction": "out", "local_idx": local_idx,
                                  "x": x, "y": y, "dir": direction},
                         "commodity": c},
                        ("s", slot_id, c),
                    )
    if req_in:
        for instance_id in sorted(placement):
            if instance_id in NON_FACILITY_PLACEMENT_MARKER_IDS:
                continue
            inst = instances_by_id[instance_id]
            operation_type = str(inst.get("operation_type") or "")
            declared_slots = generic_input_slots_by_operation.get(operation_type)
            if declared_slots is None:
                continue
            sol = placement[instance_id]
            pose = facility_pools[str(sol["facility_type"])][int(sol["pose_idx"])]
            input_ports = list(pose.get("input_port_cells", []) or [])
            # Production creates one generic-input slot for every physical pose
            # input port, then independently requires the per-operation account
            # to equal that physical count.  Accepting a surplus here and slicing
            # it away would make the sidecar strictly stronger than production,
            # exactly the kind of common-mode-adjacent projection drift this
            # second encoding exists to catch.
            if len(input_ports) != declared_slots:
                raise EmitterReject(
                    "INPUT_INVALID",
                    "GENERIC_INPUT_PORT_CAPACITY_DRIFT",
                    f"{operation_type}/{instance_id}: declares {declared_slots}, "
                    f"pose has {len(input_ports)} physical input ports",
                )
            for local_idx, port in enumerate(input_ports):
                x, y, direction = _physical_port_cell(
                    port, f"{instance_id}.input_port_cells[{local_idx}]"
                )
                slot_id = f"{instance_id}:in:{local_idx}"
                in_slots.append(slot_id)
                for c in in_commodities:
                    new_var(
                        {"kind": "generic_input",
                         "slot": {"slot_id": slot_id, "instance_id": instance_id,
                                  "direction": "in", "local_idx": local_idx,
                                  "x": x, "y": y, "dir": direction,
                                  "operation_type": operation_type},
                         "commodity": c},
                        ("s", slot_id, c),
                    )

    # ---- 约束行组装（确定性行序；conmap 记 1-based 行号，等式标记供 #equal 计数）
    rows: List[Tuple[str, bool, Dict[str, Any]]] = []  # (opb_row, is_equality, conmap_entry)

    def add_row(terms: List[Tuple[int, int]], op: str, rhs: int, family: str, params: Dict[str, Any]):
        body = " ".join(f"{'+' if coef >= 0 else '-'}{abs(coef)} x{v}" for coef, v in terms)
        rows.append((f"{body} {op} {rhs} ;", op == "=", {"family": family, **params}))

    for instance_id, var_ids in exo_bind_rows:
        if not var_ids and binding_domains.get(instance_id) == 0:
            # EMPTY(i)：canonical false row（正字面量空和 >= 1 不合法，用固定假行 +1 x1 -1 x1 …
            # 不可行表达取 0 变量形式不被 OPB 接受 → 用真实变量对消不可得；退化用
            # `>= 1` 的空和不可写 → 直接拒绝该样本更诚实（Phase 1 不可达路径）。
            raise EmitterReject("UNKNOWN", "EMPTY_DOMAIN_UNREACHABLE_PATH",
                                f"{instance_id}: empty domain in pure model (unexpected)")
        add_row([(1, v) for v in var_ids], "=", 1, "EXO-BIND", {"instance_id": instance_id})

    for slot_id in out_slots:
        add_row([(1, var_of[("s", slot_id, c)]) for c in out_commodities], "=", 1,
                "EXO-SLOT", {"slot_id": slot_id, "direction": "out"})
    for slot_id in in_slots:
        add_row([(1, var_of[("s", slot_id, c)]) for c in in_commodities], "=", 1,
                "EXO-SLOT", {"slot_id": slot_id, "direction": "in"})

    for c in sorted(req_out):
        vars_c = [var_of[("s", s, c)] for s in out_slots]
        if req_out[c] > 0:
            add_row([(1, v) for v in vars_c], "=", req_out[c], "REQ-OUT", {"commodity": c})
        else:
            for s, v in zip(out_slots, vars_c):
                add_row([(1, v)], "=", 0, "ZERO-OUT", {"commodity": c, "slot_id": s})
    for c in sorted(req_in):
        vars_c = [var_of[("s", s, c)] for s in in_slots]
        if req_in[c] > 0:
            add_row([(1, v) for v in vars_c], "=", req_in[c], "REQ-IN", {"commodity": c})
        else:
            for s, v in zip(in_slots, vars_c):
                add_row([(1, v)], "=", 0, "ZERO-IN", {"commodity": c, "slot_id": s})

    # REQ 空和边界（semantics_v1：生产对空 vars 仍 Add(sum==required)）：
    # required>0 且无槽 → 生产模型不可行。OPB 无法写空和等式 → 用显式矛盾对
    # （任取哨兵变量 v: v=0 与 v=1）。若全模型零变量则拒绝（退化输入）。
    degenerate_rows: List[Tuple[str, int]] = []
    for c in sorted(req_out):
        if req_out[c] > 0 and not out_slots:
            degenerate_rows.append((f"REQ-OUT-EMPTYSUM:{c}", req_out[c]))
    for c in sorted(req_in):
        if req_in[c] > 0 and not in_slots:
            degenerate_rows.append((f"REQ-IN-EMPTYSUM:{c}", req_in[c]))
    if degenerate_rows:
        if not varmap:
            raise EmitterReject("UNKNOWN", "DEGENERATE_NO_VARIABLES",
                                f"positive requirement with zero slots and zero vars: {degenerate_rows}")
        for label, _req in degenerate_rows:
            add_row([(1, 1)], "=", 0, "EMPTY-SUM-FALSE", {"note": label, "half": "zero"})
            add_row([(1, 1)], "=", 1, "EMPTY-SUM-FALSE", {"note": label, "half": "one"})

    n_vars = len(varmap)
    n_rows = len(rows)
    n_eq = sum(1 for _, is_eq, _ in rows if is_eq)
    header = f"* #variable= {n_vars} #constraint= {n_rows} #equal= {n_eq} intsize= 0"
    opb_lines = [header] + [r for r, _, _ in rows]

    conmap = [
        {"opb_line": i + 2, "constraint_ordinal": i + 1, "is_equality": is_eq, **entry}
        for i, (_, is_eq, entry) in enumerate(rows)
    ]
    report = {
        "schema": "binding_sidecar_emit_report_v1",
        "n_variables": n_vars,
        "n_constraints": n_rows,
        "n_equalities": n_eq,
        "binding_instances": len(binding_domains),
        "fixed_choices": len(fixed_choices),
        "domain_estimates": domain_estimates,
        "generic_output_slots": len(out_slots),
        "generic_input_slots": len(in_slots),
        "synthesized_instances": synthesized,
        "tcb_shared_semantics": [
            "plan_derived_utility_operation_by_template",
            "NON_FACILITY_PLACEMENT_MARKER_IDS",
            "plan_derived_generic_output_slots", "generic_input_slots_by_operation",
            "supports_exact_pose_level_binding_gate",
        ],
    }
    return {
        "opb": "\n".join(opb_lines) + "\n",
        "varmap": {"schema": "binding_sidecar_varmap_v1", "variables": varmap},
        "conmap": {"schema": "binding_sidecar_conmap_v1", "constraints": conmap},
        "patterns": {
            "schema": "binding_sidecar_patterns_v1",
            "fixed_choices": fixed_choices,
            "by_instance": materialized_patterns,
        },
        "report": report,
    }
