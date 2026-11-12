#!/usr/bin/env python3
"""只读：核对 `Endfield/命题.lean` 里的每条命题都已证出来，而且证明里没有留空。

做三件事：
1. 列出 `Endfield/命题.lean` 里的全部命题（`def «名» : Prop :=`）；
2. 在 `Endfield/证明/` 的源文件里找留空和绕过检查的写法（sorry、admit、axiom、native_decide、unsafe、
   implemented_by、partial、opaque），找到一处就报错；
3. 让 Lean 对每条命题打印 `Endfield.«定理».«名»` 用到的公理（`#print axioms`）。`证明/总.lean` 里
   `«定理».«名»` 的类型就是 `«命题».«名»`，所以有这条定理、它又只用到 Lean 自带的三条公理
   （propext、Classical.choice、Quot.sound），这条命题就是证完了的。

要先 `lake build`（这里读的是编译好的模块）。全部通过退出码为 0。

用法：python3 规则模型/查证明.py
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CONTRACT = os.path.join(HERE, "Endfield", "命题.lean")
PROOFS = os.path.join(HERE, "Endfield", "证明")
OK_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}
BANNED = re.compile(r"\b(sorry|admit|native_decide|implemented_by)\b|^\s*(axiom|unsafe|partial|opaque)\b", re.M)


def strip_comments(text):
    text = re.sub(r"/-.*?-/", "", text, flags=re.S)
    return re.sub(r"--.*", "", text)


def main():
    names = re.findall(r"^def («[^»]+») : Prop :=", open(CONTRACT, encoding="utf-8").read(), re.M)
    errors = []
    for root, _, files in os.walk(PROOFS):
        for f in sorted(files):
            if not f.endswith(".lean"):
                continue
            path = os.path.join(root, f)
            code = strip_comments(open(path, encoding="utf-8").read())
            for m in BANNED.finditer(code):
                line = code.count("\n", 0, m.start()) + 1
                errors.append(f"{os.path.relpath(path, HERE)} 第 {line} 行附近：{m.group(0).strip()}")
    src = "import Endfield.«证明».«总»\n" + "".join(
        f"#print axioms Endfield.«定理».{n}\n" for n in names)
    with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False, encoding="utf-8") as tmp:
        tmp.write(src)
    try:
        env = dict(os.environ)
        env["PATH"] = os.path.expanduser("~/.elan/bin") + os.pathsep + env.get("PATH", "")
        out = subprocess.run(["lake", "env", "lean", tmp.name], cwd=HERE, env=env,
                             capture_output=True, text=True)
    finally:
        os.unlink(tmp.name)
    text = out.stdout + out.stderr
    done = 0
    for n in names:
        m = re.search(r"'Endfield\.«定理»\." + re.escape(n) + r"' (depends on axioms: \[([^\]]*)\]|does not depend on any axioms)", text)
        if not m:
            errors.append(f"{n}：没有证出来（找不到 Endfield.«定理».{n}）")
            continue
        axioms = {a.strip() for a in (m.group(2) or "").replace("\n", " ").split(",") if a.strip()}
        extra = axioms - OK_AXIOMS
        if extra:
            errors.append(f"{n}：用到了不该用的公理 {sorted(extra)}")
        else:
            done += 1
            print(f"  已证  {n}" + (f"（公理：{'、'.join(sorted(axioms))}）" if axioms else "（不用公理）"))
    print(f"命题 {len(names)} 条，已证 {done} 条")
    if errors:
        print(f"有问题的 {len(errors)} 处：")
        for e in errors:
            print("  " + e)
        if out.returncode != 0 and not done:
            print(text[-2000:])
        sys.exit(1)


if __name__ == "__main__":
    main()
