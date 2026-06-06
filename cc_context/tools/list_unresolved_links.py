#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""List unresolved [[wikilink]] tokens in the repo memory tree."""
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
    names = {frontmatter_name(text, p[:-3]) for p, text in texts.items()}

    unresolved: list[tuple[str, str]] = []
    items = list(texts.items())
    memory_index = memory_dir / "MEMORY.md"
    if memory_index.exists():
        items.append(("MEMORY.md", memory_index.read_text(encoding="utf-8")))
    for filename, text in items:
        for match in LINK_RE.finditer(text):
            token = match.group(1).strip()
            if token.lower() not in names:
                unresolved.append((filename, token))

    print("unresolved count:", len(unresolved))
    for filename, token in unresolved:
        print(f"  [[{token}]]  in  {filename}")
    return 1 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
