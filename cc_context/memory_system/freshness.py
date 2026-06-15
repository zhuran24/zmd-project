from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .graph import load_nodes


def scan(mem_dir: Path) -> dict[str, dict[str, str]]:
    nodes = load_nodes(mem_dir)
    return {
        node_id: {
            "body_sha": node.body_sha,
            "desc_sha": node.desc_sha,
            "idx_sha": node.idx_sha,
            "file": node.file,
        }
        for node_id, node in sorted(nodes.items())
    }


def load_store(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_store(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8", newline="\n")


def check_freshness(mem_dir: Path, store_path: Path) -> tuple[int, list[str]]:
    current = scan(mem_dir)
    store = load_store(store_path)
    lines: list[str] = []
    if not store:
        return 1, [f"无摘要基线: 先跑 memgraph freshness --seed -> {store_path}"]

    new_nodes: list[str] = []
    dirty: list[tuple[str, list[str]]] = []
    summary_dirty: list[tuple[str, list[str]]] = []
    deleted: list[str] = []

    for node_id, cur in current.items():
        rec = store.get(node_id)
        if rec is None:
            new_nodes.append(node_id)
            continue
        if cur["body_sha"] != rec.get("body_sha"):
            stale_fields: list[str] = []
            if cur["idx_sha"] == rec.get("idx_sha"):
                stale_fields.append("index_summary")
            if cur["desc_sha"] == rec.get("desc_sha"):
                stale_fields.append("description")
            dirty.append((node_id, stale_fields))
            continue
        changed_summary_fields: list[str] = []
        if cur["idx_sha"] != rec.get("idx_sha"):
            changed_summary_fields.append("index_summary")
        if cur["desc_sha"] != rec.get("desc_sha"):
            changed_summary_fields.append("description")
        if changed_summary_fields:
            summary_dirty.append((node_id, changed_summary_fields))

    for node_id in sorted(set(store) - set(current)):
        deleted.append(node_id)

    dirty_count = len(dirty) + len(summary_dirty)
    lines.append(f"摘要新鲜度: nodes={len(current)} dirty={dirty_count} new={len(new_nodes)} deleted={len(deleted)}")
    for node_id, stale_fields in dirty:
        if stale_fields:
            lines.append(f"  DIRTY {node_id}: body changed; stale fields: {', '.join(stale_fields)}; review then --accept {node_id}")
        else:
            lines.append(f"  DIRTY {node_id}: body changed; summary metadata also changed, but baseline not accepted; review then --accept {node_id}")
    for node_id, changed_fields in summary_dirty:
        lines.append(f"  DIRTY {node_id}: summary metadata changed: {', '.join(changed_fields)}; review then --accept {node_id}")
    for node_id in new_nodes:
        lines.append(f"  NEW   {node_id}: no accepted baseline; review then --accept {node_id}")
    for node_id in deleted[:30]:
        lines.append(f"  GONE  {node_id}: present in baseline but not current tree")
    if len(deleted) > 30:
        lines.append(f"  GONE  ... {len(deleted)-30} more")

    return (1 if dirty or summary_dirty or new_nodes or deleted else 0), lines
