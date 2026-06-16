#!/usr/bin/env python3
"""Slim project memory system.

One source of truth: cc_memory/memory.db.
Generated Markdown under cc_memory/exports/ is disposable view output.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sqlite3
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MEM_DIR = Path(__file__).resolve().parent
DEFAULT_DB = MEM_DIR / "memory.db"
DEFAULT_EXPORT = MEM_DIR / "exports" / "MEMORY.md"
SCHEMA_VERSION = 1
HARD_EDGE_TYPES = {"DEPENDS_ON", "DERIVED_FROM", "SUPERSEDES", "CONTRADICTS"}
ALL_EDGE_TYPES = HARD_EDGE_TYPES | {"MENTIONS", "RELATED_TO", "SUPPORTS", "PROJECTS_TO"}
MAX_EXPORT_BYTES = 24_576


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def session_id_for(args: argparse.Namespace) -> str:
    """Session identity: explicit --session, else Claude Code's per-session id, else anonymous."""
    sid = (getattr(args, "session", None) or os.environ.get("CLAUDE_CODE_SESSION_ID") or "").strip()
    return sid or "anonymous"


def record_mutation(con: sqlite3.Connection, session_id: str, op: str, target_type: str, target_id: str) -> None:
    con.execute(
        "INSERT INTO mutations(session_id,created_at,op,target_type,target_id) VALUES(?,?,?,?,?)",
        (session_id, now(), op, target_type, target_id),
    )


def session_delta(con: sqlite3.Connection, session_id: str) -> list[sqlite3.Row] | None:
    """Mutations by OTHER sessions since this session's last boot.

    Returns None when the session has no watermark yet — treat as a fresh session:
    it loaded the latest memory, so no change report is needed (per owner design)."""
    row = con.execute("SELECT last_seen_mutation_id FROM read_watermarks WHERE session_id=?", (session_id,)).fetchone()
    if row is None:
        return None
    return list(con.execute(
        "SELECT * FROM mutations WHERE id > ? AND session_id <> ? ORDER BY id",
        (row["last_seen_mutation_id"], session_id),
    ))


def touch_watermark(con: sqlite3.Connection, session_id: str) -> None:
    """Mark this session as caught up to the latest mutation."""
    mid = int(con.execute("SELECT COALESCE(MAX(id), 0) AS m FROM mutations").fetchone()["m"])
    con.execute(
        "INSERT INTO read_watermarks(session_id,last_seen_mutation_id,last_query_at) VALUES(?,?,?) "
        "ON CONFLICT(session_id) DO UPDATE SET last_seen_mutation_id=excluded.last_seen_mutation_id, last_query_at=excluded.last_query_at",
        (session_id, mid, now()),
    )


def norm(value: str) -> str:
    value = value.strip().strip('"\'')
    value = value.replace("_", "-")
    value = re.sub(r"[^A-Za-z0-9\-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-").lower()
    return value


def short(value: str, n: int = 150) -> str:
    value = re.sub(r"\s+", " ", (value or "").strip())
    if len(value) <= n:
        return value
    cut = value[:n]
    for token in ["。", "；", "，", ";", ",", ":", " "]:
        i = cut.rfind(token)
        if i > n // 2:
            return cut[:i].rstrip(" ，,;；:") + "…"
    return cut.rstrip() + "…"


