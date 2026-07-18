#!/usr/bin/env python3
"""witness 链独立零违规审计（批 4 剩余项，2026-07-19）。

对 run_reconstructed_witness.py 各臂产出的 result.json 做**完全独立**的
零违规复核：运行时不 import 任何 ``src/`` 生产代码，也不 import 构造
harness 与 independent_front_audit.py——所有几何谓词（in-grid / 两两不
重叠 / ghost 净空 / identity front-clear 计数）在本文件内第三方重实现。
历史 front 错位 P0 正是藏在生产 helper（_DIR_DELTA 步进）里，独立审计
的意义就是不共享那套代码路径。

需求表（逐 operation 的 [req_in, vis_out]）以字面量钉死在本文件：
2026-07-19 自 src.models.port_binding.routing_visible_port_demands(op,
frozenset()) 一次性抄录（RFSC=空集 = 批 3+5 新语义）。启动自检强制其
与 05 号文档的 628 独立账吻合（机器 in 310 + core 收货 2 = 312；机器
out 264 + 边界 46 + core 6 = 316），表被改动即 fail-closed。

identity front 语义：池内 port 记录的 (x, y) 即体外第 1 格接驳格
（07-18 owner 定谳），审计谓词 = 该格在图内且未被任何本体占据。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

GRID_W = GRID_H = 70

# 池工件钉值（freeze 链同款；不匹配即拒绝审计）。
_POOL_SHA256 = (
    "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3"
)

# 逐 operation 的 [required_in, routing_visible_out]（RFSC=∅）。
DEMANDS: dict[str, tuple[int, int]] = {
    "crusher_blue_iron": (1, 1),
    "crusher_buckwheat": (1, 2),
    "crusher_sandleaf": (1, 3),
    "crusher_source": (1, 1),
    "filling_capsule": (4, 1),
    "grinder_dense_blue_iron": (3, 1),
    "grinder_dense_source": (3, 1),
    "grinder_fine_buckwheat": (3, 1),
    "molding_bottle": (2, 1),
    "packaging_battery": (5, 1),
    "parts_maker": (1, 1),
    "planter_buckwheat": (1, 1),
    "planter_sandleaf": (1, 1),
    "refinery_blue_iron": (1, 1),
    "refinery_steel": (1, 1),
    "seed_collector_buckwheat": (1, 2),
    "seed_collector_sandleaf": (1, 2),
}

# mandatory 实例逐 op 台数（自检用，与 mandatory_exact_instances.json 对账）。
EXPECTED_OP_COUNTS: dict[str, int] = {
    "boundary_io": 46,
    "crusher_blue_iron": 34,
    "crusher_buckwheat": 6,
    "crusher_sandleaf": 11,
    "crusher_source": 18,
    "filling_capsule": 3,
    "grinder_dense_blue_iron": 17,
    "grinder_dense_source": 9,
    "grinder_fine_buckwheat": 6,
    "molding_bottle": 6,
    "packaging_battery": 3,
    "parts_maker": 6,
    "planter_buckwheat": 11,
    "planter_sandleaf": 21,
    "protocol_core": 1,
    "refinery_blue_iron": 34,
    "refinery_steel": 17,
    "seed_collector_buckwheat": 6,
    "seed_collector_sandleaf": 11,
}

EXPECTED_TYPE_COUNTS: dict[str, int] = {
    "manufacturing_3x3": 132,
    "manufacturing_5x5": 49,
    "manufacturing_6x4": 38,
    "protocol_core": 1,
    "boundary_storage_port": 46,
}


def self_test() -> None:
    """启动自检：需求表须复算出 05 号文档的 628 独立账。"""
    total_in = sum(
        EXPECTED_OP_COUNTS[op] * DEMANDS[op][0] for op in DEMANDS
    )
    total_out = sum(
        EXPECTED_OP_COUNTS[op] * DEMANDS[op][1] for op in DEMANDS
    )
    if total_in != 310 or total_out != 264:
        raise SystemExit(
            f"SELF_TEST_FAIL: machine demand sums {total_in}/{total_out} != 310/264"
        )
    if total_in + 2 != 312 or total_out + 46 + 6 != 316:
        raise SystemExit("SELF_TEST_FAIL: 628 account mismatch")
    if sum(EXPECTED_OP_COUNTS.values()) != 266:
        raise SystemExit("SELF_TEST_FAIL: instance count != 266")


def load_pool(path: Path) -> dict[str, list[dict]]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != _POOL_SHA256:
        raise SystemExit(
            f"POOL_SHA_MISMATCH: {digest} != pinned {_POOL_SHA256} — refuse to audit"
        )
    payload = json.loads(raw.decode("utf-8"))
    pools = payload["facility_pools"]
    if sum(len(v) for v in pools.values()) != 82829:
        raise SystemExit("POOL_SIZE_MISMATCH: total poses != 82829")
    return pools


def audit(result_path: Path, pool_path: Path, instances_path: Path,
          *, allow_partial: bool) -> dict:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    pools = load_pool(pool_path)
    inst_payload = json.loads(instances_path.read_text(encoding="utf-8"))
    instances = inst_payload if isinstance(inst_payload, list) else inst_payload["instances"]
    inst_by_id = {str(i["instance_id"]): i for i in instances}

    violations: list[dict] = []
    solution = result["solution"]

    # A. 覆盖面
    sol_ids = set(solution)
    unknown = sol_ids - set(inst_by_id)
    if unknown:
        violations.append({"check": "coverage", "detail": f"unknown ids {sorted(unknown)[:5]}"})
    if not allow_partial:
        missing = set(inst_by_id) - sol_ids
        if missing:
            violations.append({"check": "coverage", "detail": f"missing {len(missing)} instances"})
    if len(solution) != int(result.get("placed", len(solution))):
        violations.append({"check": "coverage", "detail": "placed field != solution size"})

    # B/C/D. 类型匹配 + in-grid + 两两不重叠
    occupancy: dict[tuple[int, int], str] = {}
    type_counts: dict[str, int] = {}
    resolved: dict[str, dict] = {}
    for iid, entry in solution.items():
        ftype = str(entry["facility_type"])
        inst = inst_by_id.get(iid)
        if inst is not None and str(inst["facility_type"]) != ftype:
            violations.append({"check": "type_match", "instance": iid,
                               "detail": f"{ftype} != {inst['facility_type']}"})
        pool = pools.get(ftype)
        idx = int(entry["pose_idx"])
        if pool is None or not (0 <= idx < len(pool)):
            violations.append({"check": "pose_range", "instance": iid, "detail": idx})
            continue
        pose = pool[idx]
        resolved[iid] = pose
        type_counts[ftype] = type_counts.get(ftype, 0) + 1
        for cell in pose["occupied_cells"]:
            x, y = int(cell[0]), int(cell[1])
            if not (0 <= x < GRID_W and 0 <= y < GRID_H):
                violations.append({"check": "in_grid", "instance": iid, "cell": [x, y]})
            prev = occupancy.get((x, y))
            if prev is not None:
                violations.append({"check": "overlap", "cell": [x, y],
                                   "instances": [prev, iid]})
            occupancy[(x, y)] = iid

    if not allow_partial and type_counts != EXPECTED_TYPE_COUNTS:
        violations.append({"check": "type_counts", "detail": type_counts})

    # E. ghost 净空（空矩形谓词 = 无本体；带子/接驳格不在其列）
    gx, gy, gw, gh = (int(v) for v in result["ghost"])
    ghost_hits = [
        [x, y]
        for x in range(gx, gx + gw)
        for y in range(gy, gy + gh)
        if (x, y) in occupancy
    ]
    if ghost_hits:
        violations.append({"check": "ghost_clear", "cells": ghost_hits[:10],
                           "n": len(ghost_hits)})

    # F. identity front-clear vs 需求（独立几何谓词：口格=体外第1格）
    checked = 0
    for iid, pose in resolved.items():
        inst = inst_by_id.get(iid)
        if inst is None:
            continue
        op = str(inst["operation_type"])
        demand = DEMANDS.get(op)
        if demand is None:
            continue
        req_in, vis_out = demand
        if req_in <= 0 and vis_out <= 0:
            continue
        free: list[int] = []
        for field in ("input_port_cells", "output_port_cells"):
            n = 0
            for port in pose.get(field) or []:
                x, y = int(port["x"]), int(port["y"])
                if 0 <= x < GRID_W and 0 <= y < GRID_H and (x, y) not in occupancy:
                    n += 1
            free.append(n)
        checked += 1
        if free[0] < req_in or free[1] < vis_out:
            violations.append({"check": "front_clear", "instance": iid,
                               "op": op, "free": free,
                               "demand": [req_in, vis_out]})

    return {
        "auditor": "independent_zero_violation_audit_v1",
        "result_file": str(result_path),
        "pool_sha256": _POOL_SHA256,
        "allow_partial": allow_partial,
        "placed_audited": len(resolved),
        "front_clear_checked": checked,
        "occupied_cells": len(occupancy),
        "violations": violations,
        "pass": not violations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_json", type=Path)
    parser.add_argument("--pool", type=Path,
                        default=Path("data/preprocessed/candidate_placements.json"))
    parser.add_argument("--instances", type=Path,
                        default=Path("data/preprocessed/mandatory_exact_instances.json"))
    parser.add_argument("--allow-partial", action="store_true",
                        help="部分布局（如 cpsat_max 235/266）：跳过 266 全覆盖与全类型计数断言")
    args = parser.parse_args()
    self_test()
    verdict = audit(args.result_json, args.pool, args.instances,
                    allow_partial=args.allow_partial)
    json.dump(verdict, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0 if verdict["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
