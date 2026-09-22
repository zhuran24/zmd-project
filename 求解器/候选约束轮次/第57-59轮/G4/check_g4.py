#!/usr/bin/env python3
"""G4 的配方占格检查和局部算术复算；不模拟整厂或准入口恢复语义。"""
from fractions import Fraction
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[4]
EXPECTED = {
    "《明日方舟：终末地》游戏规则.txt": "4f04de50b2f743aec1da903f00f0f89f92f1aeba60eb4513320b71d0ee0a57fd",
    "求解任务.txt": "1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac",
    "求解约束.txt": "f6503e6c1568ae5ef05bb2dfac249df0a6a371bb24342e23ba77fafc813648b6",
    "候选约束.txt": "a0ac3f9c82f371132b7de29fe47e4c6c587904680bc2786523de0c825fd5efd9",
    "思路.txt": "95d2af723613bfd61c325ab2fafd89bcd060f099d2a2172a1d79b206c3995cee",
}
SLOTS = {
    "粉碎机": 1, "精炼炉": 1, "配件机": 1, "塑形机": 1,
    "种植机": 1, "采种机": 1, "研磨机": 2, "封装机": 2, "灌装机": 2,
}


def main():
    hashes = {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in EXPECTED}
    assert hashes == EXPECTED, "引用文件已变化，应重新核对推导及行号"
    rules = (ROOT / "《明日方舟：终末地》游戏规则.txt").read_text()
    recipes = {name: [] for name in SLOTS}
    machine = None
    for line_no, line in enumerate(rules.splitlines(), 1):
        line = line.strip()
        if line in SLOTS:
            machine = line
        if " → " not in line:
            continue
        assert machine is not None
        left = line.split(" → ")[0]
        parts = [p.strip() for p in left.split("＋")]
        ingredients = []
        for part in parts:
            match = re.fullmatch(r"(\d+)\s+(\S+)", part)
            assert match, part
            ingredients.append(match.group(2))
        recipes[machine].append({"line": line_no, "inputs": ingredients})
    assert sum(map(len, recipes.values())) == 18
    poison = []
    for name, slots in SLOTS.items():
        assert recipes[name]
        counts = [len(set(r["inputs"])) for r in recipes[name]]
        # 一格装了任何配方都不用的物品后，可放配方原料的格只剩 slots-1。
        assert all(n > slots - 1 for n in counts)
        poison.append({"machine": name, "storage_slots": slots,
                       "recipe_distinct_input_counts": counts,
                       "one_foreign_slot_blocks_every_recipe": True,
                       "recipe_lines": [r["line"] for r in recipes[name]]})

    partitions = []
    for plant, growers in [("荞花", 11), ("砂叶", 21)]:
        target = Fraction(growers, 2)
        hits = [n for n in range(growers + 1) if Fraction(n) == target]
        assert hits == []
        # 仅验证半股能解除这个整数矛盾，不表示这份速率分配有几何/运行证书。
        half_split = Fraction(growers - 1, 2) + Fraction(1, 2)
        assert half_split == target
        partitions.append({"plant": plant, "whole_stream_count": growers,
                           "target_to_each_consumer_type": str(target),
                           "integer_partitions_checked": growers + 1,
                           "feasible_integer_partitions": hits,
                           "one_half_split_arithmetic": str(half_split)})

    # 满速扇出：枚举小周期的通道总件数，检查容量上界求和取等。
    saturation_cases = 0
    for k in range(1, 7):
        for period in range(1, 6):
            for counts in product(range(period + 1), repeat=k):
                saturation_cases += 1
                if sum(counts) == k * period:
                    assert counts == (period,) * k

    # D5-4 在整数 tick 网格上的包含关系：两实组之间补零组，
    # 现行轮询均分的相邻和条件自动成立。此处不替代端口行为证明。
    padded_cases = 0
    for k in range(1, 7):
        for groups in product(range(1, k + 1), repeat=3):
            for gaps in product(range(2, 5), repeat=3):
                padded = []
                for size, gap in zip(groups, gaps):
                    padded.extend([size] + [0] * (gap - 1))
                assert all(a + b <= k for a, b in zip(padded, padded[1:] + padded[:1]))
                padded_cases += 1

    result = {
        "scope": "配方格数与整数/容量算术；不覆盖几何、可达性、整厂运行或准入口重连",
        "status": "pass",
        "source_sha256": hashes,
        "recipe_count": sum(map(len, recipes.values())),
        "poisoned_storage": poison,
        "plant_integer_partitions": partitions,
        "saturation_small_cases": saturation_cases,
        "padded_polling_sequences": padded_cases,
    }
    output = Path(__file__).with_name("复算结果.json")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "pass", "output": str(output),
                      "recipe_count": result["recipe_count"],
                      "saturation_small_cases": saturation_cases,
                      "padded_polling_sequences": padded_cases}, ensure_ascii=False))


if __name__ == "__main__":
    main()
