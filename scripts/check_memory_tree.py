#!/usr/bin/env python3
"""Repo-native memory-tree health gate.

Checks the graph shape, index coverage, current-instance drift, optional live
mirror consistency, and the MEMORY.md size guard that prevents the tail of the
index from silently falling out of context.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MEMORY_DIR = PROJECT_ROOT / "cc_context" / "memory"
MAX_MEMORY_INDEX_BYTES = 24_576
LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
MD_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+\.md)\)")
NAME_RE = re.compile(r"(?m)^name:\s*(.+?)\s*$")
INSTANCE_OPEN_RE = re.compile(r"<!-- INSTANCE:[a-z0-9_]+ -->")
INSTANCE_SLOT_RE = re.compile(
    r"<!-- INSTANCE:([a-z0-9_]+) -->(?:(?!<!-- /?INSTANCE:).)*?<!-- /INSTANCE:\1 -->",
    re.DOTALL,
)


def _default_live_mirror() -> Path:
    repo_mirror = PROJECT_ROOT / "_cc_live_memory"
    if repo_mirror.exists():
        return repo_mirror
    return PROJECT_ROOT.parent / "_cc_live_memory"


DEFAULT_LIVE_MIRROR = _default_live_mirror()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _frontmatter_name(path: Path, text: str) -> str | None:
    if not text.startswith("---"):
        return None
    try:
        block = text.split("---", 2)[1]
    except IndexError:
        return None
    match = NAME_RE.search(block)
    if not match:
        return None
    raw = match.group(1).strip().strip('"').strip("'")
    return raw or None


def _load_memory(memory_dir: Path) -> tuple[dict[str, Path], dict[str, str], list[str]]:
    errors: list[str] = []
    name_to_path: dict[str, Path] = {}
    path_to_name: dict[str, str] = {}
    seen: dict[str, list[Path]] = defaultdict(list)

    files = sorted(p for p in memory_dir.glob("*.md") if p.name != "MEMORY.md")
    for path in files:
        text = _read(path)
        name = _frontmatter_name(path, text)
        if not name:
            errors.append(f"missing frontmatter name: {path.relative_to(PROJECT_ROOT)}")
            continue
        key = name.lower()
        seen[key].append(path)
        path_to_name[str(path)] = key

    for key, paths in seen.items():
        if len(paths) > 1:
            joined = ", ".join(str(p.relative_to(PROJECT_ROOT)) for p in paths)
            errors.append(f"duplicate memory name {key!r}: {joined}")
        else:
            name_to_path[key] = paths[0]
    return name_to_path, path_to_name, errors


def _check_links(memory_dir: Path, name_to_path: dict[str, Path], path_to_name: dict[str, str]) -> list[str]:
    errors: list[str] = []
    known = set(name_to_path)
    indeg = {name: 0 for name in known}
    outdeg = {name: 0 for name in known}
    unresolved: list[str] = []

    md_files = sorted(memory_dir.glob("*.md"))
    total = resolved = 0
    for path in md_files:
        text = _read(path)
        src = path_to_name.get(str(path))
        for match in LINK_RE.finditer(text):
            target = match.group(1).strip().lower()
            total += 1
            if target in known:
                resolved += 1
                indeg[target] = indeg.get(target, 0) + 1
                if src:
                    outdeg[src] = outdeg.get(src, 0) + 1
            else:
                unresolved.append(f"{path.name}: [[{match.group(1).strip()}]]")

    if unresolved:
        errors.append(f"unresolved wikilinks ({len(unresolved)}): " + "; ".join(unresolved[:12]))

    isolated = sorted(name for name in known if indeg.get(name, 0) == 0 and outdeg.get(name, 0) == 0)
    if isolated:
        errors.append(f"isolated memory nodes ({len(isolated)}): " + ", ".join(isolated[:20]))

    index_path = memory_dir / "MEMORY.md"
    if index_path.exists():
        index_text = _read(index_path)
        wiki_index_links = {m.group(1).strip().lower() for m in LINK_RE.finditer(index_text)}
        file_index_links = {Path(m.group(1).strip()).name for m in MD_LINK_RE.finditer(index_text)}
        covered: set[str] = set(wiki_index_links)
        for filename in file_index_links:
            path = memory_dir / filename
            if path.exists():
                name = _frontmatter_name(path, _read(path))
                if name:
                    covered.add(name.lower())
        missing = sorted(known - covered)
        if missing:
            errors.append(f"MEMORY.md missing {len(missing)} nodes: " + ", ".join(missing[:20]))
    else:
        errors.append("missing MEMORY.md")

    print(f"memory graph: nodes={len(known)}, links={total}, resolved={resolved}, unresolved={len(unresolved)}")
    return errors


def _check_instance_slots(memory_dir: Path) -> list[str]:
    errors: list[str] = []
    for path in sorted(memory_dir.glob("*.md")):
        text = _read(path)
        if "<!-- INSTANCE:" not in text:
            continue
        opens = len(INSTANCE_OPEN_RE.findall(text))
        slots = len(INSTANCE_SLOT_RE.findall(text))
        if opens != slots:
            errors.append(f"unbalanced INSTANCE slots in {path.name}: opens={opens}, complete_slots={slots}")
    return errors


def _check_stamp_engine(memory_dir: Path) -> list[str]:
    script = PROJECT_ROOT / "cc_context" / "tools" / "stamp_living_status.py"
    if not script.exists():
        return ["missing cc_context/tools/stamp_living_status.py"]
    result = subprocess.run(
        [sys.executable, str(script), "--memory-dir", str(memory_dir), "--check"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if result.returncode == 0:
        line = (result.stdout or "").strip().splitlines()
        if line:
            print(line[-1])
        return []
    details = (result.stdout + result.stderr).strip().splitlines()
    return ["memory INSTANCE sync check failed: " + (details[0] if details else "non-zero exit")]


def _check_memory_index_size(memory_dir: Path, limit: int) -> list[str]:
    index_path = memory_dir / "MEMORY.md"
    if not index_path.exists():
        return []
    size = len(index_path.read_bytes())
    print(f"MEMORY.md size: {size}/{limit} bytes")
    if size > limit:
        return [f"MEMORY.md too large: {size} > {limit} bytes"]
    return []


def _check_live_mirror(memory_dir: Path, mirror_dir: Path, *, require: bool) -> list[str]:
    if not mirror_dir.exists():
        if require:
            return [f"live mirror missing: {mirror_dir}"]
        print("live memory mirror: absent (skipped)")
        return []
    errors: list[str] = []
    repo_files = {p.name: p for p in memory_dir.glob("*.md")}
    mirror_files = {p.name: p for p in mirror_dir.glob("*.md")}
    missing = sorted(set(repo_files) - set(mirror_files))
    extra = sorted(set(mirror_files) - set(repo_files))
    if missing:
        errors.append("live mirror missing files: " + ", ".join(missing[:20]))
    if extra:
        errors.append("live mirror extra files: " + ", ".join(extra[:20]))
    diffs = []
    for name in sorted(set(repo_files) & set(mirror_files)):
        if repo_files[name].read_bytes() != mirror_files[name].read_bytes():
            diffs.append(name)
    if diffs:
        errors.append("live mirror byte drift: " + ", ".join(diffs[:20]))
    if errors and not require:
        print("live memory mirror: drift detected (non-blocking without --require-live-mirror)")
        for item in errors[:5]:
            print(f"  mirror note: {item}")
        return []
    if not errors:
        print(f"live memory mirror: {len(repo_files)} files byte-identical")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check repo memory-tree structural and currency health.")
    parser.add_argument("--memory-dir", type=Path, default=DEFAULT_MEMORY_DIR)
    parser.add_argument("--live-mirror", type=Path, default=DEFAULT_LIVE_MIRROR)
    parser.add_argument("--require-live-mirror", action="store_true")
    parser.add_argument("--max-memory-index-bytes", type=int, default=MAX_MEMORY_INDEX_BYTES)
    args = parser.parse_args()

    memory_dir = args.memory_dir.resolve()
    if not memory_dir.is_dir():
        print(f"memory dir not found: {memory_dir}", file=sys.stderr)
        return 1

    errors: list[str] = []
    name_to_path, path_to_name, load_errors = _load_memory(memory_dir)
    errors.extend(load_errors)
    errors.extend(_check_links(memory_dir, name_to_path, path_to_name))
    errors.extend(_check_instance_slots(memory_dir))
    errors.extend(_check_stamp_engine(memory_dir))
    errors.extend(_check_memory_index_size(memory_dir, args.max_memory_index_bytes))
    errors.extend(_check_live_mirror(memory_dir, args.live_mirror.resolve(), require=args.require_live_mirror))

    if errors:
        print("memory tree check failed:")
        for error in errors[:50]:
            print(f"  {error}")
        if len(errors) > 50:
            print(f"  ... {len(errors) - 50} more")
        return 1

    print(
        "memory tree check passed: "
        f"{len(name_to_path)} nodes, index within cap, graph/currency healthy"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
