"""Static grid heatmap renderer for placement results and blueprint artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

from src.io.serializer import coerce_facility_pools_payload, recover_legacy_render_payload_from_blueprint

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.patches as patches
    import matplotlib.pyplot as plt
    from matplotlib.colors import to_rgba

    HAS_MPL = True
except ImportError:
    HAS_MPL = False

GRID_W, GRID_H = 70, 70

TEMPLATE_COLORS = {
    "crusher": "#4A90D9",
    "smelter": "#E74C3C",
    "grinder": "#2ECC71",
    "workshop": "#9B59B6",
    "refinery": "#F39C12",
    "assembler": "#1ABC9C",
    "power_pole": "#F1C40F",
    "protocol_box": "#E67E22",
    "border_input": "#3498DB",
    "border_output": "#E91E63",
    "core": "#FF6B6B",
}
DEFAULT_COLOR = "#95A5A6"


def get_template_color(facility_type: str) -> str:
    facility_type = str(facility_type).lower()
    for key, color in TEMPLATE_COLORS.items():
        if key in facility_type:
            return color
    return DEFAULT_COLOR


def render_placement_heatmap(
    solution: Mapping[str, Any],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    ghost_rect: Optional[Mapping[str, Any]] = None,
    ghost_pos: Optional[Tuple[int, int]] = None,
    output_path: Optional[Path] = None,
    title: str = "基地布局热力图",
) -> Optional[Path]:
    if not HAS_MPL:
        print("[VIS-01] matplotlib 不可用，跳过热力图渲染")
        return None

    normalized_pools = coerce_facility_pools_payload(pools)

    fig, ax = plt.subplots(1, 1, figsize=(14, 14), facecolor="#1a1a2e")
    ax.set_facecolor("#16213e")
    grid_rgba = np.full((GRID_H, GRID_W, 4), [0.086, 0.129, 0.243, 1.0])
    cell_owner: Dict[Tuple[int, int], str] = {}

    for _instance_id, solution_entry in solution.items():
        template = str(solution_entry.get("facility_type", "unknown"))
        pose_idx = int(solution_entry.get("pose_idx", 0))
        pool = normalized_pools.get(template, [])
        if pose_idx < 0 or pose_idx >= len(pool):
            continue
        pose = pool[pose_idx]
        color = to_rgba(get_template_color(template))

        for cell in pose.get("occupied_cells", []):
            cx, cy = int(cell[0]), int(cell[1])
            if 0 <= cx < GRID_W and 0 <= cy < GRID_H:
                grid_rgba[cy, cx] = color
                cell_owner[(cx, cy)] = template

    for _instance_id, solution_entry in solution.items():
        template = str(solution_entry.get("facility_type", ""))
        if "power_pole" not in template.lower():
            continue
        pose_idx = int(solution_entry.get("pose_idx", 0))
        pool = normalized_pools.get(template, [])
        if pose_idx < 0 or pose_idx >= len(pool):
            continue
        pose = pool[pose_idx]
        for cell in pose.get("power_coverage_cells", []) or []:
            cx, cy = int(cell[0]), int(cell[1])
            if 0 <= cx < GRID_W and 0 <= cy < GRID_H and (cx, cy) not in cell_owner:
                old = grid_rgba[cy, cx]
                grid_rgba[cy, cx] = [
                    old[0] * 0.6 + 0.4 * 0.95,
                    old[1] * 0.6 + 0.4 * 0.77,
                    old[2] * 0.6 + 0.4 * 0.06,
                    1.0,
                ]

    ax.imshow(grid_rgba, origin="lower", interpolation="nearest")

    if ghost_rect and ghost_pos:
        gx, gy = ghost_pos
        ghost_w = int(ghost_rect.get("w", 0))
        ghost_h = int(ghost_rect.get("h", 0))
        rect = patches.Rectangle(
            (gx - 0.5, gy - 0.5),
            ghost_w,
            ghost_h,
            linewidth=2,
            edgecolor="#ffffff",
            facecolor="white",
            alpha=0.3,
            linestyle="--",
        )
        ax.add_patch(rect)
        ax.text(
            gx + ghost_w / 2,
            gy + ghost_h / 2,
            f"空地\n{ghost_w}x{ghost_h}",
            ha="center",
            va="center",
            color="white",
            fontsize=10,
            fontweight="bold",
        )

    arrow_map = {"N": (0, 0.4), "S": (0, -0.4), "E": (0.4, 0), "W": (-0.4, 0)}
    for _instance_id, solution_entry in solution.items():
        template = str(solution_entry.get("facility_type", ""))
        pose_idx = int(solution_entry.get("pose_idx", 0))
        pool = normalized_pools.get(template, [])
        if pose_idx < 0 or pose_idx >= len(pool):
            continue
        pose = pool[pose_idx]
        for port in pose.get("output_port_cells", []) or []:
            dx, dy = arrow_map.get(str(port.get("dir", "N")), (0, 0.4))
            ax.annotate(
                "",
                xy=(int(port["x"]) + dx, int(port["y"]) + dy),
                xytext=(int(port["x"]), int(port["y"])),
                arrowprops=dict(arrowstyle="->", color="#2ecc71", lw=1.2),
            )
        for port in pose.get("input_port_cells", []) or []:
            dx, dy = arrow_map.get(str(port.get("dir", "N")), (0, 0.4))
            ax.annotate(
                "",
                xy=(int(port["x"]) + dx, int(port["y"]) + dy),
                xytext=(int(port["x"]), int(port["y"])),
                arrowprops=dict(arrowstyle="->", color="#e74c3c", lw=1.2),
            )

    ax.set_xticks(range(0, GRID_W, 5))
    ax.set_yticks(range(0, GRID_H, 5))
    ax.grid(True, alpha=0.15, color="white", linewidth=0.3)
    ax.set_xlim(-0.5, GRID_W - 0.5)
    ax.set_ylim(-0.5, GRID_H - 0.5)
    ax.set_title(title, fontsize=16, color="white", pad=15, fontweight="bold")

    legend_items = []
    used_types = set()
    for _instance_id, solution_entry in solution.items():
        template = str(solution_entry.get("facility_type", ""))
        if template not in used_types:
            used_types.add(template)
            legend_items.append(patches.Patch(color=get_template_color(template), label=template[:20]))
    if legend_items:
        ax.legend(handles=legend_items[:12], loc="upper right", fontsize=7, framealpha=0.7, fancybox=True)

    occupied_count = len(cell_owner)
    fill_rate = occupied_count / (GRID_W * GRID_H) * 100
    stats_text = (
        f"实例: {len(solution)} | 占格: {occupied_count}/{GRID_W * GRID_H} | 填充率: {fill_rate:.1f}%"
    )
    ax.text(0.5, -0.02, stats_text, transform=ax.transAxes, ha="center", fontsize=9, color="#aaa")
    plt.tight_layout()

    if output_path is None:
        output_path = Path("data/solutions/heatmap.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(output_path), dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[VIS-01] 热力图已保存: {output_path}")
    return output_path


def render_from_json(json_path: Path, output_path: Optional[Path] = None) -> Optional[Path]:
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

    ghost_rect = legacy_payload.get("ghost_rect")
    ghost_pos = _ghost_anchor_position(ghost_rect)
    return render_placement_heatmap(
        legacy_payload.get("placement_solution", {}),
        pools,
        ghost_rect=ghost_rect,
        ghost_pos=ghost_pos,
        output_path=output_path,
    )


def _is_blueprint_payload(payload: Mapping[str, Any]) -> bool:
    if not isinstance(payload, Mapping):
        return False
    required = {"metadata", "objective_achieved", "facilities", "routing_network"}
    return required.issubset(payload.keys())


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


def _ghost_anchor_position(ghost_rect: Optional[Mapping[str, Any]]) -> Optional[Tuple[int, int]]:
    if not isinstance(ghost_rect, Mapping):
        return None
    anchor_x = ghost_rect.get("anchor_x")
    anchor_y = ghost_rect.get("anchor_y")
    if anchor_x is None or anchor_y is None:
        return None
    try:
        anchor_x = int(anchor_x)
        anchor_y = int(anchor_y)
    except Exception:
        return None
    if anchor_x < 0 or anchor_y < 0:
        return None
    return (anchor_x, anchor_y)
