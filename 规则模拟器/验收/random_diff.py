"""Generate the same 200 v1 script files from gold layouts and compare both executables."""
import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from common import GOLD, ROOT, build, compact, equal, outputs

SEED = 0x5EED20261128
MASK = (1 << 64) - 1
DIR = ROOT / "验收" / "随机输入"
ITEMS = "源矿 源石粉末 致密源石粉末 蓝铁矿 蓝铁块 蓝铁粉末 致密蓝铁粉末 钢块 钢质瓶 钢制零件 荞花种子 荞花 荞花粉末 细磨荞花粉末 砂叶种子 砂叶 砂叶粉末 高容谷地电池 精选荞愈胶囊".split()
MATERIALS = {
    "粉碎机": ["源矿", "砂叶"], "精炼炉": ["蓝铁矿"], "研磨机": ["蓝铁粉末", "砂叶粉末"],
    "塑形机": ["钢块"], "配件机": ["钢块"], "种植机": ["荞花种子"], "采种机": ["砂叶"],
    "封装机": ["钢制零件", "致密源石粉末"], "灌装机": ["钢质瓶", "细磨荞花粉末"],
}
TRANSPORT = {"传送带", "物品准入口", "分流器", "汇流器", "桥接器格"}


class RNG:
    """xorshift64*, using explicit unsigned 64-bit arithmetic."""
    def __init__(self, seed):
        self.state = seed

    def below(self, n):
        x = self.state
        x ^= x >> 12
        x ^= (x << 25) & MASK
        x ^= x >> 27
        self.state = x
        return ((x * 2685821657736338717) & MASK) % n

    def pick(self, seq):
        return seq[self.below(len(seq))]

    def shuffle(self, seq):
        for i in range(len(seq) - 1, 0, -1):
            j = self.below(i + 1)
            seq[i], seq[j] = seq[j], seq[i]


def network(events):
    kinds, edges = {}, []
    for op, *args in events:
        if op == "建成":
            u, kind = args
            kinds[u] = kind
        elif op == "接通":
            edges.append(tuple(args[0]))
        elif op == "重接":
            ch = tuple(args[0])
            edges.remove(ch)
            edges.append(ch)
        elif op == "拆除":
            del kinds[args[0]]
            edges = [ch for ch in edges if args[0] not in ch]
        else:
            raise ValueError(op)
    return kinds, edges


def fingerprint(kinds, edges):
    # Distinct fingerprints guarantee distinct graphs even under renumbering.
    degrees = [(k, sum(b == u for a, b in edges), sum(a == u for a, b in edges))
               for u, k in kinds.items()]
    return tuple(sorted(degrees)), tuple(sorted((kinds[a], kinds[b]) for a, b in edges))


def layouts(rng):
    candidates = []
    for p in sorted(GOLD.glob("*.json")):
        group = []
        for i, s in enumerate(json.loads(p.read_bytes())["段"], 1):
            kinds, edges = network(s["历史"])
            if not (2 <= len(edges) and len(kinds) <= 26):
                continue
            if not any(k in MATERIALS or k == "协议储存箱" for k in kinds.values()):
                continue
            group.append((fingerprint(kinds, edges), p.stem, i, s, kinds, edges))
        rng.shuffle(group)
        candidates.append(group)
    chosen, seen = [], set()
    # Include every kind available in these gold layouts (also core and warehouse
    # outlets), then vary the topology among files with the remaining slots.
    all_cases = [case for group in candidates for case in group]
    uncovered = {kind for case in all_cases for kind in case[4].values()}
    while uncovered:
        case = max(all_cases, key=lambda c: len(uncovered.intersection(c[4].values())))
        chosen.append(case[1:])
        seen.add(case[0])
        uncovered.difference_update(case[4].values())
    # Round robin among source files to avoid selecting only one family of layouts.
    while len(chosen) < 25:
        size = len(chosen)
        for group in candidates:
            while group:
                key, *case = group.pop()
                if key not in seen:
                    seen.add(key)
                    chosen.append(case)
                    break
            if len(chosen) == 25:
                break
        if size == len(chosen):
            raise ValueError("黄金布局不足")
    return chosen


def reorder(kinds, edges, rng):
    build = [["建成", u, k] for u, k in sorted(kinds.items())]
    connect = [["接通", [a, b]] for a, b in edges]
    rng.shuffle(build)
    rng.shuffle(connect)
    if [e[1] for e in build] == list(kinds) and [tuple(e[1]) for e in connect] == edges:
        connect[0], connect[1] = connect[1], connect[0]
    return build + connect


