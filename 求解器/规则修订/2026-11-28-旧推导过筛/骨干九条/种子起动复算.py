"""用现行题面与配方复算。只查配方的物料关系，不模拟具体线路。"""

import re
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CROPS = ("荞花", "砂叶")


def item(text):
    count, name = text.strip().split()
    return name, int(count)


def read_recipes():
    rules = (ROOT / "《明日方舟：终末地》游戏规则.txt").read_text(encoding="utf-8")
    section = rules.split("\n配方\n", 1)[1]
    recipes = []
    for line in section.strip().splitlines():
        machine, entries = line.strip().split("：")
        for entry in entries.split("；"):
            parts, duration = entry.split("，")
            assert re.fullmatch(r"[1-9]\d* tick", duration)
            ingredients, product = parts.split(" → ")
            name, count = item(product)
            recipes.append((machine, dict(map(item, ingredients.split("＋"))), name, count))
    return recipes


def recipe_closure(recipes, starting_items):
    # 只看物种有无。把已有的物种当作用量不限，使缺失结论也适用于真实库存。
    available = set(starting_items)
    while True:
        produced = {out for _, need, out, _ in recipes if need.keys() <= available}
        if produced <= available:
            return available
        available.update(produced)


def main():
    recipes = read_recipes()
    task = (ROOT / "求解任务.txt").read_text(encoding="utf-8")
    target = re.search(r"每 (\d+) tick 至少向仓库交付前者 [\d.]+ 个、后者 ([\d.]+) 个", task)
    assert target
    ticks, capsules = map(Fraction, target.groups())
    capsule_rate = capsules / ticks

    def ingredient_per_output(product, ingredient):
        [(inputs, output_count)] = [(inputs, n) for _, inputs, out, n in recipes if out == product]
        return Fraction(inputs[ingredient], output_count)

    fine = "细磨荞花粉末"
    fine_rate = capsule_rate * ingredient_per_output("精选荞愈胶囊", fine)
    all_items = {out for _, _, out, _ in recipes}
    all_items.update(x for _, inputs, _, _ in recipes for x in inputs)
    print(f"胶囊 {capsule_rate} 个/tick，需细磨荞花粉末 {fine_rate} 件/tick")
    for crop in CROPS:
        seed, powder = crop + "种子", crop + "粉末"
        family = {crop, seed}
        crush_rate = fine_rate * ingredient_per_output(fine, powder) * ingredient_per_output(powder, crop)
        print(f"{crop}：仅胶囊的细磨粉末一路，平均至少粉碎 {crush_rate} 株/tick。")
        for machine, inputs, out, n in recipes:
            if out in family:
                material = "＋".join(f"{count} {name}" for name, count in inputs.items())
                print(f"  {machine}：{material} → {n} {out}")
        other_items = all_items - family
        for starting in (set(), {crop}, {seed}):
            reached = recipe_closure(recipes, other_items | starting) & family
            print(f"  补入 {','.join(starting) or '无'}：配方可涉及 {','.join(sorted(reached)) or '无本种植株和种子'}")
            assert reached == (family if starting else set())


if __name__ == "__main__":
    main()
