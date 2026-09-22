"""复算报告中的局部逐 tick 算术；不是整厂模拟器或 kernel 运行结果。

只创建同目录下此前不存在的 JSON/LOG 文件，不写工作区其他位置。
"""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def save(name, value):
    with (HERE / name).open("x", encoding="utf-8") as out:
        json.dump(value, out, ensure_ascii=False, indent=2)
        out.write("\n")


source_names = [
    "《明日方舟：终末地》游戏规则.txt",
    "求解任务.txt",
    "求解约束.txt",
    "求解器/规格/推导/三种相位不改产量.md",
]
save("inputs.json", {
    "scope": "局部时序算术复算，不是完整布局、可达性证书或 kernel 核对",
    "sources": [{"path": s, "sha256": hashlib.sha256((ROOT / s).read_bytes()).hexdigest()} for s in source_names],
    "continuous_filler": {"duration": 5, "use_each": 10, "initial_before_start_each": 12,
                          "arrivals_odd_each": 3, "arrivals_even_each": 1, "last_tick": 10},
    "three_fillers": {"duration": 5, "use_each": 10, "initial_after_start_each": [0, 0, 0],
                      "arrivals_AB_each": 2, "arrivals_C_odd_each": 2, "arrivals_C_even_each": 1,
                      "last_tick": 40},
    "gate_sliding_window": {"limit": 2, "offered_ticks": [0, 4, 5, 6]},
    "gate_intermittent": {"limit": 2, "offered_ticks": list(range(0, 21, 5))},
    "two_gates": {"limits": [1, 1], "window_origins": [0, 0],
                  "at_tick_0": {"front_belt": "P1", "gate_A": "P0", "gate_B": "Q0"},
                  "P1_ready_to_leave_front": 1},
    "parts_backlog": {"manufacture_duration": 1, "output_capacity": 50, "gate_limit": 1,
                      "initial_completion_tick": 0, "last_tick": 70}
})

continuous = [{"tick": 0, "incoming_each": None, "before_start_each": 12,
               "after_each": 2, "start": True, "complete": False}]
q = 2
due = 5
for t in range(1, 11):
    a = 3 if t % 2 else 1
    q += a
    done = t == due
    pre = q if done else None
    if done:
        assert q >= 10
        q -= 10
        due = t + 5
    assert 0 <= q <= 50
    continuous.append({"tick": t, "incoming_each": a, "before_start_each": pre,
                       "after_each": q, "start": done, "complete": done})
assert [r["before_start_each"] for r in continuous if r["start"]] == [12, 13, 12]
save("continuous_filler.json", continuous)

q = [0, 0, 0]
due = [5, 5, 5]
counts = [0, 0, 0]
three = [{"tick": 0, "incoming_each": [None]*3, "stock_each_after": q.copy(),
          "starts": [True]*3, "before_start_each": [10]*3,
          "completions": [False]*3, "due": due.copy(), "completed_totals": counts.copy()}]
for t in range(1, 41):
    incoming = [2, 2, 2 if t % 2 else 1]
    starts, done, pre = [False]*3, [False]*3, [None]*3
    for i in range(3):
        q[i] += incoming[i]
        if due[i] == t:
            done[i] = True
            counts[i] += 1
            due[i] = None
        if due[i] is None and q[i] >= 10:
            starts[i] = True
            pre[i] = q[i]
            q[i] -= 10
            due[i] = t + 5
        assert 0 <= q[i] <= 50
    three.append({"tick": t, "incoming_each": incoming, "stock_each_after": q.copy(),
                  "starts": starts, "before_start_each": pre, "completions": done,
                  "due": due.copy(), "completed_totals": counts.copy()})
assert three[20]["completed_totals"] == [4, 4, 3]
assert three[40]["completed_totals"] == [8, 8, 6]
assert [r["tick"] for r in three[:21] if r["starts"][2]] == [0, 7, 13, 20]
assert [r["before_start_each"][2] for r in three[:21] if r["starts"][2]] == [10, 11, 10, 10]
for t in range(21):
    a, b = three[t], three[t + 20]
    assert a["stock_each_after"] == b["stock_each_after"]
    assert [None if d is None else d-t for d in a["due"]] == [None if d is None else d-t-20 for d in b["due"]]
