"""Pure-stdlib active-front/signature b-matching for research witnesses.

The caller supplies already selected manufacturing poses and final facility/
pole occupancy.  This module computes the physical front cells that remain
usable and solves the exact per-template signature quotas with Dinic max-flow.
It deliberately permits front/front sharing: only facility and pole bodies
block an active front.  Component typing and commodity reachability remain
separate routing checks.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from itertools import combinations
from types import MappingProxyType
from typing import Iterable, Mapping, Sequence


Cell = tuple[int, int]


class ActiveSignatureMatchError(ValueError):
    """Stable fail-closed API or internal-contract error."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _nonempty_string(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise ActiveSignatureMatchError("STRING_INVALID", f"{label} must be a nonempty string")
    return value


def _nonnegative_integer(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ActiveSignatureMatchError(
            "INTEGER_INVALID",
            f"{label} must be a nonnegative exact integer",
        )
    return value


def _validate_cell(cell: object, label: str) -> Cell:
    if (
        not isinstance(cell, tuple)
        or len(cell) != 2
        or type(cell[0]) is not int
        or type(cell[1]) is not int
    ):
        raise ActiveSignatureMatchError(
            "CELL_INVALID",
            f"{label} must be a tuple of two exact integers",
        )
    return cell


def _unique_cells(cells: object, label: str) -> tuple[Cell, ...]:
    if not isinstance(cells, tuple):
        raise ActiveSignatureMatchError("FRONTS_INVALID", f"{label} must be a tuple")
    checked = tuple(_validate_cell(cell, f"{label}[{index}]") for index, cell in enumerate(cells))
    if len(set(checked)) != len(checked):
        raise ActiveSignatureMatchError("FRONTS_DUPLICATE", f"{label} contains duplicate cells")
    return checked


@dataclass(frozen=True, order=True)
class Signature:
    template: str
    inputs: int
    outputs: int

    def __post_init__(self) -> None:
        _nonempty_string(self.template, "Signature.template")
        _nonnegative_integer(self.inputs, "Signature.inputs")
        _nonnegative_integer(self.outputs, "Signature.outputs")


DEFAULT_QUOTAS: Mapping[Signature, int] = MappingProxyType(
    {
        Signature("manufacturing_3x3", 1, 1): 109,
        Signature("manufacturing_3x3", 1, 2): 6,
        Signature("manufacturing_3x3", 1, 3): 11,
        Signature("manufacturing_3x3", 2, 1): 6,
        Signature("manufacturing_5x5", 1, 1): 32,
        Signature("manufacturing_5x5", 1, 2): 17,
        Signature("manufacturing_6x4", 3, 1): 32,
        Signature("manufacturing_6x4", 4, 1): 3,
        Signature("manufacturing_6x4", 5, 1): 3,
    }
)


@dataclass(frozen=True)
class PoseFronts:
    pose_id: str
    template: str
    input_fronts: tuple[Cell, ...]
    output_fronts: tuple[Cell, ...]

    def __post_init__(self) -> None:
        _nonempty_string(self.pose_id, "PoseFronts.pose_id")
        _nonempty_string(self.template, "PoseFronts.template")
        _unique_cells(self.input_fronts, f"{self.pose_id}.input_fronts")
        _unique_cells(self.output_fronts, f"{self.pose_id}.output_fronts")


@dataclass(frozen=True)
class PoseAudit:
    pose_id: str
    template: str
    free_input_fronts: tuple[Cell, ...]
    free_output_fronts: tuple[Cell, ...]
    compatible_signatures: tuple[Signature, ...]


@dataclass(frozen=True)
class MatchedPose:
    pose_id: str
    signature: Signature
    operation: str | None
    free_input_fronts: tuple[Cell, ...]
    free_output_fronts: tuple[Cell, ...]
    active_input_fronts: tuple[Cell, ...]
    active_output_fronts: tuple[Cell, ...]


@dataclass(frozen=True)
class HallFailure:
    template: str
    signature_subset: tuple[Signature, ...]
    slot_capacity: int
    forced_pose_count: int
    deficiency: int
    minimal_witness_pose_ids: tuple[str, ...]


@dataclass(frozen=True)
class MatchResult:
    ok: bool
    pose_audits: tuple[PoseAudit, ...]
    matches: tuple[MatchedPose, ...]
    hall_failure: HallFailure | None


def _validated_occupancy(
    cells: Iterable[Cell],
    *,
    label: str,
    grid_width: int,
    grid_height: int,
) -> frozenset[Cell]:
    try:
        values = tuple(cells)
    except TypeError as exc:
        raise ActiveSignatureMatchError(
            "OCCUPANCY_INVALID",
            f"{label} must be iterable",
        ) from exc
    checked = frozenset(
        _validate_cell(cell, f"{label}[{index}]") for index, cell in enumerate(values)
    )
    outside = sorted(
        cell
        for cell in checked
        if not (0 <= cell[0] < grid_width and 0 <= cell[1] < grid_height)
    )
    if outside:
        raise ActiveSignatureMatchError(
            "OCCUPANCY_OUT_OF_GRID",
            f"{label} contains out-of-grid cells: {outside[:4]!r}",
        )
    return checked


def _validated_quotas(quotas: Mapping[Signature, int]) -> dict[Signature, int]:
    if not isinstance(quotas, Mapping):
        raise ActiveSignatureMatchError("QUOTAS_INVALID", "quotas must be a mapping")
    result: dict[Signature, int] = {}
    for signature, count in quotas.items():
        if type(signature) is not Signature:
            raise ActiveSignatureMatchError(
                "QUOTA_SIGNATURE_INVALID",
                f"quota key is not a Signature: {signature!r}",
            )
        result[signature] = _nonnegative_integer(count, f"quota[{signature!r}]")
    return result


def _validated_operation_expansion(
    operation_expansion: Mapping[Signature, Sequence[str]] | None,
    quotas: Mapping[Signature, int],
) -> dict[Signature, tuple[str, ...]] | None:
    if operation_expansion is None:
        return None
    if not isinstance(operation_expansion, Mapping):
        raise ActiveSignatureMatchError(
            "OPERATION_EXPANSION_INVALID",
            "operation_expansion must be a mapping",
        )
    unknown = set(operation_expansion) - set(quotas)
    missing = set(quotas) - set(operation_expansion)
    if unknown or missing:
        raise ActiveSignatureMatchError(
            "OPERATION_EXPANSION_KEYS",
            "operation expansion keys differ: "
            f"missing={sorted(missing, key=repr)!r}, unknown={sorted(unknown, key=repr)!r}",
        )
    result: dict[Signature, tuple[str, ...]] = {}
    for signature, count in quotas.items():
        raw = operation_expansion[signature]
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            raise ActiveSignatureMatchError(
                "OPERATION_EXPANSION_INVALID",
                f"{signature!r}: operations must be a sequence",
            )
        operations = tuple(raw)
        if len(operations) != count:
            raise ActiveSignatureMatchError(
                "OPERATION_EXPANSION_COUNT",
                f"{signature!r}: observed {len(operations)}, expected {count}",
            )
        for index, operation in enumerate(operations):
            _nonempty_string(operation, f"operation_expansion[{signature!r}][{index}]")
        result[signature] = operations
    return result


def _hall_failure(
    *,
    template: str,
    pose_ids: Sequence[str],
    compatibility: Mapping[str, frozenset[Signature]],
    signatures: Sequence[Signature],
    quotas: Mapping[Signature, int],
) -> HallFailure:
    candidates: list[tuple[int, int, tuple[Signature, ...], list[str], int]] = []
    # The empty subset diagnoses a pose with no compatible signature directly.
    for size in range(len(signatures) + 1):
        for subset_tuple in combinations(signatures, size):
            subset = frozenset(subset_tuple)
            forced = sorted(pose_id for pose_id in pose_ids if compatibility[pose_id] <= subset)
            capacity = sum(quotas[signature] for signature in subset)
            deficiency = len(forced) - capacity
            if deficiency <= 0:
                continue
            # Capacity+1 forced poses are a smallest concrete witness for this
            # subset.  Rank witnesses deterministically across all subsets.
            candidates.append(
                (capacity + 1, len(subset_tuple), tuple(subset_tuple), forced, deficiency)
            )
    if not candidates:
        raise ActiveSignatureMatchError(
            "INTERNAL_HALL_WITNESS_MISSING",
            "max-flow failed without a Hall-capacity witness",
        )
    _witness_size, _subset_size, subset, forced, deficiency = min(
        candidates,
        key=lambda item: (item[0], item[1], item[2], item[3]),
    )
    capacity = sum(quotas[signature] for signature in subset)
    return HallFailure(
        template=template,
        signature_subset=subset,
        slot_capacity=capacity,
        forced_pose_count=len(forced),
        deficiency=deficiency,
        minimal_witness_pose_ids=tuple(forced[: capacity + 1]),
    )


def _match_template(
    *,
    audits: Sequence[PoseAudit],
    signatures: Sequence[Signature],
    quotas: Mapping[Signature, int],
) -> tuple[dict[str, Signature], HallFailure | None]:
    """Run Dinic max-flow on ``source -> pose -> signature -> sink``."""

    pose_ids = [audit.pose_id for audit in audits]
    source = 0
    pose_offset = 1
    signature_offset = pose_offset + len(pose_ids)
    sink = signature_offset + len(signatures)
    node_count = sink + 1
    graph: list[list[list[int]]] = [[] for _ in range(node_count)]

    def add_edge(left: int, right: int, capacity: int) -> None:
        forward = [right, capacity, len(graph[right])]
        reverse = [left, 0, len(graph[left])]
        graph[left].append(forward)
        graph[right].append(reverse)

    for index in range(len(pose_ids)):
        add_edge(source, pose_offset + index, 1)
    signature_index = {signature: index for index, signature in enumerate(signatures)}
    for pose_index, audit in enumerate(audits):
        for signature in audit.compatible_signatures:
            add_edge(
                pose_offset + pose_index,
                signature_offset + signature_index[signature],
                1,
            )
    for index, signature in enumerate(signatures):
        add_edge(signature_offset + index, sink, quotas[signature])

    flow = 0
    while True:
        level = [-1] * node_count
        level[source] = 0
        queue = deque([source])
        while queue:
            node = queue.popleft()
            for target, capacity, _reverse in graph[node]:
                if capacity > 0 and level[target] < 0:
                    level[target] = level[node] + 1
                    queue.append(target)
        if level[sink] < 0:
            break
        cursor = [0] * node_count

        def send(node: int, amount: int) -> int:
            if node == sink:
                return amount
            while cursor[node] < len(graph[node]):
                edge = graph[node][cursor[node]]
                target, capacity, reverse_index = edge
                if capacity > 0 and level[target] == level[node] + 1:
                    pushed = send(target, min(amount, capacity))
                    if pushed:
                        edge[1] -= pushed
                        graph[target][reverse_index][1] += pushed
                        return pushed
                cursor[node] += 1
            return 0

        while (pushed := send(source, len(pose_ids) - flow)) > 0:
            flow += pushed
    if flow != len(pose_ids):
        compatibility = {
            audit.pose_id: frozenset(audit.compatible_signatures)
            for audit in audits
        }
        return {}, _hall_failure(
            template=audits[0].template,
            pose_ids=pose_ids,
            compatibility=compatibility,
            signatures=signatures,
            quotas=quotas,
        )

    assignment: dict[str, Signature] = {}
    for pose_index, pose_id in enumerate(pose_ids):
        node = pose_offset + pose_index
        for target, capacity, _reverse in graph[node]:
            if signature_offset <= target < sink and capacity == 0:
                assignment[pose_id] = signatures[target - signature_offset]
                break
        if pose_id not in assignment:
            raise ActiveSignatureMatchError(
                "INTERNAL_FLOW_EXTRACTION",
                f"matched pose {pose_id!r} has no selected residual edge",
            )
    return assignment, None


def match_active_signatures(
    poses: Sequence[PoseFronts],
    *,
    facility_body_cells: Iterable[Cell],
    pole_body_cells: Iterable[Cell],
    quotas: Mapping[Signature, int] = DEFAULT_QUOTAS,
    operation_expansion: Mapping[Signature, Sequence[str]] | None = None,
    grid_width: int = 70,
    grid_height: int = 70,
) -> MatchResult:
    """Return an exact quota assignment or a deterministic Hall witness.

    A physical front is usable exactly when it is in-grid and absent from both
    occupancy sets.  Active-front sharing is allowed; selected front tuples are
    therefore local deterministic slices, not a global cell matching.
    """

    if type(grid_width) is not int or type(grid_height) is not int or grid_width <= 0 or grid_height <= 0:
        raise ActiveSignatureMatchError(
            "GRID_INVALID",
            "grid dimensions must be positive exact integers",
        )
    if not isinstance(poses, Sequence) or isinstance(poses, (str, bytes)):
        raise ActiveSignatureMatchError("POSES_INVALID", "poses must be a sequence")
    pose_values = tuple(poses)
    if any(type(pose) is not PoseFronts for pose in pose_values):
        raise ActiveSignatureMatchError(
            "POSE_INVALID",
            "every pose must be a PoseFronts value",
        )
    pose_ids = [pose.pose_id for pose in pose_values]
    if len(set(pose_ids)) != len(pose_ids):
        raise ActiveSignatureMatchError("POSE_ID_DUPLICATE", "pose_id values must be unique")

    quota_values = _validated_quotas(quotas)
    operations_by_signature = _validated_operation_expansion(operation_expansion, quota_values)
    facility_bodies = _validated_occupancy(
        facility_body_cells,
        label="facility_body_cells",
        grid_width=grid_width,
        grid_height=grid_height,
    )
    pole_bodies = _validated_occupancy(
        pole_body_cells,
        label="pole_body_cells",
        grid_width=grid_width,
        grid_height=grid_height,
    )
    overlap = sorted(facility_bodies & pole_bodies)
    if overlap:
        raise ActiveSignatureMatchError(
            "OCCUPANCY_OVERLAP",
            f"facility and pole body occupancy overlap: {overlap[:4]!r}",
        )
    occupied = facility_bodies | pole_bodies
    pose_templates = {pose.template for pose in pose_values}
    absent_positive = sorted(
        signature
        for signature, count in quota_values.items()
        if count > 0 and signature.template not in pose_templates
    )
    if absent_positive:
        raise ActiveSignatureMatchError(
            "QUOTA_TEMPLATE_ABSENT",
            f"positive quotas name templates absent from poses: {absent_positive!r}",
        )

    signatures_by_template: dict[str, list[Signature]] = defaultdict(list)
    for signature in sorted(quota_values):
        signatures_by_template[signature.template].append(signature)
    audits: list[PoseAudit] = []
    for pose in sorted(pose_values, key=lambda item: item.pose_id):
        free_inputs = tuple(
            cell
            for cell in pose.input_fronts
            if 0 <= cell[0] < grid_width and 0 <= cell[1] < grid_height and cell not in occupied
        )
        free_outputs = tuple(
            cell
            for cell in pose.output_fronts
            if 0 <= cell[0] < grid_width and 0 <= cell[1] < grid_height and cell not in occupied
        )
        compatible = tuple(
            signature
            for signature in signatures_by_template.get(pose.template, ())
            if len(free_inputs) >= signature.inputs and len(free_outputs) >= signature.outputs
        )
        audits.append(
            PoseAudit(
                pose_id=pose.pose_id,
                template=pose.template,
                free_input_fronts=free_inputs,
                free_output_fronts=free_outputs,
                compatible_signatures=compatible,
            )
        )

    audits_by_template: dict[str, list[PoseAudit]] = defaultdict(list)
    for audit in audits:
        audits_by_template[audit.template].append(audit)
    assignment: dict[str, Signature] = {}
    for template, template_audits in sorted(audits_by_template.items()):
        signatures = tuple(signatures_by_template.get(template, ()))
        expected = sum(quota_values[signature] for signature in signatures)
        if expected != len(template_audits):
            raise ActiveSignatureMatchError(
                "TEMPLATE_QUOTA_MISMATCH",
                f"{template}: quota total {expected} differs from pose count {len(template_audits)}",
            )
        matched, failure = _match_template(
            audits=template_audits,
            signatures=signatures,
            quotas=quota_values,
        )
        if failure is not None:
            return MatchResult(False, tuple(audits), (), failure)
        assignment.update(matched)

    cursors: dict[Signature, int] = defaultdict(int)
    audit_by_id = {audit.pose_id: audit for audit in audits}
    matches: list[MatchedPose] = []
    for pose_id in sorted(assignment):
        signature = assignment[pose_id]
        audit = audit_by_id[pose_id]
        operation = None
        if operations_by_signature is not None:
            operation = operations_by_signature[signature][cursors[signature]]
            cursors[signature] += 1
        matches.append(
            MatchedPose(
                pose_id=pose_id,
                signature=signature,
                operation=operation,
                free_input_fronts=audit.free_input_fronts,
                free_output_fronts=audit.free_output_fronts,
                active_input_fronts=audit.free_input_fronts[: signature.inputs],
                active_output_fronts=audit.free_output_fronts[: signature.outputs],
            )
        )
    return MatchResult(True, tuple(audits), tuple(matches), None)


__all__ = [
    "ActiveSignatureMatchError",
    "DEFAULT_QUOTAS",
    "HallFailure",
    "MatchedPose",
    "MatchResult",
    "PoseAudit",
    "PoseFronts",
    "Signature",
    "match_active_signatures",
]
