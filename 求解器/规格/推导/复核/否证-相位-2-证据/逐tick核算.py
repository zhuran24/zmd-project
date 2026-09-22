"""正式条目下的局部计数复核；不调用 kernel，不宣称完整布局可达性。

只在本目录新建 JSON、LOG；拒绝覆盖任何既有输出。
"""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
INPUTS = [
    "《明日方舟：终末地》游戏规则.txt",
    "求解任务.txt",
    "求解约束.txt",
    "求解器/规格/推导/三种相位不改产量.md",
]


def fillers():
    machines = [{"stock": [10, 10], "finish": None} for _ in range(3)]
    rows, starts, completions = [], [[], [], []], [[], [], []]
    for t in range(21):
        events = []
        for i, m in enumerate(machines):
            if m["finish"] == t:
                completions[i].append(t)
                m["finish"] = None
            delivery = ([2, 2] if i < 2 else [2, 1] if t % 2 else [1, 2]) if t else [0, 0]
            m["stock"] = [a + b for a, b in zip(m["stock"], delivery)]
            before = list(m["stock"])
            start = m["finish"] is None and min(before) >= 10
            if start:
                starts[i].append({"tick": t, "before": before})
                m["stock"] = [a - 10 for a in before]
                m["finish"] = t + 5
            assert all(0 <= a <= 50 for a in m["stock"])
            events.append({"machine": i + 1, "arrival": delivery, "before_start_check": before,
                           "start": start, "end_stock": list(m["stock"]), "finish_due": m["finish"]})
        rows.append({"tick": t, "machines": events})
    assert starts[2] == [
        {"tick": 0, "before": [10, 10]}, {"tick": 7, "before": [11, 10]},
        {"tick": 14, "before": [11, 11]}, {"tick": 20, "before": [10, 10]},
    ]
    assert [len(x) for x in completions] == [4, 4, 3]
    assert all(row["machines"][2]["end_stock"] == [0, 0] for row in (rows[0], rows[20]))
    return {"boundary": "机器1、2各两条瓶线两条粉线；机器3一条瓶线一条粉线一条瓶粉交替混线；成品及时取走。到货表不是完整上游布局。",
            "rows": rows, "starts": starts, "completions_in_0_open_20_closed": completions}


def round_robin_types():
    records = []
    for pointer in [0, 1]:
        counts = [{"荞花": 0, "砂叶": 0} for _ in range(2)]
        rows = []
        for t in range(12):
            item = "荞花" if t % 2 == 0 else "砂叶"
            port = (pointer + t) % 2
            counts[port][item] += 1
            rows.append({"tick": t, "item": item, "port": port + 1, "next_pointer": 1 - port + 1})
        assert [sum(c.values()) for c in counts] == [6, 6]
        records.append({"initial_pointer": pointer + 1, "rows": rows, "counts": counts})
    return {"boundary": "种植机逐tick交替出两种植株；两个同级首带只收该机、收后恰1tick腾空。各接可加工两种植株的粉碎机。", "runs": records}


def head_block(pointer):
    # A=蓝铁粉末；B=砂叶粉末；研磨配方为2A+1B。
    order = ["A1", "A2", "B"]
    stock, h, finish, output = [50, 0], None, None, 0
    rows = []
    for t in range(13):
        completed = finish == t
        if completed:
            output += 1
            finish = None
        delivered = None
        if h is not None and h[1] < t:
            kind = 0 if h[0].startswith("A") else 1
            if stock[kind] < 50:
                delivered = h[0]
                stock[kind] += 1
                h = None
        start = finish is None and stock[0] >= 2 and stock[1] >= 1
        if start:
            stock[0] -= 2
            stock[1] -= 1
            finish = t + 1
        admitted = None
        if h is None:
            admitted = order[pointer]
            h = (admitted, t)
            pointer = (pointer + 1) % 3
        rows.append({"tick": t, "delivered": delivered, "start": start,
                     "completed": completed, "admitted_to_merger": admitted,
                     "merger": h[0], "stock_A_B": list(stock), "completed_total": output})
    return rows


def gate_accept(arrivals, k):
    anchor, used, rows = None, 0, []
    for t in arrivals:
        if anchor is None or t - anchor >= 5:
            anchor, used = t, 0
        assert used < k
        used += 1
        rows.append({"tick": t, "anchor": anchor, "used": used, "leave": t + 1})
    return rows


def serial_delays():
    gates = [dict(k=1, s=0, c=1, at=0, item="I0"),
             dict(k=1, s=-1, c=1, at=None, item=None)]
    rows, pending = [], False
    for t in range(11):
        if t == 1:
            pending = True
        a, b = gates
        out, moved, accepted = None, None, None
        if b["at"] is not None and b["at"] < t:
            out, b["at"], b["item"] = b["item"], None, None
        if a["at"] is not None and a["at"] < t and b["at"] is None and t - b["s"] >= 5:
            moved = a["item"]
            b.update(s=t, c=1, at=t, item=moved)
            a.update(at=None, item=None)
        if pending and a["at"] is None and t - a["s"] >= 5:
            accepted, pending = "I1", False
            a.update(s=t, c=1, at=t, item="I1")
        rows.append({"tick": t, "source_pending": pending, "gate1_accept": accepted,
                     "gate1_to_gate2": moved, "sink_receives": out,
                     "gate1_item": a["item"], "gate2_item": b["item"],
                     "anchors": [a["s"], b["s"]]})
    assert next(r["tick"] for r in rows if r["sink_receives"] == "I1") == 10
    return rows


