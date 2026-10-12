"""只验证报告中运输片段的逐组一次判定；不是项目内核或全厂达标验证。"""
import json
from fractions import Fraction


def run(game_order: bool):
    # R 是九格首尾相连的传送带；每格时间戳记录最后进入它的步。
    r = [-8] * 9
    s, a, h, b = -8, None, None, None
    sink, delivered, last = 0, 0, 0
    seen, moves = {}, []

    def age(v, t):
        return None if v is None else min(8, t - v)

    for t in range(100000):
        key = (tuple(age(v, t) for v in r), age(s, t), age(a, t),
               age(h, t), age(b, t), sink, t % 40, last)
        if key in seen:
            old_t, old_out = seen[key]
            count = delivered - old_out
            period = t - old_t
            return {"调度": "S先A后" if game_order else "A先S后对照",
                    "首次循环步": old_t, "循环步数": period, "循环交付": count,
                    "件每tick": str(Fraction(8 * count, period)),
                    "A输出前12步": moves[:12]}
        seen[key] = t, delivered
        # D->X（1级）：D满，X仓储模式且满300件，不会移动。
        # B->Y（1级）：Y无线传输，每40步清一次，远少于300件容量。
        if b is not None and t - b >= 8:
            assert sink < 300
            b = None
            sink += 1
            delivered += 1
        # H->B（2级）：桥接器只使用从西往东的独立物品格。
        if h is not None and t - h >= 8 and b is None:
            b, h = t, None

        def splitter():
            nonlocal s, a, last
            # 两个出口：D永远满；轮询可试D但失败，然后试A。
            if s is not None and t - s >= 8 and a is None:
                a, s, last = t, None, 1

        def a_out():
            nonlocal a, h
            if a is not None and t - a >= 8 and h is None:
                h, a = t, None
                moves.append(t)

        if game_order:
            splitter()  # S组2级，在A组3级之前，只访问一次。
            a_out()
        else:
            a_out()     # 对照改变S/A调度先后，其他规则保持一致。
            splitter()
        # R->S（3级）以及同一带段内从下游向上游的立即尝试。
        if r[-1] is not None and t - r[-1] >= 8 and s is None:
            s, r[-1] = t, None
        for i in range(7, -1, -1):
            if r[i] is not None and t - r[i] >= 8 and r[i + 1] is None:
                r[i + 1], r[i] = t, None
        # 非元件阶段：仓库取货口向带段头补货。
        if r[0] is None:
            r[0] = t
        if t % 40 == 0:
            sink = 0
    raise RuntimeError("未找到循环")


if __name__ == "__main__":
    print(json.dumps([run(True), run(False)], ensure_ascii=False, indent=2))
