# -*- coding: utf-8 -*-
"""P1.2 spike — 真 cut body sizing cheap gate (2026-06-02 v2, LSB-corrected)

回答 spike close gate 第九审 Finding 5 #2: cut body 的 master 约束 sizing 到底站不站得住。

**v2 修正 (v23 外审 Finding 2)**: v1 的 bitset 解码用了 MSB-first, 而项目真源
`src/cuts/oracles/region_capacity_oracle._encode_region_bitset` 是 **LSB-first**
(`arr[idx//8] |= 1 << (idx % 8)`, idx = x*70 + y)。v1 因此把 region cells 解错,
term 数偏高约 10x (region_capacity 大池子 v1 报 2026, 实际 264)。v2 改 LSB, 数字与
真 oracle 一致。同时 (Finding 1) 改为读**包内** fixture + registry, 不再读外部 v22 zip;
(Finding 4) 补 F9 density_envelope window->pose overlap 真实计数; (Finding 3) 全族
compact vs expanded 都报, scope 不再写成 "只 F1/F9"。

方法 (对真 fixture + 真 registry 直算, 不信 spike telemetry):
  - compact (no-good / witness lowering): 每 cut 锁 witness 那几个 pose, term = literal/witness 数。
  - expanded (full pose-overlap lowering): 每 cut 的几何 cell-set 覆盖的全部 master pose。
    scoped = 限定到 cut 所属 group 的 facility type (真实展开); all = 全类型并集 (宽松上界)。

运行 (**在解包后的 review 包 project/ 根下跑**):
    python docs/research/p1_2_spike_sizing_gate_20260601/sizing_gate.py
依赖 (均为包内文件):
    data/cuts/spike/oracle_emit_fixture_45cert.jsonl
    data/preprocessed/candidate_placements.json
"""
import base64
import collections
import json
import sys
from pathlib import Path

# project 根 = .../project/ (本文件在 project/docs/research/p1_2_spike_sizing_gate_20260601/)
REPO = Path(__file__).resolve().parents[3]
FIXTURE = REPO / "data" / "cuts" / "spike" / "oracle_emit_fixture_45cert.jsonl"
PLACEMENTS = REPO / "data" / "preprocessed" / "candidate_placements.json"

# region_capacity 'boundary_io' -> 真 registry facility type (真实展开按此限定)
GROUP_FACILITY_TYPE = {
    "region_capacity": "boundary_storage_port",
    "power_hitting_set": "power_pole",
    "power_grid_reach": "power_pole",
}


def load_fixture():
    if not FIXTURE.exists():
        sys.exit(
            f"fixture not found: {FIXTURE}\n"
            "本脚本是 review 包内的可复现工件, 须在解包后的 project/ 根下跑 "
            "(master 工作树不含 spike fixture, 它只在 spike 分支 / 包内)。"
        )
    return [json.loads(l) for l in FIXTURE.read_text(encoding="utf-8").splitlines() if l.strip()]


def build_index():
    """cell(x,y) -> {facility_type -> set(pose_idx)}; 另返回全类型并集 + pool sizes。"""
    pools = json.loads(PLACEMENTS.read_bytes().decode("utf-8"))["facility_pools"]
    by_type = collections.defaultdict(lambda: collections.defaultdict(set))
    allset = collections.defaultdict(set)
    g = 0
    for ft in sorted(pools):
        for pose in pools[ft]:
            for c in pose.get("occupied_cells", []):
                by_type[(c[0], c[1])][ft].add(g)
                allset[(c[0], c[1])].add(g)
            g += 1
    return by_type, allset, {k: len(v) for k, v in pools.items()}