def saturated_serial(k1, k2, s1, s2):
    gates = [dict(k=k1, s=s1, c=k1, at=None), dict(k=k2, s=s2, c=k2, at=None)]
    count = 0
    for t in range(2000):
        a, b = gates
        if b["at"] is not None and b["at"] < t:
            b["at"] = None
            count += t >= 1000
        if a["at"] is not None and a["at"] < t and b["at"] is None and (t-b["s"] >= 5 or b["c"] < b["k"]):
            a["at"] = None
            if t-b["s"] >= 5:
                b.update(s=t, c=0)
            b["c"] += 1
            b["at"] = t
        if a["at"] is None and (t-a["s"] >= 5 or a["c"] < a["k"]):
            if t-a["s"] >= 5:
                a.update(s=t, c=0)
            a["c"] += 1
            a["at"] = t
    return count


def crusher_backlog():
    stock, completed_cache, next_finish = 0, False, 0
    rows = []
    for t in range(71):
        if next_finish == t:
            completed_cache, next_finish = True, None
        initially_blocked = completed_cache and stock == 50
        if completed_cache and stock < 50:
            stock += 1
            completed_cache, next_finish = False, t + 1
        send = t % 5 == 0 and stock > 0
        if send:
            stock -= 1
        if completed_cache and stock < 50:
            stock += 1
            completed_cache, next_finish = False, t + 1
        rows.append({"tick": t, "gate_accept": int(send), "output_stock": stock,
                     "completed_batch_in_cache": int(completed_cache), "blocked_on_completion": initially_blocked})
    assert next(r["tick"] for r in rows if r["completed_batch_in_cache"]) == 63
    return rows


def main():
    targets = [HERE / "输入与结果.json", HERE / "核算.log"]
    assert all(not p.exists() for p in targets), "拒绝覆盖既有文件"
    hashes = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in INPUTS}
    blocked, live = head_block(0), head_block(2)
    assert all(r["stock_A_B"] == [50, 0] and not r["start"] for r in blocked)
    assert [r["tick"] for r in live if r["start"]] == [1, 4, 7, 10]
    window = gate_accept([0, 4, 5, 6], 2)
    assert sum(4 <= r["tick"] < 9 for r in window) == 3
    sparse = gate_accept(list(range(0, 101, 10)), 2)
    serial_checks, bad = 0, []
    for k1 in range(1, 6):
        for k2 in range(1, 6):
            for s1 in range(-4, 1):
                for s2 in range(-4, 1):
                    count = saturated_serial(k1, k2, s1, s2)
                    serial_checks += 1
                    if count != min(k1, k2) * 200:
                        bad.append([k1, k2, s1, s2, count])
    assert not bad
    result = {
        "scope": "局部条目核算；未调用kernel；外部供料表和及时出货是明列的边界，不是70x70整厂布局证书。",
        "source_sha256": hashes,
        "three_fillers": fillers(),
        "round_robin_item_types": round_robin_types(),
        "head_of_line": {"boundary": "三个源经独立首带给汇流器供A1、A2、B；源持续可供仅用于局部活分支周期；死锁分支不需要持续供给。",
                         "pointer_A1": blocked, "pointer_B": live},
        "gate_non_sliding_window": window,
        "gate_sparse_input": sparse,
        "two_serial_gates_delay": serial_delays(),
        "two_serial_gates_saturated_probe": {"cases": serial_checks, "ticks_per_case": 2000,
                                              "count_interval": "1000 <= t < 2000", "deviations": bad,
                                              "limitation": "只覆盖这个局部贪心次序、初始两格为空且旧窗口额度用尽的625例；不是一般证明。"},
        "crusher_before_k1_gate": crusher_backlog(),
    }
    with targets[0].open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with targets[1].open("x", encoding="utf-8") as f:
        f.write("局部算术断言全部通过。三灌装机完成4+4+3批；第三台开工前库存不恒定。\n")
        f.write("滑动5tick窗口有3件通过k=2门；串联示例I1从tick1等到tick10送达。\n")
        f.write("满速粉碎机接k=1门时tick63首次完成品留在缓存格。\n")
        f.write(f"饱和双门局部核算{serial_checks}例未发现稳态计数偏离min(k1,k2)/5。\n")
        f.write("未运行kernel，未证明全厂两种相位的可达循环态产率不同。\n")
    print(json.dumps({"written": [str(p) for p in targets], "checks": "passed", "serial_probe_cases": serial_checks}, ensure_ascii=False))


if __name__ == "__main__":
    main()
