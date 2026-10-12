from pathlib import Path
import json, sys
sys.dont_write_bytecode = True
base = Path(__file__).resolve().parent
src = (base / "局部联合模型快照.py").read_text()
spec = dict(labels=["蓝铁块", "源石粉末", "砂叶粉末"], roles=[],
    supply=[("蓝铁块", [2], 1), ("源石粉末", [3], 1), ("砂叶粉末", [3], 1)],
    demand=[("蓝铁块", [0], 1), ("源石粉末", [1], 1), ("砂叶粉末", [1], 1)],
    supply_points={"蓝铁块": [(0, 0, 2)], "源石粉末": [(0, 0, 3)], "砂叶粉末": [(1, 0, 3)]},
    demand_points={"蓝铁块": [(1, 0, 0)], "源石粉末": [(0, 0, 1)], "砂叶粉末": [(1, 0, 1)]})
results = {}
for tag, code in [("original_P5", src), ("without_P5", src.replace("m.Add(br[c] + br[n] <= 1)", "pass  # P5 removed for scoped counterexample"))]:
    ns = {"__name__": "audit_probe"}
    exec(compile(code, str(base / "局部联合模型快照.py"), "exec"), ns)
    results[tag] = ns["build"](spec, 2, 1, threads=1, tlimit=5, minimize=False)
assert results["original_P5"]["status"] == "INFEASIBLE"
assert results["without_P5"]["status"] in ("OPTIMAL", "FEASIBLE")
assert results["without_P5"]["bridges"] == 2
(base / "相邻桥反例结果.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
print(json.dumps(results, ensure_ascii=False, indent=2))