def decode_bitset_cells(b64):
    """LSB-first decode, matching region_capacity_oracle._encode_region_bitset:
    encoder does arr[idx//8] |= 1 << (idx % 8), idx = x*70 + y -> cell (x, y)."""
    raw = base64.b64decode(b64)
    out = []
    for bytei, byte in enumerate(raw):
        for biti in range(8):
            if byte & (1 << biti):  # LSB-first
                i = bytei * 8 + biti
                if i < 4900:
                    out.append((i // 70, i % 70))  # idx = x*70 + y
    return out


def overlap_type(by_type, cells, ft):
    u = set()
    for c in cells:
        u |= by_type[c].get(ft, set())
    return len(u)


def overlap_all(allset, cells):
    u = set()
    for c in cells:
        u |= allset[c]
    return len(u)


def cut_cells(rec, p):
    fam = rec["family"]
    if fam == "region_capacity" and p.get("region_cells_bitset_b64"):
        return decode_bitset_cells(p["region_cells_bitset_b64"])
    if fam == "cutset":
        cc = []
        for k in ("side_a_bitset_b64", "side_b_bitset_b64"):
            if p.get(k):
                cc += decode_bitset_cells(p[k])
        return cc
    if fam == "component_reach":
        return [tuple(c) for c in p.get("separator_cells", [])]
    if fam in ("power_hitting_set", "power_grid_reach"):
        return [tuple(c) for c in p.get("facility_cells", [])]
    if fam == "port_exposure":
        return [tuple(p["port_cell"]), tuple(p["front_cell"])]
    return []


def compact_terms(rec, p):
    fam = rec["family"]
    if fam == "port_exposure":
        return 2
    if fam == "pattern_nogood":
        return len(p.get("forbidden_pose_pattern", []))
    if fam == "density_envelope":
        return len(p.get("oracle_assignment_witness", []))
    return max(1, rec.get("literal_count") or 0)


def main():
    recs = load_fixture()
    by_type, allset, pools = build_index()
    print("registry pools:", pools, " total poses:", sum(pools.values()))
    print()

    by = collections.defaultdict(lambda: {"n": 0, "compact": [], "scoped": [], "allt": []})
    for r in recs:
        fam = r["family"]
        p = json.loads(base64.b64decode(r["cert_payload_b64"]))
        cells = cut_cells(r, p)
        ft = GROUP_FACILITY_TYPE.get(fam)
        scoped = overlap_type(by_type, cells, ft) if (cells and ft) else (
            overlap_all(allset, cells) if cells else compact_terms(r, p))
        allt = overlap_all(allset, cells) if cells else compact_terms(r, p)
        by[fam]["n"] += 1
        by[fam]["compact"].append(compact_terms(r, p))
        by[fam]["scoped"].append(scoped)
        by[fam]["allt"].append(allt)

    avg = lambda xs: sum(xs) / len(xs) if xs else 0
    print("逐族 term/cut (LSB-correct): compact=witness/no-good; expanded scoped=限定类型; all=全类型宽松上界")
    print("%-20s %3s %9s %14s %14s" % ("family", "n", "compact", "exp_scoped", "exp_all(ub)"))
    for fam in sorted(by):
        d = by[fam]
        print("%-20s %3d %9.1f %14.1f %14.1f" % (fam, d["n"], avg(d["compact"]), avg(d["scoped"]), avg(d["allt"])))
    print()

    # F9 density_envelope: window_rect -> pose overlap. v23 外审 F4 补测; v24 外审再指出只跑了前 2 条,
    # 这里跑**全部** density_envelope cert, 报 per-window scoped(各 manufacturing type) + all-type 上界 + max。
    mfg_types = [ft for ft in pools if ft.startswith("manufacturing")]
    print("F9 density_envelope window_rect -> pose overlap (全 fixture, scoped mfg + all-type UB):")
    print("  %-16s %6s %8s %10s" % ("window", "mfg-max", "all-type", "cells"))
    f9_scoped_vals, f9_all_vals = [], []
    for r in [x for x in recs if x["family"] == "density_envelope"]:
        p = json.loads(base64.b64decode(r["cert_payload_b64"]))
        wr = p.get("window_rect")
        if not (wr and len(wr) >= 4):
            continue
        x0, y0, w, h = wr[:4]
        cells = [(x, y) for x in range(x0, x0 + w) for y in range(y0, y0 + h) if 0 <= x < 70 and 0 <= y < 70]
        mfg_max = max((overlap_type(by_type, cells, ft) for ft in mfg_types), default=0)
        allt = overlap_all(allset, cells)
        f9_scoped_vals.append(mfg_max)
        f9_all_vals.append(allt)
        print("  %-16s %6d %8d %10d" % (str(wr), mfg_max, allt, len(cells)))
    if f9_scoped_vals:
        print("  F9 scoped(mfg) avg=%.0f max=%d ; all-type UB avg=%.0f max=%d (compact witness 仅 4, 非 window-expanded)"
              % (sum(f9_scoped_vals) / len(f9_scoped_vals), max(f9_scoped_vals),
                 sum(f9_all_vals) / len(f9_all_vals), max(f9_all_vals)))
    print()

    # v24 外审 Finding 1: proto bytes/term 必须按约束类型分 —— 实测 OR-Tools 9.15:
    #   linear (AddLinearConstraint) ~3-4 B/term; BoolOr no-good (AddBoolOr) ~10-11 B/term。
    # 旧版用 4-6 B/term 全局, 对 BoolOr expanded 低估约 2-3x。
    LINEAR_BPT, BOOLOR_BPT = 4.0, 11.0
    def proj(terms_per_cut, bpt):
        gb = terms_per_cut * 100_000 * bpt / 1e9
        return "%.0f term/cut x 100K x %.0f B = %.2f GB" % (terms_per_cut, bpt, gb)
    print("100K proto 投影 (按约束类型分 bytes/term; linear~4, BoolOr~11):")
    print("  compact (全族 1-4 term/cut): 100K -> ~1-4 MB [随便扛, 任何形态]")
    print("  expanded F1/F9 scoped (264-784 term/cut):")
    print("    linear: %s" % proj(784, LINEAR_BPT))
    print("    BoolOr: %s" % proj(784, BOOLOR_BPT))
    print("  expanded all-type UB / routing (F4 5429, F9-alltype 3341 term/cut):")
    print("    BoolOr: %s  /  %s" % (proj(5429, BOOLOR_BPT), proj(3341, BOOLOR_BPT)))
    print()
    print("结论 (LSB-correct, bytes/term-by-kind):")
    print("- compact (witness/no-good) lowering 全 9 族便宜 (~1-4 MB@100K), 任何约束形态。")
    print("- expanded lowering 的 proto 预算**取决于约束类型**: linear ~4 B/term, BoolOr no-good ~11 B/term。")
    print("  fixture F1/F9 scoped max 784 term/cut: linear ~0.3 GB / BoolOr ~0.86 GB; F4 5429 BoolOr ~6 GB。")
    print("- blow-up 是 (region/window x pool-density) x (per-term 字节, 看约束类型) 的函数, 跨**所有**族。")
    print("- P1.3A 硬约束 = 按约束类型分别设 per-cut term cap + cumulative proto budget (linear/BoolOr 不同),")
    print("  且 cap 按 max/p99 不按 family-avg。v1 的 '1.9GB / 只 F1/F9' 是 MSB 解码 bug 的假数字。")


if __name__ == "__main__":
    main()
