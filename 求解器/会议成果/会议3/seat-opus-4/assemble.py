#!/usr/bin/env python3
"""把各节主责席交来的段落拼成 会议目录/共识稿.md。只拼，不改内容。缺的段落留「待交」。"""
import os, hashlib, sys
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def part(paths, fallback):
    for path in ([paths] if isinstance(paths, str) else paths):
        p = os.path.join(D, path)
        if os.path.exists(p):
            return open(p, encoding='utf-8').read().strip()
    return fallback
head = """# 会议 3 共识稿

拼稿人 seat-opus-4：只拼各节主责席交来的段落，不改结论。每节标主责席和核过席。测点的「只说明这一次」写在测点那一行里。长论证见各席 会议目录/seat-*.md。

冻结规矩：冻结版文件名带 SHA256 前 8 位、写入后只读；按 SHA 投票；只有实质反对才换版；认可后的纯补充记在文末勘误，不换版。

交付的是什么（seat-codex-3 的措辞）：一套能覆盖全部达标布局的表示基准、附条件的放松层与候选发生方案、相应的证明边界和已完成的测点；没有证明完整模型在 70×70 上解得动，也没有交付达标布局。"""
secs = [
    "## 一、问题 1：带子这一层怎么表示",
    (lambda t: t if t.startswith("#") else "### 1.1 精确表示与实测（主责 seat-opus-2）\n\n" + t)(part(["seat-opus-2/共识稿-问题1节.md", "seat-opus-2/共识段-精确表示.md"], "（待交）")),
    part("seat-opus-1/共识段-分解与割.md", "### 1.2 分解与割（主责 seat-opus-1）\n\n（待交）").replace("### 分解与割", "### 1.2 分解与割", 1),
    part(["seat-opus-3/共识稿-1.3段.md", "seat-opus-3/共识段-L侧.md"], "### 1.3 抬 L 的受限表示（主责 seat-opus-3）\n\n（待交）").split("\n---\n")[0].strip(),
    part(["seat-codex-1/共识段-覆盖与未决.md", "seat-codex-1/共识段-覆盖审计.md"], "### 1.4 覆盖审计（核过 seat-codex-1）\n\n（待签）").split("\n## 可并入")[0].strip(),
    part("seat-opus-1/共识段-问题2.md", "## 二、问题 2\n\n（待交）"),
    part("seat-opus-4/共识段-问题3.md", "## 三、问题 3\n\n（待交）"),
]
four, five = [], []
for f in ["seat-opus-1/共识段-四五.md", "seat-opus-2/共识段-四五.md", "seat-opus-3/共识段-四五.md", "seat-opus-4/共识段-四五.md",
          "seat-codex-1/共识段-四五.md", "seat-codex-2/共识段-四五.md", "seat-codex-3/共识段-四五.md", "seat-codex-4/共识段-四五.md"]:
    p = os.path.join(D, f)
    if not os.path.exists(p):
        continue
    who = f.split("/")[0]
    txt = open(p, encoding='utf-8').read()
    cur = None
    for line in txt.splitlines():
        if line.startswith("四、"): cur = four; continue
        if line.startswith("五、"): cur = five; continue
        if cur is not None and line.startswith("- "):
            cur.append(line + f"（{who}）")
p1 = os.path.join(D, "seat-codex-1/共识段-覆盖与未决.md")
if os.path.exists(p1):
    txt = open(p1, encoding='utf-8').read()
    cur = None
    for line in txt.splitlines():
        if line.startswith("## 可并入“问题之外”"): cur = "four"; continue
        if line.startswith("## 可并入“未决”"): cur = "five"; continue
        if line.startswith("#"): cur = None; continue
        if cur == "four" and line.strip():
            four.append("- " + line.strip() + "（seat-codex-1）")
        if cur == "five" and line.startswith("- "):
            five.append(line + "（seat-codex-1）")
import re
p2 = os.path.join(D, "seat-codex-2.md")
if os.path.exists(p2):
    txt = open(p2, encoding='utf-8').read()
    cur = None
    for line in txt.splitlines():
        if line.startswith("## 十、"): cur = "four"; continue
        if line.startswith("## 十一、"): cur = "five"; continue
        if line.startswith("## "): cur = None; continue
        if cur == "four" and line.startswith("> "):
            four.append("- " + line[2:].strip() + "（seat-codex-2）")
        if cur == "five" and re.match(r"^\d+\. ", line):
            five.append("- " + re.sub(r"^\d+\. ", "", line).strip() + "（seat-codex-2）")
p3 = os.path.join(D, "seat-opus-3/共识稿-1.3段.md")
if os.path.exists(p3):
    tail = open(p3, encoding='utf-8').read().split("\n---\n", 1)
    if len(tail) == 2:
        five.extend(l + "（seat-opus-3）" for l in tail[1].splitlines() if l.startswith("- "))
# 割侧方向（seat-codex-2.md 9.2、seat-codex-3.md 第四节）：拼稿人按两席原意替换 seat-opus-2 条目里的一句，归属写在句内
CUT_OLD = "供按 d(X)+l(出X) ≤ u(入X) 复核"
CUT_NEW = ("复核时取原网络结点中它的补集 X（去掉超级源汇），看 d(X)+l(出X) ≤ u(入X) 是否违反；直接用源侧原结点集 R 则看 "
           "−d(R)+l(入R) ≤ u(出R)（集合方向按 seat-codex-2.md 9.2、seat-codex-3.md 第四节补）")
hit = [i for i, l in enumerate(four) if CUT_OLD in l]
assert len(hit) == 1, hit
four[hit[0]] = four[hit[0]].replace(CUT_OLD, CUT_NEW)
pe = os.path.join(D, "seat-opus-4/勘误条目.md")
errata = "\n".join(l for l in open(pe, encoding="utf-8").read().splitlines() if l.startswith("- ")) if os.path.exists(pe) else ""
body = "\n\n".join([head] + secs + ["## 四、问题之外，和几何求解要紧相关的", "\n".join(four) or "（待交）",
                                   "## 五、未决", "\n".join(five) or "（待交）", "## 勘误", errata or "（冻结后用）"]) + "\n"
out = os.path.join(D, "共识稿.md")
open(out, "w", encoding="utf-8").write(body)
print(out, hashlib.sha256(body.encode()).hexdigest())
