from __future__ import annotations

from collections import Counter
from pathlib import Path
import os
import sys

from src.models.master_model import (
    MasterPlacementModel,
    load_generic_io_requirements_artifact,
    load_project_data,
)

root = Path.cwd()
instances, pools, rules = load_project_data(root, "certified_exact")
generic = load_generic_io_requirements_artifact(root)
model = MasterPlacementModel(
    instances=instances,
    facility_pools=pools,
    rules=rules,
    solve_mode="certified_exact",
    skip_power_coverage=True,
    generic_io_requirements=generic,
)
d = model._coordinate_delegate
assert d is not None

class DummySlot:
    def __init__(self, template: str):
        self.template = template

collisions = []
out_of_bounds = []
for tpl, tuple_by_idx in sorted(d._template_pose_tuple_by_idx.items()):
    dummy = DummySlot(tpl)
    mode_count = max(1, d._template_mode_literals.get(tpl, 1))
    keys = {}
    for pose_idx, pose_tuple in tuple_by_idx.items():
        x, y, mode = map(int, pose_tuple)
        if not (0 <= x < d.grid_w and 0 <= y < d.grid_h and 0 <= mode < mode_count):
            out_of_bounds.append((tpl, pose_idx, pose_tuple, mode_count))
        key = d._slot_order_key_for_pose_tuple(dummy, pose_tuple)
        prev = keys.get(key)
        if prev is not None and prev != pose_tuple:
            collisions.append((tpl, key, prev, pose_tuple))
        keys[key] = pose_tuple

set_mismatches = []
compat_counter = Counter()
for group in model._mandatory_groups:
    gid = str(group["group_id"])
    slots = d.mandatory_slots.get(gid, [])
    if len(slots) < 2 or d._mandatory_group_uses_signature_table.get(gid, False):
        continue
    expected = {int(p) for p in model._candidate_pose_indices_for_group(group)}
    slot_set = set(d._slot_signature_order_pose_indices(slots[0]))
    if slot_set != expected:
        set_mismatches.append(("mandatory", gid, len(slot_set), len(expected)))
    bucket_defs = model._mandatory_signature_buckets.get(gid, [])
    sig = d._pose_signature_int_by_bucket_defs(bucket_defs, expected)
    compatible = all(d._signature_order_is_compatible_with_slot_order(slot, sig) for slot in slots)
    compat_counter[("mandatory", compatible)] += 1

for tpl, slots in sorted(d.required_optional_slots.items()):
    if len(slots) < 2 or d._required_optional_uses_signature_table.get(str(tpl), False):
        continue
    expected = set(range(len(model.facility_pools.get(str(tpl), []))))
    slot_set = set(d._slot_signature_order_pose_indices(slots[0]))
    if slot_set != expected:
        set_mismatches.append(("required_optional", str(tpl), len(slot_set), len(expected)))
    bucket_defs = model._required_optional_signature_buckets.get(str(tpl), [])
    sig = d._pose_signature_int_by_bucket_defs(bucket_defs, expected)
    compatible = all(d._signature_order_is_compatible_with_slot_order(slot, sig) for slot in slots)
    compat_counter[("required_optional", compatible)] += 1

residual_psb = None
for tpl, slots in sorted(d.residual_optional_slots.items()):
    if str(tpl) != "protocol_storage_box":
        continue
    if len(slots) < 2 or d._residual_optional_uses_signature_table.get(str(tpl), False):
        continue
    expected = set(range(len(model.facility_pools.get(str(tpl), []))))
    slot_set = set(d._slot_signature_order_pose_indices(slots[0]))
    if slot_set != expected:
        set_mismatches.append(("residual_optional", str(tpl), len(slot_set), len(expected)))
    bucket_defs = d._residual_optional_signature_buckets.get(str(tpl), [])
    sig = d._pose_signature_int_by_bucket_defs(bucket_defs, expected)
    rows = []
    for pose_idx in d._slot_signature_order_pose_indices(slots[0]):
        pose_tuple = d._template_pose_tuple_by_idx[str(tpl)][pose_idx]
        rows.append((d._slot_order_key_for_pose_tuple(slots[0], pose_tuple), sig[pose_idx], pose_idx, pose_tuple))
    rows.sort()
    drops = [(left, right) for left, right in zip(rows, rows[1:]) if right[1] < left[1]]
    compatible = all(d._signature_order_is_compatible_with_slot_order(slot, sig) for slot in slots)
    compat_counter[("residual_optional", compatible)] += 1
    residual_psb = {
        "slots": len(slots),
        "poses": len(expected),
        "buckets": len(bucket_defs),
        "compatible": compatible,
        "drops": len(drops),
        "constraints_expected": max(0, len(slots) - 1),
    }

model.build()
print("grid", d.grid_w, d.grid_h)
print("required_counts", model._exact_required_pose_optional_counts)
print("order_key_collision_count", len(collisions))
print("order_key_out_of_bounds_count", len(out_of_bounds))
print("candidate_set_mismatches", set_mismatches)
print("compat_counter", dict(compat_counter))
print("residual_protocol_storage_box", residual_psb)
print("coordinate_symmetry", model.build_stats.get("coordinate_symmetry"))
sys.stdout.flush()
os._exit(0)
