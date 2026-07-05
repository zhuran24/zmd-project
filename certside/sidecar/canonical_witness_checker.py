"""binding PB sidecar — canonical-level witness checker（设计稿 v2 §5.2 第二段）.

从**原始 model_input 语义**独立验证 SAT witness——不调用 emitter 的约束生成
函数；「应有对象集合」（binding 实例集/槽集）在本文件第二实现。对选中 pattern
只做语义合法性验证（cells ∈ pose 对应侧、无重复、计数 == profile 槽数），
不信任 emitter 枚举的完整性。

通过 → 调用方把 SIDE_SAT 升级为 DIVERGED_CANDIDATE；失败 → SIDE_SAT_UNTRUSTED。
本 checker 自身的验收红测在 run_acceptance.py 的 W 组。
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

# 与 emitter 共享的硬编码 TCB 常量（semantics_v1 §4.3）——刻意重复声明而非 import，
# 常量漂移会被 acceptance 的对照样本抓住。
POSE_OPTIONAL_OPERATION_BY_TEMPLATE = {
    "protocol_storage_box": "wireless_sink",
    "power_pole": "power_supply",
}
NON_FACILITY_PLACEMENT_MARKER_IDS = {"ghost_pick"}
GENERIC_OUTPUT_PROVIDER_OPERATIONS = {"boundary_io", "protocol_core"}
GENERIC_INPUT_RECEIVER_OPERATION = "wireless_sink"
UNUSED = "__unused__"


def _resolve_instances(model_input: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    """placement 实例解析 + pose_optional 合成（第二实现）。"""
    placement = dict(model_input["placement_solution"])
    by_id = {str(i["instance_id"]): dict(i) for i in model_input["instances"]}
    out: Dict[str, Dict[str, Any]] = {}
    for instance_id, sol in placement.items():
        if instance_id in NON_FACILITY_PLACEMENT_MARKER_IDS:
            continue
        inst = by_id.get(instance_id)
        if inst is None:
            facility_type = str(dict(sol).get("facility_type", ""))
            op = POSE_OPTIONAL_OPERATION_BY_TEMPLATE.get(facility_type)
            if op is None and instance_id.startswith("pose_optional::"):
                parts = instance_id.split("::")
                if len(parts) >= 2:
                    op = POSE_OPTIONAL_OPERATION_BY_TEMPLATE.get(parts[1])
                    if op is not None:
                        facility_type = parts[1]
            if op is None:
                raise ValueError(f"unresolvable placement instance: {instance_id}")
            inst = {"instance_id": instance_id, "facility_type": facility_type,
                    "operation_type": op}
        out[instance_id] = inst
    return out


def check_canonical_witness(
    model_input: Mapping[str, Any],
    varmap: Mapping[str, Any],
    patterns: Mapping[str, Any],
    witness: Mapping[int, int],
) -> Dict[str, Any]:
    failures: List[str] = []
    variables = list(varmap["variables"])
    profiles = dict(model_input["operation_profiles"])
    pools = dict(model_input["facility_pools"])
    placement = dict(model_input["placement_solution"])
    req_out = {str(c): int(v) for c, v in dict(model_input["required_generic_outputs"]).items()}
    req_in = {str(c): int(v) for c, v in dict(model_input["required_generic_inputs"]).items()}
    wireless_k = int(model_input["wireless_sink_generic_input_slots"])

    # ---- 0. witness 完整性
    missing = [i + 1 for i in range(len(variables)) if witness.get(i + 1) not in (0, 1)]
    if missing:
        failures.append(f"witness missing/non-binary for {len(missing)} vars (first: {missing[:5]})")

    # ---- 1. witness → 语义决策
    binding_true: Dict[str, List[int]] = {}
    slot_true: Dict[str, List[str]] = {}
    slot_seen_in_varmap: Dict[str, set] = {}
    for num, sem in enumerate(variables, start=1):
        val = witness.get(num, 0)
        kind = sem["kind"]
        if kind == "binding_choice":
            if val == 1:
                binding_true.setdefault(str(sem["instance_id"]), []).append(int(sem["binding_idx"]))
        elif kind in ("generic_input", "generic_output"):
            slot_id = str(sem["slot"]["slot_id"])
            slot_seen_in_varmap.setdefault(slot_id, set()).add(str(sem["commodity"]))
            if val == 1:
                slot_true.setdefault(slot_id, []).append(str(sem["commodity"]))
        else:
            failures.append(f"unknown varmap kind: {kind}")

    # ---- 2. 应有对象集合（第二实现）与实际对照
    try:
        instances = _resolve_instances(model_input)
    except ValueError as exc:
        return {"ok": False, "failures": [str(exc)]}

    expected_binding: Dict[str, Dict[str, Any]] = {}
    expected_out_slots: Dict[str, str] = {}   # slot_id -> instance_id
    expected_in_slots: Dict[str, str] = {}
    for instance_id, inst in instances.items():
        op = str(inst.get("operation_type") or "")
        profile = profiles.get(op)
        if profile is None:
            continue
        gi = int(profile.get("generic_input_slots", 0))
        go = int(profile.get("generic_output_slots", 0))
        if gi == 0 and go == 0:
            expected_binding[instance_id] = inst
        if req_out and op in GENERIC_OUTPUT_PROVIDER_OPERATIONS:
            sol = dict(placement[instance_id])
            pose = pools[str(sol["facility_type"])][int(sol["pose_idx"])]
            for idx in range(len(pose.get("output_port_cells", []))):
                expected_out_slots[f"{instance_id}:out:{idx}"] = instance_id
        if req_in and op == GENERIC_INPUT_RECEIVER_OPERATION:
            for idx in range(wireless_k):
                expected_in_slots[f"{instance_id}:in:{idx}"] = instance_id

    actual_slots = set(slot_seen_in_varmap)
    expected_slots = set(expected_out_slots) | set(expected_in_slots)
    if actual_slots != expected_slots:
        failures.append(
            f"slot set mismatch: missing={sorted(expected_slots - actual_slots)[:5]} "
            f"extra={sorted(actual_slots - expected_slots)[:5]}"
        )

    # ---- 3. binding：每实例恰一 pattern + 选中 pattern 语义验证
    fixed = {str(k): int(v) for k, v in dict(patterns.get("fixed_choices", {})).items()}
    by_instance = dict(patterns.get("by_instance", {}))
    chosen: Dict[str, int] = dict(fixed)
    for instance_id, idxs in binding_true.items():
        if len(idxs) != 1:
            failures.append(f"{instance_id}: {len(idxs)} patterns selected (exactly-one violated)")
            continue
        chosen[instance_id] = idxs[0]
    for instance_id in expected_binding:
        if instance_id not in chosen:
            failures.append(f"{instance_id}: no pattern selected")
    for instance_id in chosen:
        if instance_id not in expected_binding:
            failures.append(f"{instance_id}: selected but not an expected binding instance")

    for instance_id, idx in sorted(chosen.items()):
        if instance_id not in expected_binding:
            continue
        inst = expected_binding[instance_id]
        op = str(inst["operation_type"])
        profile = profiles[op]
        sol = dict(placement[instance_id])
        pose = pools[str(sol["facility_type"])][int(sol["pose_idx"])]
        plist = by_instance.get(instance_id)
        if plist is None or not (0 <= idx < len(plist)):
            failures.append(f"{instance_id}: chosen idx {idx} outside materialized patterns")
            continue
        assign = plist[idx]
        for side, cells_key, counts_key in (
            ("input", "input_port_cells", "input_slot_counts"),
            ("output", "output_port_cells", "output_slot_counts"),
        ):
            pose_cells = {(int(c["x"]), int(c["y"]), str(c["dir"]))
                          for c in pose.get(cells_key, [])}
            used = [(int(a["x"]), int(a["y"]), str(a["dir"])) for a in assign[side]]
            if len(used) != len(set(used)):
                failures.append(f"{instance_id}/{side}: duplicate cell in assignment")
            for cell in used:
                if cell not in pose_cells:
                    failures.append(f"{instance_id}/{side}: cell {cell} not a pose port cell")
            counts: Dict[str, int] = {}
            for a in assign[side]:
                counts[str(a["commodity"])] = counts.get(str(a["commodity"]), 0) + 1
            expected_counts = {str(c): int(n)
                               for c, n in dict(profile.get(counts_key, {})).items() if int(n) > 0}
            if counts != expected_counts:
                failures.append(
                    f"{instance_id}/{side}: commodity counts {counts} != profile {expected_counts}"
                )

    # ---- 4. generic 槽：恰一 + 计数 == required
    for slot_id in sorted(expected_slots):
        got = slot_true.get(slot_id, [])
        if len(got) != 1:
            failures.append(f"slot {slot_id}: {len(got)} commodities selected")
    out_counts: Dict[str, int] = {}
    in_counts: Dict[str, int] = {}
    for slot_id, commodities in slot_true.items():
        for c in commodities:
            if c == UNUSED:
                continue
            if slot_id in expected_out_slots:
                out_counts[c] = out_counts.get(c, 0) + 1
            elif slot_id in expected_in_slots:
                in_counts[c] = in_counts.get(c, 0) + 1
    for c, required in sorted(req_out.items()):
        if out_counts.get(c, 0) != required:
            failures.append(f"generic output {c}: assigned {out_counts.get(c, 0)} != required {required}")
    for c, required in sorted(req_in.items()):
        if in_counts.get(c, 0) != required:
            failures.append(f"generic input {c}: assigned {in_counts.get(c, 0)} != required {required}")
    extra_out = sorted(set(out_counts) - set(req_out))
    extra_in = sorted(set(in_counts) - set(req_in))
    if extra_out:
        failures.append(f"unrequested output commodities assigned: {extra_out}")
    if extra_in:
        failures.append(f"unrequested input commodities assigned: {extra_in}")

    return {"ok": not failures, "failures": failures}
