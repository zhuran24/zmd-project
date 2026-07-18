"""
Pose-level commodity-to-port-cell binding helpers.

This module turns an operation-level port profile plus a concrete pose into a
finite domain of legal commodity assignments on that pose's physical port cells.
It does not solve the global binding problem yet; it only exposes the exact
per-instance combinatorial domain for operations whose commodities are already
fixed.
"""

from __future__ import annotations

from itertools import combinations, product
from typing import AbstractSet, Any, Dict, List, Mapping, Sequence, Tuple

from src.preprocess.operation_profiles import get_operation_port_profile

PortCell = Dict[str, Any]
SideBinding = List[PortCell]
BindingDomain = List[Dict[str, SideBinding]]
SideBindingPattern = Tuple[Tuple[int, str], ...]
BindingPattern = Tuple[SideBindingPattern, SideBindingPattern]
PoseBindingCacheKey = Tuple[
    str,
    Tuple[Tuple[int, int, str], ...],
    Tuple[Tuple[int, int, str], ...],
]
_POSE_LEVEL_BINDING_CACHE: Dict[PoseBindingCacheKey, Tuple[BindingPattern, ...]] = {}


def supports_exact_pose_level_binding(operation_type: str) -> bool:
    profile = get_operation_port_profile(operation_type)
    return profile.generic_input_slots == 0 and profile.generic_output_slots == 0


def is_routing_visible_output_commodity(
    commodity: Any,
    routing_free_sink_commodities: AbstractSet[str],
) -> bool:
    """RFSC 输出侧排除规则的单一真相源（demand SSOT，front-clear 上收批）。

    现行 canonical generic-input 成品均是真 routed 商品，producer output
    port 必须作为 routing source。binding filter（_filter_pose_binding_domain）、
    extract_port_specs 与 master 侧 front-clear lift 的 demand 计算仍共用本
    谓词，以便未来若经 owner 裁决引入真实路由豁免时只有一个收窄点。
    取值 str-strict：缺键/坏形态在调用点崩溃 fail-closed，不静默默认。
    """
    return str(commodity) not in routing_free_sink_commodities


def routing_free_sink_commodities_from_generic_inputs(
    required_generic_inputs: Mapping[Any, Any],
) -> frozenset[str]:
    """RFSC 集派生规则的单一真相源——批 5 (2026-07-18) 改判后恒为空集。

    owner 游戏实测定谳（rules_audit_20260718/00 §3.1/§3.2）：generic_input
    终品（成品）是**真 routed 商品**——producer 输出口=routing source、绑定的
    箱/中枢实体收货槽=routing sink，"无线"仅存在于箱→仓库段、不豁免任何
    路由几何。旧派生（required>0 ⇒ routing-free）是 F03-R3-01 错位语义的
    核心开关。本函数保留为 SSOT 锚点（binding filter、extract_port_specs、
    master front-clear lift 三处仍须经由本函数拿排除集，禁止内联），但恒返
    回空集；输入仍被消费以保留坏形态崩溃的 fail-closed 行为。若未来出现
    真正 routing-free 的商品类别，必须经 owner 裁决在此重新收窄。
    """
    for commodity, required in dict(required_generic_inputs).items():
        str(commodity)
        int(required)
    return frozenset()


def routing_visible_port_demands(
    operation_type: str,
    routing_free_sink_commodities: AbstractSet[str],
) -> Tuple[int, int]:
    """返回 (req_in, vis_out)：该 op 每侧 routing-visible 绑定需求（demand SSOT）。

    语义 = 枚举器×filter 的联立蕴含（计数等价定理，doc 04 v2 §1.1/§3.4）：
    - req_in  = 输入侧 slot 计数总和（filter 对 input_ports 全量检查，无排除）；
    - vis_out = 输出侧 slot 中 commodity 过 is_routing_visible_output_commodity
      的计数总和（现行 canonical RFSC 恒为空，因此所有输出均可见）。

    demand 依赖 certified generic_io snapshot（routing_free_sink_commodities
    仍由 required_generic_inputs 的同源快照派生，但当前结果恒为空）。master
    侧仍必须传入与 binding 同源的 snapshot。generic-slot op 出范围：与枚举器同款
    raise fail-closed，绝不返回猜测值。
    """
    profile = get_operation_port_profile(operation_type)
    if profile.generic_input_slots or profile.generic_output_slots:
        raise ValueError(
            f"{operation_type} still has generic hub slots; routing-visible "
            "pose-level demand is undefined for it (out of lift scope)."
        )
    req_in = sum(count for count in profile.input_slots.values() if count > 0)
    vis_out = sum(
        count
        for commodity, count in profile.output_slots.items()
        if count > 0
        and is_routing_visible_output_commodity(
            commodity, routing_free_sink_commodities
        )
    )
    return req_in, vis_out


def clear_pose_level_binding_domain_cache() -> None:
    _POSE_LEVEL_BINDING_CACHE.clear()


