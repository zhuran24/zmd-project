"""从现行规则复算判定阶段、制造出货的步差和箱内传输的位置数。"""
from collections import Counter
from itertools import product
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[4]
RULES = (ROOT / "《明日方舟：终末地》游戏规则.txt").read_text(encoding="utf-8")


def definition(name):
    match = re.search(r"^\s*" + re.escape(name) + r"：([^\n]+)$", RULES, re.M)
    if match is None:
        raise ValueError(f"未找到规则名词 {name}")
    return match[1]


def read_phases():
    block = RULES.split("判定顺序：", 1)[1].split("输入判定：", 1)[0]
    rows = re.findall(r"^\s*(\d+)\. (.+)$", block, re.M)
    labels = {
        "各汇流器进行输入判定": "汇流器输入",
        "元件的各组": "元件移动",
        "各汇流器再进行一次输入判定": "汇流器再输入",
        "非运输单位按建成的先后": "非运输单位移动",
        "所有移动判定结束后，所有单位同时进行结束制造判定": "同时结束制造",
        "结束制造判定完成后，所有单位同时进行开始制造判定": "同时开始制造",
    }
    phases = []
    for number, wording in rows:
        (label,) = [label for prefix, label in labels.items() if wording.startswith(prefix)]
        assert int(number) == len(phases) + 1
        phases.append(label)
    assert phases == list(labels.values())
    return phases


def check_box():
    box = definition("协议储存箱")
    sides = re.search(r"大小 (\d+)×(\d+)", box)
    width, height = map(int, sides.groups())
    assert width == height and "对边全为取货端口" in box
    assert "每个端口为边上属于某一格的那段边" in definition("端口")
    assert "通往非汇流器的为一组；通往汇流器的每条各为一组" in RULES

    by_groups = Counter()
    max_positions = 0
    for outlets in product(("空", "汇流器", "非汇流器"), repeat=width):
        groups = set()
        for port, destination in enumerate(outlets):
            if destination == "汇流器":
                groups.add(("独立组", port))
            elif destination == "非汇流器":
                groups.add(("共同组",))
        # 各组依级别已有顺序。沿这个顺序列出传输以前已经处理的组数。
        prefixes = list(range(len(groups) + 1))
        by_groups[len(groups)] += 1
        max_positions = max(max_positions, len(prefixes))
    print(f"取货端口 {width}。按组数统计接法类别 {dict(sorted(by_groups.items()))}")
    print(f"取货组最多 {max(by_groups)}，传输位置最多 {max_positions}")

    # 每个出口只接一个能收货的空汇流器，每组实际至多送一件。仓库可全收。
    # 步初已有 width-1 件，元件移动时另收一件。每行是对同一局部条件单独代入一个位置。
    print("传输前已判组数 / 各组实际出货 / 无线入库")
    for before_wireless in range(width + 1):
        stock = width - 1
        stock += 1
        wired = []
        for event in [*range(before_wireless), "传输", *range(before_wireless, width)]:
            if event == "传输":
                wireless = stock
                assert wireless == width - sum(wired)
                stock = 0
            else:
                sent = min(stock, 1)
                stock -= sent
                wired.append(sent)
        assert sum(wired) + wireless + stock == width
        print(before_wireless, wired, wireless)


def main():
    phases = read_phases()
    print(f"{len(phases)} 个阶段：" + " → ".join(phases))
    timeline = [(step, phase) for step in range(2) for phase in phases]
    finish = timeline.index((0, "同时结束制造"))
    next_step, next_phase = next(
        (step, phase) for step, phase in timeline[finish + 1:]
        if phase == "非运输单位移动"
    )
    assert phases.index("元件移动") < phases.index("非运输单位移动")
    print(f"新入取货格的产物到下次本机出货判定，步号差 {next_step}，"
          f"该判定在第 {phases.index(next_phase) + 1} 阶段")
    check_box()


if __name__ == "__main__":
    main()
