"""数 master 各 layer 加完后的 vars + constraints 数量, 看 power_coverage 体积."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.models.master_model import (  # noqa: E402
    MasterPlacementModel,
    load_generic_io_requirements_artifact,
    load_project_data,
)
from src.search.benders_loop import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE  # noqa: E402


def build_and_count(skip_power: bool):
    project_root = Path(__file__).resolve().parents[3]
    instances, pools, rules = load_project_data(project_root, "certified_exact")
    generic = load_generic_io_requirements_artifact(project_root)
    t0 = time.perf_counter()
    core = MasterPlacementModel.build_exact_core(
        instances, pools, rules,
        skip_power_coverage=skip_power,
        generic_io_requirements=generic,
        master_search_profile=DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    )
    wall = time.perf_counter() - t0
    profile = core.build_stats.get("exact_core_packaging_profile", {})
    return {
        "skip_power": skip_power,
        "build_wall_s": wall,
        "proto_variables": int(profile.get("proto_variable_count", 0)),
        "proto_constraints": int(profile.get("proto_constraint_count", 0)),
    }


def main():
    print("=== master layer sizes ===\n")
    nopower = build_and_count(skip_power=True)
    withpower = build_and_count(skip_power=False)
    print(f"{'config':<25} {'wall (s)':>10} {'vars':>10} {'constraints':>14}")
    print(f"{'skip_power_coverage':<25} {nopower['build_wall_s']:>10.1f} {nopower['proto_variables']:>10} {nopower['proto_constraints']:>14}")
    print(f"{'full master':<25} {withpower['build_wall_s']:>10.1f} {withpower['proto_variables']:>10} {withpower['proto_constraints']:>14}")
    dv = withpower['proto_variables'] - nopower['proto_variables']
    dc = withpower['proto_constraints'] - nopower['proto_constraints']
    print()
    print(f"power_coverage 加了: +{dv} vars, +{dc} constraints")
    print(f"  vars 比例: +{100*dv/max(1,nopower['proto_variables']):.0f}%")
    print(f"  cons 比例: +{100*dc/max(1,nopower['proto_constraints']):.0f}%")


if __name__ == "__main__":
    main()
