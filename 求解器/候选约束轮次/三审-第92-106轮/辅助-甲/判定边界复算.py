#!/usr/bin/env python3
"""规则级边界核对，不作全厂仿真或几何反例。
区分送货资格与收货成功；同一物理桥的两轴分别收货、判定。
"""
from itertools import product
from pathlib import Path
import json

out = Path(__file__).resolve().parent
table = []
for present, age, previous_is_receiver, receiver_full in product((False, True),range(9),(False,True),(False,True)):
    token = {"entered":-age,"previous":"R" if previous_is_receiver else "U"} if present else None
    trigger = token is not None and -token["entered"]>=8 and token["previous"]!="R"
    moved = trigger and not receiver_full
    table.append({"present":present,"age":age,"came_from_receiver":previous_is_receiver,
                  "receiver_full":receiver_full,"triggers":trigger,"moves":moved})
assert len(table)==72
assert any(row["triggers"] and not row["moves"] for row in table)
assert all(not row["triggers"] for row in table if row["came_from_receiver"])

# Receiving groups use the bridge axis. A horizontal upstream with cargo
# cannot consume the vertical upstream's judgement opportunity.
upstream = {"B.horizontal":["W"],"B.vertical":["S"]}
assert set(upstream["B.horizontal"]).isdisjoint(upstream["B.vertical"])

def simulate_one_step(clear_polling, clear_cooldown):
    occupied = {"B.horizontal":True,"B.vertical":True,"E":False,"N":False}
    done = set()
    sent = []
    base = ["B.horizontal","B.vertical","machine","box"]
    polling = None if clear_polling else "previous_success"
    cooldown = 0 if clear_cooldown else 17
    def judge(component):
        if component in done:
            return
        done.add(component)
        if component.startswith("B."):
            dest = "E" if component.endswith("horizontal") else "N"
            if occupied[component] and not occupied[dest]:
                occupied[component]=False
                occupied[dest]=True
                sent.append((component,dest))
    # A prior joint call used the horizontal component's judgement already.
    judge("B.horizontal")
    for component in base:
        judge(component)
    assert len(sent)==2 and len(done)==4
    assert occupied["E"] and occupied["N"]
    return {"clear_polling":clear_polling,"clear_cooldown":clear_cooldown,
            "sent":sent,"judgements":len(done),"box_attempts":int(cooldown==0),
            "previous_unit_record_after_offline":"B_original_location","polling":polling}

cases = [simulate_one_step(a,b) for a,b in product((False,True),repeat=2)]
result = {"all_checks_passed":True,"trigger_table_cases":len(table),
          "triggers_but_receiver_full":sum(row["triggers"] and not row["moves"] for row in table),
          "offline_cases":cases,"axis_receiving_groups":upstream,
          "trigger_table":table,
          "scope":"本程序核对已明确的规则边界，不定义多出口联判的未定部分，不证明任何整厂可达性。"}
(out/"判定边界复算结果.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({k:result[k] for k in ("all_checks_passed","trigger_table_cases","triggers_but_receiver_full")},ensure_ascii=False))
