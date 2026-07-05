"""binding PB sidecar — 合成样本验收 harness（设计稿 v2 §6 五件套）.

用法: python run_acceptance.py  （Windows 侧，WSL 工具链就位后）
输出: work/acceptance_report.json + 控制台摘要。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent))
from emitter import EmitterReject, emit  # noqa: E402
from runner import run_sidecar_chain  # noqa: E402
from witness_checker import check_witness  # noqa: E402

WORK = Path(__file__).parent.parent / "work"


# ---------------------------------------------------------------- fixture 积木
def profile(ft, in_counts=None, out_counts=None, gi=0, go=0):
    return {
        "facility_type": ft,
        "input_slot_counts": in_counts or {},
        "output_slot_counts": out_counts or {},
        "generic_input_slots": gi,
        "generic_output_slots": go,
    }


def cells(n, y=0, dir_="N"):
    return [{"x": i, "y": y, "dir": dir_} for i in range(n)]


def base_input() -> Dict[str, Any]:
    return {
        "schema": "binding_sidecar_model_input_v1",
        "placement_solution": {},
        "facility_pools": {},
        "instances": [],
        "required_generic_outputs": {},
        "required_generic_inputs": {},
        "wireless_sink_generic_input_slots": 0,
        "commodity_metadata": {},
        "operation_profiles": {},
    }


def with_furnace(payload, instance_id="furnace_1", in_cells=3, need_ore=2, out_cells=1, need_ingot=1):
    """exact binding 实例：C(in_cells,need_ore)*C(out_cells,need_ingot) patterns."""
    payload["operation_profiles"].setdefault(
        "smelt", profile("furnace", {"ore": need_ore}, {"ingot": need_ingot})
    )
    payload["facility_pools"].setdefault("furnace", []).append(
        {"pose_id": f"fp{len(payload['facility_pools'].get('furnace', []))}",
         "input_port_cells": cells(in_cells), "output_port_cells": cells(out_cells, y=9)}
    )
    pose_idx = len(payload["facility_pools"]["furnace"]) - 1
    payload["placement_solution"][instance_id] = {"facility_type": "furnace", "pose_idx": pose_idx}
    payload["instances"].append(
        {"instance_id": instance_id, "facility_type": "furnace", "operation_type": "smelt"}
    )
    return payload


def with_dock(payload, instance_id="dock_1", out_cells=2):
    """generic output provider（boundary_io）."""
    payload["operation_profiles"].setdefault("boundary_io", profile("dock"))
    payload["facility_pools"].setdefault("dock", []).append(
        {"pose_id": f"dp{len(payload['facility_pools'].get('dock', []))}",
         "input_port_cells": [], "output_port_cells": cells(out_cells, y=5)}
    )
    pose_idx = len(payload["facility_pools"]["dock"]) - 1
    payload["placement_solution"][instance_id] = {"facility_type": "dock", "pose_idx": pose_idx}
    payload["instances"].append(
        {"instance_id": instance_id, "facility_type": "dock", "operation_type": "boundary_io"}
    )
    return payload


def with_sink(payload, instance_id="box_1", k=3, synthesize=False):
    """generic input receiver（wireless_sink）。synthesize=True 时不进 instances（走 pose_optional 合成）."""
    payload["operation_profiles"].setdefault(
        "wireless_sink", profile("protocol_storage_box", gi=k)
    )
    payload["facility_pools"].setdefault("protocol_storage_box", []).append(
        {"pose_id": "bp0", "input_port_cells": [], "output_port_cells": []}
    )
    pose_idx = len(payload["facility_pools"]["protocol_storage_box"]) - 1
    payload["placement_solution"][instance_id] = {
        "facility_type": "protocol_storage_box", "pose_idx": pose_idx
    }
    if not synthesize:
        payload["instances"].append(
            {"instance_id": instance_id, "facility_type": "protocol_storage_box",
             "operation_type": "wireless_sink"}
        )
    payload["wireless_sink_generic_input_slots"] = k
    return payload


def out_commodity(payload, c):
    payload["commodity_metadata"][c] = {"source_kind": "external_boundary"}
    return payload


def in_commodity(payload, c, required):
    payload["commodity_metadata"][c] = {"sink_kind": "generic_input"}
    payload["required_generic_inputs"][c] = required
    return payload


# ---------------------------------------------------------------- 样本清单
def build_samples() -> List[Dict[str, Any]]:
    samples: List[Dict[str, Any]] = []

    # --- UNSAT 组（预期 CONFIRMED）
    p = with_dock(base_input(), out_cells=2)
    out_commodity(p, "ore_out")
    p["required_generic_outputs"]["ore_out"] = 3
    samples.append({"id": "U1_output_pigeonhole", "input": p, "expect": "CONFIRMED"})

    p = with_sink(base_input(), k=3)
    in_commodity(p, "food", 4)
    samples.append({"id": "U2_input_pigeonhole", "input": p, "expect": "CONFIRMED"})

    p = with_dock(base_input(), out_cells=3)
    out_commodity(p, "a")
    out_commodity(p, "b")
    p["required_generic_outputs"].update({"a": 2, "b": 2})
    samples.append({"id": "U3_multi_commodity_overflow", "input": p, "expect": "CONFIRMED"})

    p = with_furnace(base_input())  # 提供变量，避免 DEGENERATE
    out_commodity(p, "a")
    p["required_generic_outputs"]["a"] = 1  # 无 provider → 空和哨兵矛盾对
    samples.append({"id": "U4_positive_req_zero_slots", "input": p, "expect": "CONFIRMED"})

    # --- FEASIBLE canaries（预期 SIDE_SAT + witness OK；任何 UNSAT = BLOCK）
    p = with_furnace(base_input(), in_cells=3, need_ore=2)  # 3 patterns
    with_furnace(p, instance_id="furnace_2", in_cells=2, need_ore=2)  # fixed（1 pattern）
    samples.append({"id": "C1_binding_multi_plus_fixed", "input": p, "expect": "SAT"})

    p = with_dock(base_input(), out_cells=2)
    out_commodity(p, "a")
    p["required_generic_outputs"]["a"] = 2
    with_sink(p, k=2)
    in_commodity(p, "food", 2)
    samples.append({"id": "C2_generic_exact_fit", "input": p, "expect": "SAT"})

    p = with_sink(base_input(), instance_id="pose_optional::protocol_storage_box::7",
                  k=2, synthesize=True)
    in_commodity(p, "food", 1)
    samples.append({"id": "C3_pose_optional_synthesis", "input": p, "expect": "SAT"})

    p = with_dock(base_input(), out_cells=2)
    out_commodity(p, "a")
    p["required_generic_outputs"]["a"] = 0  # ZERO 行
    samples.append({"id": "C4_zero_requirement", "input": p, "expect": "SAT"})

    p = with_furnace(base_input(), in_cells=4, need_ore=2, out_cells=2, need_ingot=1)  # 12 patterns
    with_dock(p, out_cells=3)
    out_commodity(p, "a")
    p["required_generic_outputs"]["a"] = 1
    with_sink(p, k=2)
    in_commodity(p, "food", 2)
    samples.append({"id": "C5_mixed_full_model", "input": p, "expect": "SAT"})

    # --- INPUT_INVALID 组（emitter 必须拒绝，不得发 OPB）
    p = with_dock(base_input(), out_cells=1)
    p["required_generic_outputs"]["__unused__"] = 1
    samples.append({"id": "I1_unused_sentinel", "input": p,
                    "expect": "REJECT", "subcode": "UNUSED_SENTINEL_IN_REQUIREMENTS"})

    p = with_dock(base_input(), out_cells=1)
    out_commodity(p, "a")
    p["required_generic_outputs"]["a"] = True
    samples.append({"id": "I2_bool_count", "input": p, "expect": "REJECT", "subcode": "NON_INT_FIELD"})

    p = with_dock(base_input(), out_cells=1)
    out_commodity(p, "a")
    p["required_generic_outputs"]["a"] = -1
    samples.append({"id": "I3_negative_count", "input": p, "expect": "REJECT", "subcode": "NEGATIVE_FIELD"})

    p = with_dock(base_input(), out_cells=1)
    p["commodity_metadata"]["a"] = {"source_kind": "internal"}
    p["required_generic_outputs"]["a"] = 1
    samples.append({"id": "I4_role_mismatch", "input": p, "expect": "REJECT", "subcode": "OUTPUT_ROLE_MISMATCH"})

    p = with_dock(base_input(), out_cells=1)
    out_commodity(p, "a")
    p["required_generic_outputs"]["a"] = 1
    p["commodity_metadata"]["ghost_food"] = {"sink_kind": "generic_input"}  # req_in 漏它
    samples.append({"id": "I5_completeness_gap", "input": p,
                    "expect": "REJECT", "subcode": "GENERIC_INPUT_COMPLETENESS"})

    p = with_furnace(base_input())
    p["placement_solution"]["furnace_1"]["pose_idx"] = 99
    samples.append({"id": "I6_pose_idx_oob", "input": p, "expect": "REJECT", "subcode": "POSE_IDX_OUT_OF_RANGE"})

    p = with_furnace(base_input())
    p["placement_solution"]["mystery_9"] = {"facility_type": "unknown_tpl", "pose_idx": 0}
    samples.append({"id": "I7_unsynthesizable_missing", "input": p,
                    "expect": "REJECT", "subcode": "MISSING_INSTANCE_METADATA"})

    p = with_furnace(base_input(), in_cells=1, need_ore=2)  # 槽需 2 > cells 1 → 生产 raise
    samples.append({"id": "I8_port_insufficient_raise", "input": p,
                    "expect": "REJECT", "subcode": "PRODUCTION_EXCEPTION_CLASS"})

    return samples


# ---------------------------------------------------------------- 突变（红测：验证 harness 抓得住 emitter bug）
def mutations() -> List[Dict[str, Any]]:
    return [
        # under-constraint：删一行 EXO-SLOT → U3 应从 CONFIRMED 翻成 SAT
        {"id": "M1_under_drop_exoslot", "base": "U3_multi_commodity_overflow",
         "mutate": "drop_first_exoslot", "expect_flip_from": "CONFIRMED"},
        # under-constraint：REQ rhs 3→2 → U1 翻 SAT
        {"id": "M2_under_relax_req", "base": "U1_output_pigeonhole",
         "mutate": "req_minus_one", "expect_flip_from": "CONFIRMED"},
        # over-constraint：REQ rhs 2→3 → canary C2 翻 UNSAT（必须被 canary 抓住）
        {"id": "M3_over_tighten_req", "base": "C2_generic_exact_fit",
         "mutate": "req_plus_one", "expect_flip_from": "SAT"},
        # toolchain：U1 proof 已由 runner 全链检查覆盖（玩具级篡改红测已实证），此处
        # 用「错 #equal 头」变体：emitter 头减 1 → veripb 必须拒（PROOF_REJECTED/UNKNOWN）
        {"id": "M4_bad_equal_header", "base": "U2_input_pigeonhole",
         "mutate": "equal_minus_one", "expect_flip_from": "CONFIRMED"},
    ]


def apply_mutation(opb: str, kind: str) -> str:
    lines = opb.splitlines()
    if kind == "drop_first_exoslot":
        # EXO-SLOT 行 = 第一条 rhs=1 且含 __unused__ 变量组的等式；按 conmap 语义即
        # 首个 "= 1 ;" 且项数>1 的行（EXO-BIND 也匹配——U3 无 binding 实例，安全）
        for i, ln in enumerate(lines[1:], start=1):
            if ln.endswith("= 1 ;") and ln.count(" x") > 1:
                del lines[i]
                break
    elif kind == "req_minus_one":
        for i, ln in enumerate(lines):
            if ln.endswith("= 3 ;"):
                lines[i] = ln[:-5] + "= 2 ;"
                break
    elif kind == "req_plus_one":
        for i, ln in enumerate(lines):
            if ln.endswith("= 2 ;") and i > 0:
                lines[i] = ln[:-5] + "= 3 ;"
                break
    elif kind == "equal_minus_one":
        import re as _re
        m = _re.search(r"#equal= (\d+)", lines[0])
        k = int(m.group(1))
        lines[0] = lines[0].replace(f"#equal= {k}", f"#equal= {k - 1}")
        return "\n".join(lines) + "\n"
    else:
        raise ValueError(kind)
    # 头部约束计数同步（除 equal_minus_one 外，行数变化时修 #constraint/#equal）
    n_rows = len([ln for ln in lines[1:] if ln.strip()])
    n_eq = len([ln for ln in lines[1:] if ln.strip().endswith(";") and "= " in ln and ">=" not in ln])
    import re as _re
    lines[0] = _re.sub(r"#constraint= \d+", f"#constraint= {n_rows}", lines[0])
    lines[0] = _re.sub(r"#equal= \d+", f"#equal= {n_eq}", lines[0])
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- 主流程
def run_one(sample_id: str, opb_text: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
    d = WORK / sample_id
    d.mkdir(parents=True, exist_ok=True)
    opb_path = d / "instance.opb"
    opb_path.write_text(opb_text, encoding="ascii", newline="\n")
    record = run_sidecar_chain(opb_path, d)
    if record["status"] == "SIDE_SAT_RAW":
        wit = record.get("witness_values")
        if wit is None:
            record.update(status="UNKNOWN", subcode="WITNESS_MISSING")
        else:
            chk = check_witness(opb_text, wit)
            record["witness_check"] = chk
            record["status"] = "DIVERGED_OPB_ONLY" if chk["ok"] else "SIDE_SAT_UNTRUSTED"
    (d / "verdict.json").write_text(json.dumps(record, indent=1, default=str), encoding="utf-8")
    return record


def main() -> int:
    WORK.mkdir(exist_ok=True)
    results: List[Dict[str, Any]] = []
    opb_cache: Dict[str, str] = {}
    fails = 0

    for sample in build_samples():
        sid, expect = sample["id"], sample["expect"]
        try:
            emitted = emit(sample["input"])
        except EmitterReject as exc:
            ok = expect == "REJECT" and exc.subcode == sample.get("subcode")
            results.append({"id": sid, "expect": expect, "got": f"REJECT/{exc.subcode}", "ok": ok})
            fails += 0 if ok else 1
            continue
        if expect == "REJECT":
            results.append({"id": sid, "expect": f"REJECT/{sample.get('subcode')}",
                            "got": "EMITTED", "ok": False})
            fails += 1
            continue
        opb_cache[sid] = emitted["opb"]
        d = WORK / sid
        d.mkdir(parents=True, exist_ok=True)
        (d / "varmap.json").write_text(json.dumps(emitted["varmap"], indent=1), encoding="utf-8")
        (d / "conmap.json").write_text(json.dumps(emitted["conmap"], indent=1), encoding="utf-8")
        record = run_one(sid, emitted["opb"], results)
        got = record["status"]
        ok = (expect == "CONFIRMED" and got == "CONFIRMED") or (
            expect == "SAT" and got == "DIVERGED_OPB_ONLY"
        )
        results.append({"id": sid, "expect": expect, "got": got,
                        "subcode": record.get("subcode"), "ok": ok})
        fails += 0 if ok else 1

    for mut in mutations():
        base = mut["base"]
        if base not in opb_cache:
            results.append({"id": mut["id"], "expect": "flip", "got": "BASE_MISSING", "ok": False})
            fails += 1
            continue
        mutated = apply_mutation(opb_cache[base], mut["mutate"])
        record = run_one(mut["id"], mutated, results)
        got = record["status"]
        flipped = got != mut["expect_flip_from"]
        results.append({"id": mut["id"], "expect": f"!= {mut['expect_flip_from']}",
                        "got": got, "subcode": record.get("subcode"), "ok": flipped})
        fails += 0 if flipped else 1

    report = {"schema": "binding_sidecar_acceptance_v1", "results": results,
              "total": len(results), "failed": fails}
    (WORK / "acceptance_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    width = max(len(r["id"]) for r in results)
    for r in results:
        mark = "PASS" if r["ok"] else "FAIL"
        print(f"[{mark}] {r['id']:<{width}}  expect={r['expect']}  got={r['got']}"
              + (f"/{r['subcode']}" if r.get("subcode") else ""))
    print(f"\n{len(results) - fails}/{len(results)} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
