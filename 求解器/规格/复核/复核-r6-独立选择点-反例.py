"""复核规格缺口的最小算例；不是游戏执行器或完整布局认证器。"""

import itertools
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PROFILE = json.loads((ROOT / "求解器/规格/内核配置-v1.json").read_text())


def allocate_inbound(item_order):
    # 按受限转移§4.1给定的空格全序，分别代入两种尚未规定的物种处理序。
    slots = {"W0": None, "W1": None}
    slot_order = ("W0", "W1")
    for item in item_order:
        chosen = next(slot for slot in slot_order if slots[slot] is None)
        slots[chosen] = {"item": item, "quantity": 1}
    assert len({value["item"] for value in slots.values()}) == 2
    assert all(value["quantity"] <= 80000 for value in slots.values())
    return slots


def warehouse_witness():
    assert PROFILE["axes"]["warehouse.empty_slot_identity"]["value"] == "retain_history"
    assert PROFILE["axes"]["transfer.partial_acceptance"]["value"] == "all_or_nothing"
    items = ("高容谷地电池", "精选荞愈胶囊")
    outcomes = []
    for order in itertools.permutations(items):
        slots = allocate_inbound(order)
        outcomes.append({
            "unfixed_item_iteration": list(order),
            "warehouse_after_transfer": slots,
            "port_bound_to_W0_observes": slots["W0"]["item"],
            "transferred_total": 2,
            "box_after_transfer": [],
            "cooldown_after_transfer": 5,
        })
    assert outcomes[0]["port_bound_to_W0_observes"] != outcomes[1]["port_bound_to_W0_observes"]
    return {
        "fixed_slot_order": ["W0", "W1"],
        "initial_empty_identity": {"W0": None, "W1": None},
        "input_box": {"slot_1": {"item": items[0], "quantity": 1},
                      "slot_2": {"item": items[1], "quantity": 1}},
        "outcomes": outcomes,
        "conclusion": "两种物种顺序遵守同一空格序，产生可被既有端口区分的后继；原规格缺少物种分配顺序。",
    }


def recipe_witness():
    # 只比较匹配谓词，不把未审的严格相等读法认作合法游戏机制。
    inventory = {"源矿": 2}
    recipe = {"源矿": 1}
    at_least = all(inventory.get(item, 0) >= amount for item, amount in recipe.items())
    exact = inventory == recipe
    assert at_least and not exact
    return {
        "machine": "粉碎机", "inventory": inventory, "recipe_inputs": recipe,
        "shared_axes": {"input_mixing": "single_kind", "recipe_match_scope": "input_union",
                        "recipe_completeness": "full_batch", "input_collection": "atomic_batch"},
        "at_least_one_batch": at_least, "exactly_one_batch": exact,
        "conclusion": "物种完备与求值论域相同，数量比较方向仍能改变开闸；严格相等的全规则合法性未获证明。",
    }


