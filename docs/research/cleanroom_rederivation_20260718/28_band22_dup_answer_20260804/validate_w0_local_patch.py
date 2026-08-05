#!/usr/bin/env python3
"""Standard-library validator for the local hole-1/hole-3 coordinate patch.

It validates arithmetic, body disjointness, documented route-set counts, core
front coordinates, endpoint port geometry, and strict component signatures.
It intentionally does not validate power coverage, operation-instance binding,
or the full-board connectivity predicates.
"""
from __future__ import annotations

import json
from pathlib import Path
from math import floor

BASE = Path(__file__).resolve().parent
PATCH_PATH = BASE / "w0_band22_local_patch_01_03.json"
AUTH_PATH = BASE / "authority_06_problem_instance.json"

patch = json.loads(PATCH_PATH.read_text(encoding="utf-8"))
auth = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
assert auth["grid"] == {"height": 70, "width": 70}
assert auth["sentinels"]["required_body_area"] == 3544
assert auth["sentinels"]["manufacturing_instance_count"] == 219

heights = patch["band_heights"]
c = patch["corridor_y"]
assert len(heights) == 14 and len(c) == 15
assert c[0] == 1 and c[-1] == 69
for i,h in enumerate(heights, start=1):
    assert c[i] - c[i-1] - 1 == h
assert sorted(heights) == sorted([3]*6+[4]*4+[5]*4)

width_for_height = {3:3, 4:6, 5:5}
body_cells: set[tuple[int,int]] = set()
risers: set[tuple[int,int]] = set()
counts = {3:0,4:0,5:0}
for b in patch["bands"]:
    i=b["band"]
    lo,hi=b["y"]
    h=b["height"]
    assert [lo,hi] == [c[i-1]+1,c[i]-1]
    assert h == hi-lo+1 == heights[i-1]
    w=width_for_height[h]
    assert b["template"] == f"manufacturing_{w}x{h}"
    starts=b["x_starts"]
    assert len(starts) == b["count"]
    counts[h] += len(starts)
    for x0 in starts:
        cells={(x,y) for x in range(x0,x0+w) for y in range(lo,hi+1)}
        assert min(x for x,_ in cells) >= 0 and max(x for x,_ in cells) <= 69
        assert not body_cells.intersection(cells)
        body_cells |= cells
    rx=b["riser_or_slit_x"]
    rcells={(rx,y) for y in range(lo,hi+1)}
    assert not body_cells.intersection(rcells)
    risers |= rcells
assert counts == {3:132,4:38,5:49}

core_anchor=patch["core"]["anchor"]
assert core_anchor == [61,60]
core={(x,y) for x in range(61,70) for y in range(60,69)}
assert not body_cells.intersection(core)
assert not risers.intersection(core)

# Derive authoritative core fronts.
mode=next(m for m in auth["facility_templates"]["protocol_core"]["modes"] if m["id"]==patch["core"]["mode"])
delta={"N":(0,1),"S":(0,-1),"E":(1,0),"W":(-1,0)}
expected={}
for port in mode["ports"]:
    bx=core_anchor[0]+port["body_cell"]["x"]
    by=core_anchor[1]+port["body_cell"]["y"]
    dx,dy=delta[port["direction"]]
    expected[port["id"]]=(port["kind"],port["direction"],[bx+dx,by+dy])
seen={}
for p in patch["core"]["fronts"]:
    assert p["id"] in expected
    assert (p["kind"],p["direction"],p["front"]) == expected[p["id"]]
    seen[p["id"]]=p
assert set(seen)==set(expected)
assert sum(p["active"] and p["kind"]=="input" for p in seen.values()) == 2
assert sum(p["active"] and p["kind"]=="output" for p in seen.values()) == 6

hole=patch["hole"]["rectangle"]
hole_cells={(x,y) for x in range(hole["x"][0],hole["x"][1]+1)
                    for y in range(hole["y"][0],hole["y"][1]+1)}
assert len(hole_cells)==42
assert not body_cells.intersection(hole_cells)
assert not core.intersection(hole_cells)

# Documented route set.
R=set()
for j in range(13):
    R |= {(x,c[j]) for x in range(2,70)}
R |= {(x,c[13]) for x in range(2,61)}
R |= {(x,c[14]) for x in range(2,69)}
R |= risers
R |= {(1,y) for y in range(1,69)}
assert len(R)==patch["areas"]["route_cells"]==1132
assert len(R & hole_cells)==patch["areas"]["route_intersection_hole"]==17
assert len(R | hole_cells)==patch["areas"]["route_union_hole"]==1157
assert not R.intersection(body_cells)
assert not R.intersection(core)

# Directed route skeleton: exactly one directed cycle, every feeder reaches it.
succ={}
def edge(a,b):
    assert a in R and b in R, (a,b)
    assert a not in succ, (a,succ.get(a),b)
    succ[a]=b

# Return trunk.
for y in range(68,1,-1): edge((1,y),(1,y-1))
edge((1,1),(2,c[0]))

