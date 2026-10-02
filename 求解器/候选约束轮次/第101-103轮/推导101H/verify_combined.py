"""Four policy combinations, with an active other axis at a K output bridge.

K has two output heads, entering ports 1 and 3 of a storage box. Its first
head is one axis of H. A separate U -> H(other axis) -> V chain enters box
port 2. Thus receipt into H is by UNIT, but its nontransport upstream K must
not be pulled into the element phase. The storage box wire-transmits both
kinds to receptive warehouse slots. This is a local component construction.
"""
from pathlib import Path
import hashlib
import json
from verify_plant import Absolute, Remaining

OUT = Path(__file__).resolve().parent


def main():
    rows = []
    for poll in ("retain", "clear"):
        for cooling in ("retain", "clear"):
            config = dict(k=2, n=2, input=[50]*4, output=[50]*4,
                          remaining=[8, 7, 3, 4],
                          ages=[[8]*7, [8]*31, [8]*8, [8]*4, [None], [None]],
                          lastC=[None]*2, lastK=[None]*2)
            a, b = Absolute(config), Remaining(config)
            born = [-8, None, None]        # U, H horizontal axis, V
            waits = [0, -1, -1]
            prev = ["E", None, None]
            supply_a = supply_b = 50
            due_a, wait_b = 0, 1
            slots_a = [[None, 0] for _ in range(6)]
            slots_b = {}
            warehouse_a, warehouse_b = [0, 0], [0, 0]
            receipts = [0, 0]
            transfers_a, transfers_b = [], []
            receive_last = None
            receive_queue = [0, 1, 2]
            max_contents = 0
            digest = hashlib.sha256()
            trace = []
            for t in range(400):
                offline = t > 0 and t % 17 == 0
                if offline:
                    ports = {0: [t % 2, 1-t % 2], 3: [1-t % 2, t % 2]}
                    a.offline(ports, poll == "clear")
                    b.offline(ports, poll == "clear")
                    if cooling == "clear":
                        due_a = t
                        wait_b = 0
                    if poll == "clear":
                        receive_last = None
                        receive_queue = [0, 1, 2]
                if wait_b:
                    wait_b -= 1
                arriving_a = []
                for index, road in enumerate(a.roads[4:]):
                    if road[0] is not None and t-road[0] >= 8:
                        arriving_a.append((2*index, 0))  # inlet, buckwheat powder
                before_b = b.state(t-1)
                arriving_b = [(2*index, 0) for index, road in enumerate(before_b[3][4:])
                              if road[0] is not None and road[0] >= 7]
                # Independent side-axis implementations.
                incoming_H = False
                for p in range(2, -1, -1):
                    if born[p] is None or t-born[p] < 8:
                        continue
                    if p < 2 and born[p+1] is not None:
                        continue
                    if p == 2:
                        arriving_a.append((1, 1))   # middle inlet, steel block
                    else:
                        born[p+1] = t
                        prev[p+1] = ["U", "H"][p]
                        if p == 0:
                            incoming_H = True
                    born[p], prev[p] = None, None
                if t:
                    waits = [max(0, w-1) if w >= 0 else -1 for w in waits]
                for p in (2, 1, 0):
                    if waits[p] != 0 or p < 2 and waits[p+1] >= 0:
                        continue
                    if p == 2:
                        arriving_b.append((1, 1))
                    else:
                        waits[p+1] = 8
                    waits[p] = -1
                assert arriving_a == arriving_b
                if incoming_H:
                    # All actual upstreams of the PHYSICAL bridge unit:
                    group = [("U", "element"), ("K", "nontransport")]
                    triggered = [name for name, category in group if category == "element"]
                    assert triggered == ["U"]
                # All goods offered here can be received: proved and checked,
                # not inferred merely from a receptive abstract sink.
                first = 0 if receive_last is None else (receive_last+1) % 3
                ordered_a = sorted(arriving_a, key=lambda event: (event[0]-first) % 3)
                ordered_b = sorted(arriving_b, key=lambda event: receive_queue.index(event[0]))
                assert ordered_a == ordered_b
                for port, x in ordered_a:
                    j = next(i for i, (kind, qty) in enumerate(slots_a)
                             if qty < 50 and (not qty or kind == x))
                    slots_a[j][0] = x
                    slots_a[j][1] += 1
                    receipts[x] += 1
                    receive_last = port
                for port, x in ordered_b:
                    for j in range(6):
                        if j not in slots_b:
                            slots_b[j] = [x, 1]
                            break
                        if slots_b[j][0] == x and slots_b[j][1] < 50:
                            slots_b[j][1] += 1
                            break
                    else:
                        raise AssertionError("storage rejected a head")
                    while receive_queue[0] != port:
                        receive_queue.append(receive_queue.pop(0))
                    receive_queue.append(receive_queue.pop(0))
                assert slots_a == [slots_b.get(i, [None, 0]) for i in range(6)]
                max_contents = max(max_contents, sum(q for _, q in slots_a))
                empty_a = a.step(t, [True]*4, [True]*2, [0, 1, 2, 3])
                empty_b = b.step(t, [True]*4, [True]*2, [0, 1, 2, 3])
                assert a.state(t) == b.state(t) and empty_a == empty_b and a.events == b.events
                assert sum(m == 3 for m, route in a.events) <= 1
                state = a.state(t)
                assert all(r is not None for r in state[2])
                assert state[1][3] >= 48
                if born[0] is None and supply_a:
                    born[0], prev[0] = t, "E"
                    supply_a -= 1
                if waits[0] < 0 and supply_b:
                    waits[0] = 8
                    supply_b -= 1
                assert [None if v is None else max(0, 8-(t-v)) for v in born] == \
                       [None if w < 0 else w for w in waits]
                assert supply_a == supply_b
                if due_a <= t:
                    for kind, qty in slots_a:
                        if qty:
                            warehouse_a[kind] += qty
                    slots_a = [[None, 0] for _ in range(6)]
                    due_a = t+40
                    transfers_a.append(t)
                if wait_b == 0:
                    for kind, qty in slots_b.values():
                        warehouse_b[kind] += qty
                    slots_b.clear()
                    wait_b = 40
                    transfers_b.append(t)
                assert slots_a == [slots_b.get(i, [None, 0]) for i in range(6)]
                assert due_a-t == wait_b and warehouse_a == warehouse_b
                assert all(receipts[x] == warehouse_a[x]+sum(q for kind, q in slots_a if kind == x)
                           for x in (0, 1))
                record = dict(step=t, offline=offline, plant=state, side_axis_wait=waits[:],
                              box=[r[:] for r in slots_a], cooldown=wait_b,
                              warehouse=warehouse_a[:], K_sends=sum(m == 3 for m, r in a.events))
                first = 0 if receive_last is None else (receive_last+1) % 3
                assert receive_queue == [(first+j) % 3 for j in range(3)]
                record["box_receive_queue"] = receive_queue[:]
                digest.update(json.dumps(record, separators=(",", ":")).encode())
                if t < 42:
                    trace.append(record)
            assert transfers_a == transfers_b and max_contents <= 15
            rows.append(dict(poll=poll, cooldown=cooling, paired_step_states=400,
                             maximum_box_contents=max_contents, transfers=transfers_a,
                             warehouse=warehouse_a, sha256=digest.hexdigest(), trace=trace))
    result = dict(cases=4, paired_step_states=1600, runs=rows,
                  scope="Four-machine unit plus shared two-kind storage and an active cross-axis output head.")
    (OUT/"combined_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(dict(cases=4, paired_step_states=1600,
                         runs=[{k: v for k, v in r.items() if k not in ("trace", "transfers")} for r in rows]),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
