from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .bootstrap import build_bootstrap_payload, render_bootstrap_markdown
from .freshness import check_freshness, save_store, scan
from .graph import build_graph, render_report, normalize_slug
from .indexer import write_or_check_index

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MEM_DIR = ROOT / "cc_context" / "memory"
DEFAULT_GRAPH_DIR = ROOT / "cc_context" / "memory_graph"
DEFAULT_FRESHNESS_STORE = ROOT / "cc_context" / "knowledge" / "description_review.json"
DEFAULT_LIVE_DIR = ROOT / "_cc_live_memory"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def cmd_bootstrap(args: argparse.Namespace) -> int:
    payload = build_bootstrap_payload(args.mem_dir, args.graph_dir)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_bootstrap_markdown(payload, full=args.full))
    return 0 if payload.get("status") == "OK" else 1


def cmd_check(args: argparse.Namespace) -> int:
    graph = build_graph(args.mem_dir, args.graph_dir)
    if args.write_graph:
        path = graph.write_json()
        print(f"wrote graph -> {path}")
    report = graph.validate(check_memory_cap=not args.no_cap, check_live_mirror=not args.no_live_mirror)
    print(render_report(report))
    return 0 if report.ok else 1


def cmd_build(args: argparse.Namespace) -> int:
    graph = build_graph(args.mem_dir, args.graph_dir, include_inferred=not args.no_infer)
    path = graph.write_json(args.output)
    print(f"wrote graph -> {path}")
    print(f"nodes={len(graph.nodes)} edges={len(graph.edges)}")
    return 0


def cmd_impact(args: argparse.Namespace) -> int:
    graph = build_graph(args.mem_dir, args.graph_dir)
    node_id = normalize_slug(args.node)
    try:
        impacted = graph.reverse_dependents(node_id, include_soft=args.include_soft)
    except KeyError as exc:
        print(str(exc))
        return 1
    if args.json:
        payload = [
            {
                "depth": depth,
                "node": node.id,
                "file": node.file,
                "kind": node.kind,
                "via": {"from": edge.source, "type": edge.type, "to": edge.target, "reason": edge.reason},
            }
            for depth, edge, node in impacted
        ]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(f"impact from {node_id}: {len(impacted)} dependent nodes")
    for depth, edge, node in impacted:
        print(f"  d{depth} {node.id} ({node.file}) via {edge.source} --{edge.type}--> {edge.target}")
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    out_path = args.output or (args.graph_dir / "generated" / "MEMORY.generated.md")
    rc, lines = write_or_check_index(
        args.mem_dir,
        args.graph_dir,
        apply=args.apply,
        out_path=out_path,
        live_dir=args.live_dir,
    )
    print("\n".join(lines))
    if args.check:
        return rc
    # Default mode writes generated artifact but should not fail a shell merely because
    # the checked-in MEMORY.md differs. --check is the blocking mode.
    return 0 if not args.apply else rc


def cmd_freshness(args: argparse.Namespace) -> int:
    current = scan(args.mem_dir)
    if args.seed:
        save_store(args.store, current)
        print(f"基线已建立: {len(current)} nodes -> {args.store}")
        return 0
    if args.accept:
        store = {}
        if args.store.exists():
            store = json.loads(args.store.read_text(encoding="utf-8"))
        node_id = normalize_slug(args.accept)
        if node_id not in current:
            print(f"节点不存在: {node_id}")
            return 1
        store[node_id] = current[node_id]
        save_store(args.store, store)
        print(f"已接受 {node_id} 当前态为基线")
        return 0
    rc, lines = check_freshness(args.mem_dir, args.store)
    print("\n".join(lines))
    return rc


def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")


def cmd_add_event(args: argparse.Namespace) -> int:
    event_id = args.event_id or f"evt_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    obj = {
        "id": event_id,
        "created_at": now_iso(),
        "source_type": args.source_type,
        "summary": args.summary or "manual event",
        "text": args.text,
    }
    _append_jsonl(args.graph_dir / "events.jsonl", obj)
    print(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def cmd_propose_change(args: argparse.Namespace) -> int:
    graph = build_graph(args.mem_dir, args.graph_dir)
    touched = [normalize_slug(x) for x in args.touches]
    missing = [x for x in touched if x not in graph.nodes]
    if missing:
        print("unknown touched nodes: " + ", ".join(missing))
        return 1
    affected: dict[str, Any] = {}
    for node_id in touched:
        affected[node_id] = [
            {"node": node.id, "file": node.file, "depth": depth, "via": edge.type}
            for depth, edge, node in graph.reverse_dependents(node_id)
        ]
    change_id = args.change_id or f"chg_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    obj = {
        "id": change_id,
        "created_at": now_iso(),
        "status": "proposal",
        "operation": args.operation,
        "event_id": args.event_id,
        "touches": touched,
        "reason": args.reason,
        "affected": affected,
    }
    if args.write:
        _append_jsonl(args.graph_dir / "changes.jsonl", obj)
        print(f"wrote change proposal -> {args.graph_dir / 'changes.jsonl'}")
    print(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Typed memory graph CLI")
    p.add_argument("--mem-dir", type=Path, default=DEFAULT_MEM_DIR)
    p.add_argument("--graph-dir", type=Path, default=DEFAULT_GRAPH_DIR)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("bootstrap", help="print the self-contained startup card for a fresh agent session")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--full", action="store_true", help="include warnings in markdown output")
    sp.set_defaults(func=cmd_bootstrap)

    sp = sub.add_parser("check", help="validate nodes, typed edges, hard dependency DAG, memory cap")
    sp.add_argument("--write-graph", action="store_true")
    sp.add_argument("--no-cap", action="store_true")
    sp.add_argument("--no-live-mirror", action="store_true")
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("build", help="materialize generated graph.json")
    sp.add_argument("--output", type=Path)
    sp.add_argument("--no-infer", action="store_true")
    sp.set_defaults(func=cmd_build)

    sp = sub.add_parser("impact", help="show nodes that must be reconsidered when a fact/entry changes")
    sp.add_argument("node")
    sp.add_argument("--include-soft", action="store_true")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_impact)

    sp = sub.add_parser("index", help="generate/check/apply MEMORY.md from node summaries")
    sp.add_argument("--check", action="store_true")
    sp.add_argument("--apply", action="store_true")
    sp.add_argument("--output", type=Path)
    sp.add_argument("--live-dir", type=Path, default=DEFAULT_LIVE_DIR)
    sp.set_defaults(func=cmd_index)

    sp = sub.add_parser("freshness", help="check accepted body/description/index_summary baseline")
    sp.add_argument("--store", type=Path, default=DEFAULT_FRESHNESS_STORE)
    sp.add_argument("--seed", action="store_true")
    sp.add_argument("--accept")
    sp.set_defaults(func=cmd_freshness)

    sp = sub.add_parser("add-event", help="append an immutable source event")
    sp.add_argument("--text", required=True)
    sp.add_argument("--summary")
    sp.add_argument("--source-type", default="manual")
    sp.add_argument("--event-id")
    sp.set_defaults(func=cmd_add_event)

    sp = sub.add_parser("propose-change", help="append or print a change proposal and its impact set")
    sp.add_argument("--operation", required=True, choices=["create_fact", "update_fact", "delete_fact", "update_entry", "delete_entry", "link", "unlink", "bootstrap"])
    sp.add_argument("--touches", nargs="+", required=True)
    sp.add_argument("--reason", required=True)
    sp.add_argument("--event-id")
    sp.add_argument("--change-id")
    sp.add_argument("--write", action="store_true")
    sp.set_defaults(func=cmd_propose_change)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
