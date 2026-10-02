"""Absolute deadlines and remaining-time counters for protocol storage boxes."""
from pathlib import Path
import hashlib
import itertools
import json
import random

OUT = Path(__file__).resolve().parent


def deadlines(c):
    due = c["phase"]
    slots = [[None, 0] for _ in range(6)]
    trace = []
    for t in range(c["steps"]):
        if t in c["offline"] and c["mode"] == "clear":
            due = t
        arrivals = []
        for port, phase in enumerate(c["in_phases"]):
            if t >= phase and (t-phase) % 8 == 0:
                item = 0 if c["physical"] else (t//8+port) % 6
                loc = next(i for i, (kind, n) in enumerate(slots) if n < 50 and (n == 0 or kind == item))
                slots[loc][0] = item
                slots[loc][1] += 1
                arrivals.append(item)
        pre = sum(n for _, n in slots)
        sent = None
        transfer = False
        if c["physical_first"] and c["physical"] and t % 8 == 2:
            j = next((i for i, (_, n) in enumerate(slots) if n), None)
            if j is not None:
                sent = slots[j][0]
                slots[j][1] -= 1
                if not slots[j][1]:
                    slots[j][0] = None
        delivered = 0
        if due <= t:
            delivered = sum(n for _, n in slots)
            slots = [[None, 0] for _ in range(6)]
            transfer = True
            due = t+40
        if not c["physical_first"] and c["physical"] and t % 8 == 2:
            j = next((i for i, (_, n) in enumerate(slots) if n), None)
            if j is not None:
                sent = slots[j][0]
                slots[j][1] -= 1
                if not slots[j][1]:
                    slots[j][0] = None
        trace.append([t, due-t, [s[:] for s in slots], arrivals, pre, transfer, delivered, sent])
    return trace


def countdowns(c):
    wait = c["phase"]+1
    cells = {}
    states = []
    for step in range(c["steps"]):
        wait = max(0, wait-1)
        if step in c["offline"] and c["mode"] == "clear":
            wait = 0
        received = []
        for p in range(3):
            if step >= c["in_phases"][p] and (step-c["in_phases"][p]) % 8 == 0:
                x = 0 if c["physical"] else (step//8+p) % 6
                for box in range(6):
                    if box not in cells:
                        cells[box] = [x, 1]
                        break
                    if cells[box][0] == x and cells[box][1] < 50:
                        cells[box][1] += 1
                        break
                else:
                    raise AssertionError("capacity rejection")
                received.append(x)
        occupied = sum(v[1] for v in cells.values())
        wireless = False
        delivery = 0
        physical_item = None
        actions = ("physical", "wireless") if c["physical_first"] else ("wireless", "physical")
        for action in actions:
            if action == "wireless" and wait == 0:
                delivery = sum(v[1] for v in cells.values())
                cells.clear()
                wait = 40
                wireless = True
            if action == "physical" and c["physical"] and step % 8 == 2 and cells:
                first = min(cells)
                physical_item = cells[first][0]
                cells[first][1] -= 1
                if cells[first][1] == 0:
                    del cells[first]
        states.append([step, wait, [cells.get(i, [None, 0])[:] for i in range(6)],
                       received, occupied, wireless, delivery, physical_item])
    return states


def main():
    rng = random.Random(10137)
    digest = hashlib.sha256()
    cases = pairs = maximum = 0
    # All 512 input phase triples, both cooldown policies, arbitrary erasures.
    for phases in itertools.product(range(8), repeat=3):
        for mode in ("retain", "clear"):
            c = dict(steps=160, phase=rng.randrange(40), mode=mode, in_phases=list(phases),
                     offline=[t for t in range(1, 160) if rng.randrange(31) == 0],
                     physical=bool(rng.randrange(2)), physical_first=bool(rng.randrange(2)))
            a, b = deadlines(c), countdowns(c)
            assert a == b
            assert max(row[4] for row in a) <= 15
            attempts = [row[0] for row in a if row[5]]
            assert all(1 <= v-u <= 40 for u, v in zip(attempts, attempts[1:]))
            for u, v in zip(attempts, attempts[1:]):
                if not any(u < e <= v for e in c["offline"]) or mode == "retain":
                    assert v-u == 40
            maximum = max(maximum, max(row[4] for row in a))
            digest.update(json.dumps(a, separators=(",", ":")).encode())
            cases += 1
            pairs += len(a)
    # A second, combinatorial count, independent of either box implementation.
    enumerated_max = max(sum(sum((t-p) % 8 == 0 for t in range(1, 41)) for p in phases)
                         for phases in itertools.product(range(8), repeat=3))
    assert maximum == enumerated_max == 15
    examples = {}
    for mode in ("retain", "clear"):
        c = dict(steps=105, phase=0, mode=mode, in_phases=[0, 1, 2],
                 offline=[17], physical=False, physical_first=False)
        a, b = deadlines(c), countdowns(c)
        assert a == b
        examples[mode] = dict(config=c, attempts=[r[0] for r in a if r[5]], trace=a)
    assert examples["retain"]["attempts"] == [0, 40, 80]
    assert examples["clear"]["attempts"] == [0, 17, 57, 97]
    result = dict(cases=cases, paired_step_states=pairs, maximum_contents=maximum,
                  independent_40_step_count=enumerated_max,
                  normalized_state_sha256=digest.hexdigest(), examples=examples,
                  scope="Three legal inlet streams and a receptive warehouse; not a full-factory certificate.")
    (OUT/"cooldown_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({k: v for k, v in result.items() if k != "examples"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
