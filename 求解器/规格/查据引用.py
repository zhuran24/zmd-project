#!/usr/bin/env python3
"""只读：列出 求解*.txt 里「据：」引用了、却在规则文件和求解文件里都找不到定义的名字。

名字的来源：规则文件、求解任务.txt、求解约束.txt、求解充分条件.txt、求解简化.txt 里
行首（去掉缩进后）是「名字：」的行，以及单独成行的短词（单位名、节标题）；
「存货/取货端口」这种写法拆成「存货端口」「取货端口」，原写法也算。
输出「文件:行号 名字」，一行一个；不改任何文件。规则改名、删条后用它找要重新核的约束。

用法：python3 求解器/规格/查据引用.py   （在仓库根目录下跑）
"""
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEF_FILES = ["《明日方舟：终末地》游戏规则.txt", "求解任务.txt", "求解约束.txt",
             "求解充分条件.txt", "求解简化.txt"]
CITE_FILES = ["求解约束.txt", "求解充分条件.txt", "求解简化.txt"]

NAME_RE = re.compile(r"^([^：:\s，。、；（）()「」]{1,24})[：:]")
BARE_RE = re.compile(r"^[^\s，。、；：:（）()「」0-9→＋+]{1,12}$")


def expand(name):
    out = {name}
    if "/" in name:
        a, b = name.split("/", 1)
        out.add(b)
        if len(b) > len(a):
            out.add(a + b[len(a):])
    return out


def defined_names():
    names = set()
    for f in DEF_FILES:
        p = os.path.join(ROOT, f)
        if not os.path.isfile(p):
            continue
        for line in open(p, encoding="utf-8"):
            s = line.strip()
            if not s:
                continue
            m = NAME_RE.match(s)
            if m:
                names |= expand(m.group(1))
            elif BARE_RE.match(s):
                names |= expand(s)
    return names


def main():
    names = defined_names()
    bad = []
    for f in CITE_FILES:
        p = os.path.join(ROOT, f)
        if not os.path.isfile(p):
            continue
        for no, line in enumerate(open(p, encoding="utf-8"), 1):
            m = re.match(r"^\s*据[：:](.*)$", line)
            if not m:
                continue
            for n in m.group(1).split("、"):
                n = n.strip().rstrip("。；;")
                if n and n not in names:
                    bad.append("%s:%d %s" % (f, no, n))
    for b in bad:
        print(b)
    print("共 %d 处" % len(bad), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
