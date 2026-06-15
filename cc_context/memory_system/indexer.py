from __future__ import annotations

from pathlib import Path

from .graph import MAX_MEMORY_BYTES, Node, build_graph, short_text

SECTION_ORDER = [
    ("当前状态 / 项目入口", lambda n: n.id in {"zmd-project-entry", "zmd-round2-dispatch-fix-state", "memtree-restructure"} or "handoff" in n.id),
    ("抽象事实", lambda n: n.is_fact),
    ("工作流 / 协作偏好", lambda n: n.id.startswith("feedback-") or n.id in {"root-cause-over-symptom", "task-progression-enforcement-system", "workflow-approval-not-avoidance"}),
    ("项目主线", lambda n: n.id.startswith("project-") and not n.is_fact),
    ("外发 GPT / 工具通道", lambda n: n.id.startswith("no-gpt-") or n.id.startswith("no-workflow-") or "gpt" in n.id),
    ("环境 / 运维", lambda n: n.id.startswith("zmd-env-") or n.id.startswith("zmd-checkout") or "windows" in n.id),
    ("Reference", lambda n: n.id.startswith("reference-")),
    ("其他", lambda n: True),
]


def _line_for(node: Node) -> str:
    title = node.id
    summary = node.index_summary or short_text(node.description, 96)
    return f"- [{title}]({node.file}) — {summary}"


def generate_index(mem_dir: Path, graph_dir: Path) -> str:
    graph = build_graph(mem_dir, graph_dir)
    remaining = {node.id: node for node in graph.nodes.values()}
    lines: list[str] = []
    lines.append("# Memory Index")
    lines.append("")
    lines.append("机器生成索引。节点正文仍是人类编辑面; 事实/条目依赖由 `cc_context/memory_graph/` 管。")
    lines.append("")
    for section, pred in SECTION_ORDER:
        bucket = [n for n in remaining.values() if pred(n)]
        if not bucket:
            continue
        lines.append(f"## {section}")
        lines.append("")
        # Put current state nodes early, then stable alphabetical order.
        for node in sorted(bucket, key=lambda n: (0 if n.id in {"zmd-project-entry", "zmd-round2-dispatch-fix-state", "memtree-restructure"} else 1, n.id)):
            lines.append(_line_for(node))
            remaining.pop(node.id, None)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_or_check_index(mem_dir: Path, graph_dir: Path, *, apply: bool, out_path: Path | None = None, live_dir: Path | None = None) -> tuple[int, list[str]]:
    generated = generate_index(mem_dir, graph_dir)
    size = len(generated.encode("utf-8"))
    lines = [f"生成索引大小: {size}/{MAX_MEMORY_BYTES} B"]
    if size > MAX_MEMORY_BYTES:
        lines.append("!! 超过 24KB cap, 拒绝写入")
        return 1, lines
    current_path = mem_dir / "MEMORY.md"
    current = current_path.read_text(encoding="utf-8") if current_path.exists() else ""
    changed = current != generated
    lines.append("MEMORY.md: " + ("would change" if changed else "already current"))
    if not apply:
        if out_path is None:
            out_path = graph_dir / "generated" / "MEMORY.generated.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(generated, encoding="utf-8", newline="\n")
        lines.append(f"写旁路生成物: {out_path}")
        return (1 if changed else 0), lines

    current_path.write_text(generated, encoding="utf-8", newline="\n")
    lines.append(f"已写正本: {current_path}")
    if live_dir is not None and live_dir.exists():
        (live_dir / "MEMORY.md").write_text(generated, encoding="utf-8", newline="\n")
        lines.append(f"已同步 live mirror MEMORY.md: {live_dir / 'MEMORY.md'}")
    return 0, lines
