"""Fail-closed schema gate for proof-bearing cut cert payloads."""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, Mapping

from src.io.strict_json import loads_strict_json


class CertPayloadSchemaError(ValueError):
    """Raised when a cut cert payload violates the family schema envelope."""


CERT_PAYLOAD_CERT_KIND_BY_FAMILY: Mapping[str, str] = {
    "region_capacity": "region_capacity_combinatorial",
    "cutset": "menger_min_cut",
    "port_exposure": "port_exposure_blocked",
    "component_reach": "bfs_disconnect_witness",
    "pattern_nogood": "bounded_deletion_core",
    "shape_packing_hall": "hall_interval_witness",
    "power_hitting_set": "power_cover_emptyset_ghost",
    "power_grid_reach": "power_pole_bfs_disconnect_ghost",
    "density_envelope": "density_envelope_v1",
}


CERT_PAYLOAD_ALLOWED_FIELDS: Mapping[str, FrozenSet[str]] = {
    "region_capacity": frozenset({
        "cert_kind",
        "region_kind",
        "region_cells_bitset_b64",
        "cap_R",
        "demand_R",
        "gap",
        "contributing_groups",
        "cells_per_pose",
        "lp_dual_ray_b64",
        "lp_dual_objective",
    }),
    "cutset": frozenset({
        "cert_kind",
        "side_a_bitset_b64",
        "side_b_bitset_b64",
        "cut_edges",
        "cut_size",
        "commodity_demand",
        "contributing_commodities",
    }),
    "port_exposure": frozenset({
        "cert_kind",
        "facility_group",
        "facility_pose_id",
        "port_cell",
        "port_direction",
        "front_cell",
        "blocking_facility",
        "active_port_witness_b64",
    }),
    "component_reach": frozenset({
        "cert_kind",
        "commodity_id",
        "src_cell",
        "sink_cell",
        "src_component_bitset_b64",
        "sink_component_bitset_b64",
        "separator_cells",
        "blocking_facilities",
    }),
    "pattern_nogood": frozenset({
        "cert_kind",
        "sub_problem_oracle_name",
        "sub_problem_oracle_version",
        "forbidden_pose_pattern",
        "core_minimization",
    }),
    "shape_packing_hall": frozenset({
        "cert_kind",
        "region_kind",
        "region_total_length",
        "partition_lens",
        "partition_offsets",
        "pose_length",
        "pose_shape_canonical",
        "max_packable",
        "total_packable",
        "contributing_group",
        "region_demand",
        "group_demand",
        "ghost_rect_repr",
        "exterior_blocks_digest",
    }),
    "power_hitting_set": frozenset({
        "cert_kind",
        "facility_group",
        "facility_pose_id",
        "facility_cells",
        "pole_radius",
        "pole_shape_canonical",
        "ghost_rect_repr",
        "exterior_blocks_digest",
    }),
    "power_grid_reach": frozenset({
        "cert_kind",
        "facility_group",
        "facility_pose_id",
        "facility_cells",
        "pole_jump_radius",
        "pole_shape_canonical",
        "protocol_core_cell",
        "ghost_rect_repr",
        "exterior_blocks_digest",
    }),
    "density_envelope": frozenset({
        "cert_kind",
        "witness_kind",
        "window_rect",
        "group_id",
        "max_allowed_area",
        "oracle_assignment_witness",
        "ghost_rect_repr",
    }),
}


CERT_PAYLOAD_REQUIRED_FIELDS: Mapping[str, FrozenSet[str]] = {
    family: allowed_fields
    for family, allowed_fields in CERT_PAYLOAD_ALLOWED_FIELDS.items()
}


def validate_cert_payload(family: str, raw_bytes: bytes) -> Dict[str, Any]:
    """Strictly parse and envelope-check a proof-bearing cut cert payload."""

    if family not in CERT_PAYLOAD_ALLOWED_FIELDS:
        raise CertPayloadSchemaError(f"unknown cert payload family: {family!r}")
    if not isinstance(raw_bytes, bytes):
        raise CertPayloadSchemaError(
            f"cert_payload must be bytes, got {type(raw_bytes).__name__}"
        )
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CertPayloadSchemaError(f"cert_payload must be UTF-8 JSON: {exc}") from exc
    try:
        loaded = loads_strict_json(text)
    except ValueError as exc:
        raise CertPayloadSchemaError(f"cert_payload JSON decode failed: {exc}") from exc
    if not isinstance(loaded, dict):
        raise CertPayloadSchemaError(
            f"cert_payload must decode to object, got {type(loaded).__name__}"
        )

    payload = dict(loaded)
    expected_kind = CERT_PAYLOAD_CERT_KIND_BY_FAMILY[family]
    actual_kind = payload.get("cert_kind")
    if actual_kind != expected_kind:
        raise CertPayloadSchemaError(
            f"cert_kind for family {family!r} must be {expected_kind!r}, got {actual_kind!r}"
        )

    allowed = CERT_PAYLOAD_ALLOWED_FIELDS[family]
    extra_keys = frozenset(str(key) for key in payload) - allowed
    if extra_keys:
        raise CertPayloadSchemaError(
            f"cert_payload for family {family!r} has unknown field(s): {sorted(extra_keys)!r}"
        )

    required = CERT_PAYLOAD_REQUIRED_FIELDS[family]
    missing = required - frozenset(str(key) for key in payload)
    if missing:
        raise CertPayloadSchemaError(
            f"cert_payload for family {family!r} missing required field(s): {sorted(missing)!r}"
        )
    return payload
