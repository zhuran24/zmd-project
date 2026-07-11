"""Validated, deeply immutable state projections for the Stage-B cut TCB.

``BState`` remains mutable and belongs to the untrusted generator side of the
boundary.  The sole public builder in this module validates its complete
dynamic projection, combines it with a session-scoped ``FrozenArtifactBundle``,
and only then creates a ``ValidatedStateSnapshot``.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final, TypeAlias, cast

from src.cuts.frozen_artifacts import FrozenArtifactBundle, FrozenValue

# Deliberate runtime dependency: the builder invokes ``compute_source_digest``
# to preserve the established source-identity encoding and uses exact BState /
# GroupState type checks at the trust boundary.  The import chain
# lifecycle -> cert_schema -> strict_json has been checked and does not reach
# benders/master construction or mutation code.
from src.cuts.lifecycle import (
    SOURCE_DIGEST_RUNTIME_CACHE_KEYS_BY_PATH,
    BState,
    GroupState,
    compute_source_digest,
)


Cell: TypeAlias = tuple[int, int]
PoseKey: TypeAlias = tuple[str, str]
PoseCells: TypeAlias = Mapping[PoseKey, frozenset[Cell]]

_SNAPSHOT_DIGEST_PREFIX = b"zmd.snapshot.v1:"
_BLOCKED_CELLS_DIGEST_PREFIX = b"zmd.blocked-cells.v1:"
_EXTERIOR_BLOCKS_DIGEST_PREFIX = b"zmd.exterior-blocks.v1:"
_MASTER_DOMAIN_PROJECTION_PREFIX = b"zmd.master-domain-projection.v1:"
_F1_MASTER_DOMAIN_PLACEMENT_RULES = frozenset({"left_or_bottom_boundary"})
_F6_MASTER_DOMAIN_PLACEMENT_RULES = frozenset({"left_or_bottom_boundary"})
_F6_MASTER_DOMAIN_MAX_POSE_LENGTH = 70
_MISSING_OPTIONAL_EXACT_ARTIFACT_HASH = "__MISSING_OPTIONAL_EXACT_ARTIFACT__"
# Residual hardening deliberately deferred by the owner on 2026-07-06: a
# deliberate in-process attacker can import this token, and frozen dataclass
# ``__init__`` methods can be rerun.  The Stage-B AST gate forbids production
# references to the token; runtime one-shot construction is a release-time task.
_SNAPSHOT_CONSTRUCTION_TOKEN: Final = object()


class SnapshotValidationError(ValueError):
    """Raised when an untrusted state cannot produce a complete snapshot."""


@dataclass(frozen=True, slots=True)
class GhostRect:
    """Named ghost geometry; the order is always x, y, width, height."""

    x: int
    y: int
    width: int
    height: int

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)


@dataclass(frozen=True, slots=True)
class GroupSnapshot:
    """Immutable projection of one complete ``GroupState``."""

    group_id: str
    demand: int
    pose_domain: frozenset[str]
    selected_poses: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class F1RegionInputs:
    """Static and group facts read by the F1 validator/compiler chain."""

    group_demands: Mapping[str, int]
    group_pose_domains: Mapping[str, frozenset[str]]
    pose_occupied_cells: PoseCells
    instance_to_facility_type: Mapping[str, str]
    template_placement_rules: Mapping[str, str]
    template_dimensions: Mapping[str, tuple[int, int]]


@dataclass(frozen=True, slots=True)
class F5PatternNogoodInputs:
    """Liftable state projection read by the F5 oracle re-verifier.

    This is the recursively immutable snapshot counterpart of the legacy
    ``LiftableScope``.  In particular it omits every incumbent-derived input
    (selected poses, cell ownership, ghost cells, and exterior blocks).
    """

    facility_pools: Mapping[str, FrozenValue]
    canonical_rules: Mapping[str, FrozenValue]
    instance_to_facility_type: Mapping[str, str]
    facility_templates: Mapping[str, FrozenValue]
    group_demands: Mapping[str, int]
    group_pose_domains: Mapping[str, frozenset[str]]
    artifact_hashes: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class F6HallInputs:
    """Facts read by the F6 Hall-witness validator/compiler chain."""

    group_demands: Mapping[str, int]
    group_to_facility_type: Mapping[str, str]
    template_placement_rules: Mapping[str, str]
    template_dimensions: Mapping[str, tuple[int, int]]
    ghost: GhostRect | None


@dataclass(frozen=True, slots=True)
class F7PowerInputs:
    """Facts read by the F7 power-cover validator/compiler chain."""

    ghost: GhostRect | None
    group_pose_domains: Mapping[str, frozenset[str]]
    group_to_facility_type: Mapping[str, str]
    template_needs_power: Mapping[str, bool]
    pose_occupied_cells: PoseCells
    cell_owner: Mapping[Cell, tuple[str, int]]
    pole_radius: float | None
    pole_dimensions: tuple[int, int] | None


FamilyInputs: TypeAlias = F1RegionInputs | F5PatternNogoodInputs | F6HallInputs | F7PowerInputs


@dataclass(frozen=True, slots=True)
class _CapturedState:
    """One deep-frozen capture from which every snapshot view is derived."""

    artifact_hashes: Mapping[str, str]
    ghost: GhostRect | None
    ghost_cells: frozenset[Cell]
    exterior_blocks: frozenset[Cell]
    groups: Mapping[str, GroupSnapshot]
    cell_owner: Mapping[Cell, tuple[str, int]]
    oracle_capabilities: frozenset[str]
    canonical_rules_source_present: bool
    canonical_rules: Mapping[str, FrozenValue]
    candidate_placements: Mapping[str, FrozenValue]
    facility_templates: Mapping[str, FrozenValue]
    instance_to_facility_type: Mapping[str, FrozenValue]
    commodity_demands: Mapping[str, FrozenValue]
    commodity_routes: Mapping[str, FrozenValue]


@dataclass(frozen=True, slots=True, init=False)
class ValidatedStateSnapshot:
    """Fully validated snapshot; construction is restricted to the builder."""

    source_digest: str
    artifact_hashes: Mapping[str, str]
    ghost: GhostRect | None
    blocked_cells_digest: str
    exterior_blocks_digest: str
    master_domain_projection: str
    shape_packing_hall_master_domain_projection: str
    oracle_capabilities: frozenset[str]
    canonical_rules_source_present: bool
    family_inputs: Mapping[str, FamilyInputs]
    groups: Mapping[str, GroupSnapshot]
    cell_owner: Mapping[Cell, tuple[str, int]]
    ghost_cells: frozenset[Cell]
    exterior_blocks: frozenset[Cell]
    digest: str

    def __init__(
        self,
        *,
        source_digest: str,
        artifact_hashes: Mapping[str, str],
        ghost: GhostRect | None,
        blocked_cells_digest: str,
        exterior_blocks_digest: str,
        master_domain_projection: str,
        shape_packing_hall_master_domain_projection: str,
        oracle_capabilities: frozenset[str],
        canonical_rules_source_present: bool,
        family_inputs: Mapping[str, FamilyInputs],
        groups: Mapping[str, GroupSnapshot],
        cell_owner: Mapping[Cell, tuple[str, int]],
        ghost_cells: frozenset[Cell],
        exterior_blocks: frozenset[Cell],
        digest: str,
        _construction_token: object,
    ) -> None:
        if _construction_token is not _SNAPSHOT_CONSTRUCTION_TOKEN:
            raise TypeError("ValidatedStateSnapshot is private; use build_validated_state_snapshot()")
        object.__setattr__(self, "source_digest", source_digest)
        object.__setattr__(self, "artifact_hashes", artifact_hashes)
        object.__setattr__(self, "ghost", ghost)
        object.__setattr__(self, "blocked_cells_digest", blocked_cells_digest)
        object.__setattr__(self, "exterior_blocks_digest", exterior_blocks_digest)
        object.__setattr__(
            self,
            "master_domain_projection",
            _require_sha256(
                master_domain_projection,
                path="ValidatedStateSnapshot.master_domain_projection",
            ),
        )
        object.__setattr__(
            self,
            "shape_packing_hall_master_domain_projection",
            _require_sha256(
                shape_packing_hall_master_domain_projection,
                path="ValidatedStateSnapshot.shape_packing_hall_master_domain_projection",
            ),
        )
        object.__setattr__(self, "oracle_capabilities", oracle_capabilities)
        if type(canonical_rules_source_present) is not bool:
            raise TypeError("ValidatedStateSnapshot.canonical_rules_source_present must be an exact bool")
        object.__setattr__(
            self,
            "canonical_rules_source_present",
            canonical_rules_source_present,
        )
        object.__setattr__(self, "family_inputs", family_inputs)
        object.__setattr__(self, "groups", groups)
        object.__setattr__(self, "cell_owner", cell_owner)
        object.__setattr__(self, "ghost_cells", ghost_cells)
        object.__setattr__(self, "exterior_blocks", exterior_blocks)
        object.__setattr__(self, "digest", digest)


def _is_strict_int(value: object) -> bool:
    return type(value) is int


def _require_non_empty_str(value: object, *, path: str) -> str:
    if type(value) is not str or not value:
        raise SnapshotValidationError(f"{path} must be a non-empty string")
    return value


def _require_sha256(value: object, *, path: str) -> str:
    if type(value) is not str or len(value) != 64 or value != value.lower():
        raise SnapshotValidationError(f"{path} must be a lowercase 64-hex SHA-256 digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise SnapshotValidationError(f"{path} must be a lowercase 64-hex SHA-256 digest") from exc
    return value


def _require_artifact_identity(value: object, *, path: str) -> str:
    """Validate an existing artifact identity without rewriting its contract.

    Exact-session loading represents a missing optional artifact with a stable
    sentinel.  New Stage-B digests remain full SHA-256 values, but the embedded
    legacy artifact map must preserve that already-supported identity state.
    """

    if type(value) is str and value == _MISSING_OPTIONAL_EXACT_ARTIFACT_HASH:
        return value
    return _require_sha256(value, path=path)


def _require_cell(value: object, *, path: str) -> Cell:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise SnapshotValidationError(f"{path} must be a two-coordinate cell")
    x_raw, y_raw = value
    if not _is_strict_int(x_raw) or not _is_strict_int(y_raw):
        raise SnapshotValidationError(f"{path} coordinates must be strict integers")
    return (cast(int, x_raw), cast(int, y_raw))


def _freeze_cell_set(value: object, *, path: str) -> frozenset[Cell]:
    if not isinstance(value, Set) or isinstance(value, (str, bytes)):
        raise SnapshotValidationError(f"{path} must be a set of cells")
    cells: set[Cell] = set()
    for index, raw_cell in enumerate(value):
        cell = _require_cell(raw_cell, path=f"{path}[{index}]")
        if cell in cells:
            raise SnapshotValidationError(f"{path} contains duplicate cell {cell!r}")
        cells.add(cell)
    return frozenset(cells)


def _freeze_cell_sequence(value: object, *, path: str) -> frozenset[Cell]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise SnapshotValidationError(f"{path} must be a sequence of cells")
    if not value:
        raise SnapshotValidationError(f"{path} must not be empty")
    cells: set[Cell] = set()
    for index, raw_cell in enumerate(value):
        cell = _require_cell(raw_cell, path=f"{path}[{index}]")
        if cell in cells:
            raise SnapshotValidationError(f"{path} contains duplicate cell {cell!r}")
        cells.add(cell)
    return frozenset(cells)


def _freeze_ghost(raw: object) -> GhostRect | None:
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple)):
        raise SnapshotValidationError("state.ghost_rect must be a four-integer tuple or None")
    raw_tuple = tuple(raw)
    if len(raw_tuple) != 4:
        raise SnapshotValidationError("state.ghost_rect must be a four-integer tuple or None")
    if not all(_is_strict_int(value) for value in raw_tuple):
        raise SnapshotValidationError("state.ghost_rect values must be strict integers")
    x, y, width, height = cast(tuple[int, int, int, int], raw_tuple)
    if x < 0 or y < 0:
        raise SnapshotValidationError("state.ghost_rect x/y must be non-negative")
    if width <= 0 or height <= 0:
        raise SnapshotValidationError("state.ghost_rect width/height must be positive")
    ghost = GhostRect(x=x, y=y, width=width, height=height)
    # Keep this explicit self-check: square fixtures cannot expose an axis swap.
    if ghost.as_tuple() != raw_tuple:  # pragma: no cover - structural guard
        raise SnapshotValidationError("state.ghost_rect axis-order round-trip failed")
    return ghost


def _freeze_groups(value: object) -> Mapping[str, GroupSnapshot]:
    if not isinstance(value, Mapping):
        raise SnapshotValidationError("state.groups must be a mapping")
    frozen: dict[str, GroupSnapshot] = {}
    for raw_key, group in value.items():
        group_key = _require_non_empty_str(raw_key, path="state.groups key")
        if group_key in frozen:
            raise SnapshotValidationError(f"state.groups contains duplicate key {group_key!r}")
        if type(group) is not GroupState:
            raise SnapshotValidationError(f"state.groups[{group_key!r}] must be GroupState")
        raw_group_id = group.group_id
        raw_demand = group.demand
        raw_pose_domain = group.pose_domain
        raw_selected_poses = group.selected_poses
        group_id = _require_non_empty_str(
            raw_group_id,
            path=f"state.groups[{group_key!r}].group_id",
        )
        if group_id != group_key:
            raise SnapshotValidationError(f"state.groups key {group_key!r} does not match group_id {group_id!r}")
        if not _is_strict_int(raw_demand) or raw_demand < 0:
            raise SnapshotValidationError(f"state.groups[{group_key!r}].demand must be a non-negative strict int")
        demand = raw_demand
        if not isinstance(raw_pose_domain, Set) or isinstance(
            raw_pose_domain,
            (str, bytes),
        ):
            raise SnapshotValidationError(f"state.groups[{group_key!r}].pose_domain must be a set")
        pose_domain = frozenset(
            _require_non_empty_str(
                pose_id,
                path=f"state.groups[{group_key!r}].pose_domain item",
            )
            for pose_id in raw_pose_domain
        )
        if not isinstance(raw_selected_poses, Sequence) or isinstance(
            raw_selected_poses,
            (str, bytes),
        ):
            raise SnapshotValidationError(f"state.groups[{group_key!r}].selected_poses must be a sequence")
        selected_poses = tuple(
            _require_non_empty_str(
                pose_id,
                path=f"state.groups[{group_key!r}].selected_poses[{index}]",
            )
            for index, pose_id in enumerate(raw_selected_poses)
        )
        unknown_selected = frozenset(selected_poses).difference(pose_domain)
        if unknown_selected:
            raise SnapshotValidationError(
                f"state.groups[{group_key!r}].selected_poses contains poses outside "
                f"pose_domain: {sorted(unknown_selected)!r}"
            )
        if len(selected_poses) > demand:
            raise SnapshotValidationError(f"state.groups[{group_key!r}].selected_poses exceeds demand")
        frozen[group_key] = GroupSnapshot(
            group_id=group_id,
            demand=demand,
            pose_domain=pose_domain,
            selected_poses=selected_poses,
        )
    return MappingProxyType(frozen)


def _freeze_cell_owner(
    value: object,
    *,
    groups: Mapping[str, GroupSnapshot],
) -> Mapping[Cell, tuple[str, int]]:
    if not isinstance(value, Mapping):
        raise SnapshotValidationError("state.cell_owner must be a mapping")
    frozen: dict[Cell, tuple[str, int]] = {}
    for raw_cell, raw_owner in value.items():
        cell = _require_cell(raw_cell, path="state.cell_owner key")
        if not isinstance(raw_owner, (list, tuple)) or len(raw_owner) != 2:
            raise SnapshotValidationError(f"state.cell_owner[{cell!r}] must be (group_id, slot_index)")
        group_id = _require_non_empty_str(
            raw_owner[0],
            path=f"state.cell_owner[{cell!r}].group_id",
        )
        slot_index = raw_owner[1]
        if group_id not in groups:
            raise SnapshotValidationError(f"state.cell_owner[{cell!r}] refers to unknown group {group_id!r}")
        if not _is_strict_int(slot_index) or not 0 <= slot_index < groups[group_id].demand:
            raise SnapshotValidationError(f"state.cell_owner[{cell!r}].slot_index is outside group demand")
        frozen[cell] = (group_id, cast(int, slot_index))
    return MappingProxyType(frozen)


def _freeze_artifact_hashes(
    state_hashes: object,
    bundle_hashes: Mapping[str, str],
) -> Mapping[str, str]:
    if not isinstance(state_hashes, Mapping):
        raise SnapshotValidationError("state.artifact_hashes must be a mapping")
    frozen: dict[str, str] = {}
    for raw_name, raw_digest in state_hashes.items():
        name = _require_non_empty_str(raw_name, path="state.artifact_hashes key")
        frozen[name] = _require_artifact_identity(
            raw_digest,
            path=f"state.artifact_hashes[{name!r}]",
        )
    checked_bundle_hashes: dict[str, str] = {}
    for raw_name, raw_digest in bundle_hashes.items():
        name = _require_non_empty_str(raw_name, path="bundle.artifact_hashes key")
        checked_bundle_hashes[name] = _require_artifact_identity(
            raw_digest,
            path=f"bundle.artifact_hashes[{name!r}]",
        )
    mismatched_bundle_hashes = sorted(
        name for name, digest in checked_bundle_hashes.items() if frozen.get(name) != digest
    )
    if mismatched_bundle_hashes:
        raise SnapshotValidationError(
            "bundle.artifact_hashes must be an identical subset of "
            f"state.artifact_hashes; mismatched={mismatched_bundle_hashes!r}"
        )
    return MappingProxyType(frozen)


def _freeze_oracle_capabilities(value: object) -> frozenset[str]:
    if not isinstance(value, Set) or isinstance(value, (str, bytes)):
        raise SnapshotValidationError("state.available_oracle_versions must be a set")
    return frozenset(
        _require_non_empty_str(
            capability,
            path="state.available_oracle_versions item",
        )
        for capability in value
    )


def _freeze_source_node(value: object, *, path: tuple[str, ...]) -> FrozenValue:
    """Capture one source-digest node without legacy coercions or aliases."""

    path_text = ".".join(path)
    if value is None:
        return None
    if type(value) is bool:
        return value
    if type(value) is int:
        return value
    if type(value) is float:
        number = value
        if not math.isfinite(number):
            raise SnapshotValidationError(f"{path_text} contains a non-finite float")
        return number
    if type(value) is str:
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, FrozenValue] = {}
        runtime_cache_keys = SOURCE_DIGEST_RUNTIME_CACHE_KEYS_BY_PATH.get(path, frozenset())
        for raw_key, item in value.items():
            if type(raw_key) is not str:
                raise SnapshotValidationError(f"{path_text} contains a key that is not an exact str")
            key = raw_key
            if key in runtime_cache_keys:
                continue
            if key in frozen:
                raise SnapshotValidationError(f"{path_text} contains duplicate key {key!r}")
            frozen[key] = _freeze_source_node(item, path=(*path, key))
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_source_node(item, path=(*path, f"[{index}]")) for index, item in enumerate(value))
    if isinstance(value, (set, frozenset)):
        try:
            return frozenset(_freeze_source_node(item, path=(*path, "{item}")) for item in value)
        except TypeError as exc:
            raise SnapshotValidationError(f"{path_text} contains an unfreezable set item") from exc
    raise SnapshotValidationError(
        f"{path_text} contains unsupported value type {type(value).__name__}; "
        "source identity accepts only exact JSON scalars and supported containers"
    )


def _freeze_source_mapping(value: object, *, field_name: str) -> Mapping[str, FrozenValue]:
    if value is None:
        return MappingProxyType({})
    if not isinstance(value, Mapping):
        raise SnapshotValidationError(f"state.{field_name} must be a mapping or None")
    frozen = _freeze_source_node(value, path=(field_name,))
    if not isinstance(frozen, Mapping):  # pragma: no cover - guarded above
        raise AssertionError("source mapping capture did not produce a mapping")
    return frozen


def _require_source_str_values(
    value: Mapping[str, FrozenValue],
    *,
    field_name: str,
) -> Mapping[str, FrozenValue]:
    for key, item in value.items():
        _require_non_empty_str(item, path=f"state.{field_name}[{key!r}]")
    return value


def _require_source_int_values(
    value: Mapping[str, FrozenValue],
    *,
    field_name: str,
) -> Mapping[str, FrozenValue]:
    for key, item in value.items():
        if type(item) is not int:
            raise SnapshotValidationError(f"state.{field_name}[{key!r}] must be an exact int")
    return value


def _thaw_source_node(value: FrozenValue) -> object:
    """Create builtin containers for lifecycle's established digest encoder."""

    if isinstance(value, Mapping):
        return {key: _thaw_source_node(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_thaw_source_node(item) for item in value)
    if isinstance(value, frozenset):
        return frozenset(_thaw_source_node(item) for item in value)
    return value


def _thaw_source_mapping(value: Mapping[str, FrozenValue]) -> dict[str, Any]:
    return {key: _thaw_source_node(item) for key, item in value.items()}


def _capture_state(state: BState) -> _CapturedState:
    """Read and recursively freeze each BState input exactly once."""

    # Capture every field reference before derivation.  Each mutable container
    # is then traversed once; source identity and all public projections consume
    # only the resulting immutable values, never the live BState again.
    raw_groups = state.groups
    raw_cell_owner = state.cell_owner
    raw_ghost_rect = state.ghost_rect
    raw_ghost_cells = state.ghost_cells
    raw_exterior_blocks = state.exterior_blocks
    raw_artifact_hashes = state.artifact_hashes
    raw_oracle_capabilities = state.available_oracle_versions
    raw_canonical_rules = state.canonical_rules
    raw_candidate_placements = state.candidate_placements
    raw_facility_templates = state.facility_templates
    raw_instance_mapping = state.instance_to_facility_type
    raw_commodity_demands = state.commodity_demands
    raw_commodity_routes = state.commodity_routes

    groups = _freeze_groups(raw_groups)
    return _CapturedState(
        artifact_hashes=_freeze_artifact_hashes(raw_artifact_hashes, MappingProxyType({})),
        ghost=_freeze_ghost(raw_ghost_rect),
        ghost_cells=_freeze_cell_set(raw_ghost_cells, path="state.ghost_cells"),
        exterior_blocks=_freeze_cell_set(raw_exterior_blocks, path="state.exterior_blocks"),
        groups=groups,
        cell_owner=_freeze_cell_owner(raw_cell_owner, groups=groups),
        oracle_capabilities=_freeze_oracle_capabilities(raw_oracle_capabilities),
        canonical_rules_source_present=raw_canonical_rules is not None,
        canonical_rules=_freeze_source_mapping(raw_canonical_rules, field_name="canonical_rules"),
        candidate_placements=_freeze_source_mapping(
            raw_candidate_placements,
            field_name="candidate_placements",
        ),
        facility_templates=_freeze_source_mapping(
            raw_facility_templates,
            field_name="facility_templates",
        ),
        instance_to_facility_type=_require_source_str_values(
            _freeze_source_mapping(
                raw_instance_mapping,
                field_name="mandatory_exact_instances",
            ),
            field_name="instance_to_facility_type",
        ),
        commodity_demands=_require_source_int_values(
            _freeze_source_mapping(
                raw_commodity_demands,
                field_name="generic_io_requirements",
            ),
            field_name="commodity_demands",
        ),
        commodity_routes=_freeze_source_mapping(
            raw_commodity_routes,
            field_name="commodity_routes",
        ),
    )


def _compute_captured_source_digest(captured: _CapturedState) -> str:
    source_groups = {
        group_id: GroupState(
            group_id=group.group_id,
            demand=group.demand,
            pose_domain=group.pose_domain,
            selected_poses=list(group.selected_poses),
        )
        for group_id, group in captured.groups.items()
    }
    source_state = BState(
        groups=source_groups,
        canonical_rules=_thaw_source_mapping(captured.canonical_rules),
        candidate_placements=_thaw_source_mapping(captured.candidate_placements),
        facility_templates=_thaw_source_mapping(captured.facility_templates),
        instance_to_facility_type=cast(
            dict[str, str],
            _thaw_source_mapping(captured.instance_to_facility_type),
        ),
        commodity_demands=cast(
            dict[str, int],
            _thaw_source_mapping(captured.commodity_demands),
        ),
        commodity_routes=cast(
            dict[str, dict[str, Any]],
            _thaw_source_mapping(captured.commodity_routes),
        ),
    )
    return compute_source_digest(source_state)


def _require_mapping(value: object, *, path: str) -> Mapping[str, FrozenValue]:
    if not isinstance(value, Mapping):
        raise SnapshotValidationError(f"{path} must be a mapping")
    return cast(Mapping[str, FrozenValue], value)


def _freeze_instance_mapping(
    value: Mapping[str, FrozenValue],
) -> Mapping[str, str]:
    frozen: dict[str, str] = {}
    for raw_group, raw_facility_type in value.items():
        group = _require_non_empty_str(
            raw_group,
            path="bundle.instance_to_facility_type key",
        )
        frozen[group] = _require_non_empty_str(
            raw_facility_type,
            path=f"bundle.instance_to_facility_type[{group!r}]",
        )
    return MappingProxyType(frozen)


def _freeze_template_inputs(
    value: Mapping[str, FrozenValue],
) -> tuple[
    Mapping[str, str],
    Mapping[str, tuple[int, int]],
    Mapping[str, bool],
]:
    placement_rules: dict[str, str] = {}
    dimensions: dict[str, tuple[int, int]] = {}
    needs_power: dict[str, bool] = {}
    for raw_facility_type, raw_template in value.items():
        facility_type = _require_non_empty_str(
            raw_facility_type,
            path="bundle.facility_templates key",
        )
        template = _require_mapping(
            raw_template,
            path=f"bundle.facility_templates[{facility_type!r}]",
        )
        raw_rule = template.get("placement_rule", "free")
        placement_rules[facility_type] = _require_non_empty_str(
            raw_rule,
            path=f"bundle.facility_templates[{facility_type!r}].placement_rule",
        )
        raw_dimensions = _require_mapping(
            template.get("dimensions"),
            path=f"bundle.facility_templates[{facility_type!r}].dimensions",
        )
        width = raw_dimensions.get("w")
        height = raw_dimensions.get("h")
        if not _is_strict_int(width) or not _is_strict_int(height):
            raise SnapshotValidationError(
                f"bundle.facility_templates[{facility_type!r}].dimensions must contain positive strict-int w/h"
            )
        checked_width = cast(int, width)
        checked_height = cast(int, height)
        if checked_width <= 0 or checked_height <= 0:
            raise SnapshotValidationError(
                f"bundle.facility_templates[{facility_type!r}].dimensions must contain positive strict-int w/h"
            )
        dimensions[facility_type] = (checked_width, checked_height)
        raw_needs_power = template.get("needs_power", False)
        if type(raw_needs_power) is not bool:
            raise SnapshotValidationError(f"bundle.facility_templates[{facility_type!r}].needs_power must be bool")
        needs_power[facility_type] = raw_needs_power
    return (
        MappingProxyType(placement_rules),
        MappingProxyType(dimensions),
        MappingProxyType(needs_power),
    )


def _freeze_pose_occupied_cells(
    candidate_placements: Mapping[str, FrozenValue],
) -> PoseCells:
    pools = _require_mapping(
        candidate_placements.get("facility_pools"),
        path="bundle.candidate_placements.facility_pools",
    )
    poses: dict[PoseKey, frozenset[Cell]] = {}
    for raw_facility_type, raw_pool in pools.items():
        facility_type = _require_non_empty_str(
            raw_facility_type,
            path="bundle.candidate_placements.facility_pools key",
        )
        if not isinstance(raw_pool, tuple):
            raise SnapshotValidationError(
                f"bundle.candidate_placements.facility_pools[{facility_type!r}] must be a frozen sequence"
            )
        for index, raw_pose in enumerate(raw_pool):
            pose_path = f"bundle.candidate_placements.facility_pools[{facility_type!r}][{index}]"
            pose = _require_mapping(raw_pose, path=pose_path)
            pose_id = _require_non_empty_str(
                pose.get("pose_id"),
                path=f"{pose_path}.pose_id",
            )
            pose_key = (facility_type, pose_id)
            if pose_key in poses:
                raise SnapshotValidationError(f"duplicate candidate pose key {pose_key!r}")
            poses[pose_key] = _freeze_cell_sequence(
                pose.get("occupied_cells"),
                path=f"{pose_path}.occupied_cells",
            )
    return MappingProxyType(poses)


def _freeze_pole_inputs(
    canonical_rules: Mapping[str, FrozenValue],
) -> tuple[float | None, tuple[int, int] | None]:
    raw_templates = canonical_rules.get("facility_templates")
    if raw_templates is None:
        return (None, None)
    templates = _require_mapping(
        raw_templates,
        path="bundle.canonical_rules.facility_templates",
    )
    raw_pole = templates.get("power_pole")
    if raw_pole is None:
        return (None, None)
    pole = _require_mapping(
        raw_pole,
        path="bundle.canonical_rules.facility_templates['power_pole']",
    )

    radius: float | None = None
    raw_radius = pole.get("power_coverage_radius")
    if raw_radius is not None:
        if type(raw_radius) not in (int, float):
            raise SnapshotValidationError("canonical power_pole power_coverage_radius must be finite and positive")
        numeric_radius = cast(int | float, raw_radius)
        if not math.isfinite(numeric_radius) or numeric_radius <= 0:
            raise SnapshotValidationError("canonical power_pole power_coverage_radius must be finite and positive")
        radius = float(numeric_radius)

    pole_dimensions: tuple[int, int] | None = None
    raw_dimensions = pole.get("dimensions")
    if raw_dimensions is not None:
        dimensions = _require_mapping(
            raw_dimensions,
            path="bundle.canonical_rules.facility_templates['power_pole'].dimensions",
        )
        width = dimensions.get("w")
        height = dimensions.get("h")
        if not _is_strict_int(width) or not _is_strict_int(height):
            raise SnapshotValidationError("canonical power_pole dimensions must contain positive strict-int w/h")
        checked_width = cast(int, width)
        checked_height = cast(int, height)
        if checked_width <= 0 or checked_height <= 0:
            raise SnapshotValidationError("canonical power_pole dimensions must contain positive strict-int w/h")
        pole_dimensions = (checked_width, checked_height)
    return (radius, pole_dimensions)


def _validate_group_static_bindings(
    groups: Mapping[str, GroupSnapshot],
    group_to_facility_type: Mapping[str, str],
    template_dimensions: Mapping[str, tuple[int, int]],
    pose_occupied_cells: PoseCells,
) -> None:
    for group_id, group in groups.items():
        facility_type = group_to_facility_type.get(group_id)
        if facility_type is None:
            raise SnapshotValidationError(f"group {group_id!r} has no instance_to_facility_type binding")
        if facility_type not in template_dimensions:
            raise SnapshotValidationError(f"group {group_id!r} maps to unknown facility template {facility_type!r}")
        missing_poses = sorted(
            pose_id for pose_id in group.pose_domain if (facility_type, pose_id) not in pose_occupied_cells
        )
        if missing_poses:
            raise SnapshotValidationError(
                f"group {group_id!r} pose_domain contains unregistered poses: {missing_poses!r}"
            )


def _canonical_json_bytes(value: object) -> bytes:
    try:
        rendered = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise SnapshotValidationError("snapshot digest projection is not finite canonical JSON") from exc
    return rendered.encode("utf-8")


def _validate_digest_primitive(value: object, *, path: str = "projection") -> None:
    """Enforce an injective, exact builtin-only public digest domain."""

    if value is None or type(value) in (bool, int, str):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise SnapshotValidationError(f"{path} contains a non-finite float")
        return
    if type(value) is list:
        for index, item in enumerate(cast(list[object], value)):
            _validate_digest_primitive(item, path=f"{path}[{index}]")
        return
    if type(value) is dict:
        for raw_key, item in cast(dict[object, object], value).items():
            if type(raw_key) is not str:
                raise SnapshotValidationError(f"{path} contains a key that is not an exact str")
            _validate_digest_primitive(item, path=f"{path}.{raw_key}")
        return
    raise SnapshotValidationError(
        f"{path} contains unsupported exact type {type(value).__name__}; "
        "snapshot digest accepts only dict/list/str/int/bool/null/finite-float"
    )


def snapshot_digest_v1(projection: object) -> str:
    """Hash one strict JSON primitive tree with the v1 domain separator."""

    _validate_digest_primitive(projection)
    return hashlib.sha256(_SNAPSHOT_DIGEST_PREFIX + _canonical_json_bytes(projection)).hexdigest()


def master_domain_projection_v1(
    *,
    family_subset: str,
    facility_pool_projection: object,
    mandatory_slot_rows: list[object],
    template_pose_registration_rows: list[object],
) -> str:
    """Hash the shared canonical schema for both snapshot and live-master rows.

    B2 supplies the snapshot-side row extractor; B5 will independently extract
    the same three row families from the live master and call this exact schema
    primitive.  Keeping the outer projection here prevents either side from
    inventing a second dictionary layout or domain-separation convention.
    """

    checked_family = _require_non_empty_str(
        family_subset,
        path="MasterDomainProjectionV1.family_subset",
    )
    if type(mandatory_slot_rows) is not list:
        raise SnapshotValidationError("MasterDomainProjectionV1.mandatory_slot_rows must be an exact list")
    if type(template_pose_registration_rows) is not list:
        raise SnapshotValidationError("MasterDomainProjectionV1.template_pose_registration_rows must be an exact list")
    projection = {
        "facility_pool_projection": facility_pool_projection,
        "family_subset": checked_family,
        "mandatory_slot_rows": mandatory_slot_rows,
        "schema_version": 1,
        "template_pose_registration_rows": template_pose_registration_rows,
    }
    _validate_digest_primitive(projection)
    return hashlib.sha256(_MASTER_DOMAIN_PROJECTION_PREFIX + _canonical_json_bytes(projection)).hexdigest()


def _cell_set_digest(cells: frozenset[Cell], *, prefix: bytes) -> str:
    projection = [[x, y] for x, y in sorted(cells)]
    return hashlib.sha256(prefix + _canonical_json_bytes(projection)).hexdigest()


def master_domain_facility_pool_projection_v1(value: object) -> object:
    """Canonicalize frozen snapshot or mutable live-master pool containers.

    Snapshot artifacts use mapping proxies/tuples while the live master retains
    dict/list containers.  Both representations must produce identical rows for
    the shared ``MasterDomainProjectionV1`` schema.
    """

    if value is None:
        return ["null"]
    if type(value) is bool:
        return ["bool", value]
    if type(value) is int:
        return ["int", value]
    if type(value) is float:
        if not math.isfinite(value):  # pragma: no cover - bundle construction rejects this
            raise SnapshotValidationError("master-domain projection contains a non-finite float")
        return ["float", value]
    if type(value) is str:
        return ["str", value]
    if isinstance(value, Mapping):
        captured: dict[str, object] = {}
        for raw_key, item in value.items():
            if type(raw_key) is not str:
                raise SnapshotValidationError("master-domain facility pool contains a non-string key")
            if raw_key in captured:
                raise SnapshotValidationError(f"master-domain facility pool contains duplicate key {raw_key!r}")
            captured[raw_key] = master_domain_facility_pool_projection_v1(item)
        return [
            "mapping",
            [[key, captured[key]] for key in sorted(captured)],
        ]
    if isinstance(value, (list, tuple)):
        return [
            "sequence",
            [master_domain_facility_pool_projection_v1(item) for item in value],
        ]
    if isinstance(value, (set, frozenset)):
        nodes = [master_domain_facility_pool_projection_v1(item) for item in value]
        nodes.sort(key=_canonical_json_bytes)
        return ["set", nodes]
    raise SnapshotValidationError(f"master-domain projection contains unsupported frozen type {type(value).__name__}")


def _master_domain_pose_registrations(
    facility_pools: Mapping[str, FrozenValue],
    pose_occupied_cells: PoseCells,
) -> tuple[list[object], dict[PoseKey, tuple[int, int, int]]]:
    """Mirror the F1-relevant template pose registration without importing a master."""

    registrations: list[object] = []
    pose_tuple_by_key: dict[PoseKey, tuple[int, int, int]] = {}
    for raw_facility_type, raw_pool in sorted(facility_pools.items()):
        facility_type = _require_non_empty_str(
            raw_facility_type,
            path="bundle.candidate_placements.facility_pools key",
        )
        if type(raw_pool) is not tuple:
            raise SnapshotValidationError(
                f"bundle.candidate_placements.facility_pools[{facility_type!r}] must be a frozen sequence"
            )
        prepared: list[tuple[str, int, int, tuple[str, str, str]]] = []
        for pose_index, raw_pose in enumerate(raw_pool):
            pose_path = f"bundle.candidate_placements.facility_pools[{facility_type!r}][{pose_index}]"
            pose = _require_mapping(raw_pose, path=pose_path)
            pose_id = _require_non_empty_str(
                pose.get("pose_id"),
                path=f"{pose_path}.pose_id",
            )
            raw_anchor = pose.get("anchor", MappingProxyType({}))
            anchor = _require_mapping(raw_anchor, path=f"{pose_path}.anchor")
            anchor_x = anchor.get("x", 0)
            anchor_y = anchor.get("y", 0)
            if not _is_strict_int(anchor_x) or not _is_strict_int(anchor_y):
                raise SnapshotValidationError(f"{pose_path}.anchor x/y must be exact ints")
            checked_anchor_x = cast(int, anchor_x)
            checked_anchor_y = cast(int, anchor_y)
            raw_pose_params = pose.get("pose_params", MappingProxyType({}))
            pose_params = _require_mapping(
                raw_pose_params,
                path=f"{pose_path}.pose_params",
            )
            orientation = pose_params.get("orientation", "")
            port_mode = pose_params.get("port_mode", "")
            if type(orientation) is not str or type(port_mode) is not str:
                raise SnapshotValidationError(f"{pose_path}.pose_params orientation/port_mode must be exact strings")
            occupied_cells = pose_occupied_cells.get((facility_type, pose_id))
            if occupied_cells is None:  # pragma: no cover - built from the same frozen pool
                raise SnapshotValidationError(f"{pose_path} has no frozen occupied-cell registration")
            relative_cells = tuple(sorted((x - checked_anchor_x, y - checked_anchor_y) for x, y in occupied_cells))
            if relative_cells:
                xs = tuple(x for x, _y in relative_cells)
                ys = tuple(y for _x, y in relative_cells)
                bounds_token = ":".join(
                    str(value)
                    for value in (
                        min(xs),
                        max(xs),
                        min(ys),
                        max(ys),
                    )
                )
                cell_token = ";".join(f"{x}:{y}" for x, y in relative_cells)
                footprint_key = f"footprint::{bounds_token}::{cell_token}"
            else:
                footprint_key = "footprint::missing"
            prepared.append(
                (
                    pose_id,
                    checked_anchor_x,
                    checked_anchor_y,
                    (orientation, port_mode, footprint_key),
                )
            )
        mode_tokens = sorted({item[3] for item in prepared})
        mode_id_by_token = {token: mode_id for mode_id, token in enumerate(mode_tokens)}
        serialized_poses: list[object] = []
        for pose_index, (pose_id, anchor_x, anchor_y, mode_token) in enumerate(prepared):
            mode_id = mode_id_by_token[mode_token]
            pose_tuple_by_key[(facility_type, pose_id)] = (
                anchor_x,
                anchor_y,
                mode_id,
            )
            serialized_poses.append(
                {
                    "anchor": [anchor_x, anchor_y],
                    "mode_id": mode_id,
                    "pose_id": pose_id,
                    "pose_index": pose_index,
                }
            )
        registrations.append(
            {
                "facility_type": facility_type,
                "poses": serialized_poses,
            }
        )
    return registrations, pose_tuple_by_key


def _build_f1_master_domain_projection(
    *,
    bundle: FrozenArtifactBundle,
    groups: Mapping[str, GroupSnapshot],
    group_to_facility_type: Mapping[str, str],
    template_placement_rules: Mapping[str, str],
    template_dimensions: Mapping[str, tuple[int, int]],
    pose_occupied_cells: PoseCells,
) -> str:
    raw_facility_pools = _require_mapping(
        bundle.candidate_placements.get("facility_pools"),
        path="bundle.candidate_placements.facility_pools",
    )
    relevant_group_ids = tuple(
        group_id
        for group_id in sorted(groups)
        if template_placement_rules.get(group_to_facility_type.get(group_id, "")) in _F1_MASTER_DOMAIN_PLACEMENT_RULES
    )
    relevant_facility_types = {group_to_facility_type[group_id] for group_id in relevant_group_ids}
    relevant_facility_pools = {
        facility_type: raw_facility_pools[facility_type]
        for facility_type in sorted(relevant_facility_types)
        if facility_type in raw_facility_pools
    }
    if set(relevant_facility_pools) != relevant_facility_types:
        missing = sorted(relevant_facility_types - set(relevant_facility_pools))
        raise SnapshotValidationError(f"F1 master-domain projection lacks facility pools for {missing!r}")

    registration_rows, pose_tuple_by_key = _master_domain_pose_registrations(
        relevant_facility_pools,
        pose_occupied_cells,
    )
    mandatory_slot_rows: list[object] = []
    for group_id in relevant_group_ids:
        group = groups[group_id]
        facility_type = group_to_facility_type.get(group_id)
        if facility_type is None:  # pragma: no cover - static binding gate runs first
            raise SnapshotValidationError(f"group {group_id!r} has no master-domain facility binding")
        dimensions = template_dimensions.get(facility_type)
        if dimensions is None:  # pragma: no cover - static binding gate runs first
            raise SnapshotValidationError(f"group {group_id!r} has no master-domain template dimensions")
        allowed_pose_tuples = sorted(pose_tuple_by_key[(facility_type, pose_id)] for pose_id in group.pose_domain)
        for slot_index in range(group.demand):
            mandatory_slot_rows.append(
                {
                    "allowed_pose_tuples": [list(pose_tuple) for pose_tuple in allowed_pose_tuples],
                    "candidate_pose_count": len(allowed_pose_tuples),
                    "facility_type": facility_type,
                    "group_id": group_id,
                    "slot_index": slot_index,
                    # B2 dual-review codex#2: the live master keys its literal
                    # cache on slot.key (exact_coordinate_master CoordinateSlotSpec,
                    # mandatory format "{group_id}::slot::{slot_index}"). The
                    # projection must carry the same canonical identity so a
                    # slot-key drift/alias on the master side cannot escape the
                    # B5 resolve-time comparison.
                    "slot_key": f"{group_id}::slot::{slot_index}",
                    "slot_kind": "mandatory",
                    "template_dimensions": [dimensions[0], dimensions[1]],
                }
            )
    return master_domain_projection_v1(
        family_subset="region_capacity",
        facility_pool_projection=master_domain_facility_pool_projection_v1(relevant_facility_pools),
        mandatory_slot_rows=mandatory_slot_rows,
        template_pose_registration_rows=registration_rows,
    )


def _build_f6_master_domain_projection(
    *,
    bundle: FrozenArtifactBundle,
    groups: Mapping[str, GroupSnapshot],
    group_to_facility_type: Mapping[str, str],
    template_placement_rules: Mapping[str, str],
    template_dimensions: Mapping[str, tuple[int, int]],
    pose_occupied_cells: PoseCells,
) -> str:
    """Build the F6-only snapshot side of MasterDomainProjectionV1.

    The row encoding deliberately mirrors the reviewed F1 projection while
    retaining a distinct family domain separator.  Keeping a separate stored
    digest prevents the B3 slice from changing any F1 fingerprint bytes.
    """

    raw_facility_pools = _require_mapping(
        bundle.candidate_placements.get("facility_pools"),
        path="bundle.candidate_placements.facility_pools",
    )
    relevant_group_ids_list: list[str] = []
    for group_id in sorted(groups):
        facility_type = group_to_facility_type.get(group_id, "")
        dimensions = template_dimensions.get(facility_type)
        if (
            template_placement_rules.get(facility_type) in _F6_MASTER_DOMAIN_PLACEMENT_RULES
            and dimensions is not None
            and min(dimensions) == 1
            and 2 <= max(dimensions) <= _F6_MASTER_DOMAIN_MAX_POSE_LENGTH
            and groups[group_id].demand >= 1
        ):
            relevant_group_ids_list.append(group_id)
    relevant_group_ids = tuple(relevant_group_ids_list)
    relevant_facility_types = {group_to_facility_type[group_id] for group_id in relevant_group_ids}
    relevant_facility_pools = {
        facility_type: raw_facility_pools[facility_type]
        for facility_type in sorted(relevant_facility_types)
        if facility_type in raw_facility_pools
    }
    if set(relevant_facility_pools) != relevant_facility_types:
        missing = sorted(relevant_facility_types - set(relevant_facility_pools))
        raise SnapshotValidationError(f"F6 master-domain projection lacks facility pools for {missing!r}")

    registration_rows, pose_tuple_by_key = _master_domain_pose_registrations(
        relevant_facility_pools,
        pose_occupied_cells,
    )
    mandatory_slot_rows: list[object] = []
    for group_id in relevant_group_ids:
        group = groups[group_id]
        bound_facility_type = group_to_facility_type.get(group_id)
        if bound_facility_type is None:  # pragma: no cover - static binding gate runs first
            raise SnapshotValidationError(f"group {group_id!r} has no F6 master-domain facility binding")
        dimensions = template_dimensions.get(bound_facility_type)
        if dimensions is None:  # pragma: no cover - static binding gate runs first
            raise SnapshotValidationError(f"group {group_id!r} has no F6 master-domain template dimensions")
        try:
            allowed_pose_tuples = sorted(
                pose_tuple_by_key[(bound_facility_type, pose_id)] for pose_id in group.pose_domain
            )
        except KeyError as exc:  # pragma: no cover - static binding gate runs first
            raise SnapshotValidationError(f"group {group_id!r} has an unregistered F6 pose") from exc
        for slot_index in range(group.demand):
            mandatory_slot_rows.append(
                {
                    "allowed_pose_tuples": [list(pose_tuple) for pose_tuple in allowed_pose_tuples],
                    "candidate_pose_count": len(allowed_pose_tuples),
                    "facility_type": bound_facility_type,
                    "group_id": group_id,
                    "slot_index": slot_index,
                    "slot_key": f"{group_id}::slot::{slot_index}",
                    "slot_kind": "mandatory",
                    "template_dimensions": [dimensions[0], dimensions[1]],
                }
            )
    return master_domain_projection_v1(
        family_subset="shape_packing_hall",
        facility_pool_projection=master_domain_facility_pool_projection_v1(relevant_facility_pools),
        mandatory_slot_rows=mandatory_slot_rows,
        template_pose_registration_rows=registration_rows,
    )


def _snapshot_digest_projection(
    *,
    source_digest: str,
    artifact_hashes: Mapping[str, str],
    ghost: GhostRect | None,
    blocked_cells_digest: str,
    exterior_blocks_digest: str,
    oracle_capabilities: frozenset[str],
    canonical_rules_source_present: bool,
    groups: Mapping[str, GroupSnapshot],
    cell_owner: Mapping[Cell, tuple[str, int]],
    ghost_cells: frozenset[Cell],
    exterior_blocks: frozenset[Cell],
    bundle: FrozenArtifactBundle,
) -> dict[str, object]:
    return {
        "artifact_hashes": dict(sorted(artifact_hashes.items())),
        "blocked_cells_digest": blocked_cells_digest,
        "bundle_digest": bundle.digest,
        "bundle_digest_set": dict(sorted(bundle.artifact_hashes.items())),
        "canonical_rules_source_present": canonical_rules_source_present,
        "cell_owner": [[x, y, group_id, slot] for (x, y), (group_id, slot) in sorted(cell_owner.items())],
        "exterior_blocks": [[x, y] for x, y in sorted(exterior_blocks)],
        "exterior_blocks_digest": exterior_blocks_digest,
        "ghost": None if ghost is None else list(ghost.as_tuple()),
        "ghost_cells": [[x, y] for x, y in sorted(ghost_cells)],
        "groups": {
            group_id: {
                "demand": group.demand,
                "group_id": group.group_id,
                "pose_domain": sorted(group.pose_domain),
                "selected_poses": list(group.selected_poses),
            }
            for group_id, group in sorted(groups.items())
        },
        "oracle_capabilities": sorted(oracle_capabilities),
        "schema_version": 1,
        "source_digest": source_digest,
    }


def build_validated_state_snapshot(
    state: BState,
    bundle: FrozenArtifactBundle,
) -> ValidatedStateSnapshot:
    """Build the only valid ``ValidatedStateSnapshot`` or fail closed."""

    try:
        if type(state) is not BState:
            raise SnapshotValidationError("state must be BState")
        if type(bundle) is not FrozenArtifactBundle:
            raise SnapshotValidationError("bundle must be FrozenArtifactBundle")

        captured = _capture_state(state)

        # ``BState.source_digest`` is only a caller-side note/cache.  Derive the
        # authoritative identity from the validated frozen capture so None, a
        # stale note, or a second hostile iteration cannot control it.
        try:
            computed_source_digest = _compute_captured_source_digest(captured)
        except Exception as exc:
            raise SnapshotValidationError("authoritative state source digest computation failed") from exc
        source_digest = _require_sha256(
            computed_source_digest,
            path="computed state source digest",
        )
        _require_sha256(bundle.digest, path="bundle.digest")
        artifact_hashes = _freeze_artifact_hashes(
            captured.artifact_hashes,
            bundle.artifact_hashes,
        )
        ghost = captured.ghost
        ghost_cells = captured.ghost_cells
        exterior_blocks = captured.exterior_blocks
        if ghost is None and ghost_cells:
            raise SnapshotValidationError("state.ghost_cells must be empty when state.ghost_rect is None")
        groups = captured.groups
        cell_owner = captured.cell_owner
        oracle_capabilities = captured.oracle_capabilities

        group_to_facility_type = _freeze_instance_mapping(bundle.instance_to_facility_type)
        (
            template_placement_rules,
            template_dimensions,
            template_needs_power,
        ) = _freeze_template_inputs(bundle.facility_templates)
        pose_occupied_cells = _freeze_pose_occupied_cells(bundle.candidate_placements)
        _validate_group_static_bindings(
            groups,
            group_to_facility_type,
            template_dimensions,
            pose_occupied_cells,
        )
        pole_radius, pole_dimensions = _freeze_pole_inputs(bundle.canonical_rules)

        group_demands = MappingProxyType({group_id: group.demand for group_id, group in groups.items()})
        group_pose_domains = MappingProxyType({group_id: group.pose_domain for group_id, group in groups.items()})
        facility_pools = _require_mapping(
            bundle.candidate_placements.get("facility_pools"),
            path="bundle.candidate_placements.facility_pools",
        )
        f1_inputs = F1RegionInputs(
            group_demands=group_demands,
            group_pose_domains=group_pose_domains,
            pose_occupied_cells=pose_occupied_cells,
            instance_to_facility_type=group_to_facility_type,
            template_placement_rules=template_placement_rules,
            template_dimensions=template_dimensions,
        )
        f5_inputs = F5PatternNogoodInputs(
            facility_pools=facility_pools,
            canonical_rules=bundle.canonical_rules,
            instance_to_facility_type=group_to_facility_type,
            facility_templates=bundle.facility_templates,
            group_demands=group_demands,
            group_pose_domains=group_pose_domains,
            artifact_hashes=artifact_hashes,
        )
        f6_inputs = F6HallInputs(
            group_demands=group_demands,
            group_to_facility_type=group_to_facility_type,
            template_placement_rules=template_placement_rules,
            template_dimensions=template_dimensions,
            ghost=ghost,
        )
        f7_inputs = F7PowerInputs(
            ghost=ghost,
            group_pose_domains=group_pose_domains,
            group_to_facility_type=group_to_facility_type,
            template_needs_power=template_needs_power,
            pose_occupied_cells=pose_occupied_cells,
            cell_owner=cell_owner,
            pole_radius=pole_radius,
            pole_dimensions=pole_dimensions,
        )
        family_inputs: Mapping[str, FamilyInputs] = MappingProxyType(
            {
                "pattern_nogood": f5_inputs,
                "power_hitting_set": f7_inputs,
                "region_capacity": f1_inputs,
                "shape_packing_hall": f6_inputs,
            }
        )
        master_domain_projection = _build_f1_master_domain_projection(
            bundle=bundle,
            groups=groups,
            group_to_facility_type=group_to_facility_type,
            template_placement_rules=template_placement_rules,
            template_dimensions=template_dimensions,
            pose_occupied_cells=pose_occupied_cells,
        )
        shape_packing_hall_master_domain_projection = _build_f6_master_domain_projection(
            bundle=bundle,
            groups=groups,
            group_to_facility_type=group_to_facility_type,
            template_placement_rules=template_placement_rules,
            template_dimensions=template_dimensions,
            pose_occupied_cells=pose_occupied_cells,
        )

        blocked_cells_digest = _cell_set_digest(
            ghost_cells | exterior_blocks,
            prefix=_BLOCKED_CELLS_DIGEST_PREFIX,
        )
        exterior_blocks_digest = _cell_set_digest(
            exterior_blocks,
            prefix=_EXTERIOR_BLOCKS_DIGEST_PREFIX,
        )
        digest = snapshot_digest_v1(
            _snapshot_digest_projection(
                source_digest=source_digest,
                artifact_hashes=artifact_hashes,
                ghost=ghost,
                blocked_cells_digest=blocked_cells_digest,
                exterior_blocks_digest=exterior_blocks_digest,
                oracle_capabilities=oracle_capabilities,
                canonical_rules_source_present=captured.canonical_rules_source_present,
                groups=groups,
                cell_owner=cell_owner,
                ghost_cells=ghost_cells,
                exterior_blocks=exterior_blocks,
                bundle=bundle,
            )
        )
        return ValidatedStateSnapshot(
            source_digest=source_digest,
            artifact_hashes=artifact_hashes,
            ghost=ghost,
            blocked_cells_digest=blocked_cells_digest,
            exterior_blocks_digest=exterior_blocks_digest,
            master_domain_projection=master_domain_projection,
            shape_packing_hall_master_domain_projection=shape_packing_hall_master_domain_projection,
            oracle_capabilities=oracle_capabilities,
            canonical_rules_source_present=captured.canonical_rules_source_present,
            family_inputs=family_inputs,
            groups=groups,
            cell_owner=cell_owner,
            ghost_cells=ghost_cells,
            exterior_blocks=exterior_blocks,
            digest=digest,
            _construction_token=_SNAPSHOT_CONSTRUCTION_TOKEN,
        )
    except SnapshotValidationError:
        raise
    except Exception as exc:
        raise SnapshotValidationError(f"snapshot construction failed: {exc}") from exc


__all__ = [
    "F1RegionInputs",
    "F5PatternNogoodInputs",
    "F6HallInputs",
    "F7PowerInputs",
    "GhostRect",
    "GroupSnapshot",
    "SnapshotValidationError",
    "ValidatedStateSnapshot",
    "build_validated_state_snapshot",
    "master_domain_facility_pool_projection_v1",
    "master_domain_projection_v1",
    "snapshot_digest_v1",
]
