#!/usr/bin/env python3
"""只读核对 + 生成表：`Endfield/作用.lean` 里「每样东西 × 每种事」的每一格有没有着落。

状态的字段从 `Endfield/框架.lean` 的 `structure «状态»` 读；每种操作从 `def «作用»` 的各个分支读，
走一步最后的计时从 `Endfield/框架.lean` 的 `def «计时»` 读。
每个分支里，每个字段那一行（`      «字段» := ……    -- 着落`）行尾的注释是这一格的着落，开头必须是
据、实测、没测、未定、待写、约定、无关 七种之一。少一格、多一格、没写着落、写法不在七种里，都报错，退出码 1。

用法：
  python3 规则模型/查格子.py          核对，并把表写到 规则模型/格子表.md
  python3 规则模型/查格子.py --check  只核对；格子表.md 和现在的代码对不上时也报错
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FRAME = os.path.join(HERE, "Endfield", "框架.lean")
ACT = os.path.join(HERE, "Endfield", "作用.lean")
OUT = os.path.join(HERE, "格子表.md")

KINDS = ["据", "实测", "没测", "未定", "待写", "约定", "无关"]
CASE_RE = re.compile(r"^  \| \.«([^»]+)»(?: \(\.«([^»]+)»)?")
FIELD_RE = re.compile(r"^      «([^»]+)» :=(.*)$")


def state_fields():
    text = open(FRAME, encoding="utf-8").read()
    body = text[text.index("structure «状态» where"):]
    body = body[:body.index("namespace «状态»")]
    return re.findall(r"^  «([^»]+)» :", body, re.M)


TICK_FIELD_RE = re.compile(r"^  «([^»]+)» :=(.*)$")


def cells():
    ops, table, errors = [], {}, []
    # 框架.lean 的 `计时`：走一步的最后一件事，写成和 `作用` 的一个分支一样的格子
    text = open(FRAME, encoding="utf-8").read()
    body = text[text.index("def «计时»"):]
    body = body[:body.index("/-- 判定顺序")]
    lines = [("计时", TICK_FIELD_RE, l) for l in body.split("\n")[1:]]
    ops.append("计时")
    table["计时"] = {}
    text = open(ACT, encoding="utf-8").read()
    body = text[text.index("def «作用»"):]
    lines += [(None, FIELD_RE, l) for l in body.split("\n")]
    op = None
    for fixed, field_re, line in lines:
        if fixed:
            op = fixed
        m = None if fixed else CASE_RE.match(line)
        if m:
            op = m.group(2) or m.group(1)
            ops.append(op)
            table[op] = {}
            continue
        m = field_re.match(line)
        if m and op:
            field, rest = m.group(1), m.group(2)
            if "--" not in rest:
                errors.append(f"{op} × {field}：这一行行尾没有写着落")
                continue
            note = rest.split("--", 1)[1].strip()
            kind = next((k for k in KINDS if note == k or note.startswith(k + "：")), None)
            if kind is None:
                errors.append(f"{op} × {field}：着落「{note}」不是七种写法之一")
                continue
            if field in table[op]:
                errors.append(f"{op} × {field}：写了两遍")
            table[op][field] = (kind, note[len(kind):].lstrip("："))
    return ops, table, errors


def render(fields, ops, table):
    out = []
    out.append("# 格子表")
    out.append("")
    out.append("由 `python3 查格子.py` 从 `Endfield/作用.lean` 生成，不要手改。")
    out.append("每一行是游戏记着的一样东西（状态的一个字段），每一列是会改变状态的一种事（一种操作），")
    out.append("格里写的是「这件事发生以后这样东西怎样变」这句话的着落：")
    out.append("")
    out.append("- 据：规则文件或求解任务的某一行写明了；实测：某次实测；")
    out.append("- 没测：没有哪一行写，照最自然的做法写了；未定：有不止一种说得通的做法，当参数带着；")
    out.append("- 待写：规则有，模型里还没写到；约定：只是模型里的记法；无关：这件事碰不到这样东西。")
    out.append("")
    out.append("「走一步」是五条判定加上最后的计时。五条判定还没写，等写出来以后各占一列；现在只有「计时」一列。")
    out.append("")
    cols = [o for o in ops if o != "走一步"]
    out.append("| | " + " | ".join(cols) + " |")
    out.append("|---|" + "---|" * len(cols))
    for f in fields:
        row = [table[o].get(f, ("缺", ""))[0] for o in cols]
        row = ["" if k == "无关" else k for k in row]
        out.append(f"| {f} | " + " | ".join(row) + " |")
    out.append("")
    count = {k: 0 for k in KINDS}
    for o in cols:
        for f in fields:
            k = table[o].get(f, ("缺", ""))[0]
            if k in count:
                count[k] += 1
    out.append("合计 " + "，".join(f"{k} {count[k]}" for k in KINDS) + "（空着的格是「无关」）。")
    for kind, title in (("未定", "未定的格"), ("没测", "没测的格"), ("待写", "待写的格"), ("实测", "实测的格")):
        rows = [(o, f, table[o][f][1]) for o in cols for f in fields
                if table[o].get(f, ("", ""))[0] == kind]
        if not rows:
            continue
        out.append("")
        out.append(f"## {title}")
        out.append("")
        for o, f, note in rows:
            out.append(f"- {o} × {f}：{note}")
    out.append("")
    return "\n".join(out)


def main():
    fields = state_fields()
    ops, table, errors = cells()
    for o in ops:
        if o == "走一步":
            continue
        for f in fields:
            if f not in table[o]:
                errors.append(f"{o} × {f}：没有这一格")
        for f in table[o]:
            if f not in fields:
                errors.append(f"{o} × {f}：状态里没有这个字段")
    if errors:
        print("有问题的格：")
        for e in errors:
            print("  " + e)
        sys.exit(1)
    text = render(fields, ops, table)
    n = (len(ops) - 1) * len(fields)
    if "--check" in sys.argv[1:]:
        old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        if old != text:
            print("格子表.md 和现在的代码对不上，重跑一次 python3 查格子.py")
            sys.exit(1)
        print(f"{len(fields)} 样东西 × {len(ops) - 1} 种事 = {n} 格，都有着落；格子表.md 是最新的。")
    else:
        open(OUT, "w", encoding="utf-8").write(text)
        print(f"{len(fields)} 样东西 × {len(ops) - 1} 种事 = {n} 格，都有着落；已写到 格子表.md。")


if __name__ == "__main__":
    main()
