from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .frontmatter import extract_wikilinks, read_markdown_node

MAX_MEMORY_BYTES = 24_576
HARD_EDGE_TYPES = {"DEPENDS_ON", "DERIVED_FROM", "SUPERSEDES", "CONTRADICTS"}
ORIGIN_PRIORITY = {
    "inferred": 10,
    "overlay": 20,
    "frontmatter": 30,
}
EDGE_PRIORITY = {
    "RELATED_TO": 10,
    "MENTIONS": 20,
    "SUPPORTS": 30,
    "PROJECTS_TO": 40,
    "CONTRADICTS": 70,
    "SUPERSEDES": 80,
    "DERIVED_FROM": 90,
    "DEPENDS_ON": 100,
}


def sha_text(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def normalize_slug(value: str) -> str:
    value = value.strip()
    value = value.replace("_", "-")
    value = re.sub(r"[^A-Za-z0-9\-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value.lower()


def short_text(value: str, cap: int = 92) -> str:
    value = re.sub(r"\s+", " ", value.strip())
    if len(value) <= cap:
        return value
    cut = value[:cap]
    for token in ["。", "；", "，", ",", ";", ":", " "]:
        idx = cut.rfind(token)
        if idx > cap // 2:
            return cut[:idx].rstrip(" ，,;；:") + "…"
    return cut.rstrip() + "…"


def _edge_rank(edge: "Edge") -> tuple[int, int]:
    return (ORIGIN_PRIORITY.get(edge.origin, 0), EDGE_PRIORITY.get(edge.type, 0))


@dataclass
class Node:
    id: str
    file: str
    kind: str
    title: str
    description: str
    index_summary: str
    status: str = "active"
    body_sha: str = ""
    desc_sha: str = ""
    idx_sha: str = ""
    wikilinks: list[str] = field(default_factory=list)

    @property
    def is_fact(self) -> bool:
        return self.kind == "fact" or self.id.startswith("fact-")


@dataclass
class Edge:
    source: str
    target: str
    type: str
    hard: bool = False
    reason: str = ""
    source_file: str = ""
    line: int | None = None
    origin: str = "inferred"

    def key(self) -> tuple[str, str]:
        return (self.source, self.target)

    def typed_key(self) -> tuple[str, str, str]:
        return (self.source, self.type, self.target)


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class MemoryGraph:
    nodes: dict[str, Node]
    edges: list[Edge]
    mem_dir: Path
    graph_dir: Path
    overlay_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": {k: asdict(v) for k, v in sorted(self.nodes.items())},
            "edges": [asdict(e) for e in sorted(self.edges, key=lambda x: (x.source, x.type, x.target))],
        }

    def write_json(self, path: Path | None = None) -> Path:
        if path is None:
            path = self.graph_dir / "generated" / "graph.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8", newline="\n")
        return path

    def reverse_dependents(self, node_id: str, include_soft: bool = False) -> list[tuple[int, Edge, Node]]:
        """Return nodes affected by a change to node_id.

        Hard dependency direction is dependent -> dependency. Impact travels in the
        reverse direction: dependency -> dependent.
        """
        if node_id not in self.nodes:
            raise KeyError(f"unknown node: {node_id}")
        reverse: dict[str, list[Edge]] = defaultdict(list)
        for edge in self.edges:
            if include_soft or edge.hard or edge.type in HARD_EDGE_TYPES:
                reverse[edge.target].append(edge)
        seen = {node_id}
        q: deque[tuple[str, int]] = deque([(node_id, 0)])
        out: list[tuple[int, Edge, Node]] = []
        while q:
            cur, depth = q.popleft()
            for edge in sorted(reverse.get(cur, []), key=lambda e: (e.source, e.type)):
                dep = edge.source
                if dep in seen or dep not in self.nodes:
                    continue
                seen.add(dep)
                node = self.nodes[dep]
                out.append((depth + 1, edge, node))
                q.append((dep, depth + 1))
        return out

    def validate(self, *, check_memory_cap: bool = True, check_live_mirror: bool = True) -> ValidationReport:
        report = ValidationReport()
        report.stats = {
            "nodes": len(self.nodes),
            "facts": sum(1 for n in self.nodes.values() if n.is_fact),
            "entries": sum(1 for n in self.nodes.values() if not n.is_fact),
            "edges": len(self.edges),
            "hard_edges": sum(1 for e in self.edges if e.hard or e.type in HARD_EDGE_TYPES),
        }
        report.errors.extend(self.overlay_errors)
        by_typed: set[tuple[str, str, str]] = set()
        for edge in self.edges:
            if edge.type not in EDGE_PRIORITY:
                report.errors.append(f"unknown edge type: {edge.type} ({edge.source}->{edge.target})")
            if edge.source not in self.nodes:
                report.errors.append(f"edge source missing: {edge.source} --{edge.type}--> {edge.target}")
            if edge.target not in self.nodes:
                report.errors.append(f"edge target missing: {edge.source} --{edge.type}--> {edge.target}")
            if edge.typed_key() in by_typed:
                report.warnings.append(f"duplicate edge: {edge.source} --{edge.type}--> {edge.target}")
            by_typed.add(edge.typed_key())
            if edge.type == "DEPENDS_ON" and edge.target in self.nodes and not self.nodes[edge.target].is_fact:
                report.warnings.append(f"DEPENDS_ON target is not a fact: {edge.source} -> {edge.target}")

        for node in self.nodes.values():
            if not node.description:
                report.errors.append(f"node missing description: {node.id} ({node.file})")
            if not node.index_summary:
                report.errors.append(f"node missing index_summary: {node.id} ({node.file})")
            if len(node.index_summary) > 180:
                report.warnings.append(f"index_summary too long ({len(node.index_summary)} chars): {node.id}")

        # Hard dependency cycles are almost always a modeling error.
        graph: dict[str, list[str]] = defaultdict(list)
        for edge in self.edges:
            if edge.type in HARD_EDGE_TYPES or edge.hard:
                graph[edge.source].append(edge.target)
        temp: set[str] = set()
        perm: set[str] = set()
        stack: list[str] = []
        sys.setrecursionlimit(max(10_000, len(self.nodes) * 2 + 100))

        def visit(n: str) -> None:
            if n in perm:
                return
            if n in temp:
                cycle = stack[stack.index(n):] + [n] if n in stack else [n]
                report.errors.append("hard dependency cycle: " + " -> ".join(cycle))
                return
            temp.add(n)
            stack.append(n)
            for m in graph.get(n, []):
                if m in self.nodes:
                    visit(m)
            stack.pop()
            temp.remove(n)
            perm.add(n)

        for n in sorted(self.nodes):
            visit(n)

        if check_memory_cap:
            mem_md = self.mem_dir / "MEMORY.md"
            if mem_md.exists():
                size = len(mem_md.read_bytes())
                report.stats["MEMORY.md_bytes"] = size
                if size > MAX_MEMORY_BYTES:
                    report.errors.append(f"MEMORY.md over cap: {size}/{MAX_MEMORY_BYTES} bytes")

        if check_live_mirror:
            live_dir = self.mem_dir.parents[1] / "_cc_live_memory" if len(self.mem_dir.parents) >= 2 else None
            # mem_dir = ROOT/cc_context/memory -> parents[1] = ROOT
            if live_dir and live_dir.exists():
                drift = []
                for path in sorted(self.mem_dir.glob("*.md")):
                    other = live_dir / path.name
                    if not other.exists():
                        drift.append(f"missing in _cc_live_memory: {path.name}")
                    elif path.read_bytes() != other.read_bytes():
                        drift.append(f"byte drift: {path.name}")
                for other in sorted(live_dir.glob("*.md")):
                    if not (self.mem_dir / other.name).exists():
                        drift.append(f"live-only file: {other.name}")
                report.stats["live_mirror_drift"] = len(drift)
                for item in drift[:20]:
                    report.warnings.append(item)
                if len(drift) > 20:
                    report.warnings.append(f"... {len(drift)-20} more live mirror drift items")
        return report


