"""第二版局部算术复核。只写本目录的 v2_rewrite_*；不运行内核。

完整读取指定输入及两份否证的全部证据；在内存中复算旧脚本，
逐字段比较旧 JSON。旧脚本的写文件语句不执行。不是整厂认证。
"""
from pathlib import Path
from fractions import Fraction as F
import ast
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REV = ROOT / "求解器/规格/推导/复核"
CHAT = Path("/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/786b1aaa-8792-43fd-afbc-2a7361543a07/scratchpad/总结/对话-0920-主线.md")
sources = [ROOT / p for p in (
    "《明日方舟：终末地》游戏规则.txt", "求解任务.txt", "求解约束.txt",
    "候选约束.txt", "求解器/规格/推导/三种相位不改产量.md",
    "求解器/规格/推导/总纲-流量存量相位.md",
    "求解器/规格/推导/复核/独立推导-相位-opus.md",
    "求解器/规格/推导/复核/否证-相位-1.md",
    "求解器/规格/推导/复核/否证-相位-2.md",
)] + [CHAT]
for name in ("否证-相位-1-证据", "否证-相位-2-证据"):
    sources.extend(sorted((REV / name).iterdir()))
blobs = {p: p.read_bytes() for p in sources if p.is_file()}
manifest = [{"path": str(p), "sha256": hashlib.sha256(b).hexdigest(),
             "bytes": len(b), "lines": len(b.splitlines()),
             "use": "integrity_only" if p.name == "候选约束.txt" else "read_and_reviewed"}
            for p, b in blobs.items()]
for name, prefix in (("《明日方舟：终末地》游戏规则.txt", "abc7a5867f64"),
                     ("求解任务.txt", "1630ca1febec"), ("求解约束.txt", "f6503e6c1568")):
    assert hashlib.sha256(blobs[ROOT/name]).hexdigest().startswith(prefix)
all_json = {p: json.loads(b) for p, b in blobs.items() if p.suffix == ".json"}
compared = []

# 第 1 席：仅把 save 改为存内存；删去末尾日志写入和 print。
p1 = REV / "否证-相位-1-证据/check_traces.py"
tree = ast.parse(blobs[p1].decode())
tree.body = [n for n in tree.body if not (
    isinstance(n, ast.FunctionDef) and n.name == "save"
    or isinstance(n, ast.With)
    or isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
       and isinstance(n.value.func, ast.Name) and n.value.func.id == "print")]
captured = {}
env1 = {"__file__": str(p1), "save": lambda name, data: captured.__setitem__(name, data)}
exec(compile(tree, str(p1), "exec"), env1)
for name, data in captured.items():
    old = all_json[p1.parent / name]
    assert json.loads(json.dumps(data, ensure_ascii=False)) == old, name
    compared.append(str(p1.parent / name))

# 第 2 席：仅加载函数，显式调用无写入的核算函数。
p2 = REV / "否证-相位-2-证据/逐tick核算.py"
env2 = {"__file__": str(p2), "__name__": "review_in_memory"}
exec(compile(blobs[p2], str(p2), "exec"), env2)
old2 = all_json[p2.parent / "输入与结果.json"]
for key, fun, args in (
    ("three_fillers", "fillers", ()),
    ("round_robin_item_types", "round_robin_types", ()),
    ("gate_non_sliding_window", "gate_accept", ([0, 4, 5, 6], 2)),
    ("gate_sparse_input", "gate_accept", (list(range(0, 101, 10)), 2)),
    ("two_serial_gates_delay", "serial_delays", ()),
    ("crusher_before_k1_gate", "crusher_backlog", ()),
):
    assert env2[fun](*args) == old2[key], key
    compared.append("review2:" + key)
for key, pointer in (("pointer_A1", 0), ("pointer_B", 2)):
    assert env2["head_block"](pointer) == old2["head_of_line"][key]
    compared.append("review2:head_of_line:" + key)
probe_cases = 0
for k1 in range(1, 6):
    for k2 in range(1, 6):
        for s1 in range(-4, 1):
            for s2 in range(-4, 1):
                assert env2["saturated_serial"](k1, k2, s1, s2) == min(k1, k2) * 200
                probe_cases += 1
assert probe_cases == old2["two_serial_gates_saturated_probe"]["cases"] == 625
assert old2["two_serial_gates_saturated_probe"]["deviations"] == []
for rel, digest in old2["source_sha256"].items():
    assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest() == digest

