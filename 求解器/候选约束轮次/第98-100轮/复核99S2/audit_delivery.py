"""Final independent artifact consistency, input hashes, and arithmetic checks."""
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
import json,hashlib,ast

HERE=Path(__file__).resolve().parent;BASE=HERE.parent
def read(name):return json.loads(HERE.joinpath(name).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

ar=read("arithmetic_graph.json");br=read("arithmetic_expanded.json")
assert ar["machine_count"]==br["machine_count"]==230
assert ar["body_area"]==br["body_area"]==3567
assert ar["backup"]==br["backup"]
orig=json.loads(BASE.joinpath("推导98S2/startup_budget.json").read_text())
assert ar["stock_equivalents"]==orig["machine_capacity"]
assert ar["backup"]==orig["feedstock_quota_by_item"]
assert ar["virgin_inputs"]==orig["independent_integer_recipe_expansion"]
factories=[read(f"factory_{seed}.json") for seed in (9901,9902,9903,9904)]
for f in factories:
    c=f["cycle"];assert c["period_steps"]==480 and c["direct_tuple_equality"]
    s=read(f"factory_state_{f['seed']}.json")
    assert s["before"]==s["after"]
    assert set(c["ore_per_route"])=={60} and len(c["ore_per_route"])==52
    assert F(c["deliveries"]["高容谷地电池"]*8,c["period_steps"])==F(3,5)
    assert F(c["deliveries"]["精选荞愈胶囊"]*8,c["period_steps"])==F(11,20)
startups=[read(f"startup_{seed}.json") for seed in (9951,9952)]
replays=read("certificate_replay.json");offset=read("offset_check.json")
old_cycles=[json.loads(BASE.joinpath(f"推导98S2/cycle_{seed}.json").read_text()) for seed in (98040,98041,98042)]
for c in old_cycles:assert c["delivery"]=={"高容谷地电池":36,"精选荞愈胶囊":33} and c["critical_shared_routes"]==46

small_numbers={"fast_refill_deadline":1+8*(max(10//2,15//3)-1),
               "shared_deadlines":{"core":0+6,"sand":2+3},
               "consumer_stock_bound":10+(40+7)//8+1,
               "slow_processor_stock_bound":2+(8+7)//8+1,
               "batches_per_480":{"E_each":480//40,"F1_F2_each":480//40,"F3":480//80,"F4":480//160},
               "extra_vs_221":3567-3375,"E":3567-3291,
               "pure_extra_budget_vs_221":(3567-3375)+4*(11-10)+(325-317),
               "grouped_sand_minimum":3*((5+2)//3)+2*((6+2)//3)+(3+2)//3+2}
assert small_numbers["fast_refill_deadline"]==33
assert small_numbers["consumer_stock_bound"]==16 and small_numbers["slow_processor_stock_bound"]==4
assert small_numbers["grouped_sand_minimum"]==13
# Independent direct integer event windows for the conservative stock bounds.
assert max(sum(t%8==phase for t in range(41)) for phase in range(8))+10==16
assert max(sum(t%8==phase for t in range(9)) for phase in range(8))+2==4
assert sorted(set(1+8*j for j in range(5)))==[1,9,17,25,33]

from model_spec import graph
from startup_check import WEIGHT
ms,ss,es=graph()
gains={}
for n,m in ms.items():
    if m.duration==8:
        gain=m.amount*WEIGHT[m.product]-sum(v*WEIGHT[x] for x,v in m.needs)
        assert gain>=1;gains[m.product]=gain

inputs=list((BASE/"前提快照").glob("*.txt"))+[BASE/"临时规则.md",BASE/"推导98S2.md",
BASE.parent/"第92-94轮/推导92D.md",BASE.parent/"第95-97轮/推导95S.md",BASE.parent/"第95-97轮/复核97M.md"]
inputs+=list(BASE.joinpath("推导98S2").glob("cycle_9804[012].json"))
inputs+=list(BASE.joinpath("推导98S2").glob("graph_9804[012].json"))
inputs += [BASE/"推导98S2/startup_budget.json",BASE/"推导98S2/engine_a.py",BASE/"推导98S2/engine_b.py",BASE/"推导98S2/factory_check.py"]
input_hashes={str(p.relative_to(BASE.parent)):sha(p) for p in inputs}
HERE.joinpath("inputs.json").write_text(json.dumps(input_hashes,ensure_ascii=False,indent=2)+"\n")
for p in HERE.glob("*.py"):ast.parse(p.read_text(),filename=str(p))
result={"status":"pass","small_numbers":small_numbers,"weight_gains_by_product":gains,
        "factory_cases":len(factories),"factory_steps":sum(f["steps_compared"] for f in factories),
        "startup_cases":len(startups),"startup_steps":sum(s["total_steps_compared"] for s in startups),
        "certificate_steps":sum(r["dual_transition_steps"] for r in replays),
        "all_factory_encoding_steps":sum(f["steps_compared"] for f in factories)+sum(s["total_steps_compared"] for s in startups)+sum(r["dual_transition_steps"] for r in replays),
        "local_cases":offset["two_encoding_cases"],"local_steps":offset["two_encoding_steps"],
        "local_exhaustive_transitions":sum(e["transitions"] for e in offset["exhaustive"]),
        "original_reported_steps_sum":sum(c["cross_checked_steps"] for c in old_cycles),
        "graph_planar_necessary_test":read("graph_check.json")["planar_necessary_test"],
        "input_hash_count":len(input_hashes),"report_path":str(BASE/"复核99S2.md")}
HERE.joinpath("validation.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(result,ensure_ascii=False))
