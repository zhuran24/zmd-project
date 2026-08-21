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

NON_FACILITY_PLACEMENT_MARKER_IDS = {"ghost_pick"}
UNUSED = "__unused__"


def _pose_optional_operation_map(
    model_input: Mapping[str, Any],
    profiles: Mapping[str, Mapping[str, Any]],
) -> Dict[str, str]:
    raw = model_input.get("plan_utility_operation_by_template")
    if not isinstance(raw, Mapping):
        raise ValueError("plan_utility_operation_by_template is not an object")
    normalized: Dict[str, str] = {}
    for raw_template, raw_operation in raw.items():
        template = str(raw_template)
        operation = str(raw_operation)
        if not template or not operation:
            raise ValueError("pose_optional operation map has an empty identity")
        profile = profiles.get(operation)
        if not isinstance(profile, Mapping) or str(profile.get("facility_type", "")) != template:
            raise ValueError(
                f"pose_optional operation map mismatch: {template}->{operation}"
            )
        normalized[template] = operation
    expected: Dict[str, str] = {}
    for operation, profile in profiles.items():
        if dict(profile.get("input_slot_counts", {})) or dict(
            profile.get("output_slot_counts", {})
        ):
            continue
        template = str(profile.get("facility_type", ""))
        previous = expected.get(template)
        if previous is not None and previous != operation:
            raise ValueError(
                f"ambiguous utility facility type: {template}: {previous}, {operation}"
            )
        expected[template] = str(operation)
    if normalized != expected:
        raise ValueError(
            f"utility operation map/profile mismatch: map={normalized} profiles={expected}"
        )
    represented = {
        str(instance.get("operation_type", ""))
        for instance in model_input.get("instances", [])
        if isinstance(instance, Mapping)
        and str(instance.get("operation_type", ""))
    }
    return {
        template: operation
        for template, operation in sorted(normalized.items())
        if operation not in represented
    }


