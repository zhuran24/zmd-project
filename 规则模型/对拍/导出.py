"""从副本的回放源码生成临时观察程序，运行选定的原 #guard 并收集模型状态。"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse
import json
import re
import subprocess
import tempfile

from 接口样例 import cases as interface_cases

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Endfield/回放"
DEST = ROOT / "对拍/黄金"

# 原文件的 #guard 首行，含分支、枚举及原断言。行号也随样本写入备注。
CASES = {
    "一步的尺子": [123, 125, 127], "下游放置翻转": [101, 104],
    "两个中转箱": [43, 46, 76, 79, 81], "传输周期": [93, 120, 124, 127, 153, 173],
    "供电范围": [23, 25, 27, 29, 36], "供电范围右上角": [21, 22, 23, 24, 26],
    "准入口周期": [74, 221, 297, 458], "准入口挡住的一支": [129, 248, 250],
    "出货先后走步": [98, 120], "分流器出口变动走步": [78, 84, 93],
    "分流器最后放": [109, 115], "制造单位头一条出口进汇流器": [56, 60, 85],
    "制造单位晚一步": [184, 208], "前提": [87, 88], "原料格堆满": [96, 104, 112],
    "同时接通的先后": [70, 135, 183], "存货箱和中转箱": [63, 66],
    "带子是一个整体": [87, 310], "换配方": [91, 95, 132],
    "改带子以后的先后": [181, 183], "格子": [110, 124],
    "格子边界": [133, 160, 208, 209, 241, 257], "桥接器": [74, 221, 258],
    "桥接器各边的先后": [136], "现象": [433, 437, 603, 606, 608, 621],
    "相位尺": [95], "种植机三条出口带": [96], "粉碎机整批进取货格": [73],
    "终点的时刻": [72, 73, 137], "绕回卡两件": [90, 92], "缓存格": [98, 247],
    "蓝图空格和直带相接": [34, 63, 78], "蓝图里的准入口": [140, 146, 152, 164],
    "贴箱分流器争第一格": [107], "贴箱的分流器": [169, 201],
    "连着做": [96, 97, 100, 104], "配件机和带子": [77],
}


STRIDES = {
    "一步的尺子": 512, "两个中转箱": 256, "传输周期": 256,
    "准入口周期": 128, "准入口挡住的一支": 256, "出货先后走步": 32,
    "分流器出口变动走步": 64, "分流器最后放": 64, "制造单位头一条出口进汇流器": 128,
    "制造单位晚一步": 256, "原料格堆满": 64, "同时接通的先后": 128,
    "存货箱和中转箱": 256, "带子是一个整体": 128, "改带子以后的先后": 64,
    "桥接器": 512, "桥接器各边的先后": 256, "现象": 256,
    "种植机三条出口带": 256, "终点的时刻": 128, "绕回卡两件": 32,
    "缓存格": 512, "蓝图空格和直带相接": 32, "蓝图里的准入口": 256,
    "贴箱分流器争第一格": 128, "贴箱的分流器": 512, "连着做": 256,
}


def packed(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def harness(name):
    """只复制回放调用方。模型导入保持原样，观察器包住一步和外部操作。"""
    imports = {'import «对拍».«取样»'}
    modules = {}

    def include(mod):
        if mod in modules:
            return
        code = []
        found = set()
        enabled = False
        for line_no, line in enumerate((SOURCE / (mod + ".lean")).read_text().splitlines(), 1):
            if line.startswith("import "):
                dep = re.fullmatch(r"import Endfield\.«回放»\.«([^»]+)»", line)
                if dep:
                    include(dep[1])
                else:
                    imports.add(line)
                continue
            if line.startswith("#guard "):
                enabled = True
                if mod == name and line_no in CASES[name]:
                    found.add(line_no)
                    code.append(f'#eval IO.eprintln "@case {line_no}"')
                    code.append(line)
                    enabled = False
                continue
            if enabled and line and not line[0].isspace():
                enabled = False
            if not enabled:
                code.append(line)
        if mod == name and found != set(CASES[name]):
            raise ValueError(f"{name} 缺断言 {set(CASES[name]) - found}")
        s = "\n".join(code).replace("«回放»", "«采样回放»")
        s = s.replace("Endfield.«格子».«作用»", "Oracle.Trace.gridOp")
        s = s.replace("«一步于»", "Oracle.Trace.step")
        s = re.sub(r"(?<![.])«作用»", "Oracle.Trace.applyOp", s)
        if name in {"供电范围", "供电范围右上角"} and mod == name:
            s = s.replace("«场地».«有电»", "Oracle.Trace.power")
        if mod == "蓝图里的准入口":
            # 三份实验均用原回放列出的第一个相容放货偏移。完整枚举仍在 Endfield 默认构建中。
            s = s.replace("for early in «放货偏移» s window panel do",
                          "for early in («放货偏移» s window panel).take 1 do")
        modules[mod] = s

    include(name)
    return "\n".join(sorted(imports)) + "\nset_option maxRecDepth 32768\n" + "\n".join(modules.values())


def collect(name, path):
    path.write_text(harness(name))
    with subprocess.Popen(["lake", "env", "lean", "-j1", str(path)], cwd=ROOT,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as proc:
        segments, errors = [], []
        case, last = 0, None
        checkpoint = False
        for line in proc.stdout:
            if line.startswith("@case "):
                checkpoint = False
                case = int(line[6:])
                last = None
                continue
            if not line.startswith("@oracle "):
                if line.strip():
                    errors.append(line.rstrip())
                continue
            row = json.loads(line[8:])
            if not isinstance(row, list):
                errors.append(str(row))
                continue
            ctx, state, *rest = row
            if rest == ["布局"]:
                if checkpoint:
                    segments.pop()
                segments.append([case, ctx, state, []])
                last, checkpoint = (ctx, state), True
                continue
            # 带货拆建留到下一段首。试算分支回到不同快照时也另起段。
            # 桥接器“双向读数”分别从 s、t 分支做 32 步读数和 32 步等待。
            # 断头带在两支交界处的规范快照相等，须按原剧本的步数分段。
            branch = (name == "桥接器" and case == 74 and segments
                      and len(segments[-1][3]) == 32)
            if branch or last != (ctx, state) or not rest:
                segments.append([case, ctx, state, []])
            checkpoint = False
            if rest:
                op, after = rest
                segments[-1][3].append((op, after))
                if op[0] == "离线":
                    ctx = dict(ctx, 历史=op[1])
                last = (ctx, after)
            else:
                last = None
        if proc.wait() or errors:
            raise RuntimeError(f"{name}\n" + "\n".join(errors[:25]))
    if not segments:
        raise RuntimeError(name + " 没采到状态")
    return segments


def waiting(history):
    """待接箱次序的分流器基例，有进口，零出口或唯一出口通向无出口桥接器格。"""
    kinds, edges = {}, set()
    for op, arg, *rest in history:
        if op == "建成":
            kinds[arg] = rest[0]
        elif op == "拆除":
            del kinds[arg]
            edges = {c for c in edges if arg not in c}
        elif op == "接通":
            edges.add(tuple(arg))
    for u, kind in kinds.items():
        if kind != "分流器" or not any(b == u for a, b in edges):
            continue
        outs = [b for a, b in edges if a == u]
        if not outs or (len(outs) == 1 and kinds[outs[0]] == "桥接器格" and
                        not any(a == outs[0] for a, b in edges)):
            return True
    return False


def windows(steps, width, stride, extra):
    length = len(steps)
    if stride == 1 or length <= width * 2:
        return [(0, length)]
    starts = sorted({0, length - width, *range(0, length - width, stride)})
    intervals = [(i, i + width) for i in starts]
    intervals.extend((i, i+1) for i, (op, _) in enumerate(steps) if op[0] != "走")
    intervals.extend((i-1, i+1) for i in extra if 0 < i < length)
    result = []
    for i, end in sorted(intervals):
        if result and i <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], end))
        else:
            result.append((i, end))
    return result


def render(segments, width, stride, name):
    result = []
    for serial, (case, ctx, initial, steps) in enumerate(segments, 1):
        cuts = windows(steps, width, stride, [394] if name == "贴箱分流器争第一格" else [])
        for lo, hi in cuts:
            # 离线替换历史；裁出的窗口取得其起点真正生效的历史。
            head = dict(ctx)
            for op, _ in steps[:lo]:
                if op[0] == "离线":
                    head["历史"] = op[1]
            note = f"源断言 L{case}，轨迹 {serial}，操作后读数 {lo+1}–{hi}/{len(steps)}" if steps else f"源断言 L{case}，静态段首"
            if waiting(head["历史"]):
                note += "，待接箱的次序"
            ops, rows = [], []
            for op, after in steps[lo:hi]:
                if op[0] == "走" and ops and ops[-1][0] == "走":
                    ops[-1][1] += 1
                else:
                    ops.append(op.copy())
                rows.append(after)
            result.append(dict(head, 备注=note, 状态=initial if lo == 0 else steps[lo-1][1],
                               操作=ops, 期望=rows))
    return dict(版本=1, 段=result)


def script_text(script):
    blocks = []
    for seg in script["段"]:
        fields = [packed(k) + ":" + packed(v) for k, v in seg.items() if k != "期望"]
        rows = ",\n".join(packed(row) for row in seg["期望"])
        blocks.append("{\n" + ",\n".join(fields) + ',\n"期望":[\n' + rows + "]}")
    return '{"版本":1,"段":[\n' + ",\n".join(blocks) + "]}\n"


def export(name):
    with tempfile.TemporaryDirectory(dir=DEST.parent) as tmp:
        segments = collect(name, Path(tmp) / "Sample.lean")
    # 沿用原黄金的取样间隔，以便在相同窗口比较不同版本的状态。
    stride = STRIDES.get(name, 1)
    width = max(1, 16 // max(1, stride // 128))
    script = render(segments, width, stride, name)
    data = script_text(script)
    path = DEST / (name + ".json")
    temp = path.with_suffix(".tmp")
    temp.write_text(data)
    temp.replace(path)
    ticks = sum(op[1] for s in script["段"] for op in s["操作"] if op[0] == "走")
    raw = sum(op == ["走", 1] for _, _, _, rows in segments for op, _ in rows)
    print(f"{name} 原轨迹核对 {raw} 步，{len(script['段'])} 段 {ticks} 步 {len(data.encode())} B", flush=True)


def export_interface(name, segments):
    with tempfile.TemporaryDirectory(dir=DEST.parent) as tmp:
        path = Path(tmp) / "输入.json"
        for s in segments:
            path.write_text(packed({"版本": 1, "段": [s]}))
            out = subprocess.check_output([ROOT / ".lake/build/bin/对拍", path], cwd=ROOT)
            s["期望"] = [json.loads(line) for line in out.splitlines()]
    (DEST / (name + ".json")).write_text(script_text({"段": segments}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*", help="黄金文件名（不含 .json），默认全部")
    parser.add_argument("-j", type=int, default=2, help="同时运行的 Lean 进程数")
    options = parser.parse_args()
    subprocess.run(["lake", "build", "对拍库", "对拍"], cwd=ROOT, check=True)
    DEST.mkdir(exist_ok=True)
    interfaces = interface_cases()
    names = options.names or [*CASES, *interfaces]
    for name in names:
        if name in interfaces:
            export_interface(name, interfaces[name])
    with ThreadPoolExecutor(max_workers=options.j) as pool:
        list(pool.map(export, [n for n in names if n not in interfaces]))
    size = sum(p.stat().st_size for p in DEST.glob("*.json"))
    if size > 20_000_000:
        raise SystemExit(f"黄金集合计 {size} B，超过 20 MB")
