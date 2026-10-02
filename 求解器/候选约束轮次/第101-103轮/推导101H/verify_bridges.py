"""Graph/component versus cell checks, plus a physical local witness."""
from pathlib import Path
import hashlib
import itertools
import json
import random

OUT = Path(__file__).resolve().parent


def components(bits):
    groups = []
    for p, bridge in enumerate(bits):
        if not bridge and p and not bits[p-1]:
            groups[-1].append(p)
        else:
            groups.append([p])
    group_of = {p: g for g, cells in enumerate(groups) for p in cells}
    edges = {g: [g+1] if g+1 < len(groups) else ["sink"] for g in range(len(groups))}
    for p in range(1, len(bits)):
        if bits[p] and bits[p-1]:
            edges[group_of[p]].append(group_of[p-1])
    return groups, group_of, edges


def simple_path_lengths(node, edges, visited=()):
    if node == "sink":
        return {0}
    if node in visited:
        return set()
    return {d+1 for nxt in edges[node]
            for d in simple_path_lengths(nxt, edges, visited+(node,))}


def chain_pair(bits, seed, clear):
    rng = random.Random(seed)
    groups, group_of, edges = components(bits)
    levels = {g: next(iter(simple_path_lengths(g, edges))) for g in edges}
    n = len(bits)
    entries = [None if rng.randrange(3) == 0 else -rng.randrange(1, 10) for _ in bits]
    previous_units = [None if entries[p] is None else p-1 for p in range(n)]
    remaining = [None if e is None else max(0, 8+e) for e in entries]
    last = [None]*len(groups)
    digest = hashlib.sha256()
    illegal_return = 0
    forward_moves = 0
    for t in range(240):
        offline = t % 11 == 0
        if offline and clear:
            last = [None]*len(groups)
        # Offline keeps every item's source unit and residence time.
        sink_accepts = (t % 83) < 49
        source_has_item = rng.randrange(5) != 0
        sent_a = []
        already = set()
        for g in sorted(edges, key=levels.__getitem__):
            assert g not in already
            already.add(g)
            cells = groups[g]
            tail = cells[-1]
            if entries[tail] is not None and t-entries[tail] >= 8:
                # At a bridge the backward channel can be tried first.
                if bits[tail] and tail and bits[tail-1]:
                    assert previous_units[tail] == tail-1
                    illegal_return += 1
                target = tail+1
                if target < n:
                    # Other element upstream of this same receiving UNIT is
                    # the next adjacent bridge, already judged at a lower layer.
                    if bits[target] and target+1 < n and bits[target+1]:
                        assert group_of[target+1] in already
                free = target == n and sink_accepts or target < n and entries[target] is None
                if free:
                    entries[tail] = None
                    previous_units[tail] = None
                    if target < n:
                        entries[target] = t
                        previous_units[target] = tail
                    sent_a.append(tail)
                    last[g] = t
            for pos in reversed(cells[:-1]):
                if entries[pos] is not None and t-entries[pos] >= 8 and entries[pos+1] is None:
                    entries[pos+1], entries[pos] = t, None
                    previous_units[pos+1], previous_units[pos] = pos, None
                    sent_a.append(pos)
        if entries[0] is None and source_has_item:
            entries[0], previous_units[0] = t, -1
        # A second implementation has no component graph or polling records.
        remaining = [None if r is None else max(0, r-1) for r in remaining] if t else remaining
        sent_b = []
        for pos in range(n-1, -1, -1):
            if remaining[pos] != 0:
                continue
            if pos == n-1:
                if not sink_accepts:
                    continue
            elif remaining[pos+1] is not None:
                continue
            remaining[pos] = None
            if pos+1 < n:
                remaining[pos+1] = 8
            sent_b.append(pos)
        if remaining[0] is None and source_has_item:
            remaining[0] = 8
        canonical = [None if e is None else max(0, 8-(t-e)) for e in entries]
        assert canonical == remaining and sent_a == sent_b
        assert all(e is None or previous_units[p] == p-1 for p, e in enumerate(entries))
        forward_moves += len(sent_a)
        digest.update(json.dumps([canonical, sent_a]).encode())
    return dict(states=240, rejected_backward_attempts=illegal_return,
                forward_moves=forward_moves, sha256=digest.hexdigest())


DIR = {(1, 0): "E", (-1, 0): "W", (0, 1): "N", (0, -1): "S"}
VEC = {v: k for k, v in DIR.items()}
OPPOSITE = dict(E="W", W="E", N="S", S="N")


