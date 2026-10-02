"""Two fresh encodings of polling and wireless cooldown; no foreign imports."""
from itertools import permutations, product
from pathlib import Path
from random import Random
import json

OUT = Path(__file__).resolve().parent

def polling(k, initial, arrivals, offline, mode, external=None):
    # A: absolute vacancy deadlines and last-success timestamps.
    q = initial
    next_free = [0]*k
    last = [None]*k
    connection = list(range(k))
    # B: occupancy countdowns and an explicit never-success/oldest-first list.
    inventory = initial
    hold = [0]*k
    never = list(range(k))
    queue = []
    trace, count = [], [0]*k
    prefix = [tuple(count)]
    segments = [0]
    for t, batch in enumerate(arrivals):
        hold = [max(v-1, 0) for v in hold]
        if t in offline:
            connection = list(offline[t])
            if mode == 'clear':
                last = [None]*k
                never = list(connection)
                queue = []
            else:
                never = [j for j in connection if last[j] is None]
            segments.append(t)
        q += batch
        inventory += batch
        if external and external[t] and q:
            q -= 1
            inventory -= 1
            a = b = None
        else:
            priority = sorted(range(k), key=lambda j: (0, connection.index(j)) if last[j] is None else (1, last[j]))
            a = next((j for j in priority if q and next_free[j] <= t), None)
            b = next((j for j in never+queue if inventory and hold[j] == 0), None)
            if a is not None:
                q -= 1
                last[a] = t
                next_free[a] = t+8
            if b is not None:
                inventory -= 1
                hold[b] = 8
                if b in never:
                    never.remove(b)
                else:
                    queue.remove(b)
                queue.append(b)
        assert a == b and q == inventory
        assert [max(f-t, 0) for f in next_free] == hold
        if a is not None:
            count[a] += 1
            trace.append([t,a])
        prefix.append(tuple(count))
    return trace, prefix, sorted(set(segments+[len(arrivals)]))

def diameter(prefix, k):
    return max((max(v[i]-v[j] for v in prefix)-min(v[i]-v[j] for v in prefix)
                for i in range(k) for j in range(k)), default=0)

def polling_cases():
    rng = Random(10220261002)
    checked = steps = 0
    max_blocks = 0
    max_segments = 0
    for k in range(1,7):
        for sample in range(50):
            length = 480
            arrivals = [0]*length
            if sample % 2:
                # H05: delayed integer batches; queue capacity relaxed on purpose.
                for t in range(rng.randrange(8), length, 8):
                    if rng.randrange(3):
                        arrivals[t] = k
                initial = rng.randrange(50)
                external = None
                batch_mode = True
            else:
                # H03: consecutive 8-step groups have sum <= k.
                prev = 0
                for t in range(0,length,8):
                    now = rng.randrange(k-prev+1)
                    arrivals[t] = now
                    prev = now
                initial = 0
                external = [rng.randrange(5) == 0 for _ in range(length)]
                batch_mode = False
            offline = {}
            for t in range(1, length):
                if sample % 5 == 0 or rng.randrange(29) == 0:
                    p = list(range(k))
                    rng.shuffle(p)
                    offline[t] = p
            for mode in ['retain','clear']:
                trace, prefix, segments = polling(k,initial,arrivals,offline,mode,external)
                whole = diameter(prefix,k)
                if mode == 'retain':
                    assert whole <= 1
                if batch_mode:
                    assert whole <= 2
                    max_blocks = max(max_blocks,whole)
                for left,right in zip(segments,segments[1:]):
                    d = diameter(prefix[left:right+1],k)
                    assert d <= 1
                    max_segments = max(max_segments,d)
                # Independent sampled subinterval count, with exact boundary count.
                for _ in range(20):
                    lo = rng.randrange(length)
                    hi = rng.randrange(lo+1,length+1)
                    resets = sum(lo < t < hi for t in offline)
                    counts = [prefix[hi][j]-prefix[lo][j] for j in range(k)]
                    assert max(counts)-min(counts) <= resets+1
                checked += 1
                steps += length
    one = [1 if t % 8 == 0 else 0 for t in range(160)]
    reset = {t:[0,1,2] for t in range(8,160,8)}
    one_clear = polling(3,0,one,reset,'clear')[0]
    one_retain = polling(3,0,one,reset,'retain')[0]
    two = [0]*50
    two[0] = two[40] = 3
    clear = polling(3,0,two,{30:[2,1,0]},'clear')[0]
    retain = polling(3,0,two,{30:[2,1,0]},'retain')[0]
    assert [j for t,j in clear] == [0,1,2,2,1,0]
    assert [j for t,j in retain] == [0,1,2,0,1,2]
    assert [sum(j==c for t,j in one_clear) for c in range(3)] == [20,0,0]
    return dict(cases=checked, compared_steps=steps, max_block_diameter=max_blocks,
                max_segment_diameter=max_segments, single_piece_clear=one_clear,
                single_piece_retain=one_retain,batch_clear=clear,batch_retain=retain)

def cooldown_cases():
    cases = states = 0
    overall_max = 0
    phase_example = {}
    # A uses a deadline, B a remaining cooldown. Components deposit before box.
    for residues in product(range(8), repeat=3):
        for clear in [False, True]:
            due, remaining = 0, 0
            a, b = 0, 0
            attempts_a, attempts_b = [], []
            incoming = wireless = 0
            for t in range(160):
                if t:
                    remaining = max(0, remaining-1)
                if clear and t in [17,53,54,103]:
                    due = t
                    remaining = 0
                arrivals = sum(t % 8 == r for r in residues)
                a += arrivals
                b += arrivals
                incoming += arrivals
                if attempts_a:
                    assert a <= 15
                overall_max = max(overall_max,a)
                if t >= due:
                    attempts_a.append(t)
                    wireless += a
                    a = 0
                    due = t+40
                if remaining == 0:
                    attempts_b.append(t)
                    b = 0
                    remaining = 40
                assert a == b and max(due-t,0) == remaining
                assert incoming == wireless+a
                states += 1
            assert attempts_a == attempts_b
            cases += 1
    for clear in [False,True]:
        due=0
        attempts=[]
        for t in range(101):
            if clear and t==17:
                due=t
            if t>=due:
                attempts.append(t)
                due=t+40
        phase_example['clear' if clear else 'retain']=attempts
    return dict(cases=cases, compared_steps=states, max_before_transfer=overall_max,
                one_offline_at_17=phase_example)

def main():
    result = dict(polling=polling_cases(),cooldown=cooldown_cases())
    (OUT/'interfaces.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:{a:b for a,b in v.items() if not isinstance(b,list)} for k,v in result.items()},ensure_ascii=False))

if __name__ == '__main__':
    main()