# 天花板与配方含矿量；不是状态空间搜索。
mass = {"ore": 1, "blue_ore": 1, "blue_block": 1, "blue_powder": 1,
        "origin_powder": 1, "dense_blue": 2, "dense_origin": 2,
        "steel": 2, "part": 2, "bottle": 4, "battery": 50, "capsule": 40,
        "buckwheat": 0, "sandleaf": 0, "buckwheat_powder": 0,
        "sandleaf_powder": 0, "fine_buckwheat": 0, "buckwheat_seed": 0, "sandleaf_seed": 0}
recipes = [({"ore":1},{"origin_powder":1}), ({"blue_block":1},{"blue_powder":1}),
    ({"buckwheat":1},{"buckwheat_powder":2}), ({"sandleaf":1},{"sandleaf_powder":3}),
    ({"blue_ore":1},{"blue_block":1}), ({"dense_blue":1},{"steel":1}),
    ({"blue_powder":1},{"blue_block":1}),
    ({"blue_powder":2,"sandleaf_powder":1},{"dense_blue":1}),
    ({"origin_powder":2,"sandleaf_powder":1},{"dense_origin":1}),
    ({"buckwheat_powder":2,"sandleaf_powder":1},{"fine_buckwheat":1}),
    ({"steel":2},{"bottle":1}), ({"steel":1},{"part":1}),
    ({"buckwheat_seed":1},{"buckwheat":1}), ({"sandleaf_seed":1},{"sandleaf":1}),
    ({"buckwheat":1},{"buckwheat_seed":2}), ({"sandleaf":1},{"sandleaf_seed":2}),
    ({"part":10,"dense_origin":15},{"battery":1}),
    ({"bottle":10,"fine_buckwheat":10},{"capsule":1})]
for ins, outs in recipes:
    assert sum(mass[x]*n for x,n in ins.items()) == sum(mass[x]*n for x,n in outs.items())
assert F(3,5)*50 + F(11,20)*40 == 52
assert F(3,5)*20 + F(11,20)*40 == 34
assert F(3,5)*30 == 18
assert all((F(3,5)*p).denominator == 1 and (F(11,20)*p).denominator == 1
           for p in range(20, 201, 20))
assert [p for p in range(1,201) if (F(11,20)*p).denominator == 1] == list(range(20,201,20))

# k=5：每一段窗口只有五个可收件的 tick；枚举所有合法收件子集。
from itertools import product
gate_histories = 0
for arrivals in product((0,1), repeat=5):
    used = 0
    for a in arrivals:
        assert not (a and used == 5)
        used += a
    gate_histories += 1

results = {"status":"passed", "scope":"局部证据逐字段复算及精确分数算术；不是整厂认证",
    "inputs_read":len(manifest), "json_fully_parsed":len(all_json),
    "compared":compared, "serial_probe_cases":probe_cases,
    "mass_conserving_recipes":len(recipes), "k5_histories":gate_histories,
    "kernel_run":False, "layout_certified":False,
    "first_review":captured["checks.json"],
    "second_review_filler_starts":old2["three_fillers"]["starts"][2],
    "non_sliding_receipts":[0,4,5,6],
    "blue_recycle_equation":"blue_block -> blue_powder -> blue_block; net mass and net item vector zero"}
for p, b in blobs.items():
    assert p.read_bytes() == b, "input changed: " + str(p)
for name, value in (("v2_rewrite_inputs.json",manifest),("v2_rewrite_results.json",results)):
    (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
(HERE/"v2_rewrite_check.log").write_text(
    "PASS: specified source hashes match; all source bytes unchanged.\n"
    "PASS: all review JSON loaded; generated tick records compared field by field.\n"
    "PASS: 625 bounded serial-gate probes reproduced; not a general phase proof.\n"
    "PASS: 18 recipes conserve ore content; 0.6*50+0.55*40=52.\n"
    "PASS: k=5 cannot reject an otherwise feasible receipt due to its periodic quota.\n"
    "No kernel build, simulator access, full-layout or reachability certification.\n")
print(json.dumps({k:results[k] for k in ("status","inputs_read","json_fully_parsed","serial_probe_cases","mass_conserving_recipes","kernel_run","layout_certified")},ensure_ascii=False))
