#!/usr/bin/env python3
"""Repo-native memory tree health gate."""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MEMORY_DIR = PROJECT_ROOT / "cc_context" / "memory"
DEFAULT_LIVE_MEMORY_DIR = PROJECT_ROOT / "_cc_live_memory"
SOFT_INDEX_BYTES = 24_576
HARD_INDEX_BYTES = 32_768
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
MD_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+\.md)(?:#[^)]+)?\)")
NAME_RE = re.compile(r"^name:\s*(.+?)\s*$", re.MULTILINE)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _files(memory_dir: Path) -> list[Path]:
    return sorted(p for p in memory_dir.glob("*.md") if p.is_file())


def _name(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    match = NAME_RE.search(text[:end])
    return match.group(1).strip().strip("'\"") if match else None


def check(memory_dir: Path, live_memory_dir: Path, *, require_live_mirror: bool) -> int:
    blockers: list[str] = []
    warnings: list[str] = []
    if not memory_dir.exists():
        print(f"memory tree check BLOCKED: missing {memory_dir}")
        return 1

    files = _files(memory_dir)
    by_name: dict[str, Path] = {}
    duplicates: dict[str, list[str]] = {}
    for path in files:
        if path.name == "MEMORY.md":
            continue
        name = _name(path)
        if not name:
            blockers.append(f"missing frontmatter name: {path.name}")
            continue
        if name in by_name:
            duplicates.setdefault(name, [by_name[name].name]).append(path.name)
        by_name[name] = path
    for name, paths in duplicates.items():
        blockers.append(f"duplicate memory name {name!r}: {', '.join(paths)}")

    stems = {p.stem for p in files if p.name != "MEMORY.md"}
    unresolved: list[str] = []
    total_links = 0
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for target in WIKILINK_RE.findall(text):
            total_links += 1
            target = target.strip()
            if target not in by_name and target not in stems:
                unresolved.append(f"{path.name} -> [[{target}]]")
    if unresolved:
        blockers.append(f"unresolved wikilinks: {len(unresolved)}")

    index = memory_dir / "MEMORY.md"
    if not index.exists():
        blockers.append("MEMORY.md missing")
    else:
        raw = index.read_bytes()
        if len(raw) > HARD_INDEX_BYTES:
            blockers.append(f"MEMORY.md too large: {len(raw)} > {HARD_INDEX_BYTES}")
        elif len(raw) > SOFT_INDEX_BYTES:
            warnings.append(f"MEMORY.md near soft limit: {len(raw)} > {SOFT_INDEX_BYTES}")
        text = raw.decode("utf-8", errors="replace")
        linked = {Path(rel).name for rel in MD_LINK_RE.findall(text)}
        linked.update(f"{target.strip()}.md" for target in WIKILINK_RE.findall(text))
        expected = {p.name for p in files if p.name != "MEMORY.md"}
        missing = sorted(expected - linked)
        if missing:
            blockers.append(f"MEMORY.md missing {len(missing)} file link(s): {', '.join(missing[:10])}")

    if live_memory_dir.exists():
        repo = {p.name: p for p in _files(memory_dir)}
        live = {p.name: p for p in _files(live_memory_dir)}
        missing = sorted(set(repo) - set(live))
        extra = sorted(set(live) - set(repo))
        mismatch = sorted(n for n in set(repo) & set(live) if _sha256(repo[n]) != _sha256(live[n]))
        if missing or extra or mismatch:
            blockers.append(
                "live memory mirror mismatch: "
                f"missing={len(missing)}, extra={len(extra)}, byte_mismatch={len(mismatch)}"
            )
    elif require_live_mirror:
        blockers.append("live memory mirror missing")
    else:
        warnings.append("live memory mirror absent; skipped")

    print(f"memory files: {len(files)}; named nodes: {len(by_name)}; wikilinks: {total_links}")
    for item in unresolved[:20]:
        print(f"  unresolved {item}")
    for item in warnings[:20]:
        print(f"  WARN {item}")
    if blockers:
        print(f"memory tree check BLOCKED: {len(blockers)} blocker(s)")
        for item in blockers[:20]:
            print(f"  BLOCK {item}")
        return 1
    print(f"memory tree check passed: {len(files)} files, {len(warnings)} warning(s)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check memory tree structural health")
    parser.add_argument("--memory-dir", type=Path, default=DEFAULT_MEMORY_DIR)
    parser.add_argument("--live-memory-dir", type=Path, default=DEFAULT_LIVE_MEMORY_DIR)
    parser.add_argument("--require-live-mirror", action="store_true")
    args = parser.parse_args()
    return check(args.memory_dir.resolve(), args.live_memory_dir.resolve(), require_live_mirror=args.require_live_mirror)


if __name__ == "__main__":
    raise SystemExit(main())