def _resolve_instances(
    model_input: Mapping[str, Any],
    operation_by_template: Mapping[str, str],
) -> Dict[str, Dict[str, Any]]:
    """placement 实例解析 + pose_optional 合成（第二实现）。"""
    placement = dict(model_input["placement_solution"])
    by_id = {str(i["instance_id"]): dict(i) for i in model_input["instances"]}
    out: Dict[str, Dict[str, Any]] = {}
    for instance_id, sol in placement.items():
        if instance_id in NON_FACILITY_PLACEMENT_MARKER_IDS:
            continue
        inst = by_id.get(instance_id)
        if inst is None:
            if not instance_id.startswith("pose_optional::"):
                raise ValueError(f"unresolvable placement instance: {instance_id}")
            parts = instance_id.split("::")
            if len(parts) < 3 or not parts[1]:
                raise ValueError(f"unresolvable placement instance: {instance_id}")
            facility_type = parts[1]
            solution_template = str(dict(sol).get("facility_type", ""))
            if solution_template and solution_template != facility_type:
                raise ValueError(
                    f"pose_optional template mismatch: {instance_id}: "
                    f"{solution_template}!={facility_type}"
                )
            op = operation_by_template.get(facility_type)
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
    raw_input_slot_map = model_input.get("generic_input_slots_by_operation")
    if not isinstance(raw_input_slot_map, Mapping):
        return {"ok": False, "failures": ["generic_input_slots_by_operation is not an object"]}
    generic_input_slots_by_operation: Dict[str, int] = {}
    for operation_type, raw_count in raw_input_slot_map.items():
        if isinstance(raw_count, bool) or not isinstance(raw_count, int) or raw_count <= 0:
            failures.append(
                f"generic input slot capacity for {operation_type!r} is not a positive integer"
            )
            continue
        generic_input_slots_by_operation[str(operation_type)] = int(raw_count)
    expected_input_slot_map: Dict[str, int] = {}
    for operation_type, profile in profiles.items():
        raw_count = profile.get("generic_input_slots", 0)
        if isinstance(raw_count, bool) or not isinstance(raw_count, int) or raw_count < 0:
            failures.append(
                f"profile generic input slot capacity for {operation_type!r} is not a non-negative integer"
            )
            continue
        if raw_count > 0:
            expected_input_slot_map[str(operation_type)] = int(raw_count)
    if generic_input_slots_by_operation != expected_input_slot_map:
        failures.append(
            "generic input slot map/profile mismatch: "
            f"map={generic_input_slots_by_operation} profiles={expected_input_slot_map}"
        )
    generic_output_slots_by_operation: Dict[str, int] = {}
    for operation_type, profile in profiles.items():
        raw_count = profile.get("generic_output_slots", 0)
        if isinstance(raw_count, bool) or not isinstance(raw_count, int) or raw_count < 0:
            failures.append(
                f"profile generic output slot capacity for {operation_type!r} is not a non-negative integer"
            )
            continue
        if raw_count > 0:
            generic_output_slots_by_operation[str(operation_type)] = int(raw_count)

    # ---- 0. witness 完整性
    missing = [i + 1 for i in range(len(variables)) if witness.get(i + 1) not in (0, 1)]
    if missing:
        failures.append(f"witness missing/non-binary for {len(missing)} vars (first: {missing[:5]})")

    # ---- 1. witness → 语义决策
    binding_true: Dict[str, List[int]] = {}
    slot_true: Dict[str, List[str]] = {}
    slot_seen_in_varmap: Dict[str, set] = {}
    slot_metadata_in_varmap: Dict[str, Dict[str, Any]] = {}
    for num, sem in enumerate(variables, start=1):
        val = witness.get(num, 0)
        kind = sem["kind"]
        if kind == "binding_choice":
            if val == 1:
                binding_true.setdefault(str(sem["instance_id"]), []).append(int(sem["binding_idx"]))
        elif kind in ("generic_input", "generic_output"):
            raw_slot = sem.get("slot")
            if not isinstance(raw_slot, Mapping):
                failures.append(f"variable x{num}: slot metadata is not an object")
                continue
            slot = dict(raw_slot)
            slot_id = str(slot.get("slot_id", ""))
            if not slot_id:
                failures.append(f"variable x{num}: slot_id is empty")
                continue
            prior_slot = slot_metadata_in_varmap.setdefault(slot_id, slot)
            if prior_slot != slot:
                failures.append(f"slot {slot_id}: inconsistent metadata across commodity variables")
            slot_seen_in_varmap.setdefault(slot_id, set()).add(str(sem["commodity"]))
            if val == 1:
                slot_true.setdefault(slot_id, []).append(str(sem["commodity"]))
        else:
            failures.append(f"unknown varmap kind: {kind}")

    # ---- 2. 应有对象集合（第二实现）与实际对照
    try:
        operation_by_template = _pose_optional_operation_map(
            model_input,
            profiles,
        )
        instances = _resolve_instances(
            model_input,
            operation_by_template,
        )
    except ValueError as exc:
        return {"ok": False, "failures": [str(exc)]}

    expected_binding: Dict[str, Dict[str, Any]] = {}
    expected_out_slots: Dict[str, Dict[str, Any]] = {}
    expected_in_slots: Dict[str, Dict[str, Any]] = {}
    for instance_id, inst in instances.items():
        op = str(inst.get("operation_type") or "")
        profile = profiles.get(op)
        if profile is None:
            continue
        gi = int(profile.get("generic_input_slots", 0))
        go = int(profile.get("generic_output_slots", 0))
        if gi == 0 and go == 0:
            expected_binding[instance_id] = inst
        declared_output_slots = generic_output_slots_by_operation.get(op)
        if req_out and declared_output_slots is not None:
            sol = dict(placement[instance_id])
            pose = pools[str(sol["facility_type"])][int(sol["pose_idx"])]
            output_ports = list(pose.get("output_port_cells", []) or [])
            if len(output_ports) != declared_output_slots:
                failures.append(
                    f"{instance_id}: declares {declared_output_slots} generic output slots but pose "
                    f"has {len(output_ports)} physical output ports"
                )
            for idx, port in enumerate(output_ports):
                slot_id = f"{instance_id}:out:{idx}"
                expected_out_slots[slot_id] = {
                    "slot_id": slot_id,
                    "instance_id": instance_id,
                    "direction": "out",
                    "local_idx": idx,
                    "x": int(port["x"]),
                    "y": int(port["y"]),
                    "dir": str(port["dir"]),
                }
        declared_slots = generic_input_slots_by_operation.get(op)
        if req_in and declared_slots is not None:
            sol = dict(placement[instance_id])
            pose = pools[str(sol["facility_type"])][int(sol["pose_idx"])]
            input_ports = list(pose.get("input_port_cells", []) or [])
            if len(input_ports) != declared_slots:
                failures.append(
                    f"{instance_id}: declares {declared_slots} generic input slots but pose "
                    f"has {len(input_ports)} physical input ports"
                )
            for idx, port in enumerate(input_ports):
                slot_id = f"{instance_id}:in:{idx}"
                expected_in_slots[slot_id] = {
                    "slot_id": slot_id,
                    "instance_id": instance_id,
                    "direction": "in",
                    "local_idx": idx,
                    "x": int(port["x"]),
                    "y": int(port["y"]),
                    "dir": str(port["dir"]),
                    "operation_type": op,
                }

    actual_slots = set(slot_seen_in_varmap)
    expected_slots = set(expected_out_slots) | set(expected_in_slots)
    if actual_slots != expected_slots:
        failures.append(
            f"slot set mismatch: missing={sorted(expected_slots - actual_slots)[:5]} "
            f"extra={sorted(actual_slots - expected_slots)[:5]}"
        )
    for slot_id in sorted(expected_slots & actual_slots):
        expected_metadata = (expected_out_slots | expected_in_slots)[slot_id]
        if slot_metadata_in_varmap.get(slot_id) != expected_metadata:
            failures.append(
                f"slot {slot_id}: metadata {slot_metadata_in_varmap.get(slot_id)} "
                f"!= pose-derived {expected_metadata}"
            )
        expected_domain = (
            set(req_out) | {UNUSED}
            if slot_id in expected_out_slots
            else set(req_in) | {UNUSED}
        )
        if slot_seen_in_varmap.get(slot_id, set()) != expected_domain:
            failures.append(
                f"slot {slot_id}: commodity domain {sorted(slot_seen_in_varmap.get(slot_id, set()))} "
                f"!= expected {sorted(expected_domain)}"
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
