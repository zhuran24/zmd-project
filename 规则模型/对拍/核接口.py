"""检查脚本入口的失败退出、计数策略和离线后判定表的切换。"""
import json
import subprocess
import tempfile
from pathlib import Path

from 接口样例 import cases, segment

ROOT = Path(__file__).resolve().parents[1]


def main():
    subprocess.run(["lake", "build", "对拍"], cwd=ROOT, check=True)
    with tempfile.TemporaryDirectory(dir=ROOT / "对拍") as scratch:
        file = Path(scratch) / "输入.json"

        def invoke(*segments, bad=False, raw=None):
            file.write_text(raw if raw is not None else json.dumps(
                {"版本": 1, "段": segments}, ensure_ascii=False))
            p = subprocess.run([str(ROOT / ".lake/build/bin/对拍"), str(file)], capture_output=True)
            if bad:
                assert p.returncode and p.stderr.strip(), (file.read_text(), p.stdout)
                return
            assert p.returncode == 0, p.stderr.decode()
            return [json.loads(line) for line in p.stdout.splitlines()]

        h = [["建成", 7, "物品准入口"]]
        samples = cases()
        for s in samples["接口-计数策略"]:
            first, second = invoke(s)
            g = first["准入口"][0][1]
            if s["操作"][0][0] == "离线":
                a, b = s["未定"]["离线后的计数"]
                assert (g["累计已收"], g["名额"], g["拍"]) == (
                    5 if a == "保留" else 0, [17, 3] if b == "保留" else [], 3)
                assert second["准入口"][0][1]["拍"] == 0
            else:
                a, b = s["未定"]["改设定后的计数"]
                change = second["准入口"][0][1]
                assert g["累计已收"] == (5 if a == "保留" else 0) and g["名额"] == [17, 3]
                assert change["累计已收"] == 0 and change["名额"] == ([17, 3] if b == "保留" else [])

        def compare_histories(control, switched):
            old_rows = invoke(control)
            _, *new_rows = invoke(switched)
            assert old_rows != new_rows
            assert new_rows == invoke(dict(control, 历史=switched["操作"][0][1]))
            return old_rows, new_rows

        old, new = compare_histories(*samples["接口-分流器离线换出口"])
        for rows, outlets in [(old, [4, 3, 4, 3]), (new, [3, 4, 3, 4])]:
            assert [rows[i]["分流器上次"][0][1][1] for i in (8, 16, 24, 32)] == outlets
        belts, switched, boxes, switched_boxes = samples["接口-汇流器离线换进口"]
        old, new = compare_histories(belts, switched)
        def hub_item(rows):
            return next(goods for (u, _), goods in rows[0]["货"] if u == 3)
        assert hub_item(old) == [["源矿", 1]] and hub_item(new) == [["钢块", 1]]
        compare_histories(boxes, switched_boxes)

        for s, n in zip(samples["接口-传输位置"], (3, 2, 1), strict=True):
            row, = invoke(s)
            assert row["仓库"] == [["钢块", n]]

        box = [["建成", 3, "协议储存箱"]]
        rows = invoke(*samples["接口-出库"])
        assert len(rows) == 6 and rows[-1]["仓库"] == [["钢块",7]]
        assert rows[-1]["开关"] == [[3, False]] and rows[-1]["货"] == [[[3,["格",1]],[["钢块",1]]]]
        for key, value in [("开关", True), ("制造中", None), ("储存箱", {}),
                           ("分流器上次", None), ("出货已移动", [])]:
            invoke(segment(h, 状态={key: [[7, value]]}), bad=True)
        for history, boxes, u in [(box, [3], 3), (h, [], 7)]:
            cell = [u, ["格", 0]]
            for key, value in [("已停", 1), ("来处", cell)]:
                invoke(segment(history, boxes, 状态={key: [[cell, value]]}), bad=True)
                loaded = {"货": [[cell, [["源矿", 1]]]], key: [[cell, value]]}
                invoke(segment(history, boxes, 状态=loaded), bad=bool(boxes))
            defaults = {"货": [[cell, []]], "已停": [[cell, 0]], "来处": [[cell, None]]}
            assert invoke(segment(history, boxes, 状态=defaults, 操作=[["入库", "源矿", 0]])) == [{}]
        invoke(segment(h, 状态={"货": [[[7, ["格", 0]], [["源矿", 1]]]],
                             "已停": [[[7, ["格", 0]], 9]]}), bad=True)
        for history, u, n in [(h, 7, 0), (belts["历史"][:-1], 3, 1), (belts["历史"], 3, 2)]:
            invoke(segment(history, [4] if u == 3 else [], 状态={"进货上次": [[u, max(1, n)]]}), bad=True)
            invoke(segment(history, [4] if u == 3 else [], 状态={"进货上次": [[u, max(1, n)-1]]}))
        for op in [["出库","钢块",1], ["收货",[3,["格",0]]], ["设准入口",3,None,1,None],
                   ["改布局",["拆除",3]], ["走",-1], ["走",1,"多余"], ["离线",[]]]:
            invoke(segment(box, [3], 操作=[op]), bad=True)
        for s in [segment(h, 状态={"准入口": [[7,{"拍":4}]]}),
                  segment(h, 状态={"已停": [[[7,["格",0]],9]]}),
                  segment(h, 状态={"开光": []}), segment(h, 状态={"准入口": [[7,{"柏":1}]]}),
                  segment(h, 状态={"进货上次": [[7,0],[7,0]]}),
                  segment(h, 状态={"货": [[[999,["格",0]],[["源矿",1]]]]}),
                  segment(h + h), segment(box), segment([], 操作=[["走",1]], 期望=[]),
                  segment([["建成",1,"仓库取货口"],["建成",2,"传送带"],["接通",[1,2]]])]:
            invoke(s, bad=True)
        invoke(bad=True, raw='{"版本":9,"版本":1,"段":[]}')
        assert invoke(segment([], 操作=[["走",0]])) == []
    print("通过：四种计数组合、离线重排、仓储操作、默认值、错误退出与零步。")


if __name__ == "__main__":
    main()