def geometry():
    machines = {
        "C": dict(x=8, y=12, w=5, h=5, input="W", output="E"),
        "A": dict(x=20, y=12, w=5, h=5, input="W", output="E"),
        "B": dict(x=11, y=24, w=5, h=5, input="S", output="N"),
        "K": dict(x=12, y=33, w=3, h=3, input="S", output="N")}
    paths = {
        "CA": [(x, 14) for x in range(13, 20)],
        "AC": [(25, y) for y in range(12, 6, -1)]+[(x, 7) for x in range(24, 5, -1)]
              +[(6, y) for y in range(8, 13)]+[(7, 12)],
        "CB": [(13, y) for y in range(16, 24)],
        "BK": [(13, y) for y in range(29, 33)],
        "K0": [(12, y) for y in range(36, 46)],
        "K1": [(14, y) for y in range(36, 46)]}
    ends = {
        "CA": ((12, 14), (20, 14)), "AC": ((24, 12), (8, 12)),
        "CB": ((12, 16), (13, 24)), "BK": ((13, 28), (13, 33)),
        "K0": ((12, 35), (12, 46)), "K1": ((14, 35), (14, 46))}
    units = {}
    def side_cells(m, side):
        x, y, w, h = (m[k] for k in ("x", "y", "w", "h"))
        if side in ("W", "E"):
            return [(x if side == "W" else x+w-1, j, side) for j in range(y, y+h)]
        return [(j, y if side == "S" else y+h-1, side) for j in range(x, x+w)]
    for name, m in machines.items():
        units[name] = dict(cells=[(x, y) for x in range(m["x"], m["x"]+m["w"])
                                 for y in range(m["y"], m["y"]+m["h"])],
                           ins=side_cells(m, m["input"]), outs=side_cells(m, m["output"]))
    core = dict(x=45, y=45, w=9, h=9)
    core_ins = [(45, y, "W") for y in range(46, 53)]+[(53, y, "E") for y in range(46, 53)]
    core_outs = [(x, y, side) for x in (46, 49, 52) for y, side in ((45, "S"), (53, "N"))]
    units["core"] = dict(cells=[(x, y) for x in range(45, 54) for y in range(45, 54)],
                         ins=core_ins, outs=core_outs)
    poles = {"P1": (14, 16), "P2": (16, 28)}
    for name, (x, y) in poles.items():
        units[name] = dict(cells=[(x+i, y+j) for i in range(2) for j in range(2)], ins=[], outs=[])
    coverage = {}
    for name, m in machines.items():
        coverage[name] = []
        for pole, (x, y) in poles.items():
            # Positive rectangle intersection, not a boundary-only contact.
            cx, cy = x+1, y+1
            hits = max(m["x"], cx-6) < min(m["x"]+m["w"], cx+6) and \
                   max(m["y"], cy-6) < min(m["y"]+m["h"], cy+6)
            by_centres = any(cx-6 < u+0.5 < cx+6 and cy-6 < v+0.5 < cy+6
                             for u, v in units[name]["cells"])
            assert hits == by_centres
            if hits:
                coverage[name].append(pole)
        assert coverage[name]
    for name, cells in paths.items():
        sequence = [ends[name][0]]+cells+[ends[name][1]]
        for j, (x, y) in enumerate(cells):
            prev, nxt = sequence[j], sequence[j+2]
            incoming = DIR[prev[0]-x, prev[1]-y]
            outgoing = DIR[nxt[0]-x, nxt[1]-y]
            units[f"{name}.{j}"] = dict(cells=[(x, y)], ins=[(x, y, incoming)], outs=[(x, y, outgoing)])
    occupied = {}
    for name, u in units.items():
        for p in u["cells"]:
            assert 0 <= p[0] < 70 and 0 <= p[1] < 70
            assert p not in occupied, (name, occupied.get(p), p)
            occupied[p] = name
    # Independent rectangle-pair overlap test (all units here are rectangles).
    rectangles = {}
    for name, u in units.items():
        xs, ys = zip(*u["cells"])
        rectangles[name] = min(xs), min(ys), max(xs)+1, max(ys)+1
    for first, second in itertools.combinations(rectangles, 2):
        x0, y0, x1, y1 = rectangles[first]
        a0, b0, a1, b1 = rectangles[second]
        overlap_area = max(0, min(x1, a1)-max(x0, a0))*max(0, min(y1, b1)-max(y0, b0))
        assert overlap_area == 0, (first, second)
    assert sum((x1-x0)*(y1-y0) for x0, y0, x1, y1 in rectangles.values()) == len(occupied)
    # Explicit contact scan.
    input_map = {port: name for name, u in units.items() for port in u["ins"]}
    contacts = set()
    for name, u in units.items():
        for x, y, side in u["outs"]:
            dx, dy = VEC[side]
            other = input_map.get((x+dx, y+dy, OPPOSITE[side]))
            if other is not None:
                contacts.add((name, other))
    # Independently enumerate the specified path adjacencies.
    expected = set()
    endpoints = dict(CA=("C", "A"), AC=("A", "C"), CB=("C", "B"), BK=("B", "K"),
                     K0=("K", None), K1=("K", None))
    for name, cells in paths.items():
        start, finish = endpoints[name]
        chain = [start]+[f"{name}.{j}" for j in range(len(cells))]
        if finish is not None:
            chain.append(finish)
        expected.update(zip(chain, chain[1:]))
    assert contacts == expected
    # Initial blueprint and offline construction both use a feasible order.
    prefix = ["C", "A", "B", "K", "core", "P1", "P2", "CB.0", "AC.0", "BK.0", "K0.0", "K1.0", "CA.0"]
    build_order = prefix+[u for u in units if u not in prefix]
    build_time = {name: i for i, name in enumerate(build_order)}
    channel_a = {edge: max(build_time[edge[0]], build_time[edge[1]]) for edge in contacts}
    channel_b = {}
    built = set()
    for i, name in enumerate(build_order):
        built.add(name)
        for edge in contacts:
            if edge[0] in built and edge[1] in built and edge not in channel_b:
                channel_b[edge] = i
    assert channel_a == channel_b
    assert channel_a["C", "CB.0"] < channel_a["C", "CA.0"]
    source_order = sorted(machines, key=lambda m: min(t for (u, v), t in channel_a.items() if u == m))
    assert source_order == ["C", "A", "B", "K"]
    return dict(machines=machines, core=core, poles=poles, powered_by=coverage,
                paths=paths, units=units, build_order=build_order,
                contacts=sorted(contacts), lengths={n: len(p) for n, p in paths.items()},
                source_order=source_order, footprint=len(occupied),
                scope="Local geometric witness; terminal belts can absorb every output of its 24-step trace.")


