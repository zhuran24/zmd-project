#!/usr/bin/env python3
"""Check the R4 upper certificate against problem_instance.json (stdlib only)."""
import collections, hashlib, json, sys

P = sys.argv[1] if len(sys.argv) == 2 else "problem_instance.json"
raw = open(P, "rb").read()
D = json.loads(raw)
assert D["benchmark_id"] == "factory_layout_optimality_benchmark_v1"
assert hashlib.sha256(raw).hexdigest() == "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
T, G = D["facility_templates"], D["operation_groups"]
W, H = D["grid"]["width"], D["grid"]["height"]
assert (W, H) == (70, 70)

def cdiv(a, b): return -(-a // b)
def body_area(name):
    a = {m["body"]["width"] * m["body"]["height"] for m in T[name]["modes"]}
    assert len(a) == 1
    return a.pop()
def side_len(mode, port):
    b = mode["body"]
    return b["width"] if port["direction"] in "NS" else b["height"]
def corner(mode, port):
    b, q = mode["body"], port["body_cell"]
    z = q["x"] if port["direction"] in "NS" else q["y"]
    return z in (0, side_len(mode, port) - 1)
def template_side(name):
    s = {side_len(m, p) for m in T[name]["modes"] for p in m["ports"]}
    assert len(s) == 1
    return s.pop()
def need(g, kind): return sum(g["port_needs"][kind].values())
def nreq(name): return sum(r["template"] == name for r in D["required_instances"])

required_area = sum(body_area(r["template"]) for r in D["required_instances"])
powered_area = sum(body_area(r["template"]) for r in D["required_instances"]
                   if T[r["template"]]["requires_power"])
mi = sum(g["count"] * need(g, "inputs") for g in G)
mo = sum(g["count"] * need(g, "outputs") for g in G)
raw_n = sum(D["generic_requirements"]["raw_outputs"].values())
final_n = sum(D["generic_requirements"]["final_inputs"].values())
total_t = mi + mo + raw_n + final_n
assert (required_area, powered_area, mi, mo, raw_n, final_n, total_t) == (3544, 3325, 310, 264, 52, 2, 628)

# Terminal membrane arithmetic for manufacturing bodies and boundary ports.
classes = collections.Counter()
forced_mfg = 0
forced_sides = []
for g in G:
    s, i, o = template_side(g["template"]), need(g, "inputs"), need(g, "outputs")
    classes[s, max(i, o)] += g["count"]
    ri, ro = max(0, i - 2), max(0, o - 2)
    forced_mfg += g["count"] * (ri + ro)
    forced_sides += [(s, ri), (s, ro)]
bn = nreq("boundary_storage_port")
classes[template_side("boundary_storage_port"), 1] += bn
expected = {(3,1):155,(3,2):12,(3,3):11,(5,1):32,
            (5,2):17,(6,3):32,(6,4):3,(6,5):3}
assert dict(classes) == expected
excess = sum(n * max(0, 2*a-s) for (s,a), n in classes.items())
end_extra = max(a - max(0, 2*a-s) for s,a in classes)
assert (excess, end_extra, forced_mfg) == (63, 3, 58)

# All 52 raw-output slots are forced active and are non-corner ports.
bt = T["boundary_storage_port"]
core = T["protocol_core"]
assert bn == 46 and nreq("protocol_core") == 1
assert set(D["generic_requirements"]["raw_output_providers"]) == {"boundary_storage_port", "protocol_core"}
assert bt["placement_rule"] == "matching_map_boundary"
assert all(len([p for p in m["ports"] if p["kind"] == "output"]) == 1 for m in bt["modes"])
assert all(not corner(m, p) for m in bt["modes"] for p in m["ports"])
core_out = {sum(p["kind"] == "output" for p in m["ports"]) for m in core["modes"]}
core_face = max(sum(p["kind"] == "output" and p["direction"] == d for p in m["ports"])
                for m in core["modes"] for d in "NESW")
assert core_out == {6} and core_face == 3
assert all(not corner(m, p) for m in core["modes"] for p in m["ports"] if p["kind"] == "output")
assert raw_n == bn + 6
marked = forced_mfg + raw_n
forced_sides += [(template_side("boundary_storage_port"), 1),
                 (template_side("protocol_core"), core_face)]
assert marked == 110 and all(2*r <= s for s,r in forced_sides)
rmax = max(r for s,r in forced_sides)
smax = max(s for s,r in forced_sides if r)
assert (rmax, smax) == (3, 9)

# Local doubled-weight halo: every powered body assigned to one pole costs <=396.
lam = {(3,3):2,(5,1):8,(5,5):16,(7,7):8,(9,3):2,(9,9):2,
       (11,1):2,(11,3):12,(11,5):22,(11,7):2,(11,9):2,
       (13,11):25,(15,3):2,(17,3):8}
def wt(x, y):
    a, b = sorted((abs(2*x-1), abs(2*y-1)), reverse=True)
    return lam.get((a,b), 0)
weight2 = sum(wt(x,y) for x in range(-20,21) for y in range(-20,21))
assert weight2 == 792
pole = {(0,0),(1,0),(0,1),(1,1)}
cov = D["power"]["coverage_from_pole_anchor"]
dims = {(m["body"]["width"], m["body"]["height"])
        for r in D["required_instances"] if T[r["template"]]["requires_power"]
        for m in T[r["template"]]["modes"]}
counts = {}
for w,h in dims:
    count = 0
    for x in range(cov["x_min_offset"]-w+1, cov["x_max_offset"]+1):
      for y in range(cov["y_min_offset"]-h+1, cov["y_max_offset"]+1):
        cells = {(x+i,y+j) for i in range(w) for j in range(h)}
        if cells & pole: continue
        count += 1
        assert sum(wt(*q) for q in cells) >= 2*w*h
    counts[w,h] = count
assert counts == {(3,3):180,(5,5):220,(6,4):220,(4,6):220}
pole_cap = weight2 // 2
poles = cdiv(powered_area, pole_cap)
assert (pole_cap, poles) == (396, 9)

# Boundary ports: at most floor(70/3)=23 per supported side, hence exactly
# 23 left and 23 bottom, covering 69/70 cells on each side.
b_modes = {(m["id"], m["body"]["width"], m["body"]["height"], m["ports"][0]["direction"])
           for m in bt["modes"]}
assert b_modes == {("left_boundary",1,3,"E"), ("bottom_boundary",3,1,"N")}
lengths = sorted(max(m["body"]["width"], m["body"]["height"]) for m in bt["modes"])
assert lengths == [3,3]
per_side = W // 3
assert bn == 2 * per_side and W - 3*per_side == 1

base = required_area + poles * body_area(D["power"]["pole_template"])
limit = W*H - base
assert (base, limit) == (3580, 1320)

def bounds(w, h, marked_rule=True):
    s = w + h
    k_in = (2*s + excess + 8*end_extra) // 2 + core_face + final_n
    n_old = cdiv(total_t - k_in, 4)
    n = n_old
    if marked_rule and w >= smax:
        j_in = min(marked, (2*s + 8*rmax) // 2)
        n = max(n, cdiv((total_t-k_in) + (marked-j_in), 4))
    return n

def scan(marked_rule, boundary_rule):
    best, dims = (-1,-1), []
    for w in range(D["objective"]["minimum_side"], W+1):
      for h in range(w, H+1):
        if boundary_rule and h == 70: continue
        if w*h + bounds(w,h,marked_rule) <= limit:
            z = (w*h, w)
            if z > best: best, dims = z, [(w,h)]
            elif z == best: dims.append((w,h))
    return best, dims

old, old_dims = scan(False, False)
marked_only, marked_dims = scan(True, False)
new, new_dims = scan(True, True)
assert old == (1190,34) and old_dims == [(34,35)]
assert marked_only == (1190,17) and marked_dims == [(17,70)]
assert new == (1188,22) and new_dims == [(22,54)]
print("instance_sha256", hashlib.sha256(raw).hexdigest())
print("areas required/powered/pole_cap/min_poles/base", required_area, powered_area, pole_cap, poles, base)
print("terminals total/marked/excess/endpoint_extra", total_t, marked, excess, end_extra)
print("boundary ports per side/gap", per_side, 1)
print("old relaxation", old, old_dims)
print("marked-terminal step", marked_only, marked_dims)
print("new certificate", new, new_dims)
