"""
几何预处理引擎：候选摆位枚举器 (Candidate Placement Enumeration)
对应规格书：06_candidate_placement_enumeration
Status: ACCEPTED_DRAFT

目标：穷举全场所有设施模板在 70x70 棋盘上的绝对合法物理坐标，并生成离散坑位字典。
重写自旧版草案，修正以下已知缺陷：
  - pool key 与 canonical_rules.json 的 template key 对齐
  - 协议箱(protocol_storage_box) 与制造机 3×3 同款实体口(批 5 语义批,
    owner 游戏实测定谳 2026-07-18; 原 omni_wireless 零口形态已废)
  - 动态从 canonical_rules.json 读取模板定义
  - 口坐标 identity 语义: stored 坐标即口前带子格(front 错位事故批 3)
"""

import json
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

if __package__ in {None, ""}:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

from src.io.strict_json import load_strict_json

# ==========================================
# 0. 常量
# ==========================================
GRID_W = 70
GRID_H = 70
# (批 3 identity 语义后生成器不再做 front 方向步进——原 DIR_DELTA 表已删。
#  方向约定 N=+y/S=-y/E=+x/W=-x 由 get_edge_ports 的边法向算术直接承担,
#  运行时权威表在 master_model.DIR_DELTA。)

# ==========================================
# 1. 基础几何辅助函数
# ==========================================

def get_occupied_cells(x: int, y: int, w: int, h: int) -> List[List[int]]:
    """依据 02 章，计算绝对锚点下的本体地面占格投影。
    锚点为包围盒左下角 (x, y)，右上角为 (x+w-1, y+h-1)。
    """
    return [[cx, cy] for cx in range(x, x + w) for cy in range(y, y + h)]


def get_edge_ports(x: int, y: int, w: int, h: int, edge: str,
                   indices: Optional[List[int]] = None) -> List[Dict[str, Any]]:
    """依据 02 章四边局部 1D 坐标系，生成选定边缘上的合法端口坐标及向外法向量。

    Args:
        x, y: 包围盒左下角锚点
        w, h: 包围盒宽高
        edge: 'top' | 'bottom' | 'left' | 'right'
        indices: 可选，指定该边上局部 1D 索引中允许的端口位置
    """
    ports = []
    if edge == 'top':
        for i in range(w):
            if indices is None or i in indices:
                ports.append({"x": x + i, "y": y + h, "dir": "N"})
    elif edge == 'bottom':
        for i in range(w):
            if indices is None or i in indices:
                ports.append({"x": x + i, "y": y - 1, "dir": "S"})
    elif edge == 'left':
        for i in range(h):
            if indices is None or i in indices:
                ports.append({"x": x - 1, "y": y + i, "dir": "W"})
    elif edge == 'right':
        for i in range(h):
            if indices is None or i in indices:
                ports.append({"x": x + w, "y": y + i, "dir": "E"})
    return ports


def get_port_front_cell(port: Dict[str, Any]) -> Tuple[int, int]:
    """Return the routable belt cell of a physical port (identity semantics).

    front 错位事故批 3（owner 游戏实测定谳 2026-07-18，
    docs/research/front_offset_incident_20260718/00）：候选口的 stored 坐标
    **本身就是**口前带子格（本体外第 1 格）——routing/binding 全链已于批 1
    identity 化。候选期是否保留体外 stored 格取决于模板的端口启用语义；
    任何实际启用口都由 routing/binding 要求位于 70×70 网格内且未被占用。
    旧公式 `front = port + delta`（体外第 2 格）是错位语义，已连根拔除；
    "口在体外第 1 格" 的定位由 get_edge_ports 的边法向算术直接承担
    （N=+y/S=-y/E=+x/W=-x 的方向约定以 canonical/master_model.DIR_DELTA 为准）。
    """

    return int(port["x"]), int(port["y"])


