"""Run every upstream interface assertion against Rust, then compare extra cases with Lean."""
import json
import re
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from common import MODEL, ROOT, RUST, build, compact, equal

# Import upstream assertions without writing caches or temporary input in the model.
sys.dont_write_bytecode = True
sys.path.insert(0, str(MODEL / "对拍"))
import 核接口
from 接口样例 import segment

LEAN = MODEL / ".lake" / "build" / "bin" / "对拍"


def upstream(root):
    original_root, original_proc = 核接口.ROOT, 核接口.subprocess
    (root / "对拍").mkdir()
    counts = [0, 0]

    def reroute(cmd, **kwargs):
        if cmd == ["lake", "build", "对拍"]:
            return subprocess.run(["cargo", "build", "--release", "--locked"], cwd=ROOT, check=True)
        assert Path(cmd[0]) == root / ".lake/build/bin/对拍" and len(cmd) == 2
        p = subprocess.run([RUST, cmd[1]], **kwargs)
        counts[int(p.returncode != 0)] += 1
        return p

    try:
        核接口.ROOT = root
        核接口.subprocess = SimpleNamespace(run=reroute)
        核接口.main()
    finally:
        核接口.ROOT, 核接口.subprocess = original_root, original_proc
    return counts


def extras(root):
    path = root / "边界.json"
    counts = [0, 0]

    def check(label, value, valid=False):
        path.write_text(value if isinstance(value, str) else compact(value))
        rust, lean = [subprocess.run([cmd, path], capture_output=True) for cmd in [RUST, LEAN]]
        for p in (lean, rust):
            if (p.returncode == 0) != valid or (not valid and not p.stderr.strip()):
                raise AssertionError((label, p.args, p.returncode, p.stderr, path.read_text()))
        if not valid and b"panicked" in rust.stderr:
            raise AssertionError(f"{label} Rust panic")
        equal(label, rust.stdout, lean.stdout)
        counts[int(not valid)] += 1

    def doc(s):
        return {"版本": 1, "段": [s]}

    base = segment([["建成", 1, "协议储存箱"], ["建成", 2, "物品准入口"], ["建成", 3, "研磨机"],
                    ["建成", 4, "协议核心"], ["建成", 5, "分流器"], ["建成", 6, "仓库取货口"]], [1])
    def sample(label, valid=False, **updates):
        check(label, doc(dict(base, **updates)), valid)
    def state(field, entries, valid=False):
        sample(field, valid, 状态={field: entries})
    def action(op, **kw):
        sample(str(op), 操作=[op], **kw)

    # Every negative branch of 做得了 for supported operations.
    for op in [["设准入口", 1, None, None, None], ["设准入口", 2, None, 1, None],
               ["设准入口", 2, None, None, 0], ["设准入口", 2, "源矿", 0, None],
               ["设准入口", 2, "源矿", 5001, None], ["设准入口", 2, "源矿", None, 6],
               ["重置计数", 1], ["重置计数", 2], ["设储存箱模式", 2, False],
               ["设取货指向", 3, 0, None], ["设取货指向", 4, 6, None], ["设取货指向", 6, 1, None],
               ["拨开关", [3, 2], True], ["拨开关", [99], False], ["放货", 5, "源矿", 1],
               ["放货", 3, "源矿", 0], ["放货", 99, "源矿", 2], ["收货", [3, "取货"]],
               ["收货", [1, ["格", 6]]], ["收货", [99, ["格", 0]]],
               ["入库", "源矿", 80001], ["出库", "钢块", 1],
               ["离线", base["历史"] + [["拆除", 99]]], ["离线", base["历史"][:-1]],
               ["离线", [*base["历史"][:-1], ["建成", 6, "传送带"]]],
               ["离线", base["历史"] + [["接通", [1, 2]]]]]:
        action(op)
    action(["收货", [5, ["格", 0]]], 状态={"货": [[[5, ["格", 0]], [["源矿", 1]]]]})
    action(["收货", [3, "缓存"]], 状态={"货": [[[3, "缓存"], [["致密源石粉末", 1]]]]})
    action(["入库", "源矿", 1], 状态={"仓库": [["源矿", 80000]]})

    for op in [["走", None], ["走", True], ["走", "1"], ["走", 1.0], ["走", 1.5],
               ["设储存箱模式", 1, 1], ["未知"], ["入库", "未知", 1], ["重置计数", -1]]:
        action(op)
    for event in [["建成", 88, "未知"], ["建成", 77, "协议核心"], ["接通", [1, 1]],
                  ["接通", [1, 3]], ["接通", [2, 99]], ["重接", [1, 2]], ["拆除", 99]]:
        sample(str(event), 历史=base["历史"] + [event])
    sample("重复接通", 历史=base["历史"] + [["接通", [1, 2]]] * 2)

    for k, wrong in [("版本", 2), ("段", {}), ("多余", 1)]:
        check(k, dict(doc(base), **{k: wrong}))
    for k in ("历史", "未定", "状态", "操作", "端口", "供电"):
        s = deepcopy(base)
        del s[k]
        check("缺少 " + k, doc(s))
    for k in base["未定"]:
        s = deepcopy(base)
        del s["未定"][k]
        check("缺少 " + k, doc(s))
    sample("段未知字段", 未知=0)
    sample("备注类型", 备注=None)
    sample("未定未知字段", 未定=dict(base["未定"], 未知=True))
    sample("乱序供电", 供电=[3, 1])
    sample("重复供电", 供电=[3, 3])
    sample("未知供电单位", 供电=[99])
    for k, v in [("输入判定都没货时", "未知"), ("离线后的计数", ["保留", "未知"]),
                 ("改设定后的计数", ["保留"]), ("传输排在几组之后", [[1, 1], [1, 0]])]:
        sample(k, 未定=dict(base["未定"], **{k: v}))
    net = base["历史"] + [["接通", [4, 2]], ["接通", [4, 5]]]
    for ports in [[[[4, 5], 0]], [[[4, 2], 6], [[4, 5], 0]], [[[4, 5], 1], [[4, 2], 0]],
                  [[[4, 2], 0], [[4, 2], 0]]]:
        sample("端口表", 历史=net, 端口=ports)

    g = [2, ["格", 0]]
    box = [1, ["格", 0]]
    for cell in (g, box):
        for k, v in [("已停", 1), ("来处", box)]:
            state(k, [[cell, v]])
            sample(k, valid=cell == g, 状态={"货": [[cell, [["源矿", 1]]]], k: [[cell, v]]})
    for k, default in [("来处", None), ("已停", 0), ("货", [])]:
        state(k, [[[99, ["格", 0]], default]])
        state(k, [[g, default], [box, default]])
        state(k, [[g, default], [g, default]])
    for k, value in [("准入口", {}), ("储存箱", {}), ("分流器上次", None), ("开关", True),
                     ("制造中", None), ("进货上次", 0), ("出货已移动", [])]:
        state(k, [[99, value]])
    for k, v in [("货", [[g, [["源矿", 2]]]]), ("货", [[box, [["源矿", 0]]]]),
                 ("货", [[box, [["源矿", 51]]]]), ("货", [[box, [["源矿", 1], ["钢块", 2]]]]),
                 ("货", [[[3, ["存货", i]], [["源矿", 1]]] for i in (0, 1)]),
                 ("仓库", [["钢块", 0], ["源矿", 0]]), ("仓库", [["源矿", 80001]]),
                 ("进货上次", [[5, 1]]), ("取货指向", [[[4, 6], None]]),
                 ("取货指向", [[[4, 1], None], [[4, 0], None]]), ("储存箱", [[1, {"他": None}]]),
                 ("准入口", [[2, {"拍": None}]]), ("准入口", [[2, {"累计上限": 1}]]),
                 ("准入口", [[2, {"名额": [-1]}]]), ("制造中", [[3, [{}, 0]]])]:
        state(k, v)
    for v in ['{"版本":1,"段":[],"\\u6bb5":[]}', '{"版本":1,"段":[]}xxx',
              '{"版本":1,"段":[{},]}', '{"版本":1,"段":[]} {}',
              compact(doc(base)).replace('"状态":{}', '"状态":{"准入口":[[2,{"拍":2,"拍":2}]]}'),
              compact(doc(base)).replace('"状态":{}', '"状态":{"仓库":[["源矿",{"$serde_json::private::Number":"1"}]]}')]:
        check("原始 JSON", v)
    sample("期望过多", 操作=[], 期望=[{}])
    sample("期望过少", 操作=[["走", 2]], 期望=[])
    sample("期望内容", 操作=[["走", 1]], 期望=[{"仓库": []}])
    sample("合法前缀后遇到非法操作", 操作=[["入库", "源矿", 1], ["出库", "源矿", 2]])

    # Real acceptance boundaries the model permits, including historical value
    # references outside the current key domain and repeated queue values.
    large = 2**32 - 1
    sample("计时上界、规范停步与拍", True, 供电=[1], 状态={
        "仓库": [["源矿", 80000]], "准入口": [[2, {"累计已收": large, "拍": 3, "名额": [0, large]}]],
        "储存箱": [[1, {"冷却还剩": large}]], "货": [[g, [["源矿", 1]]]], "已停": [[g, 8]],
        "来处": [[g, [large, ["存货", large]]]], "分流器上次": [[5, [large, 99]]],
        "出货已移动": [[1, [[99, 99], [99, 99]]]]}, 操作=[["走", 2]])
    sample("大单位号与传输位置", True, 历史=[["建成", large, "协议储存箱"]], 供电=[large],
           未定=dict(base["未定"], 传输排在几组之后=[[large, large]]),
           操作=[["设储存箱模式", large, True], ["放货", large, "源矿", 301], ["走", 1]])
    sample("开关空或重复、零库存、全满同种原料", True, 状态={"货": [[[3, ["存货", 0]], [["钢块", 50]]]]},
           操作=[["拨开关", [], True], ["拨开关", [1, 1], False], ["入库", "源矿", 0], ["出库", "源矿", 0],
                 ["放货", 3, "钢块", 1], ["设取货指向", 4, 5, None], ["设准入口", 2, "源矿", 5000, 0]])
    sample("空箱冷却、同种按格传到满仓", True, 供电=[1], 状态={"仓库": [["源矿", 79999]]},
           操作=[["走", 1], ["放货", 1, "源矿", 51], ["走", 40]])
    for tag in [{"未知": None}, {"钢块": 1, "源矿": 2}, []]:
        action(["入库", tag, 0])
    state("仓库", [[{"钢块": {}}, 1]])
    for note in [r"literal \ud800", "\ud800", "\udc00", "\ud800\udc00", "\ud800\ufeff"]:
        check("备注 UTF-16 转义", json.dumps(doc(dict(base, 备注=note))), True)
    check("不同转义还原出同名键", '{"版本":1,"段":[],"\\ud800":1,"\\ufffd":2}')
    for event in [["未知", 1], ["未知", 1, 2]]:
        sample("事件名与参数个数", 历史=[event])
    for op in [["未知", 1, 2, 3], ["未知", 1, 2, 3, 4],
               ["收货", [1]], ["收货", [3, ["未知", 0]]]]:
        action(op)
    for raw in [r'{"版本":1,"段":[],"备注":"\u12zz"}', r'{"版本":1,"段":[]}\x']:
        check("非法 JSON 转义", raw)
    state("仓库", [["源矿"]])
    state("货", [[[3, "缓存"], [["源矿", 1]]]])
    state("制造中", [[3, []]])
    recipe = {"单位": "研磨机", "原料": [["蓝铁粉末", 2], ["砂叶粉末", 1]],
              "产物": ["致密蓝铁粉末", 1], "时长": 1}
    sample("有效配方与缓存原料不符", 状态={"制造中": [[3, [recipe, 0]]],
                                      "货": [[[3, "缓存"], [["蓝铁粉末", 1]]]]})
    # Extract recipe rows from the Lean definitions, independently of Rust.
    source = (MODEL / "Endfield/配方.lean").read_text()
    recipes = re.findall(r'⟨«(.*?)», \[(.*?)\], \(«(.*?)», (\d+)\), (\d+)⟩', source)
    assert len(recipes) == 18
    for kind, materials, product, n, ticks in recipes:
        raw = [[x, int(count)] for x, count in re.findall(r'\(«(.*?)», (\d+)\)', materials)]
        s = segment([["建成", 1, kind]], 供电=[1], 状态={
            "货": [[[1, ["存货", i]], [p]] for i, p in enumerate(raw)] + [[[1, "取货"], [["钢块", 50]]]]},
            操作=[["走", int(ticks)*8+1], ["拨开关", [1], False], ["收货", [1, "取货"]], ["走", 1]])
        check(f"{kind} {raw} → {product} × {n}", doc(s), True)
    for args, code in [([], 2), (["a", "b"], 2), ([str(root / "missing.json")], 1)]:
        for program in (RUST, LEAN):
            result = subprocess.run([program, *args], capture_output=True)
            assert result.returncode == code and result.stderr and not result.stdout, program
        counts[1] += 1
    return counts


if __name__ == "__main__":
    build()
    with tempfile.TemporaryDirectory(dir=ROOT / "target") as d:
        a = upstream(Path(d))
        b = extras(Path(d))
    subprocess.run(["cargo", "test", "--locked", "--test", "legal_base"], cwd=ROOT, check=True)
    print(f"核接口.py 原断言 {sum(a)} 次（成功 {a[0]}，拒绝 {a[1]}），"
          f"补充双端用例 {sum(b)} 次（成功 {b[0]}，拒绝 {b[1]}），正式入口测试全部通过")
