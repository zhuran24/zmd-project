"""SAC-Hull: Separator-Aware Capacity Hull constraints for pose-bool master.

数学基础: Menger theorem + max-flow min-cut. 对任意 grid 分隔 (L, W, R), 若有
q 个 commodity 必须从 L 到 R 跨越 W, 则 routing 至少需 q 个独立 cell-layer
crossings. 现 routing model 每 cell 有 ground + elevated 2 层, 每层 AddAtMostOne,
所以每 cell 容量 = 2. 必要条件:

    sum_c cross[c, sep] <= 2 * (|W| - occupied_count(W))

其中 cross[c, sep] = 1 当且仅当 (source_L AND sink_R) OR (source_R AND sink_L)
对 commodity c 跨 sep. forced-side lower bound: source_L iff some selected
pose forces c 的 output ports 全在 L (没在 R 也没在 W ambig). ambiguous pose
不计入 lower bound, 保 sound.

此约束 sound (只在 capacity 超过时 cut), 不切真合法解.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, FrozenSet, List, Mapping, Sequence, Tuple


_DIR_DELTA: Dict[str, Tuple[int, int]] = {
    "N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0),
}


@dataclass(frozen=True)
class Separator:
    sep_id: str
    kind: str  # "axis_V" | "axis_H" | "ghost_moat_top" | ...
    wall_cells: FrozenSet[Tuple[int, int]]
    is_left_of_wall: Callable[[int, int], bool]


@dataclass(frozen=True)
class PoseCommoditySide:
    source_side: str  # "L" | "R" | "AMBIG" | "NONE"
    sink_side: str


@dataclass
class PoseVarMetadata:
    """Per pose-bool var: which pose, what operation type, ports."""
    var: Any  # cp_model.IntVar
    operation_type: str
    pose: Mapping[str, Any]


def build_static_separator_library(
    *,
    grid_w: int,
    grid_h: int,
    ghost_anchor: Tuple[int, int] | None = None,
    ghost_size: Tuple[int, int] | None = None,
    include_axis: bool = True,
    include_ghost_moat: bool = True,
    limit: int = 64,
) -> List[Separator]:
    """Build axis + ghost moat separators. limit caps total count."""
    seps: List[Separator] = []
    if include_axis:
        # axis vertical V_x: W = column x
        for x in range(1, grid_w - 1):
            wall = frozenset((x, y) for y in range(grid_h))
            seps.append(Separator(
                sep_id=f"V_{x}", kind="axis_V", wall_cells=wall,
                is_left_of_wall=lambda cx, cy, x0=x: cx < x0,
            ))
        # axis horizontal H_y
        for y in range(1, grid_h - 1):
            wall = frozenset((x, y) for x in range(grid_w))
            seps.append(Separator(
                sep_id=f"H_{y}", kind="axis_H", wall_cells=wall,
                is_left_of_wall=lambda cx, cy, y0=y: cy < y0,
            ))
    if include_ghost_moat and ghost_anchor is not None and ghost_size is not None:
        ax, ay = ghost_anchor
        gw, gh = ghost_size
        # top moat
        top_y = ay + gh
        if 0 <= top_y < grid_h:
            wall = frozenset((x, top_y) for x in range(ax, ax + gw) if 0 <= x < grid_w)
            if wall:
                seps.append(Separator(
                    sep_id=f"GM_top_{top_y}", kind="ghost_moat_top", wall_cells=wall,
                    is_left_of_wall=lambda cx, cy, y0=top_y, ax_=ax, gw_=gw: (cy > y0 and ax_ <= cx < ax_ + gw_),
                ))
        # bot moat
        bot_y = ay - 1
        if 0 <= bot_y < grid_h:
            wall = frozenset((x, bot_y) for x in range(ax, ax + gw) if 0 <= x < grid_w)
            if wall:
                seps.append(Separator(
                    sep_id=f"GM_bot_{bot_y}", kind="ghost_moat_bot", wall_cells=wall,
                    is_left_of_wall=lambda cx, cy, y0=bot_y, ax_=ax, gw_=gw: (cy < y0 and ax_ <= cx < ax_ + gw_),
                ))
        # left moat
        left_x = ax - 1
        if 0 <= left_x < grid_w:
            wall = frozenset((left_x, y) for y in range(ay, ay + gh) if 0 <= y < grid_h)
            if wall:
                seps.append(Separator(
                    sep_id=f"GM_left_{left_x}", kind="ghost_moat_left", wall_cells=wall,
                    is_left_of_wall=lambda cx, cy, x0=left_x, ay_=ay, gh_=gh: (cx < x0 and ay_ <= cy < ay_ + gh_),
                ))
        # right moat
        right_x = ax + gw
        if 0 <= right_x < grid_w:
            wall = frozenset((right_x, y) for y in range(ay, ay + gh) if 0 <= y < grid_h)
            if wall:
                seps.append(Separator(
                    sep_id=f"GM_right_{right_x}", kind="ghost_moat_right", wall_cells=wall,
                    is_left_of_wall=lambda cx, cy, x0=right_x, ay_=ay, gh_=gh: (cx > x0 and ay_ <= cy < ay_ + gh_),
                ))
    if len(seps) > limit:
        # prioritize ghost moat, then axis V (often more discriminating), then H
        priority = {
            "ghost_moat_top": 0, "ghost_moat_bot": 1,
            "ghost_moat_left": 2, "ghost_moat_right": 3,
            "axis_V": 4, "axis_H": 5,
        }
        seps.sort(key=lambda s: priority.get(s.kind, 99))
        seps = seps[:limit]
    return seps


def classify_pose_commodity_side(
    operation_type: str,
    pose: Mapping[str, Any],
    separator: Separator,
    grid_w: int,
    grid_h: int,
) -> Dict[str, PoseCommoditySide]:
    """For each commodity that this pose has (input or output), classify
    whether forced source/sink onto L, R, or AMBIG.

    Returns {commodity: PoseCommoditySide}.
    """
    from src.preprocess.operation_profiles import get_operation_port_profile
    try:
        profile = get_operation_port_profile(operation_type)
    except Exception:
        return {}
    input_commodities = set(profile.input_slots.keys()) if hasattr(profile, "input_slots") else set()
    output_commodities = set(profile.output_slots.keys()) if hasattr(profile, "output_slots") else set()

    def front_side(port: Mapping[str, Any]) -> str:
        dx, dy = _DIR_DELTA.get(str(port["dir"]), (0, 0))
        fx, fy = int(port["x"]) + dx, int(port["y"]) + dy
        if not (0 <= fx < grid_w and 0 <= fy < grid_h):
            return "OOG"
        if (fx, fy) in separator.wall_cells:
            return "W"
        return "L" if separator.is_left_of_wall(fx, fy) else "R"

    input_sides = {front_side(p) for p in pose.get("input_port_cells", []) or []}
    output_sides = {front_side(p) for p in pose.get("output_port_cells", []) or []}

    def reduce_sides(sides):
        lr = sides - {"OOG", "W"}
        if not lr:
            return "NONE"
        if lr == {"L"}:
            return "L"
        if lr == {"R"}:
            return "R"
        return "AMBIG"

    sink_side = reduce_sides(input_sides)
    source_side = reduce_sides(output_sides)

    result: Dict[str, PoseCommoditySide] = {}
    for c in input_commodities:
        result[c] = PoseCommoditySide(source_side="NONE", sink_side=sink_side)
    for c in output_commodities:
        prev = result.get(c)
        sink = prev.sink_side if prev else "NONE"
        result[c] = PoseCommoditySide(source_side=source_side, sink_side=sink)
    return result


def add_separator_capacity_hull_constraints(
    *,
    model: Any,  # cp_model.CpModel
    separators: Sequence[Separator],
    pose_var_metadata: Sequence[PoseVarMetadata],
    cell_poses: Mapping[Tuple[int, int], Sequence[Any]],
    grid_w: int,
    grid_h: int,
    max_dense_side_lits: int = 50000,
) -> Dict[str, Any]:
    """Add SAC-Hull constraints to model. Returns stats.

    For each separator s and commodity c in actual use:
      source_L[s,c] = OR(pose_vars whose pose forces source of c onto L)
      ... similar source_R, sink_L, sink_R
      cross_LR[s,c] = source_L AND sink_R
      cross_RL[s,c] = source_R AND sink_L
      cross[s,c] = cross_LR OR cross_RL

      sum_c cross[s,c] + 2 * sum_{cell in W} cell_occupied[cell] <= 2 * |W|

    cell_occupied[cell] uses cell_poses (existing AddAtMostOne enforces 0/1).
    """
    stats = {
        "separator_count": len(separators),
        "commodity_pressure_pairs": 0,
        "side_bool_vars": 0,
        "cross_bool_vars": 0,
        "capacity_constraints": 0,
        "skipped_dense_side_expr": 0,
    }

    # Pre-compute per-sep per-commodity forced-side lists
    # forced[sep_id][commodity] = {side: [vars]}
    forced: Dict[str, Dict[str, Dict[str, List[Any]]]] = {}
    for sep in separators:
        forced[sep.sep_id] = {}
    for meta in pose_var_metadata:
        if not meta.operation_type or not meta.pose:
            continue
        for sep in separators:
            classification = classify_pose_commodity_side(
                meta.operation_type, meta.pose, sep, grid_w, grid_h,
            )
            for c, sides in classification.items():
                bucket = forced[sep.sep_id].setdefault(c, {
                    "source_L": [], "source_R": [], "sink_L": [], "sink_R": [],
                })
                if sides.source_side == "L":
                    bucket["source_L"].append(meta.var)
                elif sides.source_side == "R":
                    bucket["source_R"].append(meta.var)
                if sides.sink_side == "L":
                    bucket["sink_L"].append(meta.var)
                elif sides.sink_side == "R":
                    bucket["sink_R"].append(meta.var)

    def or_aux(lits, name) -> Any | None:
        """Build aux BoolVar = OR(lits). Returns aux or None when no lits (constant 0)."""
        if not lits:
            return None
        if len(lits) > max_dense_side_lits:
            stats["skipped_dense_side_expr"] += 1
            return None
        aux = model.NewBoolVar(name)
        # forward: any lit → aux
        for lit in lits:
            model.AddImplication(lit, aux)
        # backward: aux → OR(lits)
        model.AddBoolOr(lits + [aux.Not()])
        stats["side_bool_vars"] += 1
        return aux

    for sep in separators:
        cross_vars: List[Any] = []
        for commodity, sides in forced[sep.sep_id].items():
            if not any(sides.values()):
                continue
            stats["commodity_pressure_pairs"] += 1
            source_L = or_aux(sides["source_L"], f"sL_{sep.sep_id}_{commodity}")
            source_R = or_aux(sides["source_R"], f"sR_{sep.sep_id}_{commodity}")
            sink_L = or_aux(sides["sink_L"], f"kL_{sep.sep_id}_{commodity}")
            sink_R = or_aux(sides["sink_R"], f"kR_{sep.sep_id}_{commodity}")

            # cross_LR = source_L AND sink_R
            cross_LR = None
            if source_L is not None and sink_R is not None:
                cross_LR = model.NewBoolVar(f"cLR_{sep.sep_id}_{commodity}")
                model.Add(cross_LR >= source_L + sink_R - 1)
                model.Add(cross_LR <= source_L)
                model.Add(cross_LR <= sink_R)
                stats["cross_bool_vars"] += 1
            cross_RL = None
            if source_R is not None and sink_L is not None:
                cross_RL = model.NewBoolVar(f"cRL_{sep.sep_id}_{commodity}")
                model.Add(cross_RL >= source_R + sink_L - 1)
                model.Add(cross_RL <= source_R)
                model.Add(cross_RL <= sink_L)
                stats["cross_bool_vars"] += 1

            if cross_LR is None and cross_RL is None:
                continue
            cross = model.NewBoolVar(f"c_{sep.sep_id}_{commodity}")
            terms = [v for v in (cross_LR, cross_RL) if v is not None]
            model.AddMaxEquality(cross, terms)
            cross_vars.append(cross)
            stats["cross_bool_vars"] += 1

        if not cross_vars:
            continue
        # capacity: sum(cross) + 2 * sum(cell_occupied[wall]) <= 2 * |W|
        occupied_terms: List[Any] = []
        for cell in sep.wall_cells:
            occupied_terms.extend(cell_poses.get(cell, []))
        # 注意: cell_poses[cell] 是该 cell 的所有候选 pose vars, 至多 1 个 true (cell exclusivity)
        # 所以 sum(occupied_terms over cell) = sum_{cell in W} cell_occupied[cell]. 但
        # 如果同 cell 多 pose vars, sum overcounts? No — AddAtMostOne 保证至多 1 true.
        # 所以 sum(occupied_terms) = total occupied wall cells.
        wall_size = len(sep.wall_cells)
        if occupied_terms:
            model.Add(sum(cross_vars) + 2 * sum(occupied_terms) <= 2 * wall_size)
        else:
            model.Add(sum(cross_vars) <= 2 * wall_size)
        stats["capacity_constraints"] += 1
    return stats
