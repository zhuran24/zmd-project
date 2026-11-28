"""接口黄金的手写输入。期望由对拍可执行程序生成。"""


def segment(history, boxes=(), **fields):
    return {"历史": history, "供电": [], "端口": [],
            "未定": {"传输排在几组之后": [[u, 3] for u in boxes],
                   "改设定后的计数": ["保留", "保留"], "离线后的计数": ["保留", "保留"],
                   "输入判定都没货时": "每步判两次"}, "状态": {}, "操作": [], **fields}


def layout(kinds, edges):
    return [["建成", u, k] for u, k in kinds] + [["接通", [a, b]] for a, b in edges]


def stock(u, item, n=1):
    return [[u, ["格", 0]], [[item, n]]]


def reordered(kinds, edges, boxes, state, ticks):
    # 两个出口（或进口）排在末尾，同时保存旧历史的对照段。
    old = layout(kinds, edges)
    new = layout(kinds, edges[:-2] + edges[-2:][::-1])
    return [segment(old, boxes, 状态=state, 操作=[["走", ticks]]),
            segment(old, boxes, 状态=state, 操作=[["离线", new], ["走", ticks]])]


def cases():
    box, belt = "协议储存箱", "传送带"
    split = reordered([(1, box), (2, "分流器"), (3, box), (4, box)],
                      [(1, 2), (2, 3), (2, 4)], [1, 3, 4],
                      {"货": [stock(1, "源矿", 4)]}, 34)
    merge = reordered([(1, belt), (2, belt), (3, "汇流器"), (4, box)],
                      [(3, 4), (1, 3), (2, 3)], [4],
                      {"货": [stock(1, "源矿"), stock(2, "钢块")],
                       "已停": [[[u, ["格", 0]], 8] for u in [1, 2]], "进货上次": [[3, 1]]}, 17)

    # 箱直进汇流器，覆盖非运输单位移动时使用输入判定的路径。
    merge += reordered([(10, box), (20, box), (30, "汇流器"), (40, box)],
                       [(30, 40), (10, 30), (20, 30)], [10, 20, 40],
                       {"货": [stock(10, "源矿"), stock(20, "钢块")]}, 1)

    h = [["建成", 7, "物品准入口"]]
    gate = {"放行": "源矿", "累计上限": 7, "每5tick上限": 2,
            "累计已收": 5, "名额": [17, 3], "拍": 3}
    counters = []
    for a in ("保留", "清空"):
        for b in ("保留", "清空"):
            for policy, ops in [
                ("离线后的计数", [["离线", h], ["走", 1]]),
                ("改设定后的计数", [["设准入口", 7, "源矿", 7, 3], ["设准入口", 7, "蓝铁矿", 7, 3]])]:
                s = segment(h, 状态={"准入口": [[7, gate]]}, 操作=ops)
                s["未定"][policy] = [a, b]
                counters.append(s)

    trans = []
    h = layout([(1, box), (2, belt), (3, "汇流器"), (4, box), (5, box)],
               [(1, 2), (2, 4), (1, 3), (3, 5)])
    for n in (0, 1, 2):
        s = segment(h, [1, 4, 5], 供电=[1], 状态={"货": [stock(1, "钢块", 3)]}, 操作=[["走", 1]])
        s["未定"]["传输排在几组之后"][0][1] = n
        trans.append(s)

    warehouse = segment([["建成", 3, box]], [3], 操作=[
        ["走", 0], ["拨开关", [3], False], ["设储存箱模式", 3, True], ["放货", 3, "钢块", 51],
        ["收货", [3, ["格", 0]]], ["入库", "钢块", 12], ["出库", "钢块", 5]])
    return {"接口-分流器离线换出口": split, "接口-汇流器离线换进口": merge,
            "接口-计数策略": counters, "接口-传输位置": trans, "接口-出库": [warehouse]}
