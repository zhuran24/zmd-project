"""b0_4r C1 首解的独立覆盖复验（fail-closed v2，2026-07-10 按 GPT Pro 外审三份补丁重写）。

检查：边界 / 两两不重叠 / ghost 区域全空（由 ghost_pick 动态解码）/ 每个 needs_power
设施被至少一根活跃杆覆盖（按设施-杆对：occupied ∩ coverage ≠ ∅）/ unforced 杆
fail-closed（每杆必须是至少一个需电设施的唯一覆盖者，且杆数 ≤ 需电设施数——对齐
exact_campaign 终端验证器语义）/ mandatory 完整性。

v2 修复（v1 的 PASS 只算本机一次性研究记录，不够格当证明件）：
- strict JSON（拒绝重复键 / NaN / Infinity），frozen 工件缺失即 VERIFY_FAIL 退出；
- ghost 区域从 solution["ghost_pick"] 动态解码（生产枚举 rect_idx = anchor_x*(H-gh+1)+anchor_y），
  不再硬编码；
- unforced 从「记录不判死」升为硬失败；
- 去 assert（python -O 免疫），全部显式 raise/fail。
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
CASE_DIR = Path(__file__).resolve().parent
SOL_PATH = CASE_DIR / "b0_4r_free_c1_w6.json.solution.json"
POOLS_PATH = ROOT / "data/preprocessed/candidate_placements.json"
RULES_PATH = ROOT / "rules/canonical_rules.json"
MANDATORY_PATH = ROOT / "data/preprocessed/mandatory_exact_instances.json"
GHOST_W, GHOST_H = 6, 6
EXPECTED_MANDATORY = 266


class VerifyError(Exception):
    pass


def _reject_dup_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise VerifyError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _reject_constant(value: str) -> Any:
    raise VerifyError(f"non-finite JSON constant: {value}")


def _strict_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise VerifyError(f"non-finite JSON float: {value}")
    return parsed


def load_strict(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_dup_keys,
        parse_constant=_reject_constant,
        parse_float=_strict_float,
    )


def strict_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise VerifyError(f"{label} 不是整数: {value!r}")
    return int(value)


def main() -> int:
    fails: list[str] = []
    if not POOLS_PATH.is_file():
        print("VERIFY_FAIL")
        print(
            " - frozen 外部工件缺失: data/preprocessed/candidate_placements.json；"
            "没有 hash-bound 池字节，本脚本不能给出 PASS"
        )
        return 1

    sol = load_strict(SOL_PATH)
    pools = load_strict(POOLS_PATH)["facility_pools"]
    rules = load_strict(RULES_PATH)
    templates = rules["facility_templates"]
    grid = rules["globals"]["grid"]
    W, H = int(grid["width"]), int(grid["height"])

    _inst_raw = load_strict(MANDATORY_PATH)
    _insts = _inst_raw if isinstance(_inst_raw, list) else _inst_raw.get("instances", [])
    inst_tpl = {str(i["instance_id"]): str(i["facility_type"]) for i in _insts}

    # ghost 区域：从 ghost_pick 动态解码（外层 anchor_x、内层 anchor_y 的生产枚举）
    ghost_idx = strict_int(sol.get("ghost_pick"), "ghost_pick")
    y_count = H - GHOST_H + 1
    anchor_x, anchor_y = divmod(ghost_idx, y_count)
    if not (0 <= anchor_x <= W - GHOST_W and 0 <= anchor_y <= H - GHOST_H):
        raise VerifyError(f"ghost_pick 越界: {ghost_idx} -> ({anchor_x}, {anchor_y})")
    ghost_cells = {
        (x, y)
        for x in range(anchor_x, anchor_x + GHOST_W)
        for y in range(anchor_y, anchor_y + GHOST_H)
    }

    units: list[tuple[str, set[tuple[int, int]]]] = []
    powered_units: list[tuple[str, set[tuple[int, int]]]] = []
    mandatory_seen = 0
    for key, val in sol.items():
        if key.startswith("__") or key == "ghost_pick":
            continue
        if key.startswith("pose_optional::"):
            _, tpl, pose_id = key.split("::")
            matches = [p for p in pools[tpl] if p["pose_id"] == pose_id]
            if len(matches) != 1:
                raise VerifyError(f"optional pose_id 匹配数 {len(matches)}: {key}")
            pose = matches[0]
        else:
            if key not in inst_tpl:
                raise VerifyError(f"未知实例: {key}")
            tpl = inst_tpl[key]
            pose_idx = strict_int(val, f"{key} pose_idx")
            pool = pools[tpl]
            if not (0 <= pose_idx < len(pool)):
                raise VerifyError(f"{key} pose_idx 越界: {pose_idx}")
            pose = pool[pose_idx]
            mandatory_seen += 1
        occ = {(int(c[0]), int(c[1])) for c in pose["occupied_cells"]}
        units.append((key, occ))
        if templates.get(tpl, {}).get("needs_power", False):
            powered_units.append((key, occ))

    if mandatory_seen != EXPECTED_MANDATORY:
        fails.append(f"mandatory 不完整: {mandatory_seen} != {EXPECTED_MANDATORY}")

    poles: list[tuple[int, set[tuple[int, int]], set[tuple[int, int]]]] = []
    seen_pole_idx: set[int] = set()
    for entry in sol.get("__c1_active_poles__", []):
        pose_idx = strict_int(entry.get("pose_idx"), "pole pose_idx")
        if pose_idx in seen_pole_idx:
            raise VerifyError(f"重复杆 pose_idx: {pose_idx}")
        seen_pole_idx.add(pose_idx)
        pole_pool = pools["power_pole"]
        if not (0 <= pose_idx < len(pole_pool)):
            raise VerifyError(f"杆 pose_idx 越界: {pose_idx}")
        pose = pole_pool[pose_idx]
        if pose["anchor"] != entry.get("anchor"):
            raise VerifyError(f"杆 anchor 与池不一致: {entry}")
        occ = {(int(c[0]), int(c[1])) for c in pose["occupied_cells"]}
        cov = {(int(c[0]), int(c[1])) for c in (pose.get("power_coverage_cells") or [])}
        units.append((f"pole_{pose_idx}", occ))
        poles.append((pose_idx, occ, cov))

    # 1. 边界
    for label, occ in units:
        bad = [c for c in occ if not (0 <= c[0] < W and 0 <= c[1] < H)]
        if bad:
            fails.append(f"越界: {label} {bad[:3]}")
    # 2. 两两不重叠
    total = sum(len(occ) for _, occ in units)
    union: set[tuple[int, int]] = set().union(*(occ for _, occ in units)) if units else set()
    if total != len(union):
        fails.append(f"重叠: 总格 {total} vs 并集 {len(union)}")
    # 3. ghost 区域空
    hit = [(label, sorted(occ & ghost_cells)[:3]) for label, occ in units if occ & ghost_cells]
    if hit:
        fails.append(f"ghost 区域被占: {hit[:5]}")
    # 4. 供电覆盖（按设施-杆对）
    uncovered = [
        label
        for label, occ in powered_units
        if not any(occ & cov for _, _, cov in poles)
    ]
    if uncovered:
        fails.append(f"供电未覆盖 {len(uncovered)} 个: {uncovered[:8]}")
    # 5. unforced：对齐终端验证器（exact_campaign.py:1243-1253）——硬失败
    if len(poles) > len(powered_units):
        fails.append(f"unforced: 杆数 {len(poles)} > 需电设施数 {len(powered_units)}")
    coverers_by_unit: dict[str, list[int]] = {}
    for label, occ in powered_units:
        coverers_by_unit[label] = [idx for idx, _, cov in poles if occ & cov]
    for pole_idx, _occ, cov in poles:
        covered = [label for label, occ in powered_units if occ & cov]
        if not covered:
            fails.append(f"unforced: 杆 {pole_idx} 不覆盖任何需电设施")
            continue
        if not any(coverers_by_unit[label] == [pole_idx] for label in covered):
            fails.append(f"unforced: 杆 {pole_idx} 不是任何需电设施的唯一覆盖者")

    print(f"单位数: {len(units)}（含杆 {len(poles)}）; 需电设施: {len(powered_units)}")
    if fails:
        print("VERIFY_FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print(
        "VERIFY_PASS: 边界/无重叠/ghost 全空/供电全覆盖/unforced/mandatory 完整 —— 六项全过"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
