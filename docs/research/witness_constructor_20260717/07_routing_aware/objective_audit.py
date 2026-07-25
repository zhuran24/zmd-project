"""Independent body-only maximum-empty-rectangle audit.

The implementation is intentionally exhaustive.  A two-dimensional prefix sum
makes each rectangle query constant-time; all admissible rectangles are still
enumerated, so this does not share the histogram algorithm used by the strict
checker.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence


class ObjectiveAuditError(ValueError):
    """The witness objective input or claim is structurally or semantically invalid."""


@dataclass(frozen=True)
class EmptyRectangle:
    x: int
    y: int
    width: int
    height: int
    area: int
    min_side: int

    @property
    def score(self) -> tuple[int, int]:
        return self.area, self.min_side


@dataclass(frozen=True)
class ObjectiveAudit:
    computed: EmptyRectangle
    claimed: EmptyRectangle
    body_cell_count: int

    @property
    def score(self) -> tuple[int, int]:
        return self.computed.score

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": "OBJECTIVE_AUDIT_OK",
            "body_cell_count": self.body_cell_count,
            "computed": asdict(self.computed),
            "claimed": asdict(self.claimed),
        }


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ObjectiveAuditError(f"{label}: expected object")
    return value


def _sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise ObjectiveAuditError(f"{label}: expected array")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ObjectiveAuditError(f"{label}: expected non-empty string")
    return value


def _integer(value: Any, label: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ObjectiveAuditError(f"{label}: expected integer")
    if minimum is not None and value < minimum:
        raise ObjectiveAuditError(f"{label}: expected integer >= {minimum}")
    return value


def _validate_grid(width: int, height: int, minimum_side: int) -> None:
    for value, label in ((width, "width"), (height, "height"), (minimum_side, "minimum_side")):
        _integer(value, label, minimum=1)


def _validate_occupied(
    occupied: Iterable[tuple[int, int]],
    width: int,
    height: int,
) -> frozenset[tuple[int, int]]:
    result: set[tuple[int, int]] = set()
    for index, cell in enumerate(occupied):
        if not isinstance(cell, tuple) or len(cell) != 2:
            raise ObjectiveAuditError(f"occupied[{index}]: expected (x, y) tuple")
        x = _integer(cell[0], f"occupied[{index}].x")
        y = _integer(cell[1], f"occupied[{index}].y")
        if not (0 <= x < width and 0 <= y < height):
            raise ObjectiveAuditError(f"occupied[{index}]: cell {(x, y)} leaves the grid")
        result.add((x, y))
    return frozenset(result)


def _prefix_sum(width: int, height: int, occupied: frozenset[tuple[int, int]]) -> list[list[int]]:
    prefix = [[0] * (width + 1) for _ in range(height + 1)]
    for y in range(height):
        running = 0
        previous = prefix[y]
        current = prefix[y + 1]
        for x in range(width):
            running += (x, y) in occupied
            current[x + 1] = previous[x + 1] + running
    return prefix


def _rectangle_sum(prefix: list[list[int]], x: int, y: int, width: int, height: int) -> int:
    right = x + width
    top = y + height
    return prefix[top][right] - prefix[y][right] - prefix[top][x] + prefix[y][x]


def maximum_empty_rectangle(
    width: int,
    height: int,
    occupied: Iterable[tuple[int, int]],
    minimum_side: int,
) -> EmptyRectangle:
    """Exhaustively maximize ``(area, min_side)`` over body-empty rectangles.

    Remaining ties use the strict checker's deterministic representative:
    lowest y, then lowest x, then larger width, then larger height.
    """

    _validate_grid(width, height, minimum_side)
    body_cells = _validate_occupied(occupied, width, height)
    prefix = _prefix_sum(width, height, body_cells)
    best = EmptyRectangle(0, 0, 0, 0, 0, 0)
    best_key = (0, 0, 0, 0, 0, 0)

    for y in range(0, height - minimum_side + 1):
        for rect_height in range(minimum_side, height - y + 1):
            for x in range(0, width - minimum_side + 1):
                for rect_width in range(minimum_side, width - x + 1):
                    if _rectangle_sum(prefix, x, y, rect_width, rect_height):
                        continue
                    area = rect_width * rect_height
                    min_side = min(rect_width, rect_height)
                    key = (area, min_side, -y, -x, rect_width, rect_height)
                    if key > best_key:
                        best_key = key
                        best = EmptyRectangle(x, y, rect_width, rect_height, area, min_side)
    return best


def extract_body_cells(
    instance: Mapping[str, Any],
    witness: Mapping[str, Any],
) -> tuple[int, int, int, frozenset[tuple[int, int]]]:
    """Extract all mandatory and optional facility bodies from a strict witness.

    Route components and port access/front cells are intentionally never read.
    Power poles and storage boxes are optional placements, so their bodies are
    included by the same generic template/mode path as mandatory facilities.
    """

    grid = _mapping(instance.get("grid"), "instance.grid")
    width = _integer(grid.get("width"), "instance.grid.width", minimum=1)
    height = _integer(grid.get("height"), "instance.grid.height", minimum=1)
    objective = _mapping(instance.get("objective"), "instance.objective")
    minimum_side = _integer(
        objective.get("minimum_side"),
        "instance.objective.minimum_side",
        minimum=1,
    )
    if objective.get("body_cells_only") is not True:
        raise ObjectiveAuditError("instance.objective.body_cells_only must be true")

    templates = _mapping(instance.get("facility_templates"), "instance.facility_templates")
    mode_index: dict[tuple[str, str], Mapping[str, Any]] = {}
    for template_id, raw_template in templates.items():
        template = _mapping(raw_template, f"instance template {template_id}")
        for raw_mode in _sequence(template.get("modes"), f"instance template {template_id}.modes"):
            mode = _mapping(raw_mode, f"instance template {template_id}.mode")
            mode_id = _string(mode.get("id"), f"instance template {template_id}.mode.id")
            key = (template_id, mode_id)
            if key in mode_index:
                raise ObjectiveAuditError(f"duplicate mode {template_id}/{mode_id}")
            mode_index[key] = mode

    required_records = _sequence(instance.get("required_instances"), "instance.required_instances")
    required_by_id: dict[str, str] = {}
    for index, raw_record in enumerate(required_records):
        record = _mapping(raw_record, f"instance.required_instances[{index}]")
        instance_id = _string(record.get("id"), f"instance.required_instances[{index}].id")
        template_id = _string(record.get("template"), f"instance.required_instances[{index}].template")
        if instance_id in required_by_id:
            raise ObjectiveAuditError(f"duplicate required instance id {instance_id!r}")
        required_by_id[instance_id] = template_id
    repeatable = set(_sequence(instance.get("repeatable_auxiliaries"), "instance.repeatable_auxiliaries"))

    occupied: set[tuple[int, int]] = set()
    owner_by_cell: dict[tuple[int, int], str] = {}
    seen_ids: set[str] = set()
    required_seen: set[str] = set()
    for field, is_required in (("required_placements", True), ("optional_placements", False)):
        for index, raw_placement in enumerate(_sequence(witness.get(field), f"witness.{field}")):
            label = f"witness.{field}[{index}]"
            placement = _mapping(raw_placement, label)
            instance_id = _string(placement.get("instance_id"), f"{label}.instance_id")
            template_id = _string(placement.get("template"), f"{label}.template")
            mode_id = _string(placement.get("mode"), f"{label}.mode")
            if instance_id in seen_ids:
                raise ObjectiveAuditError(f"{label}: duplicate placement id {instance_id!r}")
            seen_ids.add(instance_id)
            if is_required:
                if required_by_id.get(instance_id) != template_id:
                    raise ObjectiveAuditError(f"{label}: required id/template mismatch")
                required_seen.add(instance_id)
            elif instance_id in required_by_id or template_id not in repeatable:
                raise ObjectiveAuditError(f"{label}: invalid optional instance/template")
            mode = mode_index.get((template_id, mode_id))
            if mode is None:
                raise ObjectiveAuditError(f"{label}: unknown template/mode {template_id}/{mode_id}")
            anchor = _mapping(placement.get("anchor"), f"{label}.anchor")
            anchor_x = _integer(anchor.get("x"), f"{label}.anchor.x")
            anchor_y = _integer(anchor.get("y"), f"{label}.anchor.y")
            body = _mapping(mode.get("body"), f"{label}.body")
            body_width = _integer(body.get("width"), f"{label}.body.width", minimum=1)
            body_height = _integer(body.get("height"), f"{label}.body.height", minimum=1)
            for x in range(anchor_x, anchor_x + body_width):
                for y in range(anchor_y, anchor_y + body_height):
                    if not (0 <= x < width and 0 <= y < height):
                        raise ObjectiveAuditError(f"{label}: body leaves grid at {(x, y)}")
                    if (x, y) in owner_by_cell:
                        raise ObjectiveAuditError(
                            f"{label}: body overlaps {owner_by_cell[(x, y)]!r} at {(x, y)}"
                        )
                    owner_by_cell[(x, y)] = instance_id
                    occupied.add((x, y))

    missing = sorted(set(required_by_id) - required_seen)
    if missing:
        raise ObjectiveAuditError(f"witness.required_placements: missing required ids {missing[:5]}")
    return width, height, minimum_side, frozenset(occupied)


def _claimed_rectangle(witness: Mapping[str, Any]) -> tuple[EmptyRectangle, int, int]:
    claim = _mapping(witness.get("claimed_objective"), "witness.claimed_objective")
    rectangle = _mapping(claim.get("rectangle"), "witness.claimed_objective.rectangle")
    x = _integer(rectangle.get("x"), "claimed rectangle.x")
    y = _integer(rectangle.get("y"), "claimed rectangle.y")
    width = _integer(rectangle.get("width"), "claimed rectangle.width", minimum=1)
    height = _integer(rectangle.get("height"), "claimed rectangle.height", minimum=1)
    claimed_area = _integer(claim.get("area"), "claimed area", minimum=0)
    claimed_min_side = _integer(claim.get("min_side"), "claimed min_side", minimum=0)
    return (
        EmptyRectangle(x, y, width, height, width * height, min(width, height)),
        claimed_area,
        claimed_min_side,
    )


def audit_witness_objective(
    instance: Mapping[str, Any],
    witness: Mapping[str, Any],
) -> ObjectiveAudit:
    """Recompute and fail-closed validate the witness's body-only objective claim."""

    width, height, minimum_side, occupied = extract_body_cells(instance, witness)
    computed = maximum_empty_rectangle(width, height, occupied, minimum_side)
    claimed, declared_area, declared_min_side = _claimed_rectangle(witness)
    if claimed.x < 0 or claimed.y < 0 or claimed.x + claimed.width > width or claimed.y + claimed.height > height:
        raise ObjectiveAuditError("claimed rectangle leaves the grid")
    if claimed.min_side < minimum_side:
        raise ObjectiveAuditError("claimed rectangle is inadmissibly narrow")
    if declared_area != claimed.area or declared_min_side != claimed.min_side:
        raise ObjectiveAuditError("claimed score differs from claimed rectangle dimensions")
    if any(
        (x, y) in occupied
        for x in range(claimed.x, claimed.x + claimed.width)
        for y in range(claimed.y, claimed.y + claimed.height)
    ):
        raise ObjectiveAuditError("claimed rectangle contains a facility body cell")
    if claimed.score != computed.score:
        raise ObjectiveAuditError(
            f"claimed score {claimed.score} differs from recomputed score {computed.score}"
        )
    return ObjectiveAudit(computed=computed, claimed=claimed, body_cell_count=len(occupied))
