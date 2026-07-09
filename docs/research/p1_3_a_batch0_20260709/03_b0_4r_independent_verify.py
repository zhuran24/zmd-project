"""b0_4r C1 首解的独立覆盖复验（G0.4 门：照 exact_campaign 验证器语义重写，不 import 生产码）。

检查：边界 / 两两不重叠 / ghost 6×6 区域全空 / 每个 needs_power 设施被至少一根活跃杆覆盖
（按设施-杆对：occupied ∩ coverage ≠ ∅）。unforced（每杆唯一覆盖者）只记录不判死（修订二）。
"""
import json

SOL = "docs/research/p1_3_a_batch0_20260709/b0_4r_free_c1_w6.json.solution.json"
sol = json.load(open(SOL))
pools = json.load(open("data/preprocessed/candidate_placements.json"))["facility_pools"]
rules = json.load(open("rules/canonical_rules.json"))
templates = rules["facility_templates"]
grid = rules["globals"]["grid"]
W, H = int(grid["width"]), int(grid["height"])

_inst_raw = json.load(open("data/preprocessed/mandatory_exact_instances.json"))
_insts = _inst_raw if isinstance(_inst_raw, list) else _inst_raw.get("instances", [])
inst_tpl = {str(i["instance_id"]): str(i["facility_type"]) for i in _insts}

GHOST = {(x, y) for x in range(55, 61) for y in range(50, 56)}  # ghost_pick=3625 → (55,50) 6×6

units = []  # (label, occupied_set)
powered_units = []  # 需要供电的
for key, val in sol.items():
    if key.startswith("__") or key == "ghost_pick":
        continue
    if key.startswith("pose_optional::"):
        _, tpl, pose_id = key.split("::")
        pose = next(p for p in pools[tpl] if p["pose_id"] == pose_id)
    else:
        tpl = inst_tpl[key]
        pose = pools[tpl][int(val)]
    occ = {(int(c[0]), int(c[1])) for c in pose["occupied_cells"]}
    units.append((key, occ))
    if templates.get(tpl, {}).get("needs_power", False):
        powered_units.append((key, occ))

poles = []  # (pose_idx, occ, coverage)
for entry in sol["__c1_active_poles__"]:
    pose = pools["power_pole"][int(entry["pose_idx"])]
    assert pose["anchor"] == entry["anchor"], f"杆 anchor 不一致: {entry}"
    occ = {(int(c[0]), int(c[1])) for c in pose["occupied_cells"]}
    cov = {(int(c[0]), int(c[1])) for c in (pose.get("power_coverage_cells") or [])}
    units.append((f"pole_{entry['pose_idx']}", occ))
    poles.append((entry["pose_idx"], occ, cov))

fails = []
# 1. 边界
for label, occ in units:
    bad = [c for c in occ if not (0 <= c[0] < W and 0 <= c[1] < H)]
    if bad:
        fails.append(f"越界: {label} {bad[:3]}")
# 2. 两两不重叠
total = sum(len(occ) for _, occ in units)
union = set().union(*(occ for _, occ in units))
if total != len(union):
    seen, dup = {}, []
    for label, occ in units:
        for c in occ:
            if c in seen:
                dup.append((c, seen[c], label))
            seen[c] = label
    fails.append(f"重叠: 总格 {total} vs 并集 {len(union)}，样本 {dup[:5]}")
# 3. ghost 区域空
hit = [(label, sorted(occ & GHOST)[:3]) for label, occ in units if occ & GHOST]
if hit:
    fails.append(f"ghost 区域被占: {hit[:5]}")
# 4. 供电覆盖（按设施-杆对）
uncovered = []
for label, occ in powered_units:
    if not any(occ & cov for _, _, cov in poles):
        uncovered.append(label)
if uncovered:
    fails.append(f"供电未覆盖 {len(uncovered)} 个: {uncovered[:8]}")
# 5. unforced 记录（不判死）
redundant = []
for idx, _, cov in poles:
    sole = [
        label for label, occ in powered_units
        if occ & cov and sum(1 for _, _, c2 in poles if occ & c2) == 1
    ]
    if not sole:
        redundant.append(idx)

print(f"单位数: {len(units)}（含杆 {len(poles)}）; 需电设施: {len(powered_units)}")
print(f"unforced 记录: {len(redundant)} 根杆不是任何设施的唯一覆盖者 {redundant}")
if fails:
    print("VERIFY_FAIL")
    for f in fails:
        print(" -", f)
else:
    print("VERIFY_PASS: 边界/无重叠/ghost 全空/供电全覆盖 —— 四项全过")
