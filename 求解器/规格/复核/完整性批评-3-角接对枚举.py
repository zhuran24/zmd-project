#!/usr/bin/env python3
# 完整性批评（第三次）§四.4 的可复现脚本：枚举三个样例里
# connection.port_meeting 两个取值会给出不同 PC 集合的端口对。
# 本版 shared_edge_opposite 只承认「闭单位边段全长重合」；
# 待审 closed_segment_touch 还承认「闭边段非空相交」（含仅共一个角点）。
# 本脚本独立读目录与样例，不调用 check_examples.py。
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]          # 求解器/
CATALOG = ROOT / "数据" / "正式静态目录.json"
SAMPLES = ["混做粉碎机两下游", "桥接器双通路", "分流器三路轮询"]

CCW = ["north", "west", "south", "east"]                    # 逆时针
OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}


def quantity(x):
    """目录里的数字是 {value, category} 封套。"""
    return int(x["value"]) if isinstance(x, dict) else int(x)


def rotate_cell(a, b, w, h, r):
    """内核输入 §2.1 的逆时针换码。"""
    return {"r0": (a, b), "r90": (h - 1 - b, a),
            "r180": (w - 1 - a, h - 1 - b), "r270": (b, w - 1 - a)}[r]


def rotate_facing(side, r):
    return CCW[(CCW.index(side) + {"r0": 0, "r90": 1, "r180": 2, "r270": 3}[r]) % 4]


def edge_segment(x, y, facing):
    """端口所在格的那一条闭单位边段，用两个格点表示。"""
    return {"north": ((x, y + 1), (x + 1, y + 1)), "south": ((x, y), (x + 1, y)),
            "east": ((x + 1, y), (x + 1, y + 1)), "west": ((x, y), (x, y + 1))}[facing]


def collect_ports(sample, units):
    ports = []
    for inst in sample["layout"]["units"]:
        spec = units[inst["kind"]]
        w = quantity(spec["dimensions"]["width"])
        h = quantity(spec["dimensions"]["height"])
        ox, oy = quantity(inst["origin"][0]), quantity(inst["origin"][1])
        r = inst["rotation"]
        layout = spec["ports"]["layouts"][inst.get("port_layout") or 0]
        for group in layout:
            side, role = group["side"], group["role"]
            for position in group["positions"]:
                p = quantity(position)
                a, b = {"south": (p, 0), "north": (p, h - 1),
                        "west": (0, p), "east": (w - 1, p)}[side]
                u, v = rotate_cell(a, b, w, h, r)
                ports.append({
                    "unit": inst["id"], "family": spec.get("family"), "role": role,
                    "cell": (ox + u, oy + v), "facing": rotate_facing(side, r),
                    "label": "%s:%s:%d" % (inst["id"], side, p),
                })
    return ports


def main():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = {u["id"]: u for u in catalog["units"]}
    report = {}
    for name in SAMPLES:
        sample = json.loads((ROOT / "数据" / "样例" / (name + ".json")).read_text(encoding="utf-8"))
        ports = collect_ports(sample, units)
        corner = []
        for a in ports:
            if a["role"] != "output":
                continue
            for b in ports:
                # 角色互补、法向相反、至少一端运输：两个取值共用的守卫
                if b["unit"] == a["unit"] or b["role"] != "input":
                    continue
                if b["facing"] != OPPOSITE[a["facing"]]:
                    continue
                if not (a["family"] == "transport" or b["family"] == "transport"):
                    continue
                sa = set(edge_segment(*a["cell"], a["facing"]))
                sb = set(edge_segment(*b["cell"], b["facing"]))
                if sa == sb:
                    continue                      # 全长重合：本版已计为 PC
                if sa & sb:                       # 仅相交（本例均为共一个角点）
                    corner.append([a["label"], b["label"], sorted(sa & sb)])
        report[name] = {
            "本版PC": len(sample["layout"].get("physical_channels", [])),
            "closed_segment_touch新增有向PC": len(corner),
            "明细": corner,
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
