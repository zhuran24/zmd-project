"""python3 独立对拍.py [--rust PATH] [--inputs DIR]"""
import argparse
import hashlib
import json
import random
import subprocess
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIM = HERE.parents[1]
MODEL = SIM.parent / "规则模型"
SEED = 0xC4D5A17
ITEMS = "源矿 源石粉末 致密源石粉末 蓝铁矿 蓝铁块 蓝铁粉末 致密蓝铁粉末 钢块 钢质瓶 钢制零件 荞花种子 荞花 荞花粉末 细磨荞花粉末 砂叶种子 砂叶 砂叶粉末 高容谷地电池 精选荞愈胶囊".split()


def graph(history):
    units, edges = {}, []
    for tag, *v in history:
        if tag == "建成":
            units[v[0]] = v[1]
        elif tag == "拆除":
            del units[v[0]]
            edges = [edge for edge in edges if v[0] not in edge]
        elif tag in ("接通", "重接"):
            if tag == "重接":
                edges.remove(v[0])
            edges.append(v[0])
        else:
            raise ValueError(tag)
    return units, edges


def catalog():
    buckets = defaultdict(list)
    for path in sorted((MODEL / "对拍/黄金").glob("*.json")):
        for i, seg in enumerate(json.loads(path.read_bytes())["段"]):
            units, edges = graph(seg["历史"])
            if not (edges and len(units) <= 17 and "协议储存箱" in units.values() and seg["期望"]):
                continue
            key = tuple(sorted(units.values()))
            buckets[key].append((path.name, i, seg))
    return buckets


def new_history(units, edges, rng):
    ids = rng.sample(sorted(units), len(units))
    pending = list(edges)
    built = set()
    history = []
    # Interleave early connections with building. Include a removed prefix and a reconnect.
    history.extend([["建成", ids[-1], "桥接器格"], ["拆除", ids[-1]]])
    for u in ids:
        history.append(["建成", u, units[u]])
        built.add(u)
        ready = [e for e in pending if set(e) <= built]
        for e in rng.sample(ready, rng.randrange(len(ready) + 1)):
            history.append(["接通", e])
            pending.remove(e)
    history.extend(["接通", e] for e in rng.sample(pending, len(pending)))
    history.append(["重接", rng.choice(edges)])
    return history


def generate(case, rng):
    file, i, original = case
    seg = deepcopy(original)
    row = rng.randrange(len(seg["期望"]))
    state = seg.pop("期望")[row]
    remaining = row + 1
    for op in seg["操作"]:
        if op[0] == "离线":
            seg["历史"] = op[1]
        remaining -= op[1] if op[0] == "走" else 1
        if remaining <= 0:
            break
    seg["备注"] = f"{file} 第{i+1}段第{row+1}行"
    units, edges = graph(seg["历史"])
    boxes = [u for u in units if units[u] == "协议储存箱"]
    powered = [u for u, k in units.items() if k in {
        "协议储存箱", "粉碎机", "精炼炉", "研磨机", "塑形机", "配件机", "种植机", "采种机", "封装机", "灌装机"}]
    gates = [u for u in units if units[u] == "物品准入口"]
    ports = [(u, p) for u, k in units.items() for p in range({"协议核心": 6, "仓库取货口": 1}.get(k, 0))]
    box = rng.choice(boxes)
    key = [box, ["格", rng.randrange(6)]]
    cargo = [entry for entry in state.get("货", []) if entry[0] != key]
    cargo.append([key, [[rng.choice(ITEMS), rng.choice([1, 7, 49, 50])]]])
    # Preserve model order within all other units, insert just this box slot in order.
    cargo.sort(key=lambda p: (p[0][0], p[0][1][1] if p[0][0] == box else 0))
    state["货"] = cargo
    state["仓库"] = [[x, rng.randrange(3000, 5000)] for x in ITEMS]
    seg["状态"] = state
    policy = seg["未定"]
    for k in ("离线后的计数", "改设定后的计数"):
        policy[k] = rng.choices(["保留", "清空"], k=2)
    policy["输入判定都没货时"] = rng.choice(["每步判两次", "轮到的那条", "都收", "再判一次", "不收"])
    ops = []
    seg["操作"] = ops
    previous = 0
    for cut in sorted(rng.sample(range(1, 300), 7)):
        box, item = rng.choice(boxes), rng.choice(ITEMS)
        changes = [
            [["拨开关", [rng.choice(powered)], rng.choice([False, True])]],
            [["离线", new_history(units, edges, rng)]],
            [["放货", box, item, rng.choice([1, 49, 51, 107])], ["收货", [box, ["格", 0]]]],
            [["设储存箱模式", box, rng.choice([True, False])]],
            [["入库", item, rng.randrange(1, 15)]],
            [["出库", rng.choice(ITEMS), rng.randrange(1, 15)]],
        ]
        if gates:
            u = rng.choice(gates)
            changes.append([["设准入口", u, item, rng.randint(1, 50), rng.randrange(6)], ["重置计数", u]])
        if ports:
            u, p = rng.choice(ports)
            changes.append([["设取货指向", u, p, rng.choice([None, item])]])
        changes.append([["走", cut - previous]])
        rng.shuffle(changes)
        ops.extend(action for group in changes for action in group)
        previous = cut
    ops.append(["走", 300 - previous])
    return {"版本": 1, "段": [seg]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rust", type=Path, default=SIM / "target/release/endfield-sim")
    parser.add_argument("--inputs", type=Path)
    args = parser.parse_args()
    rng = random.Random(SEED)
    buckets = catalog()
    # Reserve a stratum for warehouse targets on a core and on an outlet.
    keys = [rng.choice([k for k in sorted(buckets) if kind in k])
            for kind in ("协议核心", "仓库取货口")]
    keys = list(dict.fromkeys(keys))
    keys += rng.sample([k for k in sorted(buckets) if k not in keys], 25 - len(keys))
    counts = Counter()
    digest = hashlib.sha256()
    with tempfile.TemporaryDirectory() as tmp:
        dest = (args.inputs or Path(tmp)).resolve()
        dest.mkdir(exist_ok=True, parents=True)
        jobs = []
        for i in range(200):
            s = generate(rng.choice(buckets[keys[i % len(keys)]]), rng)
            payload = (json.dumps(s, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
            digest.update(payload)
            path = dest / f"{i+1:03}.json"
            path.write_bytes(payload)
            ops = s["段"][0]["操作"]
            steps = sum(op[1] for op in ops if op[0] == "走")
            assert steps == 300
            counts.update(op[0] for op in ops if op[0] != "走")
            jobs.append((path, steps + sum(op[0] != "走" for op in ops)))

        def verify(job):
            path, lines = job
            actual, oracle = [subprocess.run([*cmd, path], cwd=MODEL, capture_output=True, timeout=180)
                              for cmd in [[args.rust.resolve()], ["lake", "exe", "对拍"]]]
            if (actual.returncode or oracle.returncode or actual.stdout != oracle.stdout
                    or oracle.stdout.count(b"\n") != lines):
                (HERE / ("差异-" + path.name)).write_bytes(path.read_bytes())
                raise RuntimeError(path.name, actual.returncode, oracle.returncode, actual.stderr, oracle.stderr)
            return lines

        with ThreadPoolExecutor(4) as pool:
            rows = sum(pool.map(verify, jobs))
    print(f"{SEED:#x} 25 种 × 8 份 × 300 步，{rows} 行，0 差异。")
    print(dict(sorted(counts.items())), digest.hexdigest())


if __name__ == "__main__":
    main()
