"""从现行规则读取箱体和时长，核算库存及空格。运行时只读规则文件。"""

import re
from pathlib import Path

RULES = (Path(__file__).resolve().parents[4]/"《明日方舟：终末地》游戏规则.txt")


def read_constants():
    rows = RULES.read_text(encoding="utf-8").splitlines()

    def row(name):
        return next(line.strip() for line in rows if line.strip().startswith(name + "："))

    def number(name, pattern):
        return int(re.search(pattern, row(name)).group(1))

    steps = number("步", r"每 1/(\d+) tick")
    cooldown = number("传输", r"然后冷却 (\d+) tick")
    dwell = number("滞留", r"至少 (\d+) tick")
    box = row("协议储存箱")
    width, height = map(int, re.search(r"大小 (\d+)×(\d+)", box).groups())
    assert width == height and "任意一条边全为存货端口" in box
    slots, capacity = map(int, re.search(r"含 (\d+) 个有编号的物品格（上限 (\d+)）", box).groups())
    return steps * cooldown, steps * dwell, width, slots, capacity


def prefix_maxima(window, gap):
    # 分别考虑末步不进件、末步进一件。可以跳过任意多步。
    best = [0]
    for length in range(1, window + 1):
        best.append(max(best[-1], 1 + best[max(0, length - gap)]))
    return best


def first_blocking_word(slots, kinds):
    """从全空格到六格全占且缺一种来货，最少要有几次填入空格？"""
    empty = (0,) * slots
    frontier = {empty}
    seen = {empty}
    admissions = 0
    while frontier:
        if any(0 not in word and len(set(word)) < kinds for word in frontier):
            return admissions
        fresh = set()
        for word in frontier:
            for kind in range(1, kinds + 1):
                index = next((j for j, x in enumerate(word) if x in (0, kind)), None)
                if index is None or word[index] == kind:
                    continue
                new = word[:index] + (kind,) + word[index + 1:]
                # 一次入空格之后，闭包中收进任意次取空最前非空格的结果。
                # 已访问的词在首次入表时就已处理过这条取货链。
                while new not in seen:
                    seen.add(new)
                    fresh.add(new)
                    first = next((j for j, x in enumerate(new) if x), None)
                    if first is None:
                        break
                    new = new[:first] + (0,) + new[first + 1:]
        frontier = fresh
        admissions += 1
    return None


def box_examples(slots, capacity):
    # 用逐件存取（保留件数）核验无外送和有外送的例子。
    def put(cells, kind):
        for cell in cells:
            if not cell or (cell[0] == kind and len(cell) < capacity):
                cell.append(kind)
                return True
        return False

    cells = [[] for _ in range(slots)]
    for kind in "ABCDEFABCDEF":
        assert put(cells, kind)
    assert [cell[0] for cell in cells] == list("ABCDEF")
    assert not put(cells, "G")

    cells = [[] for _ in range(slots)]
    assert put(cells, "A") and put(cells, "B")
    next(cell for cell in cells if cell).pop()
    for kind in "BCDEF":
        assert put(cells, kind)
    assert not put(cells, "A")
    return "、".join("".join(cell) for cell in cells)


def main():
    window, gap, ports, slots, capacity = read_constants()
    best = prefix_maxima(window, gap)
    assert all(b == (j + gap - 1) // gap for j, b in enumerate(best))
    by_ports = [m * best[-1] for m in range(ports + 1)]
    print(f"相邻触发 {window} 步，单口相邻进件至少 {gap} 步。")
    print(f"按进货口数 0 至 {ports} 的上界：{by_ports}。箱体有 {slots} 格，每格 {capacity} 件，共 {slots * capacity} 件。")
    witness = list(range(gap, window + 1, gap))
    assert len(witness) == best[-1] and by_ports[-1] < capacity
    print(f"各口在相对步 {witness} 进件，下一次触发前共 {ports * len(witness)} 件。")

    minima = {k: first_blocking_word(slots, k) for k in range(1, slots + 2)}
    print(f"各来货种数到首次可拒收状态所需的最少填空次数（None 为不可达）：{minima}")
    assert slots > by_ports[1] and minima[4] > by_ports[2] and minima[3] > by_ports[3]
    print("有外送时的保证：一口不限种，两口至多 4 种，三口至多 3 种。")
    print(f"六种来货、有外送的箱格示例：{box_examples(slots, capacity)}，此时 A 无格可放。")


if __name__ == "__main__":
    main()