def generate(case, rng, case_id):
    name, index, original, kinds, edges = case
    s = {k: deepcopy(original[k]) for k in ("历史", "端口", "未定")}
    s["备注"] = f"黄金/{name}.json 第 {index} 段，随机脚本 {case_id}"
    ordered = sorted(kinds)
    machines = [u for u in ordered if kinds[u] in MATERIALS]
    boxes = [u for u in ordered if kinds[u] == "协议储存箱"]
    gates = [u for u in ordered if kinds[u] == "物品准入口"]
    outlets = [(u, i) for u in ordered for i in range(
        {"协议核心": 6, "仓库取货口": 1}.get(kinds[u], 0))]
    powered = sorted(machines + boxes)
    s["供电"] = [u for u in powered if rng.below(4) != 0]
    policy = s["未定"]
    for k in ["离线后的计数", "改设定后的计数"]:
        policy[k] = [rng.pick(["保留", "清空"]) for _ in range(2)]
    for entry in policy["传输排在几组之后"]:
        entry[1] = rng.below(5)
    policy["输入判定都没货时"] = rng.pick(["每步判两次", "不收", "都收", "再判一次", "轮到的那条"])

    item = rng.pick(ITEMS)
    cargo, stopped = [], []
    for u in ordered:
        k = kinds[u]
        if k in TRANSPORT:
            if rng.below(3) == 0:
                cell = [u, ["格", 0]]
                cargo.append([cell, [[rng.pick([item, rng.pick(ITEMS)]), 1]]])
                stopped.append([cell, rng.below(9)])
        elif k == "协议储存箱":
            cell = [u, ["格", rng.below(6)]]
            cargo.append([cell, [[rng.pick([item, rng.pick(ITEMS)]), 1 + rng.below(50)]]])
        elif k in MATERIALS:
            for i, raw in enumerate(MATERIALS[k][:2] if k in ("研磨机", "封装机", "灌装机") else [rng.pick(MATERIALS[k])]):
                cargo.append([[u, ["存货", i]], [[raw, 1 + rng.below(50)]]])
        elif k not in {"仓库取货口", "协议核心"}:
            raise ValueError(k)
    s["状态"] = {
        "货": cargo, "已停": stopped, "仓库": [[x, 2000 + rng.below(2000)] for x in ITEMS],
        "取货指向": [[list(port), rng.pick(ITEMS)] for port in outlets],
        "储存箱": [[u, {"仓储模式": bool(rng.below(2)), "冷却还剩": rng.below(41)}] for u in boxes],
        "准入口": [[u, {"放行": item, "拍": rng.below(4)}] for u in gates],
    }
    ops = []
    # Every script includes deposits, withdrawals, switch changes and a genuine
    # offline reorder. Their interleaving and the lengths of walking windows vary.
    changes = [["入库", rng.pick(ITEMS), 1 + rng.below(30)],
               ["出库", rng.pick(ITEMS), 1 + rng.below(30)],
               ["拨开关", [rng.pick(powered)], bool(rng.below(2))],
               ["放货", rng.pick(powered), item, 1 + rng.below(90)],
               ["离线", reorder(kinds, edges, rng)]]
    if boxes:
        changes.append(["设储存箱模式", rng.pick(boxes), bool(rng.below(2))])
    if gates:
        changes.append(["设准入口", rng.pick(gates), item, 1 + rng.below(80), rng.below(6)])
    if outlets:
        u, port = rng.pick(outlets)
        changes.append(["设取货指向", u, port, rng.pick(ITEMS)])
    changes.extend([["放货", rng.pick(powered), rng.pick(ITEMS), 1 + rng.below(60)],
                    ["拨开关", [rng.pick(powered)], True]])
    rng.shuffle(changes)
    # Positive walking windows add up to exactly 300 model steps.
    cuts = set()
    while len(cuts) < len(changes):
        cuts.add(1 + rng.below(299))
    last = 0
    for cut, change in zip(sorted(cuts), changes, strict=True):
        ops.extend([["走", cut - last], change])
        last = cut
    ops.append(["走", 300 - last])
    s["操作"] = ops
    return {"版本": 1, "段": [s]}


def verify(p):
    rust, lean = outputs(p)
    equal(p.name, rust, lean)
    rows = rust.count(b"\n")
    ops = json.loads(p.read_bytes())["段"][0]["操作"]
    steps = sum(op[1] for op in ops if op[0] == "走")
    assert steps == 300 and rows == steps + sum(op[0] != "走" for op in ops), p
    return rows


if __name__ == "__main__":
    build()
    rng = RNG(SEED)
    cases = layouts(rng)
    DIR.mkdir(exist_ok=True)
    files = []
    for i in range(200):
        p = DIR / f"{i + 1:03}.json"
        doc = generate(cases[i % len(cases)], rng, i + 1)
        p.write_text(compact(doc) + "\n", encoding="utf-8")
        files.append(p)
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = sum(pool.map(verify, files))
    print(f"种子 {SEED:#x}，{len(cases)} 种布局，{len(files)} 份 × 300 步，{rows} 行，0 差异")
