from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .graph import MemoryGraph, build_graph


def _load_protocol(graph_dir: Path) -> dict[str, Any]:
    path = graph_dir / "agent_protocol.json"
    if not path.exists():
        return {
            "schema_version": 0,
            "purpose": "missing agent_protocol.json",
            "single_bootstrap_command": "python cc_context/tools/memgraph.py bootstrap",
            "health_command": "python cc_context/tools/sync_knowledge.py --check",
            "entry_files": ["cc_context/memory/MEMORY.md"],
            "workflows": {},
            "hard_rules": [],
            "danger_signs": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _memory_entry_lines(mem_dir: Path, limit: int = 8) -> list[str]:
    path = mem_dir / "MEMORY.md"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    in_current = False
    for line in lines:
        if line.startswith("## 当前状态"):
            in_current = True
            continue
        if in_current and line.startswith("## "):
            break
        if in_current and line.startswith("- "):
            out.append(line)
            if len(out) >= limit:
                break
    if out:
        return out
    # Fallback: first normal index lines after the heading.
    return [line for line in lines if line.startswith("- ")][:limit]


def _fact_lines(graph: MemoryGraph, limit: int = 10) -> list[str]:
    facts = [n for n in graph.nodes.values() if n.is_fact]
    out: list[str] = []
    for node in sorted(facts, key=lambda n: n.id)[:limit]:
        summary = node.index_summary or node.description
        out.append(f"- {node.id}: {summary}")
    return out


def build_bootstrap_payload(mem_dir: Path, graph_dir: Path) -> dict[str, Any]:
    graph = build_graph(mem_dir, graph_dir)
    report = graph.validate()
    protocol = _load_protocol(graph_dir)
    return {
        "status": "OK" if report.ok else "FAIL",
        "stats": report.stats,
        "errors": report.errors[:20],
        "warnings": report.warnings[:20],
        "protocol": protocol,
        "current_entries": _memory_entry_lines(mem_dir),
        "facts": _fact_lines(graph),
    }


def render_bootstrap_markdown(payload: dict[str, Any], *, full: bool = False) -> str:
    protocol = payload["protocol"]
    health_command = protocol.get("health_command") or "python cc_context/tools/memgraph.py check"
    status = payload["status"]
    stats = payload.get("stats", {})
    lines: list[str] = []
    lines.append("# 新会话记忆启动卡")
    lines.append("")
    lines.append(f"状态: {status}")
    if stats:
        compact = ", ".join(f"{k}={v}" for k, v in sorted(stats.items()) if k in {"nodes", "facts", "entries", "edges", "hard_edges", "MEMORY.md_bytes"})
        if compact:
            lines.append(f"图规模: {compact}")
    lines.append("")
    lines.append("你不需要先理解整套系统。按下面四步用就够了。")
    lines.append("")
    lines.append("1. 先读入口索引: `cc_context/memory/MEMORY.md`。它只负责定位节点，不是事实本体。")
    lines.append("2. 要查背景，打开索引里命中的具体 `.md` 节点。不要预读全库。")
    lines.append("3. 要改事实或条目，先跑 `python cc_context/tools/memgraph.py impact <node-id>` 看影响面。")
    lines.append(f"4. 改完必须跑 `{health_command}`，绿了才算维护完成。")
    lines.append("")
    lines.append("## 最常用命令")
    lines.append("")
    lines.append("```bash")
    lines.append("python cc_context/tools/memgraph.py bootstrap")
    lines.append("python cc_context/tools/memgraph.py check --write-graph")
    lines.append("python cc_context/tools/memgraph.py impact <fact-or-entry-id>")
    lines.append("python cc_context/tools/memgraph.py add-event --source-type user_message --summary \"...\" --text \"...\"")
    lines.append("python cc_context/tools/memgraph.py propose-change --operation update_fact --touches <node-id> --reason \"...\"")
    lines.append("python cc_context/tools/memgraph.py freshness --accept <changed-node-id>")
    lines.append("python cc_context/tools/memgraph.py index --apply")
    lines.append(health_command)
    lines.append("```")
    lines.append("")
    lines.append("## 当前入口节点")
    lines.append("")
    entries = payload.get("current_entries") or []
    if entries:
        lines.extend(entries)
    else:
        lines.append("- 未找到 MEMORY.md 入口行。先运行 `memgraph.py index --apply`。")
    lines.append("")
    lines.append("## 硬规则")
    lines.append("")
    for item in protocol.get("hard_rules", [])[:8]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 当前事实层")
    lines.append("")
    fact_lines = payload.get("facts") or []
    if fact_lines:
        lines.extend(fact_lines)
    else:
        lines.append("- 未找到 fact 节点。")
    if payload.get("errors"):
        lines.append("")
        lines.append("## 阻断错误")
        lines.append("")
        for err in payload["errors"]:
            lines.append(f"- {err}")
    if payload.get("warnings") and full:
        lines.append("")
        lines.append("## 警告")
        lines.append("")
        for warn in payload["warnings"]:
            lines.append(f"- {warn}")
    lines.append("")
    lines.append("更多说明: `cc_context/MEMORY_AGENT_GUIDE.md`。")
    return "\n".join(lines).rstrip() + "\n"