def is_edge_starved(ports: List[Dict[str, Any]]) -> bool:
    """Return whether a physical side has no in-grid access cell.

    This is a sound candidate-domain filter only when the selected template and
    mode require at least one active port on the supplied side. Generic hub/box
    sides may be entirely inactive and therefore must not call this filter.
    """
    if not ports:
        return False

    return all(
        fx < 0 or fx >= GRID_W or fy < 0 or fy >= GRID_H
        for fx, fy in (get_port_front_cell(port) for port in ports)
    )


def build_placement_obj(x: int, y: int, o: int, mode: str, w: int, h: int,
                        in_ports: List, out_ports: List,
                        cov: Optional[List] = None) -> Dict[str, Any]:
    """组装规范化的候选位姿字典对象。"""
    return {
        "pose_id": f"p_x{x:02d}_y{y:02d}_o{o}_m_{mode}",
        "anchor": {"x": x, "y": y},
        "pose_params": {"orientation": o, "port_mode": mode},
        "occupied_cells": get_occupied_cells(x, y, w, h),
        "input_port_cells": in_ports,
        "output_port_cells": out_ports,
        "power_coverage_cells": cov
    }


def _require_positive_int(value: Any, field_name: str) -> int:
    """Return a positive JSON integer, rejecting bool/float drift fail-closed."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer, got {value!r}")
    return value


def _require_bool(value: Any, field_name: str) -> bool:
    """Return a JSON boolean, rejecting truthy/falsy non-bool drift fail-closed."""
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean, got {value!r}")
    return value


def _require_exact_dimensions(tpl_key: str, port_rule: str, w: int, h: int,
                              expected_w: int, expected_h: int) -> None:
    """Lock hard-coded generators to the canonical geometry they actually emit."""
    if (w, h) != (expected_w, expected_h):
        raise ValueError(
            f"{tpl_key} uses port_rule={port_rule!r}, whose generator emits "
            f"{expected_w}x{expected_h} poses; canonical dimensions are {w}x{h}"
        )


def _require_exact_rotatable(tpl_key: str, actual: bool, expected: bool, reason: str) -> None:
    """Lock canonical rotatability to the orientation family emitted by a generator."""
    if actual != expected:
        raise ValueError(
            f"{tpl_key}.rotatable is {actual!r}; {reason}; "
            f"the placement generator expects rotatable={expected!r}"
        )


def _validate_template_geometry_contract(tpl_key: str, tpl_def: Dict[str, Any]) -> Tuple[int, int, str]:
    """Validate schema-visible template geometry against generator assumptions.

    Several template families are emitted by closed-form geometry generators rather
    than by a generic rotation matrix over arbitrary dimensions.  This guard keeps
    a schema-valid canonical edit from silently desynchronizing template geometry
    and generated candidate poses.
    """
    if not isinstance(tpl_def, dict):
        raise ValueError(f"template {tpl_key!r} must be an object")

    dims = tpl_def.get("dimensions")
    if not isinstance(dims, dict):
        raise ValueError(f"{tpl_key}.dimensions must be an object")

    w = _require_positive_int(dims.get("w"), f"{tpl_key}.dimensions.w")
    h = _require_positive_int(dims.get("h"), f"{tpl_key}.dimensions.h")

    port_rule = tpl_def.get("port_rule")
    if not isinstance(port_rule, str):
        raise ValueError(f"{tpl_key}.port_rule must be a string, got {port_rule!r}")
    rotatable = _require_bool(tpl_def.get("rotatable"), f"{tpl_key}.rotatable")
    is_solid_z = _require_bool(tpl_def.get("is_solid_z"), f"{tpl_key}.is_solid_z")
    if not is_solid_z:
        raise ValueError(
            f"{tpl_key}.is_solid_z is {is_solid_z!r}; "
            "the placement generator emits solid occupied_cells for every template"
        )

    if port_rule == "long_sides":
        _require_exact_rotatable(
            tpl_key,
            rotatable,
            True,
            "long_sides generation emits both unrotated and rotated rectangular footprints",
        )
        if w <= h:
            raise ValueError(
                f"{tpl_key} uses port_rule='long_sides' but dimensions are {w}x{h}; "
                "the manufacturing generator expects the unrotated long side on top/bottom (w > h)"
            )

    elif port_rule == "opposite_parallel_sides":
        _require_exact_rotatable(
            tpl_key,
            rotatable,
            True,
            "opposite_parallel_sides generation encodes orthogonal side-pair modes",
        )
        if w != h:
            raise ValueError(
                f"{tpl_key} uses port_rule='opposite_parallel_sides' but dimensions are {w}x{h}; "
                "the square manufacturing generator requires w == h"
            )

    elif port_rule == "core_specific":
        _require_exact_rotatable(
            tpl_key,
            rotatable,
            True,
            "core_specific generation emits o=0 and o=1 port topologies",
        )
        _require_exact_dimensions(tpl_key, port_rule, w, h, 9, 9)
        core_limits = tpl_def.get("core_limits")
        if not isinstance(core_limits, dict):
            raise ValueError(f"{tpl_key}.core_limits must be present for port_rule='core_specific'")
        max_outputs = _require_positive_int(core_limits.get("max_outputs"), f"{tpl_key}.core_limits.max_outputs")
        max_inputs = _require_positive_int(core_limits.get("max_inputs"), f"{tpl_key}.core_limits.max_inputs")
        if (max_outputs, max_inputs) != (6, 14):
            raise ValueError(
                f"{tpl_key}.core_limits are {max_outputs}/{max_inputs}; "
                "the core_specific generator emits exactly 6 outputs and 14 inputs"
            )

    # (批 5: omni_wireless 分支已退役——协议箱改走 opposite_parallel_sides
    #  标准路径; 该值同步从 canonical schema enum 删除, 复活即 schema 拒绝。)
    elif port_rule == "none":
        _require_exact_rotatable(
            tpl_key,
            rotatable,
            False,
            "none/power-pole generation emits a single fixed orientation",
        )
        _require_exact_dimensions(tpl_key, port_rule, w, h, 2, 2)
        radius = _require_positive_int(tpl_def.get("power_coverage_radius"), f"{tpl_key}.power_coverage_radius")
        if radius != 5:
            raise ValueError(
                f"{tpl_key}.power_coverage_radius is {radius}; "
                "the power-pole generator emits the frozen radius-5 coverage stencil"
            )

    elif port_rule == "inward_facing":
        _require_exact_rotatable(
            tpl_key,
            rotatable,
            True,
            "inward_facing boundary generation emits vertical left-base and rotated horizontal bottom-base poses",
        )
        _require_exact_dimensions(tpl_key, port_rule, w, h, 1, 3)
        placement_rule = tpl_def.get("placement_rule")
        if placement_rule != "left_or_bottom_boundary":
            raise ValueError(
                f"{tpl_key}.placement_rule must be 'left_or_bottom_boundary' for port_rule='inward_facing', "
                f"got {placement_rule!r}"
            )

    else:
        raise ValueError(f"未知的 port_rule: {port_rule} (模板: {tpl_key})")

    return w, h, port_rule


# ==========================================
# 2. 设施模板遍历发生器 (Generators)
# ==========================================

def gen_rect_manufacturing(w_base: int, h_base: int) -> List[Dict]:
    """生成长方形设施 (如 6x4)。
    port_rule=long_sides: 端口强制分布在两条长边上。
    对于 6x4，长边=6 格，两种旋转 (o=0 横向, o=1 竖向) × 两种通流方向。

    每个 canonical 制造 operation 都要求至少一个输入和一个输出，且该
    mode 的全部输入/输出各自集中在一侧；因此必需侧整侧朝外时可安全裁剪。
    """
    placements = []

    # o=0 (横向 w_base x h_base): 长边为 top/bottom (w_base 格)
    w, h = w_base, h_base
    for x in range(GRID_W - w + 1):
        for y in range(GRID_H - h + 1):
            for in_e, out_e, mode in [('top', 'bottom', 'TB'), ('bottom', 'top', 'BT')]:
                in_p = get_edge_ports(x, y, w, h, in_e)
                out_p = get_edge_ports(x, y, w, h, out_e)
                if not is_edge_starved(in_p) and not is_edge_starved(out_p):
                    placements.append(build_placement_obj(x, y, 0, mode, w, h, in_p, out_p))

    # o=1 (竖向 h_base x w_base): 长边为 left/right (w_base 格)
    w, h = h_base, w_base
    for x in range(GRID_W - w + 1):
        for y in range(GRID_H - h + 1):
            for in_e, out_e, mode in [('right', 'left', 'RL'), ('left', 'right', 'LR')]:
                in_p = get_edge_ports(x, y, w, h, in_e)
                out_p = get_edge_ports(x, y, w, h, out_e)
                if not is_edge_starved(in_p) and not is_edge_starved(out_p):
                    placements.append(build_placement_obj(x, y, 1, mode, w, h, in_p, out_p))

    return placements


def gen_square_manufacturing(
    s: int,
    *,
    allow_inactive_oog_port_sides: bool,
) -> List[Dict]:
    """生成正方形设施 (制造机 3x3/5x5 与协议箱 3x3——批 5 起同款口形态)。
    port_rule=opposite_parallel_sides: 在每个 (x,y) 下生成四种正交端口模式。
    旋转对等性去重 (§6.5.2): 正方形 o=0 与 o=2 等价, o=1 与 o=3 等价。
    因此固定 o=0，通过 port_mode 覆盖所有物理可行域。

    ``allow_inactive_oog_port_sides=False`` 用于 manufacturing 模板：其输入
    与输出侧各至少有一个 active 口，故整侧朝外可安全裁剪。协议箱传 True：
    箱的输入和输出槽都允许 ``__unused__``，候选期不能假定任一侧已启用。
    """
    placements = []
    w, h = s, s
    for x in range(GRID_W - w + 1):
        for y in range(GRID_H - h + 1):
            modes = [
                ('top', 'bottom', 'TB'),
                ('bottom', 'top', 'BT'),
                ('right', 'left', 'RL'),
                ('left', 'right', 'LR'),
            ]
            for in_e, out_e, mode in modes:
                in_p = get_edge_ports(x, y, w, h, in_e)
                out_p = get_edge_ports(x, y, w, h, out_e)
                if allow_inactive_oog_port_sides or (
                    not is_edge_starved(in_p) and not is_edge_starved(out_p)
                ):
                    placements.append(build_placement_obj(x, y, 0, mode, w, h, in_p, out_p))
    return placements


def gen_protocol_core() -> List[Dict]:
    """生成 9x9 协议核心。
    port_rule=core_specific:
      o=0: 左右出 (局部索引 1,4,7 → 3×2=6 出口)，上下进 (局部索引 1-7 → 7×2=14 入口)
      o=1: 上下出 (局部索引 1,4,7)，左右进 (局部索引 1-7)

    核心也保留所有本体在图内的 pose。某一物理边整侧朝外不代表该边上
    有 active 口；实际启用口的可用性由 binding/routing 精确判定。
    """
    placements = []
    w, h = 9, 9
    output_indices = [1, 4, 7]
    input_indices = list(range(1, 8))

    for x in range(GRID_W - w + 1):
        for y in range(GRID_H - h + 1):

            # o=0: 左右出，上下进
            out_left = get_edge_ports(x, y, w, h, 'left', output_indices)
            out_right = get_edge_ports(x, y, w, h, 'right', output_indices)
            in_bottom = get_edge_ports(x, y, w, h, 'bottom', input_indices)
            in_top = get_edge_ports(x, y, w, h, 'top', input_indices)

            all_out_0 = out_left + out_right
            all_in_0 = in_bottom + in_top

            placements.append(build_placement_obj(
                x, y, 0, 'core_LR_out', w, h, all_in_0, all_out_0))

            # o=1: 上下出，左右进
            out_top = get_edge_ports(x, y, w, h, 'top', output_indices)
            out_bottom = get_edge_ports(x, y, w, h, 'bottom', output_indices)
            in_left = get_edge_ports(x, y, w, h, 'left', input_indices)
            in_right = get_edge_ports(x, y, w, h, 'right', input_indices)

            all_out_1 = out_top + out_bottom
            all_in_1 = in_left + in_right

            placements.append(build_placement_obj(
                x, y, 1, 'core_TB_out', w, h, all_in_1, all_out_1))

    return placements


# (批 5 语义批: 原 gen_protocol_storage_box——零口 omni_wireless 形态——已删。
#  owner 游戏实测定谳 2026-07-18(rules_audit_20260718/00 §3.1): 协议箱口形态
#  与制造机 3×3 完全同款(一边 3 进/对边 3 出/四朝向模式), "无线"仅存在于
#  箱→仓库段。canonical port_rule 已改 opposite_parallel_sides, 池经
#  gen_square_manufacturing(3, allow_inactive_oog_port_sides=True) 标准路径生成。)


def gen_power_pole() -> List[Dict]:
    """生成供电桩 (极简扫描 + 自动裁剪 12x12 越界覆盖域)。
    port_rule=none: 无端口，面壁死锁不适用。
    旋转对称：2x2 正方形，固定 o=0。
    覆盖域：以桩体中心为圆心的 12x12 方形区域，边界处自动截断至 [0, 69]。
    桩体占格 [x, x+1] × [y, y+1]，覆盖域中心约为 (x+0.5, y+0.5)，
    因此覆盖 X ∈ [x-5, x+6], Y ∈ [y-5, y+6]。
    """
    placements = []
    w, h = 2, 2
    for x in range(GRID_W - w + 1):
        for y in range(GRID_H - h + 1):
            cov = [[cx, cy]
                   for cx in range(max(0, x - 5), min(GRID_W, x + 7))
                   for cy in range(max(0, y - 5), min(GRID_H, y + 7))]
            placements.append(build_placement_obj(x, y, 0, 'omni', w, h, [], [], cov))
    return placements


def gen_boundary_ports() -> List[Dict]:
    """生成边界仓库存/取货口 (强制基线锚定法 §6.4.3)。
    port_rule=inward_facing: 端口固定朝场内方向。
    placement_rule=left_or_bottom_boundary。

    左基线: x=0, 竖向 1×3, y ∈ [0, 67)。中间格向右出向。
    下基线: y=0, 横向 3×1, x ∈ [0, 67)。中间格向上出向。
    起点从 0 开始，左下角 (0, 0) 拐角的两个 pose 均纳入候选域；
    互斥由 master 的 cell-exclusivity 下游强制，不在枚举期预删。

    注意：边界口的端口方向是"对场内供料"，因此算作 output_port_cells。
    """
    placements = []

    # 左基线: x=0, w=1, h=3, y ∈ [0, 67]
    for y in range(0, GRID_H - 3 + 1):
        # 端口在中间格 (0, y+1)，向右 (E) 供料给场内
        out_p = [{"x": 1, "y": y + 1, "dir": "E"}]
        placements.append(build_placement_obj(0, y, 0, 'left_base', 1, 3, [], out_p))

    # 下基线: y=0, w=3, h=1, x ∈ [0, 67]
    for x in range(0, GRID_W - 3 + 1):
        # 端口在中间格 (x+1, 0)，向上 (N) 供料给场内
        out_p = [{"x": x + 1, "y": 1, "dir": "N"}]
        placements.append(build_placement_obj(x, 0, 1, 'bottom_base', 3, 1, [], out_p))

    return placements


def generate_empty_rect_domain(w: int, h: int) -> List[Dict]:
    """供给外层 Python 智能打分引擎调用的动态幽灵空地候选域 (§6.7)。
    输入：外层传入的空地宽度 w 和高度 h。
    输出：纯粹的占格集合。
    """
    domains = []
    for x in range(GRID_W - w + 1):
        for y in range(GRID_H - h + 1):
            domains.append({
                "pose_id": f"rect_w{w}_h{h}_x{x:02d}_y{y:02d}",
                "anchor": {"x": x, "y": y},
                "occupied_cells": get_occupied_cells(x, y, w, h)
            })
    return domains


# ==========================================
# 3. 主控引擎
# ==========================================


@lru_cache(maxsize=1)
def _load_canonical_rules_schema() -> Dict[str, Any]:
    project_root = Path(__file__).resolve().parent.parent.parent
    return load_strict_json(project_root / "rules" / "canonical_rules.schema.json")


def load_templates(rules_path: Optional[Path] = None) -> Dict[str, Any]:
    """从 canonical_rules.json 动态加载模板定义。"""
    from jsonschema import validate as validate_json_schema

    if rules_path is None:
        project_root = Path(__file__).resolve().parent.parent.parent
        rules_path = project_root / "rules" / "canonical_rules.json"
    rules = load_strict_json(rules_path)
    validate_json_schema(instance=rules, schema=_load_canonical_rules_schema())
    return rules["facility_templates"]


def generate_all_pools(templates: Dict[str, Any]) -> Dict[str, List[Dict]]:
    """根据模板定义分派对应的枚举逻辑，生成全部模板级候选池。
    Pool key 严格使用 canonical_rules.json 中的 template key。
    """
    pools: Dict[str, List[Dict]] = {}

    for tpl_key, tpl_def in templates.items():
        w, h, port_rule = _validate_template_geometry_contract(tpl_key, tpl_def)

        if port_rule == "long_sides":
            # 长方形制造设施 (如 manufacturing_6x4)
            pools[tpl_key] = gen_rect_manufacturing(w, h)

        elif port_rule == "opposite_parallel_sides":
            assert w == h, f"opposite_parallel_sides 只适用于正方形，但 {tpl_key} 尺寸为 {w}x{h}"
            if tpl_key == "protocol_storage_box":
                pools[tpl_key] = gen_square_manufacturing(
                    w,
                    allow_inactive_oog_port_sides=True,
                )
            elif tpl_key in {"manufacturing_3x3", "manufacturing_5x5"}:
                pools[tpl_key] = gen_square_manufacturing(
                    w,
                    allow_inactive_oog_port_sides=False,
                )
            else:
                raise ValueError(
                    f"opposite_parallel_sides 模板 {tpl_key!r} 缺少明确的端口启用语义分派"
                )

        elif port_rule == "core_specific":
            # 协议核心
            pools[tpl_key] = gen_protocol_core()

        elif port_rule == "none":
            # 供电桩
            pools[tpl_key] = gen_power_pole()

        elif port_rule == "inward_facing":
            # 边界仓库口
            pools[tpl_key] = gen_boundary_ports()


    return pools


def main():
    print("🚀 [开始] 启动几何降维引擎，执行全图模板合法域枚举...")
    start_time = time.time()

    templates = load_templates()
    facility_pools = generate_all_pools(templates)

    total_placements = 0
    print("\n📊 各模板合法位姿字典规模审计：")
    for template, placements in facility_pools.items():
        count = len(placements)
        total_placements += count
        print(f"   - {template.ljust(30)}: {count:7d} 个合法解")

    elapsed = time.time() - start_time
    print(f"\n✅ [降维成功] 扫描完毕！全场共生成 {total_placements} 个纯净合法坑位，耗时 {elapsed:.2f} 秒！")

    # 落地保存
    project_root = Path(__file__).resolve().parent.parent.parent
    output_dir = project_root / "data" / "preprocessed"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "candidate_placements.json"

    # 使用紧凑格式节约 IO 体积
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"facility_pools": facility_pools}, f, separators=(',', ':'), allow_nan=False)

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"💾 [保存] 降维字典序列化完成！文件大小约 {file_size_mb:.2f} MB")
    print(f"   -> 已安全存储至 {output_path.relative_to(project_root)}")
    print("-" * 65)
    print("【几何引擎就绪】极其恐怖的无限坐标搜索空间，已被成功坍缩为离散的『座位名单』！")
    print("【下一步】即将开启 occupancy_masks 与 symmetry_breaking 构建。")


if __name__ == "__main__":
    main()