# Standard c0..c11 plus bands1..12.
for j in range(12):
    y=c[j]
    if j%2==0:
        for x in range(2,69): edge((x,y),(x+1,y))
        endpoint=(69,y)
    else:
        for x in range(69,2,-1): edge((x,y),(x-1,y))
        endpoint=(2,y)
    band=j+1
    rx=patch["bands"][band-1]["riser_or_slit_x"]
    assert endpoint==(rx,y)
    lo,hi=patch["bands"][band-1]["y"]
    edge(endpoint,(rx,lo))
    for yy in range(lo,hi): edge((rx,yy),(rx,yy+1))
    edge((rx,hi),(rx,c[j+1]))

# c12 main arm, right source tail, and b13 riser.
for x in range(2,60): edge((x,c[12]),(x+1,c[12]))
for x in range(69,60,-1): edge((x,c[12]),(x-1,c[12]))
edge((60,c[12]),(60,60))
for y in range(60,64): edge((60,y),(60,y+1))
# c13 westbound into trunk.
for x in range(60,2,-1): edge((x,c[13]),(x-1,c[13]))
edge((2,c[13]),(1,c[13]))
# c14 two arms and downward slit.
for x in range(2,58): edge((x,c[14]),(x+1,c[14]))
for x in range(68,58,-1): edge((x,c[14]),(x-1,c[14]))
edge((58,c[14]),(58,68))
for y in range(68,65,-1): edge((58,y),(58,y-1))
edge((58,65),(58,c[13]))

assert set(succ)==R, (len(succ),len(R), sorted(R-set(succ))[:10])
# A functional digraph has one cycle per component. Enumerate distinct cycles.
cycles=set()
for start in R:
    pos={}
    path=[]
    u=start
    while u not in pos:
        pos[u]=len(path); path.append(u); u=succ[u]
    cyc=path[pos[u]:]
    # Canonical rotation.
    k=min(range(len(cyc)), key=lambda i:cyc[i])
    canon=tuple(cyc[k:]+cyc[:k])
    cycles.add(canon)
assert len(cycles)==1, [len(z) for z in cycles]
route_cycle_length=len(next(iter(cycles)))

manufacturing_area=len(body_cells)
assert manufacturing_area==3325
fixed_area=manufacturing_area+81+46*3
assert fixed_area==patch["areas"]["required_body_cells"]==3544
remaining=4900-fixed_area-len(R|hole_cells)
assert remaining==patch["areas"]["global_cells_left_for_poles"]==199
assert remaining//4==patch["areas"]["global_area_pole_upper"]==49

# Free-column runs and optimistic within-band slots.
slot_total=0
for b in patch["bands"]:
    lo,hi=b["y"]
    blocked=body_cells|risers|core|hole_cells
    free=[]
    for x in range(2,70):
        if all((x,y) not in blocked for y in range(lo,hi+1)):
            free.append(x)
    runs=[]
    if free:
        a=prev=free[0]
        for x in free[1:]:
            if x==prev+1:
                prev=x
            else:
                runs.append([a,prev]); a=prev=x
        runs.append([a,prev])
    assert runs==b["free_column_runs"]
    cap=sum(((v-u+1)//2)*(b["height"]//2) for u,v in runs)
    assert cap==b["optimistic_2x2_slots_inside_band"]
    slot_total += cap
assert slot_total==patch["areas"]["optimistic_band_internal_slot_upper"]==38

# Strict component arity and direction checks.
dirs={"N","E","S","W"}
opposite={"N":"S","S":"N","E":"W","W":"E"}
for z in patch["special_transport_components"]:
    ins=z["inputs"]; outs=z["outputs"]; kind=z["kind"]
    assert len(ins)==len(set(ins)) and len(outs)==len(set(outs))
    assert set(ins)|set(outs) <= dirs
    assert not set(ins)&set(outs)
    if kind=="straight":
        assert len(ins)==len(outs)==1 and opposite[ins[0]]==outs[0]
    elif kind=="turn":
        assert len(ins)==len(outs)==1 and opposite[ins[0]]!=outs[0]
    elif kind=="splitter":
        assert len(ins)==1 and len(outs) in (2,3)
    elif kind=="merger":
        assert len(ins) in (2,3) and len(outs)==1
    else:
        raise AssertionError(kind)

# Endpoint port bindings really exist in authoritative modes.
for binding in patch["endpoint_port_bindings"]:
    band=patch["bands"][binding["band"]-1]
    template=auth["facility_templates"][band["template"]]
    mode=next(m for m in template["modes"] if m["id"]==binding["pose"])
    target_front=binding["front"]
    x0=binding["machine_body_x"][0]
    y0=band["y"][0]
    possible=[]
    for port in mode["ports"]:
        if port["kind"]!="output": continue
        bx=x0+port["body_cell"]["x"]
        by=y0+port["body_cell"]["y"]
        dx,dy=delta[port["direction"]]
        possible.append([bx+dx,by+dy])
    assert target_front in possible, (binding,target_front,possible)

print("PATCH_VALIDATION: PASS")
print("manufacturing counts: 3x3=132, 5x5=49, 6x4=38")
print("core fronts: 20 exact, active inputs=2, active outputs=6")
print(f"route cells=1132, one directed route cycle length={route_cycle_length}, route_union_hole=1157")
print("fixed_body_area=3544")
print("area pole upper=49, optimistic band-internal slot upper=38")
print("NOT CHECKED: power coverage, operation binding, full strict connectivity")