save("three_fillers.json", three)


def gate_trace(offered, k):
    start, used, held = None, 0, None
    rows = []
    for t in range(max(offered) + 2):
        leave = held is not None and held + 1 <= t
        if leave:
            held = None
        if start is not None and t >= start + 5:
            start, used = None, 0
        accepted = False
        if t in offered:
            assert held is None and used < k
            if start is None:
                start = t
            used += 1
            held = t
            accepted = True
        rows.append({"tick": t, "offered": t in offered, "accept": accepted,
                     "leave": leave, "window_start": start, "used": used})
    return rows


sliding = gate_trace([0, 4, 5, 6], 2)
assert sum(r["accept"] for r in sliding if 4 <= r["tick"] < 9) == 3
save("gate_sliding_window.json", sliding)
intermittent = gate_trace(list(range(0, 21, 5)), 2)
assert sum(r["accept"] for r in intermittent if 0 <= r["tick"] < 20) == 4
save("gate_intermittent.json", intermittent)

# 已在相同相位运行的两只准入口；每格滞留至少 1 tick。
# t=0 的三件物品分别在前带、A、B 中。后续每 5 tick 源头再出一件。
front, A, B = ("P1", 0), ("P0", 0), ("Q0", 0)
next_A, next_B = 5, 5
serial = []
delivered_P1 = None
for t in range(12):
    actions = []
    if B is not None and B[1] + 1 <= t:
        actions.append(f"{B[0]}:B->sink")
        if B[0] == "P1":
            delivered_P1 = t
        B = None
    if A is not None and A[1] + 1 <= t and B is None and t >= next_B:
        actions.append(f"{A[0]}:A->B")
        B = (A[0], t)
        A = None
        next_B = t + 5
    if front is not None and front[1] + 1 <= t and A is None and t >= next_A:
        actions.append(f"{front[0]}:front->A")
        A = (front[0], t)
        front = None
        next_A = t + 5
    if t and t % 5 == 0:
        assert front is None
        front = (f"P{t//5+1}", t)
        actions.append(f"{front[0]}:source->front")
    serial.append({"tick": t, "actions": actions, "front": front, "A": A, "B": B,
                   "next_A": next_A, "next_B": next_B})
assert delivered_P1 == 11
assert delivered_P1 - 3 == 8
save("serial_gates.json", serial)

q, pending, due = 0, False, 0
backlog = []
first_block = None
for t in range(71):
    done = due == t
    if done:
        assert not pending
        pending = True
        due = None
    # 先尝试整批出缓存，再尝试通道，再重试出缓存/开工。
    if pending and q < 50:
        q += 1
        pending = False
    admitted = t % 5 == 0 and q > 0
    if admitted:
        q -= 1
    if pending and q < 50:
        q += 1
        pending = False
    if pending and first_block is None:
        first_block = t
    if due is None and not pending:
        due = t + 1
    backlog.append({"tick": t, "completion": done, "gate_admit": admitted,
                    "output_stock": q, "completed_in_cache": int(pending), "next_due": due})
assert first_block == 63
assert backlog[62]["output_stock"] == 50 and backlog[63]["completed_in_cache"] == 1
save("parts_backlog.json", backlog)

checks = {
    "continuous_start_stock": [12, 13, 12],
    "third_filler_starts_0_to_20": [0, 7, 13, 20],
    "third_filler_prestart_stock": [10, 11, 10, 10],
    "three_filler_completions_in_0_open_20_closed": [4, 4, 3],
    "three_filler_state_period": 20,
    "gate_limit_2_in_sliding_4_to_9": 3,
    "intermittent_gate_limit_2_actual_per_20": 4,
    "serial_P1_delivery_tick": 11,
    "serial_extra_delay_against_empty_unlimited_path": 8,
    "parts_first_completed_batch_block_tick": first_block,
    "kernel_run": False,
    "whole_layout_or_phase_dependent_long_run_counterexample": False,
}
save("checks.json", checks)
with (HERE / "checks.log").open("x", encoding="utf-8") as log:
    log.write(json.dumps(checks, ensure_ascii=False, indent=2) + "\nall assertions passed\n")
print(json.dumps(checks, ensure_ascii=False, indent=2))