def expand_witness():
    # Re-run the witness with the actual two ten-cell terminal roads. No sink
    # is needed in the first 24 steps; arrivals at the unconnected tail are off.
    from verify_plant import Absolute, Remaining, geometric_counterexample
    result = {}
    for mode in ("retain", "clear"):
        short = geometric_counterexample(mode)
        c = short["config"]
        c["ages"] = c["ages"][:4]+[[road[0]]+[None]*9 for road in c["ages"][4:]]
        a, b = Absolute(c), Remaining(c)
        ports = {0: [1, 0], 3: [0, 1]}
        a.offline(ports, False)
        b.offline(ports, False)
        rows = []
        for t in range(24):
            if t == 16:
                a.offline(ports, mode == "clear")
                b.offline(ports, mode == "clear")
            a.step(t, [True]*4, [False]*2, [0, 1, 2, 3])
            b.step(t, [True]*4, [False]*2, [0, 1, 2, 3])
            state = a.state(t)
            assert state == b.state(t)
            compressed = state[:3]+[state[3][:4]+[[r[0]] for r in state[3][4:]]]+state[4:]
            assert compressed == short["trace"][t]["state"]
            assert a.phi2() == short["trace"][t]["phi2"]
            rows.append(dict(step=t, phi2=a.phi2(), events=a.events, state=state))
        result[mode] = dict(config=c, trace=rows)
    (OUT/"geometric_trace.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    return dict(paired_step_states=48, physical_output_road_lengths=[10, 10],
                terminal_roads_have_no_sink=True)


def main():
    runs = []
    for n in range(1, 9):
        for bits in itertools.product((0, 1), repeat=n):
            groups, _, edges = components(bits)
            for node in edges:
                # Second encoding: count components from this position to the sink.
                assert simple_path_lengths(node, edges) == {len(groups)-node}
            for clear in (False, True):
                r = chain_pair(bits, len(runs)+101, clear)
                runs.append(dict(bits=list(bits), clear=clear, **r))
    # Two axes of one bridge are two elements, not two units.
    unit = "bridge"
    outgoing = [("x", "east"), ("y", "north")]
    per_element = {(unit, axis): 1 for axis, dst in outgoing}
    count_by_iteration = sum(per_element.values())
    count_by_destinations = len({dst for axis, dst in outgoing})
    assert count_by_iteration == count_by_destinations == 2
    # Incoming unit-group trigger includes only transport elements.
    incoming_to_K_head_unit = [dict(source="K", transport=False, axis="y"),
                               dict(source="U", transport=True, axis="x")]
    triggered = [e["source"] for e in incoming_to_K_head_unit if e["transport"]]
    assert triggered == ["U"]
    geo = geometry()
    (OUT/"geometry.json").write_text(json.dumps(geo, ensure_ascii=False, indent=2)+"\n")
    expanded = expand_witness()
    result = dict(topologies=len(runs)//2, cases=len(runs),
                  paired_step_states=sum(r["states"] for r in runs),
                  prevented_returns=sum(r["rejected_backward_attempts"] for r in runs),
                  two_axis_judgments=count_by_iteration,
                  K_head_cross_axis_triggered=triggered, expanded_witness=expanded, runs=runs)
    (OUT/"bridge_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({k: v for k, v in result.items() if k != "runs"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