def load_nodes(mem_dir: Path) -> dict[str, Node]:
    nodes: dict[str, Node] = {}
    for path in sorted(mem_dir.glob("*.md")):
        if path.name == "MEMORY.md":
            continue
        raw = read_markdown_node(path)
        name = raw.meta.get("name") or path.stem
        node_id = normalize_slug(str(name))
        meta_type = str(raw.meta.get("metadata.type") or raw.meta.get("type") or "").strip().lower()
        if meta_type in {"fact", "feedback", "project", "reference", "design", "user"}:
            kind = "fact" if meta_type == "fact" or node_id.startswith("fact-") else "entry"
        else:
            kind = "fact" if node_id.startswith("fact-") or path.stem.startswith("fact_") else "entry"
        desc = str(raw.meta.get("description") or "").strip()
        idx = str(raw.meta.get("index_summary") or "").strip()
        status = str(raw.meta.get("status") or "active").strip() or "active"
        nodes[node_id] = Node(
            id=node_id,
            file=path.name,
            kind=kind,
            title=node_id,
            description=desc,
            index_summary=idx,
            status=status,
            body_sha=sha_text(raw.body),
            desc_sha=sha_text(desc),
            idx_sha=sha_text(idx),
            wikilinks=extract_wikilinks(raw.body),
        )
    return nodes