def simultaneous_gate_recovery():
    # a、b是同一制造单位到两个准入口的同级取货边，接通全序固定a<b。
    # 两门窗口在t=0各收一件后阻断，货在t=1离开；t=5一起到期。
    # 本函数只投影边界恢复与源侧轮询；其余状态在两个分支完全相同。
    assert PROFILE["axes"]["polling.membership_change"]["value"] == "retain_survivors"
    assert PROFILE["axes"]["polling.initial_cursor"]["value"] == "first_connected"
    assert PROFILE["axes"]["gate.window_clock"]["value"] == "wall_clock"
    outcomes = []
    for restoration_order in itertools.permutations(("a", "b")):
        members = []
        cursor = None
        restoration_log = []
        for channel in restoration_order:
            old_members = list(members)
            members = sorted(members + [channel])
            # §3.4：空级删除；新级首接起轮；加入边不抢现有续接位置。
            if not old_members:
                cursor = members[0]
            restoration_log.append({"restored": channel, "ring": list(members), "cursor": cursor})
        assert members == ["a", "b"]
        source_quantity = 1
        received = {"a": 0, "b": 0}
        successful_channel = None
        # 相同事件模板序a,b，不借判定次序的变化制造分歧。
        for channel in ("a", "b"):
            physical = source_quantity > 0 and channel in members
            source_authorized = physical and cursor == channel
            target_authorized = physical
            if source_authorized and target_authorized:
                source_quantity -= 1
                received[channel] += 1
                successful_channel = channel
                cursor = members[(members.index(channel) + 1) % len(members)]
                # 该门重新用尽窗口额度，按原规则断入边，保留另一成员。
                members.remove(channel)
        assert source_quantity == 0
        outcomes.append({"unfixed_restoration_order": list(restoration_order),
                         "restoration_log": restoration_log,
                         "fixed_template_order": ["a", "b"],
                         "successful_channel": successful_channel,
                         "gate_received_at_t5": received,
                         "active_channels_after_closure": members,
                         "source_next_channel": cursor})
    assert outcomes[0]["successful_channel"] == "a"
    assert outcomes[1]["successful_channel"] == "b"
    return {"connection_order": ["a", "b"],
            "before_boundary": {"source_output_quantity": 1, "source_level_members": [],
                                "gate_a": {"quantity": 0, "window_limit": 1, "window_started_at": 0, "window_received": 1},
                                "gate_b": {"quantity": 0, "window_limit": 1, "window_started_at": 0, "window_received": 1}},
            "instant": 5, "outcomes": outcomes,
            "conclusion": "接通序和判定模板序相同，仅未定的同刻窗口恢复维护序不同，产生两个不同闭包后继。"}


def splitter_probe(ticks=8):
    # 仅投影分流器三个出口的T1/T3算法。下游边界使首格在收件恰1 tick后腾空。
    # 未将运输单位的不分级侧自动认作正式轮询均分中的同级，因此本探针不独立确证违规。
    assert PROFILE["axes"]["polling.ungraded_blocked"]["value"] == "empty_turn"
    assert PROFILE["axes"]["time.instant_end"]["value"] == "repeat_scheduler_state"
    cursor = 1
    trace = []
    counts = [0, 0, 0]
    for tick in range(ticks):
        # 上游在前一tick送入一件，本tick恰到1 tick，所有首格已腾空。
        source = 1
        occupied = [False, False, False]
        used = [False, False, False]
        seen = {(source, tuple(occupied), tuple(used), cursor)}
        events = []
        sweeps = 0
        while True:
            for channel in range(3):
                physical = bool(source) and not occupied[channel] and not used[channel]
                source_authorized = cursor == channel
                target_authorized = physical
                if not (source_authorized or target_authorized):
                    continue
                success = physical and source_authorized and target_authorized
                if success:
                    source = 0
                    occupied[channel] = True
                    used[channel] = True
                    counts[channel] += 1
                    events.append(chr(ord("a") + channel))
                if source_authorized:
                    cursor = (channel + 1) % 3
            sweeps += 1
            key = (source, tuple(occupied), tuple(used), cursor)
            if key in seen:
                break
            seen.add(key)
            assert sweeps < 20
        trace.append({"tick": tick, "successful_channels": events,
                      "closure_cursor": chr(ord("a") + cursor), "sweeps": sweeps})
    assert [row["successful_channels"] for row in trace] == [["b"]] + [["a"]] * (ticks - 1)
    return {"trace": trace, "counts": counts,
            "status": "条件探针，未列为独立发现",
            "unresolved_premise": "不分级取货侧是否落在正式轮询均分的同级量词中，三正式文件未显式给该衔接。"}


if __name__ == "__main__":
    print(json.dumps({"simultaneous_gate_recovery": simultaneous_gate_recovery(),
                      "warehouse_witness": warehouse_witness(),
                      "recipe_match_witness": recipe_witness(),
                      "splitter_probe": splitter_probe()}, ensure_ascii=False, indent=2))
