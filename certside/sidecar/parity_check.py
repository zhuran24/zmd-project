"""对拍脚本：前端独立推导的 operation profiles vs 生产 OPERATION_PORT_PROFILES.

⚠ 本脚本是验证 harness、不是 sidecar 组件——它刻意 import 生产代码当 oracle
（sidecar 本体 emitter/frontend/runner/witness_checker 保持零 import src/）。
从项目根跑：python <path>/parity_check.py <project_root>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def main() -> int:
    project_root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    sys.path.insert(0, str(project_root))

    from frontend import derive_operation_profiles, load_artifact  # noqa: E402
    from src.models.binding_subproblem import load_generic_input_slots_by_operation  # noqa: E402
    from src.preprocess.operation_profiles import OPERATION_PORT_PROFILES  # noqa: E402

    rules, _ = load_artifact(project_root / "rules" / "canonical_rules.json")
    plan, _ = load_artifact(project_root / "rules" / "preprocess_plan.json")
    ours = derive_operation_profiles(rules, plan)

    prod = {
        op: {
            "facility_type": str(p.facility_type),
            "input_slot_counts": dict(p.input_slots),
            "output_slot_counts": dict(p.output_slots),
            "generic_input_slots": int(p.generic_input_slots),
            "generic_output_slots": int(p.generic_output_slots),
        }
        for op, p in OPERATION_PORT_PROFILES.items()
    }

    mismatches = []
    for op in sorted(set(ours) | set(prod)):
        if op not in ours:
            mismatches.append(f"missing in frontend: {op}")
        elif op not in prod:
            mismatches.append(f"extra in frontend: {op}")
        elif ours[op] != prod[op]:
            mismatches.append(f"DIFF {op}:\n  frontend={ours[op]}\n  prod    ={prod[op]}")

    ours_generic_input_map = {
        op: int(profile["generic_input_slots"])
        for op, profile in sorted(ours.items())
        if int(profile["generic_input_slots"]) > 0
    }
    prod_generic_input_map = load_generic_input_slots_by_operation(project_root=project_root)
    if ours_generic_input_map != prod_generic_input_map:
        mismatches.append(
            "DIFF generic_input_slots_by_operation:\n"
            f"  frontend={ours_generic_input_map}\n"
            f"  prod    ={prod_generic_input_map}"
        )

    if mismatches:
        print(f"PARITY FAIL ({len(mismatches)}):")
        for m in mismatches:
            print(" ", m)
        return 1
    print(f"PARITY OK: {len(ours)} operation profiles identical "
          f"(recipes + utilities, slot counts exact); "
          f"generic_input_slots_by_operation={ours_generic_input_map}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
