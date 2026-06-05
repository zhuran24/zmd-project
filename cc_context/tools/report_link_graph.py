# -*- coding: utf-8 -*-
"""Report link-graph health: nodes, edges, resolved/unresolved, isolated count."""
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
# nodes = files (by name). edges directed file->target name
indeg = {n: 0 for n in names}
outdeg = {n: 0 for n in names}
total = resolved = 0
mem_path = os.path.join(MEM, "MEMORY.md")
extra = []
if os.path.exists(mem_path):
    with io.open(mem_path, "r", encoding="utf-8") as fp:
        extra = [("MEMORY.md", fp.read())]
for f, t in list(texts.items()) + extra:
    src = name_of.get(f)
    for m in LINK_RE.finditer(t):
        tok = m.group(1).strip().lower()
        total += 1
        if tok in names:
            resolved += 1
            indeg[tok] = indeg.get(tok, 0) + 1
            if src in outdeg:
                outdeg[src] += 1
isolated = [n for n in names if indeg.get(n,0)==0 and outdeg.get(n,0)==0]
print("files(nodes):", len(files))
print("total links:", total, "resolved:", resolved, "unresolved:", total-resolved)
print("isolated (0 in + 0 out):", len(isolated))
for n in sorted(isolated):
    print("   ISO", n)