def _node_aliases(nodes: dict[str, Node]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in nodes.values():
        aliases[node.id] = node.id
        aliases[normalize_slug(Path(node.file).stem)] = node.id
        if node.id.startswith("feedback-"):
            aliases[node.id.removeprefix("feedback-")] = node.id
        if node.id.startswith("project-"):
            aliases[node.id.removeprefix("project-")] = node.id
        if node.id.startswith("reference-"):
            aliases[node.id.removeprefix("reference-")] = node.id
    return aliases


def _frontmatter_links(meta: dict[str, Any], key: str) -> list[str]:
    value = meta.get(key)
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    out: list[str] = []
    for item in values:
        text = str(item).strip()
        if text:
            out.append(text)
    return out


def _frontmatter_field_line(frontmatter: str, key: str) -> int | None:
    pattern = re.compile(rf"^{re.escape(key)}\s*:")
    for lineno, line in enumerate(frontmatter.splitlines(), start=2):
        if pattern.match(line):
            return lineno
    return None


def _strip_list_marker(line: str) -> str:
    stripped = line.strip()
    stripped = re.sub(r"^(?:>\s*)+", "", stripped).strip()
    return re.sub(r"^(?:[-*+]\s+|\d+[.)]\s+)", "", stripped).strip()


def _is_see_also_context(line: str) -> bool:
    """Only softens lines that are just a see-also label plus wikilinks."""
    stripped = _strip_list_marker(line)
    if not extract_wikilinks(stripped):
        return False
    label = re.match(
        r"^(?:"
        r"相关(?:事实|节点|条目)?|参见|另见|见|"
        r"see\s+also\b|also\s+see\b|seealso\b|related\b(?:\s+(?:facts?|nodes?|entries?))?"
        r")\s*(?::|：|-|--|—)?\s*",
        stripped,
        flags=re.IGNORECASE,
    )
    if not label:
        return False
    rest = stripped[label.end():].strip()
    if not rest:
        return False
    without_links = re.sub(r"\[\[[^\]]+\]\]", "", rest)
    residue = re.sub(r"[\s,，、;；/|+&()（）\[\]{}<>《》:：.。\-—–]+", "", without_links)
    return not residue


def _is_projection_heading(line: str) -> tuple[int, bool]:
    match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line.strip())
    if not match:
        return 0, False
    level = len(match.group(1))
    title = match.group(2).strip()
    return level, level >= 2 and "投影" in title