def enumerate_pose_level_port_bindings_with_cache_info(
    operation_type: str,
    pose: Mapping[str, Any],
) -> Tuple[BindingDomain, bool]:
    profile = get_operation_port_profile(operation_type)
    if profile.generic_input_slots or profile.generic_output_slots:
        raise ValueError(
            f"{operation_type} still has generic hub slots; exact pose-level binding "
            "must be decided by a higher-level assignment model."
        )

    ordered_input_cells = _ordered_port_cells(pose.get("input_port_cells", []))
    ordered_output_cells = _ordered_port_cells(pose.get("output_port_cells", []))
    cache_key = _pose_binding_cache_key(operation_type, ordered_input_cells, ordered_output_cells)

    patterns = _POSE_LEVEL_BINDING_CACHE.get(cache_key)
    cache_hit = patterns is not None
    if patterns is None:
        input_patterns = _enumerate_side_binding_patterns(
            len(ordered_input_cells),
            profile.input_slots,
            port_type="input",
        )
        output_patterns = _enumerate_side_binding_patterns(
            len(ordered_output_cells),
            profile.output_slots,
            port_type="output",
        )
        patterns = tuple(product(input_patterns, output_patterns))
        _POSE_LEVEL_BINDING_CACHE[cache_key] = patterns

    bindings: BindingDomain = []
    for input_pattern, output_pattern in patterns:
        input_ports = _materialize_side_binding(
            ordered_input_cells,
            input_pattern,
            port_type="input",
        )
        output_ports = _materialize_side_binding(
            ordered_output_cells,
            output_pattern,
            port_type="output",
        )
        bindings.append(
            {
                "input_ports": input_ports,
                "output_ports": output_ports,
                "active_ports": input_ports + output_ports,
            }
        )
    return bindings, cache_hit


def enumerate_pose_level_port_bindings(
    operation_type: str,
    pose: Mapping[str, Any],
) -> List[Dict[str, List[Dict[str, Any]]]]:
    """Enumerate all legal commodity assignments for one placed pose."""
    bindings, _cache_hit = enumerate_pose_level_port_bindings_with_cache_info(
        operation_type,
        pose,
    )
    return bindings


def _ordered_port_cells(
    port_cells: Sequence[Mapping[str, Any]],
) -> List[PortCell]:
    ordered_cells = [_normalize_port_cell(port) for port in port_cells]
    ordered_cells.sort(key=lambda item: (item["x"], item["y"], item["dir"]))
    return ordered_cells


def _pose_binding_cache_key(
    operation_type: str,
    ordered_input_cells: Sequence[PortCell],
    ordered_output_cells: Sequence[PortCell],
) -> PoseBindingCacheKey:
    all_cells = [*ordered_input_cells, *ordered_output_cells]
    if all_cells:
        origin_x = min(int(cell["x"]) for cell in all_cells)
        origin_y = min(int(cell["y"]) for cell in all_cells)
    else:
        origin_x = 0
        origin_y = 0

    def _normalize_side_signature(cells: Sequence[PortCell]) -> Tuple[Tuple[int, int, str], ...]:
        return tuple(
            (
                int(cell["x"]) - origin_x,
                int(cell["y"]) - origin_y,
                str(cell["dir"]),
            )
            for cell in cells
        )

    return (
        str(operation_type),
        _normalize_side_signature(ordered_input_cells),
        _normalize_side_signature(ordered_output_cells),
    )


def _enumerate_side_binding_patterns(
    ordered_cell_count: int,
    slot_counts: Mapping[str, int],
    port_type: str,
) -> List[SideBindingPattern]:
    required = [(commodity, count) for commodity, count in slot_counts.items() if count > 0]
    total_slots = sum(count for _, count in required)
    if total_slots > ordered_cell_count:
        raise ValueError(
            f"{port_type} ports are insufficient: need {total_slots}, have {ordered_cell_count}"
        )
    if not required:
        return [tuple()]

    results: List[SideBindingPattern] = []

    def backtrack(
        req_idx: int,
        remaining_indices: Sequence[int],
        chosen: Dict[int, str],
    ) -> None:
        if req_idx >= len(required):
            results.append(
                tuple((idx, str(chosen[idx])) for idx in sorted(chosen))
            )
            return

        commodity, count = required[req_idx]
        for combo in combinations(remaining_indices, count):
            next_chosen = dict(chosen)
            for idx in combo:
                next_chosen[idx] = commodity
            next_remaining = [idx for idx in remaining_indices if idx not in combo]
            backtrack(req_idx + 1, next_remaining, next_chosen)

    backtrack(0, list(range(ordered_cell_count)), {})
    return results


def _materialize_side_binding(
    ordered_cells: Sequence[PortCell],
    binding_pattern: SideBindingPattern,
    *,
    port_type: str,
) -> SideBinding:
    return [
        {
            "type": port_type,
            "commodity": commodity,
            "x": int(ordered_cells[idx]["x"]),
            "y": int(ordered_cells[idx]["y"]),
            "dir": str(ordered_cells[idx]["dir"]),
        }
        for idx, commodity in binding_pattern
    ]


def _normalize_port_cell(port: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "x": int(port["x"]),
        "y": int(port["y"]),
        "dir": str(port["dir"]),
    }
