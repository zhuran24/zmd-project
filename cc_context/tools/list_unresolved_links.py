# -*- coding: utf-8 -*-
"""列出记忆树里 unresolved 的 [[wikilink]] (token + 出处文件), 配 report_link_graph.py 用。"""
import re
import os
import io
import sys

MEM = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Lenovo\.claude\projects\D-----zmd\memory"
LINK_RE = re.compile(r'\[\[([^\]\|]+?)\]\]')

files = [f for f in os.listdir(MEM) if f.endswith(".md") and f != "MEMORY.md"]
name_of = {}
texts = {}
for f in files:
    with io.open(os.path.join(MEM, f), "r", encoding="utf-8") as fp:
        t = fp.read()
    texts[f] = t
    m = re.search(r'(?m)^name:[ \t]*(.+?)[ \t]*$', t)
    name_of[f] = (m.group(1).strip() if m else f).lower()

names = set(name_of.values())
mem_path = os.path.join(MEM, "MEMORY.md")
extra = []
if os.path.exists(mem_path):
    with io.open(mem_path, "r", encoding="utf-8") as fp:
        extra = [("MEMORY.md", fp.read())]

unresolved = []
for f, t in list(texts.items()) + extra:
    for m in LINK_RE.finditer(t):
        tok = m.group(1).strip().lower()
        if tok not in names:
            unresolved.append((f, m.group(1).strip()))

print("unresolved count:", len(unresolved))
for f, tok in unresolved:
    print("  [[%s]]  in  %s" % (tok, f))
