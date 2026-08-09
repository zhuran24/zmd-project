"""Optional ASCII renderer for legacy solutions and canonical blueprints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.io.serializer import coerce_facility_pools_payload, recover_legacy_render_payload_from_blueprint

GRID_W = 70
GRID_H = 70


def render_ascii(
    solution: Mapping[str, Any],
    facility_pools: Mapping[str, Any],
    *,
    ghost_rect: Optional[Mapping[str, Any]] = None,
    grid_w: int = GRID_W,
    grid_h: int = GRID_H,
) -> str:
    pools = coerce_facility_pools_payload(facility_pools)
    canvas = [["." for _ in range(int(grid_w))] for _ in range(int(grid_h))]

    for solution_entry in solution.values():
        if not isinstance(solution_entry, Mapping):
            continue
        facility_type = str(solution_entry.get("facility_type", ""))
        pose_idx = int(solution_entry.get("pose_idx", -1))
        pool = pools.get(facility_type, ())
        if pose_idx < 0 or pose_idx >= len(pool):
            raise ValueError(f"pose_idx {pose_idx} out of range for facility_type {facility_type!r}")
        pose = pool[pose_idx]
        glyph = _facility_glyph(facility_type)
        for raw_cell in pose.get("occupied_cells", []) or []:
            cx, cy = int(raw_cell[0]), int(raw_cell[1])
            if 0 <= cx < grid_w and 0 <= cy < grid_h:
                canvas[cy][cx] = glyph

    _overlay_ghost_rect(canvas, ghost_rect)
    lines = ["".join(row) for row in reversed(canvas)]
    if isinstance(ghost_rect, Mapping):
        lines.append(
            f"ghost_rect={int(ghost_rect.get('w', 0))}x{int(ghost_rect.get('h', 0))}"
        )
    return "\n".join(lines) + "\n"


def render_from_json(
    json_path: Path,
    *,
    output_path: Optional[Path] = None,
) -> str:
    with json_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    pools = _load_candidate_pools_for_render(json_path)
    if _is_blueprint_payload(payload):
        legacy_payload = recover_legacy_render_payload_from_blueprint(
            blueprint_payload=payload,
            facility_pools=pools,
        )
    else:
        legacy_payload = {
            "placement_solution": payload.get("placement_solution", {}),
            "ghost_rect": payload.get("ghost_rect"),
        }

    rendered = render_ascii(
        legacy_payload.get("placement_solution", {}),
        pools,
        ghost_rect=legacy_payload.get("ghost_rect"),
    )
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    return rendered


def _facility_glyph(facility_type: str) -> str:
    text = str(facility_type).strip()
    if not text:
        return "?"
    return text[0].upper()


def _overlay_ghost_rect(canvas: list[list[str]], ghost_rect: Optional[Mapping[str, Any]]) -> None:
    if not isinstance(ghost_rect, Mapping):
        return
    try:
        anchor_x = int(ghost_rect.get("anchor_x", -1))
        anchor_y = int(ghost_rect.get("anchor_y", -1))
        width = int(ghost_rect.get("w", 0))
        height = int(ghost_rect.get("h", 0))
    except Exception:
        return
    if anchor_x < 0 or anchor_y < 0 or width <= 0 or height <= 0:
        return
    max_y = len(canvas)
    max_x = len(canvas[0]) if canvas else 0
    for cx in range(anchor_x, min(anchor_x + width, max_x)):
        for cy in (anchor_y, anchor_y + height - 1):
            if 0 <= cy < max_y and canvas[cy][cx] == ".":
                canvas[cy][cx] = "#"
    for cy in range(anchor_y, min(anchor_y + height, max_y)):
        for cx in (anchor_x, anchor_x + width - 1):
            if 0 <= cx < max_x and canvas[cy][cx] == ".":
                canvas[cy][cx] = "#"


def _is_blueprint_payload(payload: Mapping[str, Any]) -> bool:
    if not isinstance(payload, Mapping):
        return False
    return {"metadata", "objective_achieved", "facilities", "routing_network"}.issubset(payload.keys())


def _load_candidate_pools_for_render(json_path: Path) -> Dict[str, Sequence[Mapping[str, Any]]]:
    candidate_paths = [
        json_path.parent / "candidate_placements.json",
        json_path.parent.parent / "preprocessed" / "candidate_placements.json",
    ]
    for candidate_path in candidate_paths:
        if candidate_path.exists():
            with candidate_path.open("r", encoding="utf-8") as handle:
                return coerce_facility_pools_payload(json.load(handle))
    raise FileNotFoundError(
        "candidate_placements.json not found beside output payload or under data/preprocessed"
    )
