"""逐字节复算场地黄金，把全部建成行交给步进模式，并检查场地格式错误。"""
from copy import deepcopy
from itertools import zip_longest
import json
from pathlib import Path
import subprocess
import tempfile

from 导出场地 import DEST, ROOT, SOURCE, grid_replay
from 手写场地 import FAMILIES
from 接口样例 import segment
from 生成场地 import example, piece

EXE = ROOT / ".lake/build/bin/对拍"


def verify(path, tmp):
    expected = path.with_suffix(".jsonl").read_bytes()
    actual = subprocess.check_output([EXE, path], cwd=ROOT)
    for i, (a, b) in enumerate(zip_longest(expected.splitlines(True), actual.splitlines(True)), 1):
        if a != b:
            raise ValueError(f"{path.name} 第 {i} 行的 UTF-8 字节不同，期望 {a!r}，实际 {b!r}")
    rows = [json.loads(line) for line in actual.splitlines()]
    inputs = json.loads(path.read_bytes())["场地"]
    if len(rows) != len(inputs):
        raise ValueError(f"{path.name} 有 {len(inputs)} 例，得 {len(rows)} 行")
    segments = []
    for row in rows:
        if row == "拒绝":
            continue
        if set(row) != {"历史", "供电", "端口"}:
            raise ValueError("场地输出须恰好三栏")
        boxes = sorted(e[1] for e in row["历史"] if e[0] == "建成" and e[2] == "协议储存箱")
        segments.append(dict(segment([], boxes), **row))
    tmp.write_text(json.dumps({"版本": 1, "段": segments}, ensure_ascii=False))
    if subprocess.check_output([EXE, tmp], cwd=ROOT):
        raise ValueError("空操作段应输出零行")
    return len(segments), len(rows) - len(segments)


def malformed():
    p = piece(10, 20, 20, "供电桩")
    empty = example([])
    base = example([p])
    core = example([piece(20, 30, 30, "协议核心", "上下")])

    def packed(doc):
        return json.dumps(doc, ensure_ascii=False, separators=(",", ":"))

    def doc(ex):
        return packed({"版本": 1, "场地": [ex]})

    for root in [{}, {"版本": 1}, {"场地": []}, {"版本": True, "场地": []}, {"版本": 2, "场地": []},
                 {"版本": 1, "场地": {}}, {"版本": 1, "场地": [], "段": []},
                 {"版本": 1, "场地": [], "多": 1}]:
        yield packed(root)
    for ex in [{}, {"摆件": []}, {"核心先后": []}, dict(empty, 其他=[]),
               dict(empty, 摆件=None), dict(empty, 核心先后={}), dict(base, 核心先后=[[["上", 1], 0]])]:
        yield doc(ex)
    for field in ("号", "位置", "种类"):
        q = p.copy()
        del q[field]
        yield doc(dict(base, 摆件=[q]))
    for q in [dict(p, n=1), dict(p, 号="1"), dict(p, 号=False), dict(p, 位置=[0]),
              dict(p, 位置=[0, 0, 0]), dict(p, 位置=[False, 0]), dict(p, 位置={"i": 20, "j": 20}),
              dict(p, 种类="供电桩"), dict(p, 种类=["供电桩", "左"]), dict(p, 种类=["桥接器"]),
              dict(p, 种类=["制造", "机器", "右"]), dict(p, 种类=["分流器", "北"]),
              dict(p, 种类=["传送带", "上"]), dict(p, 种类=["桥接器格", "下"])]:
        # 前件已经越界，也必须读完本例并报后件的格式错误。
        yield doc(dict(base, 摆件=[dict(p, 位置=[99, 99]), q]))
    yield doc(dict(core, 核心先后=core["核心先后"][:-1]))
    for key in [["上", 2], ["右", 0], ["左", 8], ["北", 1]]:
        ex = deepcopy(core)
        ex["核心先后"][0][0] = key
        yield doc(ex)
    for extra in [[[["上", 1], 9]], [[["上", 2], 0]]]:
        yield doc(dict(core, 核心先后=core["核心先后"] + extra))
    for row in [core["核心先后"][1], [["下", 4], -1], [["上", 1], False], [["上", 1], "3"],
                [["上", 1]], [["上", 1], 1, 3], [["上"], 3]]:
        ex = deepcopy(core)
        ex["核心先后"][0] = row
        yield doc(ex)
    for token in ["-0", "-1", "1.0", "1.00", "1e0", "1E+0", "1e-0", "01", "+1", "NaN", "1e9999999999"]:
        yield doc(base).replace('"号":10', '"号":' + token)
    for token in ["1.00", "1e0", "01", "-0"]:
        yield doc(empty).replace('"版本":1', '"版本":' + token)
    for src, dst in [('"版本":1', '"版本":2,"版本":1'),
                     ('"摆件":[', '"摆件":[],"摆件":['),
                     ('"号":10', '"号":2,"\\u53f7":10'),
                     ('"位置":[20,20]', '"位置":[20,20],'),
                     ('"核心先后":[]', '"核心先后":[')]:
        yield doc(base).replace(src, dst)


def main():
    subprocess.run(["lake", "build", "对拍"], cwd=ROOT, check=True)
    paths = sorted(DEST.glob("*.json"))
    names = {p.stem for p in SOURCE.glob("*.lean") if grid_replay(p.stem)}
    names.update("手写-" + k for k in FAMILIES)
    if not names == {p.stem for p in paths} == {p.stem for p in DEST.glob("*.jsonl")}:
        raise ValueError("场地输入、输出与回放/手写清单不符")
    good = rejected = 0
    with tempfile.TemporaryDirectory() as scratch:
        tmp = Path(scratch) / "输入.json"
        for path in paths:
            a, b = verify(path, tmp)
            good += a
            rejected += b
        errors = list(malformed())
        for raw in errors:
            tmp.write_text(raw)
            p = subprocess.run([EXE, tmp], capture_output=True)
            if p.returncode == 0 or not p.stderr.strip():
                raise ValueError(f"该输入须非零退出并给原因 {raw}")
        # 不同键序和转义拼写按解码后的键识别。空文件集不产生行。
        tmp.write_text(r'{"\u573a\u5730":[],"\u7248\u672c":1}')
        if subprocess.check_output([EXE, tmp]):
            raise ValueError("零场地须输出零行")
    print(f"{len(paths)} 份，{good + rejected} 行逐字节相同。{good} 个建成行全被步进模式接收，"
          f"{rejected} 个拒绝。{len(errors)} 份坏输入均以非零退出并给出原因。")


if __name__ == "__main__":
    main()
