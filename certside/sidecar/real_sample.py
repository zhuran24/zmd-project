"""真实冻结工件端到端样本：266 mandatory 实例 + 可选 pose_optional 储存箱.

R1（no_sinks）：不放 protocol_storage_box → required_generic_inputs 无槽 → 预期 UNSAT。
R2（with_sinks）：补 ceil(total_in/K) 个 box → 预期 SAT + witness。
placement 全用 pose_idx=0（binding 子问题不涉几何重叠谓词）。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
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
    placement = {
        str(i["instance_id"]): {"facility_type": str(i["facility_type"]), "pose_idx": 0}
        for i in mand
    }
    total_in = sum(int(v) for v in dict(gio["required_generic_inputs"]).values())
    k = 3  # preprocess_plan wireless_sink.generic_input_slots（frontend 会复核）
    n_boxes = -(-total_in // k)
    print(f"required_generic_inputs total={total_in}, boxes needed={n_boxes} (K={k})")

    fails = 0
    for sample_id, extra in (
        ("R1_real_no_sinks", {}),
        ("R2_real_with_sinks", {
            f"pose_optional::protocol_storage_box::{n}": {
                "facility_type": "protocol_storage_box", "pose_idx": 0}
            for n in range(n_boxes)
        }),
    ):
        expect = "CONFIRMED" if sample_id.startswith("R1") else "SAT"
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
            chk = check_witness(emitted["opb"], record.get("witness_values") or {})
            got = "DIVERGED_OPB_ONLY" if chk["ok"] else "SIDE_SAT_UNTRUSTED"
            record["witness_check"] = {k2: v for k2, v in chk.items() if k2 != "failed_rows"} | {
                "failed_rows_count": len(chk["failed_rows"])}
        (d / "verdict.json").write_text(json.dumps(record, indent=1, default=str), encoding="utf-8")
        ok = (expect == "CONFIRMED" and got == "CONFIRMED") or (
            expect == "SAT" and got == "DIVERGED_OPB_ONLY")
        print(f"[{'PASS' if ok else 'FAIL'}] {sample_id}: expect={expect} got={got}"
              f"{'/' + str(record.get('subcode')) if record.get('subcode') else ''} "
              f"solver={record['solver']['wall_seconds']:.1f}s"
              + (f" checker={record['checker']['wall_seconds']:.1f}s" if record.get("checker") else ""))
        fails += 0 if ok else 1
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
