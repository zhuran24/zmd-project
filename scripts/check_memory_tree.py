#!/usr/bin/env python3
"""Repo-native memory-tree health gate.

Checks the graph shape, index coverage, current-instance drift, optional live
mirror consistency, and the MEMORY.md size guard that prevents the tail of the
index from silently falling out of context.  If a clean observation point tracks
`_cc_live_memory/` inside the repository, that mirror is checked by default;
older CC layouts can still pass an external mirror with `--live-mirror`.
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
DEFAULT_LIVE_MIRROR = (
    PROJECT_ROOT / "_cc_live_memory"
    if (PROJECT_ROOT / "_cc_live_memory").exists()
    else PROJECT_ROOT.parent / "_cc_live_memory"
)
MAX_MEMORY_INDEX_BYTES = 24_576
LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
MD_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+\.md)\)")
NAME_RE = re.compile(r"(?m)^name:\s*(.+?)\s*$")
FACT_NAME_PREFIX = "fact-"
FACT_EXEMPTIONS = PROJECT_ROOT / "cc_context" / "memory_fact_projection_exemptions.txt"
INSTANCE_OPEN_RE = re.compile(r"<!-- INSTANCE:[a-z0-9_]+ -->")
INSTANCE_SLOT_RE = re.compile(
    r"<!-- INSTANCE:([a-z0-9_]+) -->(?:(?!<!-- /?INSTANCE:).)*?<!-- /INSTANCE:\1 -->",
    re.DOTALL,
)


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




def _frontmatter_block(text: str) -> str:
    if not text.startswith("---"):
        return ""
    try:
        return text.split("---", 2)[1]
    except IndexError:
        return ""


def _is_fact_node(path: Path, text: str, name: str | None = None) -> bool:
    nm = (name or _frontmatter_name(path, text) or "").lower()
    block = _frontmatter_block(text)
    return path.name.startswith("fact_") or nm.startswith(FACT_NAME_PREFIX) or bool(
        re.search(r"(?m)^\s*type:\s*fact\s*$", block)
    )


def _is_projection_candidate(path: Path, text: str) -> bool:
    """Projection nodes that must eventually point at at least one fact.

    The first rollout is incremental: existing unmatched feedback nodes live in a
    checked-in exemption file that should only shrink. New feedback/rule nodes not
    in that baseline must connect to fact layer immediately.
    """
    if path.name == "MEMORY.md" or _is_fact_node(path, text):
        return False
    block = _frontmatter_block(text)
    if path.name.startswith("feedback_"):
        return True
    return bool(re.search(r"(?m)^\s*type:\s*feedback\s*$", block))


def _load_fact_exemptions() -> set[str]:
    if not FACT_EXEMPTIONS.exists():
        return set()
    out: set[str] = set()
    for raw in FACT_EXEMPTIONS.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip().lower()
        if line:
            out.add(line)
    return out


def _fact_links_in(text: str, facts: set[str]) -> set[str]:
    return {m.group(1).strip().lower() for m in LINK_RE.finditer(text) if m.group(1).strip().lower() in facts}


def _check_fact_projection_contract(memory_dir: Path, name_to_path: dict[str, Path]) -> list[str]:
    """Hard gate for the normalized fact → projection layer.

    Checks the mechanical shape, not semantic truth: facts must be first-class
    nodes; every fact must have at least one projection backlink; new feedback
    projections must reference facts unless deliberately grandfathered.
    """
    errors: list[str] = []
    facts: set[str] = set()
    texts: dict[str, str] = {}
    paths_by_name: dict[str, Path] = {}
    for name, path in name_to_path.items():
        text = _read(path)
        texts[name] = text
        paths_by_name[name] = path
        if _is_fact_node(path, text, name):
            facts.add(name)
    if not facts:
        print("memory facts: none declared (fact contract skipped)")
        return []

    exemptions = _load_fact_exemptions()
    incoming: dict[str, list[str]] = {fact: [] for fact in facts}
    missing_refs: list[str] = []
    stale_exemptions: list[str] = []
    unknown_exemptions = sorted(exemptions - set(name_to_path))

    for name, path in paths_by_name.items():
        text = texts[name]
        if name in facts:
            continue
        refs = _fact_links_in(text, facts)
        for fact in refs:
            incoming[fact].append(name)
        if _is_projection_candidate(path, text):
            if refs:
                if name in exemptions:
                    stale_exemptions.append(name)
            elif name not in exemptions:
                missing_refs.append(name)

    orphan_facts = sorted(fact for fact, srcs in incoming.items() if not srcs)
    if orphan_facts:
        errors.append("fact nodes without projection backlinks: " + ", ".join(orphan_facts[:20]))
    if missing_refs:
        errors.append(
            "projection nodes missing fact refs (add [[fact-*]] or baseline only for legacy): "
            + ", ".join(sorted(missing_refs)[:20])
        )
    if unknown_exemptions:
        errors.append("unknown names in memory_fact_projection_exemptions.txt: " + ", ".join(unknown_exemptions[:20]))
    if stale_exemptions:
        errors.append(
            "baseline exemptions now have fact refs; remove them from memory_fact_projection_exemptions.txt: "
            + ", ".join(sorted(stale_exemptions)[:20])
        )

    edges = sum(len(srcs) for srcs in incoming.values())
    print(f"memory facts: facts={len(facts)}, projection_edges={edges}, baseline_exemptions={len(exemptions)}")
    return errors


def _check_harness_projection_sync(memory_dir: Path) -> list[str]:
    """If local harness exists, require repo→harness projection sync to be current.

    CI has no harness, so absence skips. On the owner machine this turns fact-node
    and projection drift into a local preflight blocker instead of a silent recall
    split-brain.
    """
    script = PROJECT_ROOT / "cc_context" / "tools" / "sync_memory_to_harness.py"
    harness_dir = Path.home() / ".claude" / "projects" / "C--claude-pj-zmd-pj" / "memory"
    if not script.exists() or not harness_dir.is_dir():
        return []
    result = subprocess.run(
        [sys.executable, str(script), "--check", "--repo-dir", str(memory_dir), "--harness-dir", str(harness_dir)],
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
    return ["repo→harness memory projection drift: " + (details[0] if details else "non-zero exit")]

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


_ARCHIVE_REF_EXEMPT = {"project_paradigm_death_timeline_27_lever.md"}

def _normalize_crosstree(text: str) -> str:
    """归一两树对 harness-only 节点的引用风格 (harness 用 [[slug]], cc_context 用
    散文 harness memory「slug」), 这样只把真内容 drift 报出来, 不误报合法风格差异。"""
    text = text.replace("harness memory「", "「")
    for token in ("[[", "]]", "「", "」"):
        text = text.replace(token, "")
    return text


def _check_harness_mirror(memory_dir: Path, harness_dir: Path | None = None) -> list[str]:
    """Warn (non-blocking) on content drift of co-maintained files between the
    project tree and the live CC harness tree.

    harness (~/.claude/projects/<slug>/memory, kebab operational memory) and
    cc_context/memory (snake project memory) are DIFFERENT content sets — only a
    few files live in both. We compare those (cross-tree wikilink style
    normalized away) so a harness edit that was not manually mirrored shows up
    loudly instead of silently diverging (the 2026-06-14 root cause). Harness
    unreachable (CI / fresh clone / other machine) -> skip. Never blocks.
    """
    if harness_dir is None:
        slug = re.sub(r"[^A-Za-z0-9]", "-", str(PROJECT_ROOT))
        harness_dir = Path.home() / ".claude" / "projects" / slug / "memory"
    if not harness_dir.is_dir():
        return []
    # 共维护文件 = 两树文件名交集 (动态发现, 含将来新增的共维护文件; harness kebab 与
    # cc_context snake 命名体系隔离, 交集即真共维护项, 不会误纳任一树独有的节点)。
    proj = {p.name: p for p in memory_dir.glob("*.md") if p.name != "MEMORY.md"}
    harn = {p.name: p for p in harness_dir.glob("*.md") if p.name != "MEMORY.md"}
    drift = [
        name
        for name in sorted(set(proj) & set(harn))
        if _normalize_crosstree(_read(proj[name])) != _normalize_crosstree(_read(harn[name]))
    ]
    if drift:
        return [
            "harness↔cc_context co-maintained drift (手动双写漏了, 同步 "
            f"cc_context+_cc_live+harness 三处): {', '.join(drift)}"
        ]
    return []


def _check_archived_dangling(memory_dir: Path, known: set[str], archive_dir: Path | None = None) -> list[str]:
    """Warn (non-blocking) if active prose references an archived node by bare slug.

    Wikilink form [[slug]] to an archived node is already caught by _check_links
    (unresolved). This catches the BARE prose form ("见 X") the link checker can
    not see — the 2026-06-14 cleanup found 26 such leftovers from the 2026-06-10
    slimming. A slug already annotated with (已归档)/(archived), or inside [[ ]],
    is fine. The dead-end timeline node intentionally points at archived single
    entries, so it is exempt.
    """
    archive_dir = archive_dir or PROJECT_ROOT / "cc_context" / "memory_archive"
    if not archive_dir.is_dir():
        return []
    archive_slugs: set[str] = set()
    for path in archive_dir.glob("*.md"):
        name = _frontmatter_name(path, _read(path))
        if name:
            archive_slugs.add(name.lower())
    archive_only = archive_slugs - known
    if not archive_only:
        return []
    hits: list[str] = []
    for path in sorted(memory_dir.glob("*.md")):
        if path.name == "MEMORY.md" or path.name in _ARCHIVE_REF_EXEMPT:
            continue
        text = _read(path).lower()
        for slug in sorted(archive_only):
            for match in re.finditer(re.escape(slug), text):
                if text[max(0, match.start() - 2):match.start()] == "[[":
                    continue
                if re.match(r"\s*[(（](?:已归档|archived)", text[match.end():match.end() + 10]):
                    continue
                hits.append(f"{path.name}: '{slug}'")
                break
    if hits:
        return [
            "archived-node prose refs not annotated (顺指针会扑空, 标 (已归档)): "
            + "; ".join(hits[:12])
        ]
    return []


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
    warnings: list[str] = []
    name_to_path, path_to_name, load_errors = _load_memory(memory_dir)
    errors.extend(load_errors)
    errors.extend(_check_links(memory_dir, name_to_path, path_to_name))
    errors.extend(_check_fact_projection_contract(memory_dir, name_to_path))
    errors.extend(_check_instance_slots(memory_dir))
    errors.extend(_check_stamp_engine(memory_dir))
    errors.extend(_check_memory_index_size(memory_dir, args.max_memory_index_bytes))
    errors.extend(_check_live_mirror(memory_dir, args.live_mirror.resolve(), require=args.require_live_mirror))
    # Finding 2 (owner 2026-06-15): harness 投影同步降为 warning, 不进 errors —— 与既有
    # _check_harness_mirror 一致。harness 不进自动 gate (CI 无 harness 本就 skip); 不让
    # harness 存量 drift 物理挡 owner 本机 pre-push。漏同步靠此 warning + 落地 runbook 的
    # sync --apply 步兜。
    warnings.extend(_check_harness_projection_sync(memory_dir))
    warnings.extend(_check_harness_mirror(memory_dir))
    warnings.extend(_check_archived_dangling(memory_dir, set(name_to_path)))

    if warnings:
        print("memory tree warnings (non-blocking):")
        for warning in warnings[:20]:
            print(f"  WARN {warning}")

    if errors:
        print("memory tree check failed:")
        for error in errors[:50]:
            print(f"  {error}")
        if len(errors) > 50:
            print(f"  ... {len(errors) - 50} more")
        return 1

    suffix = f", {len(warnings)} warning(s)" if warnings else ""
    print(
        "memory tree check passed: "
        f"{len(name_to_path)} nodes, index within cap, graph/currency healthy{suffix}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
