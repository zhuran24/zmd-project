"""核对同次传输的两个落格补全；不把局部补全宣称为全规则合法运行。"""
from copy import deepcopy
from itertools import permutations
import json


initial_items = ["源矿", "蓝铁矿", "荞花", "砂叶", "荞花种子", "砂叶种子"]
new_items = ["源石粉末", "蓝铁粉末"]
initial_warehouse = {
    f"W{index}": {"item": item, "quantity": 80000, "empty_identity": None}
    for index, item in enumerate(initial_items)
}
initial_warehouse.update({
    "WA": {"item": None, "quantity": 0, "empty_identity": None},
    "WB": {"item": None, "quantity": 0, "empty_identity": None},
})
empty_slot_order = ["WA", "WB"]
box_slots = [
    {"number": 1, "item": new_items[0], "quantity": 1},
    {"number": 2, "item": new_items[1], "quantity": 1},
]
port_assignment = "WA"


def plan_allocation(item_order):
    # 内部计划不向其它判定暴露；最后整箱一次提交，保持单位原子性。
    planned = deepcopy(initial_warehouse)
    plan = []
    for item in item_order:
        assert not any(slot["item"] == item for slot in planned.values())
        assert not any(slot["empty_identity"] == item for slot in planned.values())
        target = next(slot_id for slot_id in empty_slot_order
                      if planned[slot_id]["item"] is None
                      and planned[slot_id]["empty_identity"] is None)
        planned[target] = {"item": item, "quantity": 1, "empty_identity": None}
        plan.append({"item": item, "slot": target, "quantity": 1})
    occupied_items = [slot["item"] for slot in planned.values() if slot["quantity"]]
    assert len(occupied_items) == len(set(occupied_items))
    assert all(0 <= slot["quantity"] <= 80000 for slot in planned.values())
    assert sum(slot["quantity"] for slot in planned.values()) == 6 * 80000 + 2
    return {
        "unprovided_item_order": list(item_order),
        "atomic_allocation_plan": plan,
        "warehouse_after": planned,
        "box_remaining": 0,
        "cooldown_after": 5,
        "fixed_port_assignment": port_assignment,
        "assigned_port_item_after": planned[port_assignment]["item"],
    }


outcomes = [plan_allocation(order) for order in permutations(new_items)]
assert len({outcome["assigned_port_item_after"] for outcome in outcomes}) == 2
print(json.dumps({
    "status": "KNOWN_UNCOVERED_CASE_CONFIRMED",
    "scope": "仅核同一已给输入下两个未排序的批内落格补全；不是执行器或全规则反例认证",
    "given": {
        "warehouse_empty_slot_order": empty_slot_order,
        "empty_identity": {"WA": None, "WB": None},
        "warehouse_empty_slot_identity": "retain_history",
        "transfer_partial_acceptance": "all_or_nothing",
        "box_slots": box_slots,
        "box_powered_and_enabled": True,
        "box_cooldown_before": 0,
        "port_assignment": port_assignment,
    },
    "missing": "同一单位原子传输中多个新物种的落格先后或明确的整批分配函数",
    "outcomes": outcomes,
    "safe_fallback": "受限转移定义第79行允许落格关系未解时unsupported；本例不能由现有选值推出ok后继",
}, ensure_ascii=False, indent=2))
