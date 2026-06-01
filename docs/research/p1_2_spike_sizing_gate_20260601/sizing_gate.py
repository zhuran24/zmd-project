# -*- coding: utf-8 -*-
"""P1.2 spike — 真 cut body sizing cheap gate (2026-06-01)

回答 spike close gate 第九审的 Finding 5 #2: "true cut body distribution sizing"
到底站不站得住。结论: cut body 的 master 约束大小不是一个固定可测的事实, 而是个
~1000x 的设计变量, 完全取决于 lowering 方式, 且整个风险集中在 F1/F9 两族。

方法 (不信 spike telemetry, 直接对真 fixture + 真 registry 算):
  1. 从送审 v22 包读 GPT 实际审的 50-cert fixture。
  2. 载真 prod candidate_placements.json (81,795 pose), 建 cell->pose(按类型) 索引。
  3. 每族算两种 lowering 下 master 约束的 term 数:
       - compact no-good: 只锁 witness 那几个 pose (= literal/witness count, 1-4)
       - expanded: 该 cut 几何相关的全部 pose, **按 cut 所属设施类型限定**
  4. 投影 100K, 对照 spike 实测的合成 3-literal (19.55 MB proto)。

运行: python docs/research/p1_2_spike_sizing_gate_20260601/sizing_gate.py
依赖: cc_context/review/phase1_2_spike_review_v22.zip (fixture 源)
      data/preprocessed/candidate_placements.json (真 registry)
"""
import base64
import collections
import json
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ZIP = REPO / "cc_context" / "review" / "phase1_2_spike_review_v22.zip"
PLACEMENTS = REPO / "data" / "preprocessed" / "candidate_placements.json"
FIXTURE_IN_ZIP = "_phase1_2_pkg_v22/project/data/cuts/spike/oracle_emit_fixture_45cert.jsonl"

# region_capacity 的 contributing group 'boundary_io' -> 真 registry 的设施类型
GROUP_FACILITY_TYPE = {
    "region_capacity": "boundary_storage_port",
    "power_hitting_set": "power_pole",
    "power_grid_reach": "power_pole",
}


def load_fixture():
    z = zipfile.ZipFile(ZIP)
    txt = z.read(FIXTURE_IN_ZIP).decode("utf-8")
    return [json.loads(l) for l in txt.splitlines() if l.strip()]


def build_index():
    """cell(r,c) -> {facility_type -> set(pose_global_idx)}; 返回 (index, pool_sizes)."""
    pl = json.loads(PLACEMENTS.read_bytes().decode("utf-8"))
    pools = pl["facility_pools"]
    idx = collections.defaultdict(lambda: collections.defaultdict(set))
    g = 0
    for ft in sorted(pools):
        for pose in pools[ft]:
            for c in pose.get("occupied_cells", []):
                idx[(c[0], c[1])][ft].add(g)
            g += 1
    return idx, {k: len(v) for k, v in pools.items()}


def decode_bitset_cells(b64):
    """613-byte bitset over 70x70, MSB-first. -> [(r,c)] of set bits."""
    raw = base64.b64decode(b64)
    out = []
    for bytei, byte in enumerate(raw):
        for biti in range(8):
            if byte & (1 << (7 - biti)):
                i = bytei * 8 + biti
                if i < 4900:
                    out.append((i // 70, i % 70))
    return out


def overlap(idx, cells, ft):
    """| union of poses of type ft touching any cell |."""
    u = set()
    for c in cells:
        u |= idx.get((c[0], c[1]), {}).get(ft, set())
    return len(u)


def cut_cells(rec, payload):
    """该 cut 的几何 cell-set (用于 expanded lowering 的 term 计数)。"""
    fam = rec["family"]
    if fam == "region_capacity" and payload.get("region_cells_bitset_b64"):
        return decode_bitset_cells(payload["region_cells_bitset_b64"])
    if fam == "component_reach":
        return [tuple(c) for c in payload.get("separator_cells", [])]
    if fam == "cutset":
        cc = []
        for k in ("side_a_bitset_b64", "side_b_bitset_b64"):
            if payload.get(k):
                cc += decode_bitset_cells(payload[k])
        return cc
    if fam in ("power_hitting_set", "power_grid_reach"):
        return [tuple(c) for c in payload.get("facility_cells", [])]
    if fam == "port_exposure":
        return [tuple(payload["port_cell"]), tuple(payload["front_cell"])]
    return []


def compact_terms(rec, payload):
    """compact no-good lowering 的 term 数 = witness/literal count。"""
    fam = rec["family"]
    if fam == "port_exposure":
        return 2
    if fam == "pattern_nogood":
        return len(payload.get("forbidden_pose_pattern", []))
    if fam == "density_envelope":
        return len(payload.get("oracle_assignment_witness", []))
    return max(1, rec.get("literal_count") or 0)


def main():
    recs = load_fixture()
    idx, pools = build_index()
    print("registry pools:", pools)
    print("total poses:", sum(pools.values()))
    print()

    by = collections.defaultdict(lambda: {"n": 0, "compact": [], "expanded": []})
    for r in recs:
        fam = r["family"]
        p = json.loads(base64.b64decode(r["cert_payload_b64"]))
        cells = cut_cells(r, p)
        ft = GROUP_FACILITY_TYPE.get(fam)
        if cells and ft:
            exp = overlap(idx, cells, ft)
        elif cells:
            # 无明确类型映射 (routing 族): 取全类型并集作宽松上界
            exp = len(set().union(*(idx.get(c, {}).get(t, set())
                                    for c in cells for t in pools)) if cells else set())
        else:
            exp = compact_terms(r, p)
        by[fam]["n"] += 1
        by[fam]["compact"].append(compact_terms(r, p))
        by[fam]["expanded"].append(exp)

    avg = lambda xs: sum(xs) / len(xs) if xs else 0
    print("%-20s %3s %10s %14s" % ("family", "n", "compact", "expanded(scoped)"))
    for fam in sorted(by):
        d = by[fam]
        print("%-20s %3d %10.1f %14.1f" % (fam, d["n"], avg(d["compact"]), avg(d["expanded"])))
    print()

    # 大池子容量 cut 上界: 同一 139 格区域落到各类型
    rc = next(r for r in recs if r["family"] == "region_capacity")
    rc_cells = decode_bitset_cells(json.loads(base64.b64decode(rc["cert_payload_b64"]))["region_cells_bitset_b64"])
    print("大池子容量 cut 上界 (139 格区域 x 各设施类型 pose 覆盖):")
    for ft in sorted(pools):
        print("  %-22s pool=%6d  overlap=%6d" % (ft, pools[ft], overlap(idx, rc_cells, ft)))
    print()
    print("100K 投影 (proto ~ terms x 6 bytes):")
    print("  compact no-good   (~1-4 term/cut)   : 100K -> ~0.1-0.4M term -> ~1-3 MB")
    print("  expanded 小池子    (~16-68 term/cut) : 100K -> ~2-7M term     -> ~10-40 MB")
    print("  expanded 大池子    (~2-3K term/cut)  : 100K -> ~200-320M term -> ~1.2-1.9 GB  <-- 爆")
    print("  spike 实测合成 3-literal             : 100K -> ~300K term     -> 19.55 MB")


if __name__ == "__main__":
    main()