def connect(db: Path = DEFAULT_DB) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def jdump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def jload(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def init_schema(con: sqlite3.Connection, *, reset: bool = False) -> None:
    if reset:
        for table in ["meta", "events", "facts", "entries", "edges", "aliases", "changes"]:
            con.execute(f"DROP TABLE IF EXISTS {table}")
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events(
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            source_type TEXT NOT NULL,
            summary TEXT NOT NULL,
            text TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS facts(
            id TEXT PRIMARY KEY,
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            value TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            confidence TEXT NOT NULL DEFAULT 'medium',
            valid_from TEXT,
            valid_to TEXT,
            source_event_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY(source_event_id) REFERENCES events(id)
        );
        CREATE TABLE IF NOT EXISTS entries(
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            pinned INTEGER NOT NULL DEFAULT 0,
            source_event_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY(source_event_id) REFERENCES events(id)
        );
        CREATE TABLE IF NOT EXISTS edges(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL CHECK(source_type IN ('fact','entry')),
            source_id TEXT NOT NULL,
            edge_type TEXT NOT NULL,
            target_type TEXT NOT NULL CHECK(target_type IN ('fact','entry')),
            target_id TEXT NOT NULL,
            hard INTEGER NOT NULL DEFAULT 0,
            reason TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            UNIQUE(source_type, source_id, edge_type, target_type, target_id)
        );
        CREATE TABLE IF NOT EXISTS aliases(
            alias TEXT PRIMARY KEY,
            target_type TEXT NOT NULL CHECK(target_type IN ('fact','entry')),
            target_id TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS changes(
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            operation TEXT NOT NULL,
            touches_json TEXT NOT NULL,
            reason TEXT NOT NULL,
            event_id TEXT,
            affected_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'proposal',
            FOREIGN KEY(event_id) REFERENCES events(id)
        );
        CREATE TABLE IF NOT EXISTS mutations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            op TEXT NOT NULL,
            target_type TEXT,
            target_id TEXT
        );
        CREATE TABLE IF NOT EXISTS read_watermarks(
            session_id TEXT PRIMARY KEY,
            last_seen_mutation_id INTEGER NOT NULL DEFAULT 0,
            last_query_at TEXT NOT NULL
        );
        """
    )
    con.execute(
        "INSERT INTO meta(key,value) VALUES('schema_version', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(SCHEMA_VERSION),),
    )
    con.commit()


def put_alias(con: sqlite3.Connection, alias: str, typ: str, node_id: str) -> None:
    alias = norm(alias)
    if alias:
        con.execute(
            "INSERT OR REPLACE INTO aliases(alias,target_type,target_id) VALUES(?,?,?)",
            (alias, typ, node_id),
        )


def add_event_row(con: sqlite3.Connection, event_id: str, source_type: str, summary: str, text: str, metadata: dict[str, Any] | None = None) -> None:
    con.execute(
        """INSERT OR REPLACE INTO events(id,created_at,source_type,summary,text,metadata_json)
           VALUES(?,?,?,?,?,?)""",
        (event_id, now(), source_type, summary, text, jdump(metadata or {})),
    )


def add_fact_row(
    con: sqlite3.Connection,
    fact_id: str,
    subject: str,
    predicate: str,
    value: str,
    *,
    status: str = "active",
    confidence: str = "medium",
    source_event_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    ts = now()
    con.execute(
        """INSERT INTO facts(id,subject,predicate,value,status,confidence,source_event_id,created_at,updated_at,metadata_json)
           VALUES(?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             subject=excluded.subject, predicate=excluded.predicate, value=excluded.value,
             status=excluded.status, confidence=excluded.confidence, source_event_id=excluded.source_event_id,
             updated_at=excluded.updated_at, metadata_json=excluded.metadata_json""",
        (fact_id, subject, predicate, value, status, confidence, source_event_id, ts, ts, jdump(metadata or {})),
    )
    put_alias(con, fact_id, "fact", fact_id)


def add_entry_row(
    con: sqlite3.Connection,
    entry_id: str,
    title: str,
    body: str,
    *,
    status: str = "active",
    pinned: bool = False,
    source_event_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    ts = now()
    con.execute(
        """INSERT INTO entries(id,title,body,status,pinned,source_event_id,created_at,updated_at,metadata_json)
           VALUES(?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             title=excluded.title, body=excluded.body, status=excluded.status, pinned=excluded.pinned,
             source_event_id=excluded.source_event_id, updated_at=excluded.updated_at,
             metadata_json=excluded.metadata_json""",
        (entry_id, title, body, status, 1 if pinned else 0, source_event_id, ts, ts, jdump(metadata or {})),
    )
    put_alias(con, entry_id, "entry", entry_id)


def add_edge_row(con: sqlite3.Connection, source_type: str, source_id: str, edge_type: str, target_type: str, target_id: str, *, reason: str = "") -> None:
    edge_type = edge_type.upper()
    if edge_type not in ALL_EDGE_TYPES:
        raise SystemExit(f"unknown edge type: {edge_type}")
    hard = 1 if edge_type in HARD_EDGE_TYPES else 0
    if source_id == target_id and source_type == target_type:
        return
    con.execute(
        """INSERT OR IGNORE INTO edges(source_type,source_id,edge_type,target_type,target_id,hard,reason,created_at)
           VALUES(?,?,?,?,?,?,?,?)""",
        (source_type, source_id, edge_type, target_type, target_id, hard, reason, now()),
    )


def resolve_node(con: sqlite3.Connection, raw: str) -> tuple[str, str] | None:
    node_id = norm(raw)
    row = con.execute("SELECT id FROM facts WHERE id=?", (node_id,)).fetchone()
    if row:
        return "fact", row["id"]
    row = con.execute("SELECT id FROM entries WHERE id=?", (node_id,)).fetchone()
    if row:
        return "entry", row["id"]
    row = con.execute("SELECT target_type,target_id FROM aliases WHERE alias=?", (node_id,)).fetchone()
    if row:
        return row["target_type"], row["target_id"]
    return None


def node_exists(con: sqlite3.Connection, typ: str, node_id: str) -> bool:
    table = "facts" if typ == "fact" else "entries"
    return con.execute(f"SELECT 1 FROM {table} WHERE id=?", (node_id,)).fetchone() is not None


def list_counts(con: sqlite3.Connection) -> dict[str, int]:
    return {t: int(con.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"]) for t in ["events", "facts", "entries", "edges", "changes"]}


def outgoing_edges(con: sqlite3.Connection, typ: str, node_id: str) -> list[sqlite3.Row]:
    return list(con.execute("SELECT * FROM edges WHERE source_type=? AND source_id=? ORDER BY hard DESC, edge_type, target_id", (typ, node_id)))


def incoming_edges(con: sqlite3.Connection, typ: str, node_id: str, *, include_soft: bool = False) -> list[sqlite3.Row]:
    if include_soft:
        return list(con.execute("SELECT * FROM edges WHERE target_type=? AND target_id=? ORDER BY hard DESC, edge_type, source_id", (typ, node_id)))
    return list(con.execute("SELECT * FROM edges WHERE target_type=? AND target_id=? AND hard=1 ORDER BY edge_type, source_id", (typ, node_id)))


def impact_set(con: sqlite3.Connection, start_typ: str, start_id: str, *, include_soft: bool = False) -> list[tuple[int, sqlite3.Row, str, str]]:
    seen = {(start_typ, start_id)}
    q: deque[tuple[str, str, int]] = deque([(start_typ, start_id, 0)])
    out: list[tuple[int, sqlite3.Row, str, str]] = []
    while q:
        typ, node_id, depth = q.popleft()
        for e in incoming_edges(con, typ, node_id, include_soft=include_soft):
            nxt = (e["source_type"], e["source_id"])
            if nxt in seen:
                continue
            seen.add(nxt)
            out.append((depth + 1, e, e["source_type"], e["source_id"]))
            q.append((e["source_type"], e["source_id"], depth + 1))
    return out


def node_summary(con: sqlite3.Connection, typ: str, node_id: str) -> str:
    if typ == "fact":
        row = con.execute("SELECT value FROM facts WHERE id=?", (node_id,)).fetchone()
        return short(row["value"] if row else "", 160)
    row = con.execute("SELECT body, metadata_json FROM entries WHERE id=?", (node_id,)).fetchone()
    if not row:
        return ""
    meta = jload(row["metadata_json"], {})
    return short(meta.get("index_summary") or meta.get("description") or row["body"], 160)


def export_markdown(con: sqlite3.Connection, path: Path = DEFAULT_EXPORT) -> str:
    counts = list_counts(con)
    lines: list[str] = [
        "# Project Memory Export",
        "",
        "Generated from `cc_memory/memory.db`. Do not hand-edit this file; run `python cc_memory/mem.py export`.",
        "",
        "Fresh session:",
        "",
        "```bash",
        "python cc_memory/mem.py boot",
        "```",
        "",
        "## Stats",
        "",
        f"- facts: {counts['facts']}",
        f"- entries: {counts['entries']}",
        f"- hard edges: {con.execute('SELECT count(*) AS n FROM edges WHERE hard=1').fetchone()['n']}",
        "",
    ]
    pinned = list(con.execute("SELECT * FROM entries WHERE pinned=1 AND status='active' ORDER BY id"))
    if pinned:
        lines += ["## Start Here", ""]
        for r in pinned[:20]:
            lines.append(f"- `{r['id']}` — {node_summary(con, 'entry', r['id'])}")
        lines.append("")
    facts = list(con.execute("SELECT * FROM facts WHERE status='active' ORDER BY id"))
    if facts:
        lines += ["## Active Facts", ""]
        for r in facts:
            lines.append(f"- `{r['id']}` — {short(r['value'], 140)}")
        lines.append("")
    entries = list(con.execute("SELECT * FROM entries WHERE status='active' AND pinned=0 ORDER BY id"))
    if entries:
        lines += ["## Entries", ""]
        for r in entries:
            lines.append(f"- `{r['id']}` — {node_summary(con, 'entry', r['id'])}")
        lines.append("")
    text = "\n".join(lines).rstrip() + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return text


def check_db(con: sqlite3.Connection, *, export_path: Path = DEFAULT_EXPORT) -> tuple[int, list[str]]:
    init_schema(con)
    errors: list[str] = []
    warnings: list[str] = []
    # Schema marker.
    row = con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    if not row or row["value"] != str(SCHEMA_VERSION):
        errors.append("schema_version mismatch or missing")
    for e in con.execute("SELECT * FROM edges"):
        if e["edge_type"] not in ALL_EDGE_TYPES:
            errors.append(f"unknown edge type on edge {e['id']}: {e['edge_type']}")
        if not node_exists(con, e["source_type"], e["source_id"]):
            errors.append(f"edge {e['id']} source missing: {e['source_type']}:{e['source_id']}")
        if not node_exists(con, e["target_type"], e["target_id"]):
            errors.append(f"edge {e['id']} target missing: {e['target_type']}:{e['target_id']}")
        if e["hard"] and e["edge_type"] not in HARD_EDGE_TYPES:
            errors.append(f"edge {e['id']} hard=1 but soft edge_type={e['edge_type']}")
    # Hard dependency cycles.
    graph: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for e in con.execute("SELECT * FROM edges WHERE hard=1"):
        graph[(e["source_type"], e["source_id"])].append((e["target_type"], e["target_id"]))
    temp: set[tuple[str, str]] = set()
    perm: set[tuple[str, str]] = set()
    stack: list[tuple[str, str]] = []

    def visit(n: tuple[str, str]) -> None:
        if n in perm:
            return
        if n in temp:
            try:
                cycle = stack[stack.index(n):] + [n]
            except ValueError:
                cycle = [n]
            errors.append("hard dependency cycle: " + " -> ".join(f"{t}:{i}" for t, i in cycle))
            return
        temp.add(n)
        stack.append(n)
        for m in graph.get(n, []):
            visit(m)
        stack.pop()
        temp.remove(n)
        perm.add(n)

    for n in list(graph):
        visit(n)
    export = export_markdown(con, export_path)
    size = len(export.encode("utf-8"))
    if size > MAX_EXPORT_BYTES:
        warnings.append(f"export is large: {size}/{MAX_EXPORT_BYTES} bytes")
    counts = list_counts(con)
    lines = ["memory check", *(f"  {k}: {v}" for k, v in counts.items()), f"  export_bytes: {size}"]
    lines.extend(f"ERROR {e}" for e in errors)
    lines.extend(f"WARN  {w}" for w in warnings)
    lines.append("status: " + ("OK" if not errors else "FAIL"))
    return (0 if not errors else 1), lines


def cmd_init(args: argparse.Namespace) -> int:
    con = connect(args.db)
    init_schema(con, reset=args.reset)
    if args.seed_basic:
        eid = "evt-basic-seed"
        add_event_row(con, eid, "seed", "Basic slim memory seed", "Created from mem.py init --seed-basic")
        add_fact_row(con, "fact-memory-single-source", "memory_system", "single_source", "The only editable memory truth is cc_memory/memory.db; exports are generated views.", confidence="high", source_event_id=eid)
        add_entry_row(con, "memory-operating-protocol", "Memory operating protocol", "Fresh sessions start with `python cc_memory/mem.py boot`. Change facts through events, facts/entries, typed edges, check, then export.", pinned=True, source_event_id=eid)
        add_edge_row(con, "entry", "memory-operating-protocol", "DEPENDS_ON", "fact", "fact-memory-single-source", reason="operating rule")
        con.commit()
    print(f"initialized {args.db}")
    return 0


def cmd_boot(args: argparse.Namespace) -> int:
    con = connect(args.db)
    init_schema(con)
    counts = list_counts(con)
    rc, check_lines = check_db(con, export_path=args.export)
    print("# Memory boot")
    print("")
    print("One source of truth: `cc_memory/memory.db`. Generated views under `cc_memory/exports/` are disposable.")
    print("")
    print(f"status: {'OK' if rc == 0 else 'FAIL'}")
    print(" ".join(f"{k}={v}" for k, v in counts.items()))
    print("")
    sid = session_id_for(args)
    delta = session_delta(con, sid)
    print("## Session")
    print(f"- session: {sid}")
    if delta is None:
        print("- new session: no prior visit recorded — loaded latest memory, no change report needed")
    elif not delta:
        print("- no changes by other sessions since your last boot")
    else:
        print(f"- {len(delta)} change(s) by OTHER sessions since your last boot:")
        for m in delta[:30]:
            print(f"  - [{(m['session_id'] or '')[:8]}] {m['op']} {m['target_type']}:{m['target_id']}  ({m['created_at']})")
        if len(delta) > 30:
            print(f"  - ... {len(delta) - 30} more")
    print("")
    pinned = list(con.execute("SELECT * FROM entries WHERE pinned=1 AND status='active' ORDER BY id LIMIT ?", (args.limit,)))
    print("## Read first")
    if not pinned:
        print("- no pinned entries yet; run search or add-entry")
    for r in pinned:
        print(f"- `{r['id']}` — {node_summary(con, 'entry', r['id'])}")
    print("")
    print("## Commands")
    print("- `python cc_memory/mem.py search \"query\"`")
    print("- `python cc_memory/mem.py read <id>`")
    print("- `python cc_memory/mem.py impact <id>` before changing a fact or entry")
    print("- `python cc_memory/mem.py add-event --text \"...\"` then `set-fact` / `add-entry` / `link`")
    print("- `python cc_memory/mem.py propose --operation update_fact --touches <id> --reason \"...\"`")
    print("- `python cc_memory/mem.py check && python cc_memory/mem.py export`")
    print("")
    if rc:
        print("## Check failures")
        print("\n".join(check_lines))
    touch_watermark(con, sid)
    con.commit()
    return rc


def cmd_search(args: argparse.Namespace) -> int:
    con = connect(args.db)
    q = f"%{args.query}%"
    rows: list[tuple[str, str, str]] = []
    for r in con.execute("SELECT id,value FROM facts WHERE id LIKE ? OR value LIKE ? OR subject LIKE ? OR predicate LIKE ? ORDER BY id LIMIT ?", (q, q, q, q, args.limit)):
        rows.append(("fact", r["id"], short(r["value"], 180)))
    left = max(0, args.limit - len(rows))
    if left:
        for r in con.execute("SELECT id,body,metadata_json FROM entries WHERE id LIKE ? OR title LIKE ? OR body LIKE ? ORDER BY id LIMIT ?", (q, q, q, left)):
            rows.append(("entry", r["id"], node_summary(con, "entry", r["id"])))
    for typ, node_id, s in rows:
        print(f"{typ}:{node_id} — {s}")
    if not rows:
        print("no matches")
    return 0


def cmd_read(args: argparse.Namespace) -> int:
    con = connect(args.db)
    resolved = resolve_node(con, args.node)
    if not resolved:
        print(f"unknown node: {args.node}")
        return 1
    typ, node_id = resolved
    print(f"# {typ}:{node_id}")
    if typ == "fact":
        r = con.execute("SELECT * FROM facts WHERE id=?", (node_id,)).fetchone()
        assert r
        print(f"subject: {r['subject']}")
        print(f"predicate: {r['predicate']}")
        print(f"status: {r['status']} confidence: {r['confidence']}")
        print(f"value: {r['value']}")
        meta = jload(r["metadata_json"], {})
    else:
        r = con.execute("SELECT * FROM entries WHERE id=?", (node_id,)).fetchone()
        assert r
        print(f"title: {r['title']}")
        print(f"status: {r['status']} pinned: {bool(r['pinned'])}")
        print(f"summary: {node_summary(con, typ, node_id)}")
        meta = jload(r["metadata_json"], {})
        if args.body:
            print("\n## Body\n")
            print(r["body"])
    if meta:
        print("metadata: " + json.dumps(meta, ensure_ascii=False, sort_keys=True))
    outs = outgoing_edges(con, typ, node_id)
    print("\n## Edges out")
    if not outs:
        print("none")
    for e in outs:
        strength = "hard" if e["hard"] else "soft"
        print(f"- {e['edge_type']}/{strength} -> {e['target_type']}:{e['target_id']}  # {e['reason']}")
    impacts = impact_set(con, typ, node_id, include_soft=args.include_soft)
    print(f"\n## Impact ({len(impacts)})")
    for depth, e, st, sid in impacts[: args.limit]:
        print(f"- d{depth} {st}:{sid} via {e['source_type']}:{e['source_id']} --{e['edge_type']}--> {e['target_type']}:{e['target_id']}")
    if len(impacts) > args.limit:
        print(f"... {len(impacts) - args.limit} more")
    return 0


def cmd_impact(args: argparse.Namespace) -> int:
    con = connect(args.db)
    resolved = resolve_node(con, args.node)
    if not resolved:
        print(f"unknown node: {args.node}")
        return 1
    typ, node_id = resolved
    impacts = impact_set(con, typ, node_id, include_soft=args.include_soft)
    if args.json:
        print(json.dumps([{"depth": d, "type": st, "id": sid, "via_edge_id": e["id"], "edge_type": e["edge_type"]} for d, e, st, sid in impacts], ensure_ascii=False, indent=2))
        return 0
    print(f"impact from {typ}:{node_id}: {len(impacts)}")
    for depth, e, st, sid in impacts:
        print(f"- d{depth} {st}:{sid} via {e['edge_type']} ({e['reason']})")
    return 0


def cmd_add_event(args: argparse.Namespace) -> int:
    con = connect(args.db)
    init_schema(con)
    eid = args.id or f"evt-{_dt.datetime.now(_dt.timezone.utc).strftime('%Y%m%d%H%M%S')}"
    add_event_row(con, eid, args.source_type, args.summary or short(args.text, 100), args.text, {"manual": True})
    record_mutation(con, session_id_for(args), "add-event", "event", eid)
    con.commit()
    print(eid)
    return 0


def cmd_set_fact(args: argparse.Namespace) -> int:
    con = connect(args.db)
    init_schema(con)
    fact_id = norm(args.id or f"fact-{args.subject}-{args.predicate}")
    if not fact_id:
        raise SystemExit("refusing empty fact id (non-ASCII subject/predicate collapsed to ''); pass an explicit ASCII --id")
    if con.execute("SELECT 1 FROM facts WHERE id=?", (fact_id,)).fetchone() and not args.force:
        raise SystemExit(f"fact '{fact_id}' already exists; pass --force to overwrite or use a different --id")
    add_fact_row(con, fact_id, args.subject, args.predicate, args.value, status=args.status, confidence=args.confidence, source_event_id=args.event, metadata={"manual": True})
    record_mutation(con, session_id_for(args), "set-fact", "fact", fact_id)
    con.commit()
    print(f"fact:{fact_id}")
    return 0


def cmd_add_entry(args: argparse.Namespace) -> int:
    con = connect(args.db)
    init_schema(con)
    entry_id = norm(args.id or args.title)
    if not entry_id:
        raise SystemExit("refusing empty entry id (non-ASCII title collapsed to ''); pass an explicit ASCII --id")
    if con.execute("SELECT 1 FROM entries WHERE id=?", (entry_id,)).fetchone() and not args.force:
        raise SystemExit(f"entry '{entry_id}' already exists; pass --force to overwrite or use a different --id")
    body = args.body
    if args.body_file:
        body = args.body_file.read_text(encoding="utf-8")
    add_entry_row(con, entry_id, args.title, body, pinned=args.pinned, source_event_id=args.event, metadata={"manual": True, "index_summary": args.summary or short(body, 140)})
    for dep in args.depends_on or []:
        resolved = resolve_node(con, dep)
        if not resolved:
            raise SystemExit(f"unknown dependency: {dep}")
        ttyp, tid = resolved
        add_edge_row(con, "entry", entry_id, "DEPENDS_ON", ttyp, tid, reason="add-entry --depends-on")
    record_mutation(con, session_id_for(args), "add-entry", "entry", entry_id)
    con.commit()
    print(f"entry:{entry_id}")
    return 0


def cmd_link(args: argparse.Namespace) -> int:
    con = connect(args.db)
    src = resolve_node(con, args.source)
    tgt = resolve_node(con, args.target)
    if not src:
        raise SystemExit(f"unknown source: {args.source}")
    if not tgt:
        raise SystemExit(f"unknown target: {args.target}")
    add_edge_row(con, src[0], src[1], args.type, tgt[0], tgt[1], reason=args.reason or "manual link")
    record_mutation(con, session_id_for(args), "link", "edge", f"{src[1]}->{tgt[1]}")
    con.commit()
    print(f"{src[0]}:{src[1]} --{args.type.upper()}--> {tgt[0]}:{tgt[1]}")
    return 0


def cmd_propose(args: argparse.Namespace) -> int:
    con = connect(args.db)
    touches: list[dict[str, Any]] = []
    affected: dict[str, Any] = {}
    for raw in args.touches:
        resolved = resolve_node(con, raw)
        if not resolved:
            raise SystemExit(f"unknown touched node: {raw}")
        typ, node_id = resolved
        touches.append({"type": typ, "id": node_id})
        affected[f"{typ}:{node_id}"] = [
            {"depth": d, "type": st, "id": sid, "edge_type": e["edge_type"], "reason": e["reason"]}
            for d, e, st, sid in impact_set(con, typ, node_id)
        ]
    cid = args.id or f"chg-{_dt.datetime.now(_dt.timezone.utc).strftime('%Y%m%d%H%M%S')}"
    con.execute(
        "INSERT OR REPLACE INTO changes(id,created_at,operation,touches_json,reason,event_id,affected_json,status) VALUES(?,?,?,?,?,?,?,?)",
        (cid, now(), args.operation, jdump(touches), args.reason, args.event, jdump(affected), "proposal"),
    )
    con.commit()
    print(json.dumps({"id": cid, "operation": args.operation, "touches": touches, "affected": affected}, ensure_ascii=False, indent=2))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    con = connect(args.db)
    rc, lines = check_db(con, export_path=args.export)
    print("\n".join(lines))
    return rc


def cmd_export(args: argparse.Namespace) -> int:
    con = connect(args.db)
    text = export_markdown(con, args.export)
    print(f"wrote {args.export} ({len(text.encode('utf-8'))} bytes)")
    return 0


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Slim SQLite memory system")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--export", type=Path, default=DEFAULT_EXPORT)
    p.add_argument("--session", default=None, help="session id (defaults to $CLAUDE_CODE_SESSION_ID, else 'anonymous')")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init")
    sp.add_argument("--reset", action="store_true")
    sp.add_argument("--seed-basic", action="store_true")
    sp.set_defaults(func=cmd_init)


    sp = sub.add_parser("boot")
    sp.add_argument("--limit", type=int, default=12)
    sp.set_defaults(func=cmd_boot)

    sp = sub.add_parser("search")
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=20)
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("read")
    sp.add_argument("node")
    sp.add_argument("--body", action="store_true")
    sp.add_argument("--include-soft", action="store_true")
    sp.add_argument("--limit", type=int, default=50)
    sp.set_defaults(func=cmd_read)

    sp = sub.add_parser("impact")
    sp.add_argument("node")
    sp.add_argument("--include-soft", action="store_true")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_impact)

    sp = sub.add_parser("add-event")
    sp.add_argument("--text", required=True)
    sp.add_argument("--summary")
    sp.add_argument("--source-type", default="manual")
    sp.add_argument("--id")
    sp.set_defaults(func=cmd_add_event)

    sp = sub.add_parser("set-fact")
    sp.add_argument("--id")
    sp.add_argument("--subject", required=True)
    sp.add_argument("--predicate", required=True)
    sp.add_argument("--value", required=True)
    sp.add_argument("--status", default="active")
    sp.add_argument("--confidence", default="medium")
    sp.add_argument("--event")
    sp.add_argument("--force", action="store_true")
    sp.set_defaults(func=cmd_set_fact)

    sp = sub.add_parser("add-entry")
    sp.add_argument("--id")
    sp.add_argument("--title", required=True)
    sp.add_argument("--body", default="")
    sp.add_argument("--body-file", type=Path)
    sp.add_argument("--summary")
    sp.add_argument("--event")
    sp.add_argument("--pinned", action="store_true")
    sp.add_argument("--depends-on", action="append")
    sp.add_argument("--force", action="store_true")
    sp.set_defaults(func=cmd_add_entry)

    sp = sub.add_parser("link")
    sp.add_argument("source")
    sp.add_argument("target")
    sp.add_argument("--type", default="DEPENDS_ON")
    sp.add_argument("--reason")
    sp.set_defaults(func=cmd_link)

    sp = sub.add_parser("propose")
    sp.add_argument("--operation", required=True)
    sp.add_argument("--touches", nargs="+", required=True)
    sp.add_argument("--reason", required=True)
    sp.add_argument("--event")
    sp.add_argument("--id")
    sp.set_defaults(func=cmd_propose)

    sp = sub.add_parser("check")
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("export")
    sp.set_defaults(func=cmd_export)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