def _is_list_item(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith(("- ", "* ", "+ ")) or bool(re.match(r"^\d+[.)]\s+", stripped))


def infer_edges(mem_dir: Path, nodes: dict[str, Node]) -> list[Edge]:
    aliases = _node_aliases(nodes)
    edges: dict[tuple[str, str], Edge] = {}

    def add(edge: Edge) -> None:
        if edge.source == edge.target:
            return
        key = edge.key()
        prev = edges.get(key)
        if prev is None or _edge_rank(edge) > _edge_rank(prev):
            edges[key] = edge

    for node in nodes.values():
        raw = read_markdown_node(mem_dir / node.file)
        depends_on_line = _frontmatter_field_line(raw.frontmatter, "depends_on")
        for link in _frontmatter_links(raw.meta, "depends_on"):
            target = aliases.get(normalize_slug(link))
            if target and target in nodes:
                add(Edge(source=node.id, target=target, type="DEPENDS_ON", hard=True,
                         reason="frontmatter depends_on", source_file=node.file, line=depends_on_line,
                         origin="frontmatter"))
        related_to_line = _frontmatter_field_line(raw.frontmatter, "related_to")
        for link in _frontmatter_links(raw.meta, "related_to"):
            target = aliases.get(normalize_slug(link))
            if target and target in nodes:
                add(Edge(source=node.id, target=target, type="RELATED_TO", hard=False,
                         reason="frontmatter related_to", source_file=node.file, line=related_to_line,
                         origin="frontmatter"))

        in_projection_section = False
        projection_level = 0
        for lineno, line in enumerate(raw.body.splitlines(), start=raw.body_start_line):
            heading_level, is_projection_heading = _is_projection_heading(line)
            if heading_level:
                if in_projection_section and heading_level <= projection_level:
                    in_projection_section = False
                if is_projection_heading:
                    in_projection_section = True
                    projection_level = heading_level
            links = extract_wikilinks(line)
            if not links:
                continue
            for link in links:
                target = aliases.get(normalize_slug(link))
                if not target or target not in nodes:
                    continue
                target_node = nodes[target]
                stripped = line.strip()
                if node.is_fact and not target_node.is_fact:
                    if in_projection_section and _is_list_item(stripped):
                        add(Edge(source=target, target=node.id, type="DEPENDS_ON", hard=True,
                                 reason="fact projection backlink", source_file=node.file, line=lineno))
                    else:
                        add(Edge(source=node.id, target=target, type="MENTIONS", hard=False,
                                 reason="wikilink", source_file=node.file, line=lineno))
                elif target_node.is_fact and not node.is_fact:
                    if _is_see_also_context(stripped):
                        add(Edge(source=node.id, target=target, type="MENTIONS", hard=False,
                                 reason="see-also fact mention", source_file=node.file, line=lineno))
                    else:
                        add(Edge(source=node.id, target=target, type="DEPENDS_ON", hard=True,
                                 reason="wikilink to fact", source_file=node.file, line=lineno))
                else:
                    add(Edge(source=node.id, target=target, type="MENTIONS", hard=False,
                             reason="wikilink", source_file=node.file, line=lineno))
    return list(edges.values())


def load_overlay_edges(graph_dir: Path) -> tuple[list[Edge], list[str]]:
    path = graph_dir / "edges.jsonl"
    if not path.exists():
        return [], []
    out: list[Edge] = []
    errors: list[str] = []
    for idx, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid overlay JSON at edges.jsonl:{idx}: {exc}")
            continue
        etype = str(data.get("type") or data.get("edge_type") or "MENTIONS").upper()
        if etype not in EDGE_PRIORITY:
            errors.append(f"unknown overlay edge type at edges.jsonl:{idx}: {etype}")
            continue
        source = normalize_slug(str(data.get("from") or data.get("source") or ""))
        target = normalize_slug(str(data.get("to") or data.get("target") or ""))
        if not source or not target:
            errors.append(f"invalid overlay edge endpoint at edges.jsonl:{idx}: source and target are required")
            continue
        hard = bool(data.get("hard", etype in HARD_EDGE_TYPES))
        out.append(Edge(
            source=source,
            target=target,
            type=etype,
            hard=hard,
            reason=str(data.get("reason") or "overlay"),
            source_file=str(data.get("source_file") or "memory_graph/edges.jsonl"),
            line=idx,
            origin="overlay",
        ))
    return out, errors


def merge_edges(edges: Iterable[Edge]) -> list[Edge]:
    # Duplicate same source-target collapses by source authority first, then edge strength.
    by_pair: dict[tuple[str, str], Edge] = {}
    for edge in edges:
        key = edge.key()
        prev = by_pair.get(key)
        if prev is None or _edge_rank(edge) >= _edge_rank(prev):
            by_pair[key] = edge
    return list(by_pair.values())


def build_graph(mem_dir: Path, graph_dir: Path, *, include_inferred: bool = True) -> MemoryGraph:
    nodes = load_nodes(mem_dir)
    edges: list[Edge] = []
    if include_inferred:
        edges.extend(infer_edges(mem_dir, nodes))
    overlay_edges, overlay_errors = load_overlay_edges(graph_dir)
    edges.extend(overlay_edges)
    return MemoryGraph(nodes=nodes, edges=merge_edges(edges), mem_dir=mem_dir, graph_dir=graph_dir, overlay_errors=overlay_errors)


def render_report(report: ValidationReport) -> str:
    lines = ["memory graph check"]
    for k, v in sorted(report.stats.items()):
        lines.append(f"  {k}: {v}")
    if report.errors:
        lines.append("errors:")
        lines.extend(f"  ERROR {e}" for e in report.errors)
    if report.warnings:
        lines.append("warnings:")
        lines.extend(f"  WARN  {w}" for w in report.warnings[:80])
        if len(report.warnings) > 80:
            lines.append(f"  WARN  ... {len(report.warnings)-80} more warnings")
    lines.append("status: " + ("OK" if report.ok else "FAIL"))
    return "\n".join(lines)
