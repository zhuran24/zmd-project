"""真实冻结工件端到端样本：mandatory 实例 + 可选 pose_optional 储存箱.

R1（core_only）：mandatory protocol_core 的 14 个实体进口承接终品 → SAT + witness。
R2（core_plus_box）：再放一个具备 3 个实体进口的箱 → SAT + witness。
placement 全用 pose_idx=0（binding 子问题不涉几何重叠谓词）。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from canonical_witness_checker import check_canonical_witness  # noqa: E402
from emitter import EmitterReject, emit  # noqa: E402
from frontend import build_model_input, load_artifact  # noqa: E402
from runner import run_sidecar_chain  # noqa: E402
from witness_checker import check_witness  # noqa: E402

WORK = Path(__file__).parent.parent / "work"


def main() -> int:
    project_root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    mand, _ = load_artifact(
        project_root / "data" / "preprocessed" / "mandatory_exact_instances.json"
    )
    gio, _ = load_artifact(
        project_root / "data" / "preprocessed" / "generic_io_requirements.json"
    )
    plan, _ = load_artifact(project_root / "rules" / "preprocess_plan.json")
    placement = {
        str(i["instance_id"]): {"facility_type": str(i["facility_type"]), "pose_idx": 0}
        for i in mand
    }
    total_in = sum(int(v) for v in dict(gio["required_generic_inputs"]).values())
    utility_operations = dict(plan.get("utility_operations") or {})
    core_k = int(dict(utility_operations.get("protocol_core") or {})["generic_input_slots"])
    box_k = int(dict(utility_operations.get("box_sink") or {})["generic_input_slots"])
    print(
        f"required_generic_inputs total={total_in}, protocol_core K={core_k}, "
        f"box_sink K={box_k}"
    )

    fails = 0
    for sample_id, extra in (
        ("R1_real_core_only", {}),
        ("R2_real_core_plus_box", {
            "pose_optional::protocol_storage_box::0": {
                "facility_type": "protocol_storage_box", "pose_idx": 0}
        }),
    ):
        expect = "SAT"
        pl = dict(placement)
        pl.update(extra)
        t0 = time.time()
        try:
            model_input = build_model_input(project_root, pl)
            emitted = emit(model_input)
        except EmitterReject as exc:
            print(f"[FAIL] {sample_id}: emitter rejected {exc.status}/{exc.subcode}: {exc.detail}")
            fails += 1
            continue
        rep = emitted["report"]
        print(f"{sample_id}: emit ok in {time.time()-t0:.1f}s — vars={rep['n_variables']} "
              f"cons={rep['n_constraints']} eq={rep['n_equalities']} "
              f"binding_inst={rep['binding_instances']} fixed={rep['fixed_choices']} "
              f"out_slots={rep['generic_output_slots']} in_slots={rep['generic_input_slots']}")
        d = WORK / sample_id
        d.mkdir(parents=True, exist_ok=True)
        opb_path = d / "instance.opb"
        opb_path.write_text(emitted["opb"], encoding="ascii", newline="\n")
        (d / "varmap.json").write_text(json.dumps(emitted["varmap"]), encoding="utf-8")
        (d / "conmap.json").write_text(json.dumps(emitted["conmap"]), encoding="utf-8")
        record = run_sidecar_chain(opb_path, d, solve_timeout_s=300, check_timeout_s=600)
        got = record["status"]
        if got == "SIDE_SAT_RAW":
            wit = record.get("witness_values") or {}
            chk = check_witness(emitted["opb"], wit)
            record["witness_check"] = {k2: v for k2, v in chk.items() if k2 != "failed_rows"} | {
                "failed_rows_count": len(chk["failed_rows"])}
            if not chk["ok"]:
                got = "SIDE_SAT_UNTRUSTED"
            else:
                cchk = check_canonical_witness(
                    model_input, emitted["varmap"], emitted["patterns"], wit
                )
                record["canonical_witness_check"] = cchk
                got = "DIVERGED_CANDIDATE" if cchk["ok"] else "SIDE_SAT_UNTRUSTED"
        (d / "verdict.json").write_text(json.dumps(record, indent=1, default=str), encoding="utf-8")
        ok = expect == "SAT" and got == "DIVERGED_CANDIDATE"
        print(f"[{'PASS' if ok else 'FAIL'}] {sample_id}: expect={expect} got={got}"
              f"{'/' + str(record.get('subcode')) if record.get('subcode') else ''} "
              f"solver={record['solver']['wall_seconds']:.1f}s"
              + (f" checker={record['checker']['wall_seconds']:.1f}s" if record.get("checker") else ""))
        fails += 0 if ok else 1
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
