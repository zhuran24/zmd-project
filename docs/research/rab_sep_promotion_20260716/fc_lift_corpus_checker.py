"""front-clear lift 阶梯3：corpus 无 solve 结构检查（doc 04 v2 §5 阶梯3）。

输入 = A/B OFF 臂捕获的 6 张真实 master incumbent 布局（binding 全判死的
「lift 应排除」正例集）。对每张布局 × 每个范围内实例，双向核对：

    RAB filter 后域空  ⟺  (输入侧自由 front 计数 < req_in)
                        ∨ (可见输出侧自由 front 计数 < vis_out)

左侧 = 真实 binding 枚举器 + RAB filter 重建（ground truth）；
右侧 = 独立重算（pose 原始端口 + _DIR_DELTA + context 占据 + SSOT demand），
即 master lift 约束的数学语义。⟸ 方向是负控（非空 owner 必须计数达标——
只验 ⟹ 会看不见超杀方向，审查 F4b/R18）。

全部通过 ⟹ lift 约束在 prod 布局上语义正确，且这 6 张布局在 lift ON 的
master 里必然不可行（吞并判据的镜像面）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.io.strict_json import load_strict_json  # noqa: E402
from src.models.binding_subproblem import (  # noqa: E402
    PortBindingModel,
    load_generic_io_requirements,
)
from src.models.port_binding import (  # noqa: E402
    routing_free_sink_commodities_from_generic_inputs,
    routing_visible_port_demands,
    supports_exact_pose_level_binding,
)
from src.models.routing_binding_context import (  # noqa: E402
    _DIR_DELTA,
    build_routing_binding_context,
    port_front_status,
)
from src.preprocess.operation_profiles import OPERATION_PORT_PROFILES  # noqa: E402


def main() -> int:
    corpus_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        PROJECT_ROOT / ".artifacts/fc_lift_ab_20260716/arm_off/arm_off_layouts"
    )
    pools = dict(
        load_strict_json(
            PROJECT_ROOT / "data/preprocessed/candidate_placements.json"
        )["facility_pools"]
    )
    instances = load_strict_json(
        PROJECT_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    io_requirements = load_generic_io_requirements(project_root=PROJECT_ROOT)
    rfsc = routing_free_sink_commodities_from_generic_inputs(
        io_requirements["required_generic_inputs"]
    )
    op_by_instance = {
        str(inst["instance_id"]): str(inst.get("operation_type", ""))
        for inst in instances
    }

    layout_files = sorted(corpus_dir.glob("layout_*.json"))
    if not layout_files:
        print(f"NO LAYOUTS under {corpus_dir}")
        return 2

    total_checked = 0
    total_empty = 0
    mismatches: list[str] = []
    for layout_file in layout_files:
        solution = json.loads(layout_file.read_text(encoding="utf-8"))
        context = build_routing_binding_context(
            solution, pools, grid_w=70, grid_h=70
        )
        model = PortBindingModel(
            placement_solution=solution,
            facility_pools=pools,
            instances=instances,
            required_generic_outputs=io_requirements["required_generic_outputs"],
            required_generic_inputs=io_requirements["required_generic_inputs"],
            project_root=PROJECT_ROOT,
            routing_context=context,
        )
        model.build()
        empty_ids = {
            str(entry["instance_id"])
            for entry in model.extract_empty_binding_domain_instances()
        }
        layout_checked = 0
        for instance_id, sol_entry in solution.items():
            operation_type = op_by_instance.get(str(instance_id), "")
            if (
                not operation_type
                or operation_type not in OPERATION_PORT_PROFILES
                or not supports_exact_pose_level_binding(operation_type)
            ):
                continue
            req_in, vis_out = routing_visible_port_demands(operation_type, rfsc)
            if req_in <= 0 and vis_out <= 0:
                continue
            tpl = str(sol_entry["facility_type"])
            pose = pools[tpl][int(sol_entry["pose_idx"])]
            # 独立重算：每侧自由 front 计数（lift 约束的数学语义）
            # 每侧自由 front 计数。注意 pose 端口 cell 无 commodity（commodity
            # 是 pattern 级赋值）：定理右侧按「任意分配」语义对**全部**该侧
            # cell 计自由 front，RFSC/不可见槽位由 demand 侧（vis_out）吸收。
            counts = []
            for field_name in ("input_port_cells", "output_port_cells"):
                free_count = 0
                for port in pose.get(field_name, []) or []:
                    status = port_front_status(port, context, str(instance_id))
                    if status.in_grid and status.is_free:
                        free_count += 1
                counts.append(free_count)
            free_in, free_out = counts
            predicted_empty = (free_in < req_in) or (free_out < vis_out)
            actually_empty = str(instance_id) in empty_ids
            layout_checked += 1
            total_checked += 1
            if actually_empty:
                total_empty += 1
            if predicted_empty != actually_empty:
                mismatches.append(
                    f"{layout_file.name}:{instance_id} op={operation_type} "
                    f"free=({free_in},{free_out}) demand=({req_in},{vis_out}) "
                    f"predicted_empty={predicted_empty} actual={actually_empty}"
                )
        print(
            f"{layout_file.name}: checked={layout_checked} "
            f"empty={len(empty_ids & {str(k) for k in solution})} "
            f"mismatches_so_far={len(mismatches)}"
        )

    print(
        f"\nTOTAL instance-checks={total_checked} empty={total_empty} "
        f"nonempty(负控)={total_checked - total_empty}"
    )
    if mismatches:
        print(f"MISMATCH x{len(mismatches)}:")
        for line in mismatches[:20]:
            print(" ", line)
        return 1
    print("EQUIVALENCE-HOLDS-BOTH-DIRECTIONS (corpus 全量)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
