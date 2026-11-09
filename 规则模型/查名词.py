#!/usr/bin/env python3
"""只读：核对规则模型的每条声明和规则文件的对应关系。

每条 def / abbrev / structure / inductive / class / theorem 前面都要有 /-- … -/ 文档注释，
注释第一行是下面七种之一：
  名词：……       规则文件里「名词：」那一行的原文（去掉缩进后逐字相同）。这条声明就是这个名词的定义。
  据：甲、乙      由规则文件的这几行推出来的辅助定义或定理；也可以写「规则里没有：」登记过的名字。
  规则里没有：名字  规则文件没写、写代码时不得不定下来的东西。要在 边界清单.md 里有一条。
  工具：……       和规则无关的表、数的引理。
  回放：……       把实测、现象写成编译时核对的测试用的脚手架。
  例子：……       照规则算一遍的小布局，不是实测。
  框架：……       模型的骨架（状态、操作这些），不对应规则文件的某一行。

输出：规则文件里已有定义的名词、还没有定义的名词数、「规则里没有」的名字、不合上面写法的声明。
有不合写法的声明时退出码为 1。规则文件某一行改了字，引它的那条声明会在这里报出来。

用法：python3 规则模型/查名词.py [-v]   （-v 列出还没有定义的名词）
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = os.path.join(HERE, "..", "《明日方舟：终末地》游戏规则.txt")
SRC = os.path.join(HERE, "Endfield")

NAME_RE = re.compile(r"^([^：:\s，。、；（）()「」]{1,24})[：:]")
DOC_DECL_RE = re.compile(
    r"/--((?:(?!-/).)*)-/\s*(?:@\[[^\]]*\]\s*)*(?:(?:private|protected|noncomputable)\s+)*"
    r"(theorem|def|abbrev|structure|inductive|class)\s+([^\s:({\[]+)", re.S)
DECL_RE = re.compile(
    r"^[ \t]*(?:(?:private|protected|noncomputable)\s+)*"
    r"(theorem|def|abbrev|structure|inductive|class)\s+([^\s:({\[]+)", re.M)


def expand(name):
    out = {name}
    if "/" in name:
        a, b = name.split("/", 1)
        out.add(b)
        if len(b) > len(a):
            out.add(a + b[len(a):])
    return out


def rule_nouns():
    lines = {}
    for line in open(RULES, encoding="utf-8"):
        s = line.strip()
        m = NAME_RE.match(s)
        if m:
            lines.setdefault(m.group(1), s)
    return lines


def main():
    verbose = "-v" in sys.argv[1:]
    nouns = rule_nouns()
    citable = set()
    for n in nouns:
        citable |= expand(n)
    defined, hidden, cites, errors = {}, [], [], []
    for root, _, files in os.walk(SRC):
        for f in sorted(files):
            if not f.endswith(".lean"):
                continue
            path = os.path.join(root, f)
            rel = os.path.relpath(path, HERE)
            text = open(path, encoding="utf-8").read()
            documented = set()
            for m in DOC_DECL_RE.finditer(text):
                decl = m.group(3)
                documented.add(m.start(2))
                first = m.group(1).strip().split("\n", 1)[0].strip()
                where = f"{rel}: {decl}"
                if first.startswith("据："):
                    cites.append((where, re.split("[、，]", first[2:].strip())))
                elif first.startswith("规则里没有："):
                    hidden.append((first[len("规则里没有："):].strip(), where))
                elif first.startswith(("工具：", "回放：", "例子：", "框架：")):
                    pass
                else:
                    nm = NAME_RE.match(first)
                    if not nm or nm.group(1) not in nouns:
                        errors.append(f"{where}：注释第一行不是规则文件的名词行，也没有标「据：」等：{first[:40]}")
                    elif first != nouns[nm.group(1)]:
                        errors.append(f"{where}：和规则文件「{nm.group(1)}」一行不一样\n    规则：{nouns[nm.group(1)]}\n    注释：{first}")
                    else:
                        defined.setdefault(nm.group(1), where)
            for m in DECL_RE.finditer(text):
                if m.start(1) not in documented:
                    errors.append(f"{rel}: {m.group(2)}：没有文档注释")
    hidden_names = {h for h, _ in hidden}
    for where, names in cites:
        for n in names:
            n = n.strip()
            if n and n not in citable and n not in hidden_names:
                errors.append(f"{where}：「据：{n}」在规则文件和「规则里没有」的名字里都找不到")
    print(f"规则文件的名词行 {len(nouns)} 个，规则模型里已有定义 {len(defined)} 个：")
    for n, w in defined.items():
        print(f"  {n}  ←  {w}")
    if verbose:
        print("还没有定义的名词：" + "、".join(n for n in nouns if n not in defined))
    print(f"规则里没有、写代码时定下来的 {len(hidden)} 个：")
    for h, w in hidden:
        print(f"  {h}  ←  {w}")
    if errors:
        print(f"不合写法的 {len(errors)} 处：")
        for e in errors:
            print("  " + e)
        sys.exit(1)
    print("不合写法的 0 处")


if __name__ == "__main__":
    main()
