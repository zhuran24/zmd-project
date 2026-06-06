#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Report memory link-graph health: nodes, edges, resolved/unresolved, isolated."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

DEFAULT_MEMORY_DIR = Path(__file__).resolve().parents[1] / "memory"
LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
NAME_RE = re.compile(r"(?m)^name:[ \t]*(.+?)[ \t]*$")


def frontmatter_name(text: str, fallback: str) -> str:
    match = NAME_RE.search(text)
    return (match.group(1).strip().strip('"').strip("'") if match else fallback).lower()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("memory_dir", nargs="?", type=Path, default=DEFAULT_MEMORY_DIR)
    args = parser.parse_args()

    memory_dir = args.memory_dir.resolve()
    files = sorted(p for p in memory_dir.glob("*.md") if p.name != "MEMORY.md")
    texts = {p.name: p.read_text(encoding="utf-8") for p in files}
    name_of = {p: frontmatter_name(text, p[:-3]) for p, text in texts.items()}
    names = set(name_of.values())

    indeg = {name: 0 for name in names}
    outdeg = {name: 0 for name in names}
    total = resolved = 0
    items = list(texts.items())
    memory_index = memory_dir / "MEMORY.md"
    if memory_index.exists():
        items.append(("MEMORY.md", memory_index.read_text(encoding="utf-8")))

    for filename, text in items:
        src = name_of.get(filename)
        for match in LINK_RE.finditer(text):
            target = match.group(1).strip().lower()
            total += 1
            if target in names:
                resolved += 1
                indeg[target] = indeg.get(target, 0) + 1
                if src in outdeg:
                    outdeg[src] += 1

    isolated = [name for name in names if indeg.get(name, 0) == 0 and outdeg.get(name, 0) == 0]
    print("files(nodes):", len(files))
    print("total links:", total, "resolved:", resolved, "unresolved:", total - resolved)
    print("isolated (0 in + 0 out):", len(isolated))
    for name in sorted(isolated):
        print("   ISO", name)
    return 1 if total != resolved or isolated else 0


if __name__ == "__main__":
    raise SystemExit(main())
