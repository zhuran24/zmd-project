#!/usr/bin/env python3
"""Slim project memory system.

One source of truth: cc_memory/memory.db.
Generated Markdown under cc_memory/exports/ is disposable view output.
"""
from __future__ import annotations

import argparse
import array
import datetime as _dt
import hashlib
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MEM_DIR = Path(__file__).resolve().parent
DEFAULT_DB = MEM_DIR / "memory.db"
DEFAULT_EXPORT = MEM_DIR / "exports" / "MEMORY.md"
SCHEMA_VERSION = 3
HARD_EDGE_TYPES = {"DEPENDS_ON", "DERIVED_FROM", "SUPERSEDES", "CONTRADICTS"}
ALL_EDGE_TYPES = HARD_EDGE_TYPES | {"MENTIONS", "RELATED_TO", "SUPPORTS", "PROJECTS_TO"}
MAX_EXPORT_BYTES = 24_576
SUGGESTION_REVIEW_SCORE = 12.0
SUGGESTION_STORE_SCORE = 8.0
DEFAULT_EMBED_PYTHON = Path(os.environ.get("CC_MEMORY_EMBED_PYTHON", r"C:\Users\22957\zmd_embed_ab\venv\Scripts\python.exe"))
DEFAULT_EMBED_MODEL = os.environ.get("CC_MEMORY_EMBED_MODEL", "microsoft/harrier-oss-v1-0.6b")
EMBED_HELPER = MEM_DIR / "embed_helper.py"
EMBED_PROVIDER = "sentence-transformers"
EMBED_NORMALIZE = 1
DEFAULT_RERANK_PYTHON = Path(os.environ.get("CC_MEMORY_RERANK_PYTHON", r"C:\Users\22957\zmd_embed_ab\venv\Scripts\python.exe"))
DEFAULT_RERANK_MODEL = os.environ.get("CC_MEMORY_RERANK_MODEL", "Qwen/Qwen3-Reranker-0.6B")
RERANK_HELPER = MEM_DIR / "rerank_helper.py"
RERANK_CANDIDATE_LIMIT = 20
# Cross-encoder relevance below this is pruned. Calibrated on own-data dogfood:
# Qwen3-Reranker is decisive for SPECIFIC queries (true ~1.0 / noise ~0), but for
# BROAD/topical drafts genuinely-related nodes cluster ~0.40-0.49, which 0.50 wrongly
# pruned. 0.40 keeps those while still cutting clear noise (<0.2). High-score pruned
# candidates emit a WARN so over-pruning stays observable.
RERANK_SCORE_FLOOR = 0.40
SEMANTIC_DENSE_LIMIT = 80
# Dense cosine -> suggestion score via a shifted-linear: only the part of the cosine
# ABOVE the floor counts, so a weak dense-only hit cannot flood the review queue or
# trip the option-A gate alone. cosine>=~0.6 reaches the 12.0 review gate; 0.5..0.6
# stores as advisory; <0.5 only nudges a lexically/graph-corroborated candidate.
# Conservative initial values — recalibrate on a real corpus cosine distribution (P3).
SEMANTIC_SCORE_SCALE = 40.0
SEMANTIC_COSINE_FLOOR = 0.30


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
    con.execute("PRAGMA busy_timeout = 5000")
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
        for table in [
            "node_embeddings",
            "embedding_models",
            "relation_suggestions",
            "read_watermarks",
            "mutations",
            "changes",
            "aliases",
            "edges",
            "entries",
            "facts",
            "events",
            "meta",
        ]:
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
        CREATE TABLE IF NOT EXISTS relation_suggestions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL CHECK(source_type IN ('fact','entry')),
            source_id TEXT NOT NULL,
            target_type TEXT NOT NULL CHECK(target_type IN ('fact','entry')),
            target_id TEXT NOT NULL,
            suggested_edge_type TEXT NOT NULL,
            score REAL NOT NULL,
            signals_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','rejected','stale')),
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            UNIQUE(source_type, source_id, target_type, target_id)
        );
        CREATE TABLE IF NOT EXISTS embedding_models(
            id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            model_name TEXT NOT NULL,
            dim INTEGER NOT NULL,
            normalize INTEGER NOT NULL,
            device TEXT NOT NULL,
            created_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS node_embeddings(
            node_type TEXT NOT NULL CHECK(node_type IN ('fact','entry')),
            node_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            dim INTEGER NOT NULL,
            dtype TEXT NOT NULL,
            vector_blob BLOB NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY(node_type, node_id, model_id),
            FOREIGN KEY(model_id) REFERENCES embedding_models(id)
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
    return {
        t: int(con.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"])
        for t in ["events", "facts", "entries", "edges", "changes", "mutations", "read_watermarks", "relation_suggestions"]
    }


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


STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "from", "into", "have", "not", "are", "you", "but", "can", "then",
    "shall", "should", "would", "could", "when", "before", "after", "entry", "fact", "memory", "system", "python",
    "一个", "这个", "那个", "需要", "不是", "不能", "可以", "必须", "因为", "所以", "如果", "以及", "或者", "然后", "当前", "系统", "记忆", "条目", "事实",
}
ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]{1,}")
CJK_RUN_RE = re.compile(r"[\u3400-\u9fff]{2,}")


def _cjk_ngrams(run: str) -> set[str]:
    out: set[str] = set()
    # Bigrams and trigrams give Chinese text useful deterministic recall without a model.
    for n in (2, 3):
        if len(run) >= n:
            out.update(run[i : i + n] for i in range(len(run) - n + 1))
    if 2 <= len(run) <= 8:
        out.add(run)
    return out


def text_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for raw in ASCII_TOKEN_RE.findall(text.lower()):
        for part in re.split(r"[_\-]+", raw):
            if len(part) >= 2 and part not in STOPWORDS:
                tokens.add(part)
        if len(raw) >= 3 and raw not in STOPWORDS:
            tokens.add(raw)
    for run in CJK_RUN_RE.findall(text):
        for token in _cjk_ngrams(run):
            if token not in STOPWORDS:
                tokens.add(token)
    return tokens


def node_text_for_relation(row: sqlite3.Row, typ: str) -> str:
    if typ == "fact":
        return "\n".join([row["id"], row["subject"], row["predicate"], row["value"], row["metadata_json"] or ""])
    meta = jload(row["metadata_json"], {})
    return "\n".join([row["id"], row["title"], meta.get("index_summary", ""), meta.get("description", ""), row["body"], row["metadata_json"] or ""])


def node_text_by_id(con: sqlite3.Connection, typ: str, node_id: str) -> str | None:
    if typ == "fact":
        row = con.execute("SELECT * FROM facts WHERE id=? AND status='active'", (node_id,)).fetchone()
    else:
        row = con.execute("SELECT * FROM entries WHERE id=? AND status='active'", (node_id,)).fetchone()
    if not row:
        return None
    return node_text_for_relation(row, typ)


def all_active_nodes(con: sqlite3.Connection) -> list[tuple[str, sqlite3.Row]]:
    nodes: list[tuple[str, sqlite3.Row]] = []
    nodes.extend(("fact", r) for r in con.execute("SELECT * FROM facts WHERE status='active' ORDER BY id"))
    nodes.extend(("entry", r) for r in con.execute("SELECT * FROM entries WHERE status='active' ORDER BY id"))
    return nodes


class EmbeddingUnavailable(RuntimeError):
    """Optional semantic backend is unavailable; lexical behavior should continue."""


class RerankUnavailable(RuntimeError):
    """Optional rerank backend is unavailable; pre-rerank behavior should continue."""


def embedding_python() -> Path:
    return Path(os.environ.get("CC_MEMORY_EMBED_PYTHON", str(DEFAULT_EMBED_PYTHON)))


def embedding_model_name(model: str | None = None) -> str:
    return model or os.environ.get("CC_MEMORY_EMBED_MODEL", DEFAULT_EMBED_MODEL)


def embedding_model_id(model: str) -> str:
    return f"{EMBED_PROVIDER}:{model}"


def embedding_env() -> dict[str, str]:
    env = os.environ.copy()
    hf_home = env.get("HF_HOME") or r"E:\caches\huggingface"
    env["HF_HOME"] = hf_home
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("TRANSFORMERS_OFFLINE", "1")
    env.setdefault("HF_HUB_CACHE", str(Path(hf_home) / "hub"))
    env.setdefault("HF_XET_CACHE", str(Path(hf_home) / "xet"))
    return env


def rerank_python() -> Path:
    return Path(os.environ.get("CC_MEMORY_RERANK_PYTHON", str(DEFAULT_RERANK_PYTHON)))


def rerank_model_name(model: str | None = None) -> str:
    return model or os.environ.get("CC_MEMORY_RERANK_MODEL", DEFAULT_RERANK_MODEL)


def rerank_env() -> dict[str, str]:
    env = os.environ.copy()
    hf_home = env.get("HF_HOME") or r"E:\caches\huggingface"
    env["HF_HOME"] = hf_home
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("TRANSFORMERS_OFFLINE", "1")
    env.setdefault("HF_HUB_CACHE", str(Path(hf_home) / "hub"))
    env.setdefault("HF_XET_CACHE", str(Path(hf_home) / "xet"))
    return env


def call_embed_helper(
    texts: list[str],
    *,
    mode: str,
    model: str | None = None,
    batch_size: int = 8,
    timeout: int = 600,
) -> dict[str, Any]:
    if mode not in {"doc", "query"}:
        raise ValueError(f"unknown embedding mode: {mode}")
    if not texts:
        return {
            "model": embedding_model_name(model),
            "vectors": [],
            "dim": 0,
            "dtype": "float32",
            "normalize": EMBED_NORMALIZE,
            "device": "unknown",
        }
    py = embedding_python()
    if not py.exists():
        raise EmbeddingUnavailable(f"embedding python not found: {py}")
    if not EMBED_HELPER.exists():
        raise EmbeddingUnavailable(f"embedding helper not found: {EMBED_HELPER}")
    payload = {
        "texts": texts,
        "mode": mode,
        "model": embedding_model_name(model),
        "batch_size": batch_size,
    }
    try:
        proc = subprocess.run(
            [str(py), str(EMBED_HELPER)],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            cwd=ROOT,
            env=embedding_env(),
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EmbeddingUnavailable(f"embedding helper could not run: {exc}") from exc
    if proc.returncode != 0:
        detail = short((proc.stderr or proc.stdout or "").strip(), 1000)
        raise EmbeddingUnavailable(f"embedding helper failed with exit {proc.returncode}: {detail}")
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        detail = short(proc.stdout.strip(), 1000)
        raise EmbeddingUnavailable(f"embedding helper returned invalid JSON: {detail}") from exc
    if out.get("status") != "ok":
        raise EmbeddingUnavailable(str(out.get("error") or "embedding helper did not report ok"))
    return out


def call_rerank_helper(
    query: str,
    docs: list[str],
    *,
    model: str | None = None,
    batch_size: int = 8,
    timeout: int = 600,
) -> list[float]:
    if not docs:
        return []
    py = rerank_python()
    if not py.exists():
        raise RerankUnavailable(f"rerank python not found: {py}")
    if not RERANK_HELPER.exists():
        raise RerankUnavailable(f"rerank helper not found: {RERANK_HELPER}")
    payload = {
        "query": query,
        "docs": docs,
        "model": rerank_model_name(model),
        "batch_size": batch_size,
    }
    try:
        proc = subprocess.run(
            [str(py), str(RERANK_HELPER)],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            cwd=ROOT,
            env=rerank_env(),
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RerankUnavailable(f"rerank helper could not run: {exc}") from exc
    if proc.returncode != 0:
        detail = short((proc.stderr or proc.stdout or "").strip(), 1000)
        raise RerankUnavailable(f"rerank helper failed with exit {proc.returncode}: {detail}")
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        detail = short(proc.stdout.strip(), 1000)
        raise RerankUnavailable(f"rerank helper returned invalid JSON: {detail}") from exc
    scores = out.get("scores")
    if not isinstance(scores, list):
        raise RerankUnavailable("rerank helper returned no scores list")
    if len(scores) != len(docs):
        raise RerankUnavailable(f"rerank helper returned {len(scores)} scores for {len(docs)} docs")
    try:
        return [float(score) for score in scores]
    except (TypeError, ValueError) as exc:
        raise RerankUnavailable("rerank helper returned non-numeric scores") from exc


def node_content_hash(typ: str, node_id: str, text: str) -> str:
    h = hashlib.sha256()
    h.update(typ.encode("utf-8"))
    h.update(b"\0")
    h.update(node_id.encode("utf-8"))
    h.update(b"\0")
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def vector_to_blob(vector: list[float]) -> bytes:
    return array.array("f", (float(x) for x in vector)).tobytes()


def active_node_embedding_rows(con: sqlite3.Connection, model_id: str) -> list[sqlite3.Row]:
    return list(
        con.execute(
            """
            SELECT ne.node_type, ne.node_id, ne.dim, ne.dtype, ne.vector_blob
            FROM node_embeddings ne
            JOIN facts f ON ne.node_type='fact' AND ne.node_id=f.id
            WHERE ne.model_id=? AND f.status='active'
            UNION ALL
            SELECT ne.node_type, ne.node_id, ne.dim, ne.dtype, ne.vector_blob
            FROM node_embeddings ne
            JOIN entries e ON ne.node_type='entry' AND ne.node_id=e.id
            WHERE ne.model_id=? AND e.status='active'
            """,
            (model_id, model_id),
        )
    )


def semantic_relation_candidates(
    con: sqlite3.Connection,
    *,
    query_text: str,
    source_type: str | None = None,
    source_id: str | None = None,
    model: str | None = None,
    limit: int = SEMANTIC_DENSE_LIMIT,
    warnings: list[str] | None = None,
) -> list[dict[str, Any]]:
    model_name = embedding_model_name(model)
    model_id = embedding_model_id(model_name)
    rows = active_node_embedding_rows(con, model_id)
    if source_type and source_id:
        rows = [r for r in rows if not (r["node_type"] == source_type and r["node_id"] == source_id)]
    if not rows:
        if warnings is not None:
            warnings.append(f"semantic suggestions unavailable: no active embeddings for model {model_name}")
        return []
    try:
        import numpy as np
    except ImportError:
        if warnings is not None:
            warnings.append("semantic suggestions unavailable: numpy is not installed in this Python")
        return []
    try:
        payload = call_embed_helper([query_text], mode="query", model=model_name)
    except EmbeddingUnavailable as exc:
        if warnings is not None:
            warnings.append(f"semantic suggestions unavailable: {exc}")
        return []
    vectors = payload.get("vectors") or []
    if not vectors:
        return []
    query_vec = np.asarray(vectors[0], dtype=np.float32)
    query_norm = float(np.linalg.norm(query_vec))
    if query_norm == 0.0:
        return []
    query_vec = query_vec / query_norm

    kept: list[sqlite3.Row] = []
    doc_vectors: list[Any] = []
    for row in rows:
        if row["dtype"] != "float32":
            continue
        vec = np.frombuffer(row["vector_blob"], dtype=np.float32)
        if vec.shape[0] != query_vec.shape[0]:
            continue
        norm_v = float(np.linalg.norm(vec))
        if norm_v == 0.0:
            continue
        doc_vectors.append(vec / norm_v)
        kept.append(row)
    if not kept:
        return []
    matrix = np.vstack(doc_vectors)
    scores = matrix @ query_vec
    ranked = np.argsort(-scores)[:limit]
    out: list[dict[str, Any]] = []
    for idx in ranked:
        cosine = float(scores[int(idx)])
        weighted = max(0.0, cosine - SEMANTIC_COSINE_FLOOR) * SEMANTIC_SCORE_SCALE
        if weighted <= 0.0:
            continue
        row = kept[int(idx)]
        out.append(
            {
                "type": row["node_type"],
                "id": row["node_id"],
                "cosine": cosine,
                "score": round(weighted, 2),
                "signal": f"dense semantic cosine: {cosine:.4f}",
            }
        )
    return out


def relation_suggestions(
    con: sqlite3.Connection,
    *,
    title: str = "",
    body: str = "",
    source_type: str | None = None,
    source_id: str | None = None,
    limit: int = 20,
    min_score: float = 6.0,
    semantic: bool = False,
    semantic_model: str | None = None,
    semantic_limit: int = SEMANTIC_DENSE_LIMIT,
    warnings: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Find related facts/entries deterministically.

    This is the system-side antidote to "the current agent must remember all related entries".
    It combines exact id/alias mentions, token overlap with IDF weighting, and one-hop graph
    propagation. It produces a review queue; it does not ask the user to discover candidates.
    """
    draft_text = "\n".join([title or "", body or ""])
    q_tokens = text_tokens(draft_text)
    normalized_draft = norm(draft_text)
    nodes = all_active_nodes(con)
    if source_type and source_id:
        nodes = [(t, r) for t, r in nodes if not (t == source_type and r["id"] == source_id)]

    node_tokens: dict[tuple[str, str], set[str]] = {}
    df: dict[str, int] = defaultdict(int)
    for typ, row in nodes:
        toks = text_tokens(node_text_for_relation(row, typ))
        node_tokens[(typ, row["id"])] = toks
        for tok in toks:
            df[tok] += 1
    n_docs = max(1, len(nodes))

    alias_rows = list(con.execute("SELECT alias,target_type,target_id FROM aliases"))
    aliases_by_target: dict[tuple[str, str], list[str]] = defaultdict(list)
    for r in alias_rows:
        aliases_by_target[(r["target_type"], r["target_id"])].append(r["alias"])

    scores: dict[tuple[str, str], float] = defaultdict(float)
    signals: dict[tuple[str, str], list[str]] = defaultdict(list)

    for typ, row in nodes:
        key = (typ, row["id"])
        cid = norm(row["id"])
        if cid and cid in normalized_draft:
            scores[key] += 80.0
            signals[key].append(f"exact id mention: {row['id']}")
        for alias in aliases_by_target.get(key, []):
            if alias and alias in normalized_draft and alias != cid:
                scores[key] += 65.0
                signals[key].append(f"alias mention: {alias}")
                break
        toks = node_tokens[key]
        shared = q_tokens & toks
        if shared:
            weighted = sum(math.log((n_docs + 1) / (df.get(tok, 0) + 1)) + 1.0 for tok in shared)
            denom = math.sqrt(max(1, len(q_tokens)) * max(1, len(toks)))
            overlap_score = 42.0 * weighted / denom
            scores[key] += overlap_score
            preview = ", ".join(sorted(shared, key=lambda x: (-len(x), x))[:8])
            signals[key].append(f"token overlap: {preview}")
        # Subject/predicate names are strong hooks for fact dependency discovery.
        if typ == "fact":
            hooks = text_tokens(f"{row['subject']} {row['predicate']} {row['id']}")
            hook_shared = q_tokens & hooks
            if hook_shared:
                scores[key] += 10.0 + 4.0 * len(hook_shared)
                signals[key].append("fact slot hook: " + ", ".join(sorted(hook_shared)[:5]))

    if semantic:
        for candidate in semantic_relation_candidates(
            con,
            query_text=draft_text,
            source_type=source_type,
            source_id=source_id,
            model=semantic_model,
            limit=semantic_limit,
            warnings=warnings,
        ):
            key = (candidate["type"], candidate["id"])
            scores[key] += float(candidate["score"])
            signals[key].append(candidate["signal"])

    # Graph propagation: matching a fact should surface entries that depend on it; matching an
    # entry should surface its hard dependencies. This helps the system find clusters, not just
    # isolated lexical twins.
    seed_scores = dict(scores)
    for (typ, node_id), score in sorted(seed_scores.items(), key=lambda kv: kv[1], reverse=True):
        if score < min_score:
            continue
        if typ == "fact":
            for e in incoming_edges(con, "fact", node_id, include_soft=True):
                key = (e["source_type"], e["source_id"])
                if source_type and source_id and key == (source_type, source_id):
                    continue
                bump = min(18.0, score * (0.45 if e["hard"] else 0.25))
                scores[key] += bump
                signals[key].append(f"graph neighbor via {e['edge_type']} to fact:{node_id}")
        else:
            for e in outgoing_edges(con, "entry", node_id):
                key = (e["target_type"], e["target_id"])
                if source_type and source_id and key == (source_type, source_id):
                    continue
                bump = min(16.0, score * (0.35 if e["hard"] else 0.2))
                scores[key] += bump
                signals[key].append(f"shared dependency from entry:{node_id} via {e['edge_type']}")

    out: list[dict[str, Any]] = []
    for key, score in scores.items():
        if score < min_score:
            continue
        typ, node_id = key
        suggested_edge = "RELATED_TO"
        if typ == "fact":
            # Exact mentions and strong fact-slot matches are good hard-dependency candidates;
            # weaker fact matches stay soft until reviewed.
            exactish = any(sig.startswith("exact id mention") or sig.startswith("alias mention") for sig in signals[key])
            suggested_edge = "DEPENDS_ON" if exactish or score >= 34.0 else "MENTIONS"
        out.append({
            "type": typ,
            "id": node_id,
            "score": round(score, 2),
            "suggested_edge_type": suggested_edge,
            "summary": node_summary(con, typ, node_id),
            "signals": signals[key][:10],
        })
    out.sort(key=lambda x: (-float(x["score"]), x["type"], x["id"]))
    return out[:limit]


def rerank_relation_suggestions(
    con: sqlite3.Connection,
    suggestions: list[dict[str, Any]],
    *,
    query_text: str,
    model: str | None = None,
    limit: int = RERANK_CANDIDATE_LIMIT,
    floor: float = RERANK_SCORE_FLOOR,
    warnings: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Use a cross-encoder only to prune and order top candidates.

    Rerank scores are intentionally not folded into suggestion["score"], because
    the existing lexical/semantic score remains the only store/review gate.
    """
    if not suggestions:
        return suggestions
    head = suggestions[: max(0, limit)]
    if not head:
        return []

    docs: list[str] = []
    for suggestion in head:
        text = node_text_by_id(con, suggestion["type"], suggestion["id"])
        if text is None and warnings is not None:
            warnings.append(f"rerank: no full text for {suggestion['type']}:{suggestion['id']}, scoring on summary")
        docs.append(text if text is not None else suggestion.get("summary", ""))
    try:
        scores = call_rerank_helper(query_text, docs, model=model)
    except RerankUnavailable as exc:
        if warnings is not None:
            warnings.append(f"rerank suggestions unavailable: {exc}")
        return suggestions

    kept: list[dict[str, Any]] = []
    for suggestion, rerank_score in zip(head, scores, strict=True):
        updated = dict(suggestion)
        updated["signals"] = list(updated.get("signals") or [])
        updated["rerank_score"] = round(float(rerank_score), 4)
        updated["signals"].append(f"rerank relevance: {float(rerank_score):.4f}")
        if float(rerank_score) >= floor:
            kept.append(updated)
        elif warnings is not None and float(suggestion["score"]) >= SUGGESTION_REVIEW_SCORE:
            warnings.append(
                f"rerank pruned a high-score candidate {suggestion['type']}:{suggestion['id']} "
                f"(score={float(suggestion['score']):.1f}, rerank={float(rerank_score):.3f}<{floor}); "
                f"check RERANK_SCORE_FLOOR if unexpected"
            )
    kept.sort(key=lambda x: (-float(x.get("rerank_score", 0.0)), -float(x["score"]), x["type"], x["id"]))
    return kept


def store_relation_suggestions(
    con: sqlite3.Connection,
    source_type: str,
    source_id: str,
    suggestions: list[dict[str, Any]],
    *,
    min_score: float = SUGGESTION_STORE_SCORE,
    skip_existing_edges: bool = True,
) -> int:
    stored = 0
    for s in suggestions:
        if float(s["score"]) < min_score:
            continue
        if skip_existing_edges:
            existing = con.execute(
                """SELECT 1 FROM edges WHERE source_type=? AND source_id=? AND target_type=? AND target_id=?""",
                (source_type, source_id, s["type"], s["id"]),
            ).fetchone()
            if existing:
                continue
        con.execute(
            """INSERT INTO relation_suggestions(
                   source_type,source_id,target_type,target_id,suggested_edge_type,score,signals_json,status,created_at
               ) VALUES(?,?,?,?,?,?,?,?,?)
               ON CONFLICT(source_type,source_id,target_type,target_id) DO UPDATE SET
                   suggested_edge_type=excluded.suggested_edge_type,
                   score=excluded.score,
                   signals_json=excluded.signals_json,
                   status=CASE WHEN relation_suggestions.status='accepted' THEN 'accepted' ELSE 'pending' END,
                   created_at=excluded.created_at""",
            (source_type, source_id, s["type"], s["id"], s["suggested_edge_type"], float(s["score"]), jdump(s["signals"]), "pending", now()),
        )
        stored += 1
    return stored


def pending_relation_suggestions(con: sqlite3.Connection, *, min_score: float = SUGGESTION_REVIEW_SCORE) -> list[sqlite3.Row]:
    return list(
        con.execute(
            """SELECT * FROM relation_suggestions
               WHERE status='pending' AND score>=?
               ORDER BY score DESC, id""",
            (min_score,),
        )
    )


def export_markdown(con: sqlite3.Connection, path: Path = DEFAULT_EXPORT) -> str:
    counts = list_counts(con)
    pending_suggestions = con.execute("SELECT count(*) AS n FROM relation_suggestions WHERE status='pending'").fetchone()["n"]
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
        f"- pending relation suggestions: {pending_suggestions}",
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
    for s in con.execute("SELECT * FROM relation_suggestions"):
        if s["suggested_edge_type"] not in ALL_EDGE_TYPES:
            errors.append(f"suggestion {s['id']} unknown edge type: {s['suggested_edge_type']}")
        if not node_exists(con, s["source_type"], s["source_id"]):
            errors.append(f"suggestion {s['id']} source missing: {s['source_type']}:{s['source_id']}")
        if not node_exists(con, s["target_type"], s["target_id"]):
            errors.append(f"suggestion {s['id']} target missing: {s['target_type']}:{s['target_id']}")
    pending = pending_relation_suggestions(con)
    if pending:
        preview = ", ".join(str(r["id"]) for r in pending[:10])
        errors.append(
            f"pending relation suggestions need review: {len(pending)} above score {SUGGESTION_REVIEW_SCORE:g} "
            f"(ids: {preview})"
        )
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
    print("- `python cc_memory/mem.py suggest --title \"...\" --body \"...\"` before adding memory")
    print("- `python cc_memory/mem.py read <id>`")
    print("- `python cc_memory/mem.py impact <id>` before changing a fact or entry")
    print("- `python cc_memory/mem.py add-event --text \"...\"` then `set-fact` / `add-entry` / `relations` review")
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


def _suggestion_lines(suggestions: list[dict[str, Any]], *, limit: int = 12) -> list[str]:
    lines: list[str] = []
    for i, s in enumerate(suggestions[:limit], start=1):
        signals = "; ".join(s.get("signals", [])[:3])
        lines.append(
            f"{i:>2}. {s['type']}:{s['id']} score={s['score']} suggest={s['suggested_edge_type']} — {s.get('summary','')}"
        )
        if signals:
            lines.append(f"    signals: {signals}")
    if len(suggestions) > limit:
        lines.append(f"    ... {len(suggestions) - limit} more")
    return lines


def cmd_suggest(args: argparse.Namespace) -> int:
    con = connect(args.db)
    init_schema(con)
    body = args.body or ""
    if args.body_file:
        body = args.body_file.read_text(encoding="utf-8")
    warnings: list[str] = []
    suggestions = relation_suggestions(
        con,
        title=args.title or "",
        body=body,
        limit=args.limit,
        min_score=args.min_score,
        semantic=args.semantic,
        semantic_model=args.model,
        semantic_limit=args.semantic_limit,
        warnings=warnings,
    )
    if args.rerank:
        suggestions = rerank_relation_suggestions(
            con,
            suggestions,
            query_text="\n".join([args.title or "", body]),
            model=args.rerank_model,
            warnings=warnings,
        )
    if args.json:
        for warning in warnings:
            print(f"WARN {warning}", file=sys.stderr)
        print(json.dumps(suggestions, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    for warning in warnings:
        print(f"WARN {warning}", file=sys.stderr)
    print(f"relation suggestions: {len(suggestions)}")
    for line in _suggestion_lines(suggestions, limit=args.limit):
        print(line)
    if not suggestions:
        print("no candidates above threshold")
    return 0


def cmd_relations(args: argparse.Namespace) -> int:
    con = connect(args.db)
    init_schema(con)
    min_score = args.min_score
    if args.all:
        rows = list(con.execute("SELECT * FROM relation_suggestions ORDER BY status, score DESC, id"))
    else:
        rows = list(
            con.execute(
                "SELECT * FROM relation_suggestions WHERE status='pending' AND score>=? ORDER BY score DESC, id",
                (min_score,),
            )
        )
    if args.json:
        print(json.dumps([dict(r) | {"signals": jload(r["signals_json"], [])} for r in rows], ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print(f"relation suggestions: {len(rows)}" + (" (all)" if args.all else " pending"))
    for r in rows:
        signals = "; ".join(jload(r["signals_json"], [])[:3])
        print(
            f"#{r['id']} {r['status']} score={r['score']:.2f} "
            f"{r['source_type']}:{r['source_id']} --{r['suggested_edge_type']}--> {r['target_type']}:{r['target_id']}"
        )
        if signals:
            print(f"    signals: {signals}")
    if not rows:
        print("no relation suggestions needing review")
    return 0


def cmd_review_relation(args: argparse.Namespace) -> int:
    con = connect(args.db)
    init_schema(con)
    row = con.execute("SELECT * FROM relation_suggestions WHERE id=?", (args.id,)).fetchone()
    if not row:
        print(f"unknown relation suggestion: {args.id}")
        return 1
    if args.accept == args.reject:
        raise SystemExit("pass exactly one of --accept or --reject")
    if args.accept:
        edge_type = (args.type or row["suggested_edge_type"]).upper()
        add_edge_row(
            con,
            row["source_type"],
            row["source_id"],
            edge_type,
            row["target_type"],
            row["target_id"],
            reason=args.reason or f"accepted relation suggestion #{row['id']} score={row['score']:.2f}",
        )
        con.execute(
            "UPDATE relation_suggestions SET status='accepted', reviewed_at=? WHERE id=?",
            (now(), args.id),
        )
        con.commit()
        print(f"accepted #{args.id}: {row['source_type']}:{row['source_id']} --{edge_type}--> {row['target_type']}:{row['target_id']}")
        return 0
    con.execute("UPDATE relation_suggestions SET status='rejected', reviewed_at=? WHERE id=?", (now(), args.id))
    con.commit()
    print(f"rejected #{args.id}")
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
    suggestions: list[dict[str, Any]] = []
    stored = 0
    warnings: list[str] = []
    if args.semantic or args.rerank:
        suggestions = relation_suggestions(
            con,
            title=f"{args.subject} {args.predicate}",
            body=args.value,
            source_type="fact",
            source_id=fact_id,
            limit=args.suggest_limit,
            min_score=args.suggest_min_score,
            semantic=args.semantic,
            semantic_model=args.model,
            semantic_limit=args.semantic_limit,
            warnings=warnings,
        )
        if args.rerank:
            suggestions = rerank_relation_suggestions(
                con,
                suggestions,
                query_text="\n".join([f"{args.subject} {args.predicate}", args.value]),
                model=args.rerank_model,
                warnings=warnings,
            )
        stored = store_relation_suggestions(con, "fact", fact_id, suggestions)
    con.commit()
    print(f"fact:{fact_id}")
    for warning in warnings:
        print(f"WARN {warning}", file=sys.stderr)
    if args.semantic or args.rerank:
        print(f"relation suggestions stored: {stored}")
        for line in _suggestion_lines(suggestions, limit=min(args.suggest_limit, 12)):
            print(line)
        if stored:
            print("review required: run `python cc_memory/mem.py relations` and accept/reject suggestions before final `check`")
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
    suggestions: list[dict[str, Any]] = []
    stored = 0
    warnings: list[str] = []
    if not args.no_suggest:
        suggestions = relation_suggestions(
            con,
            title=args.title,
            body=body,
            source_type="entry",
            source_id=entry_id,
            limit=args.suggest_limit,
            min_score=args.suggest_min_score,
            semantic=args.semantic,
            semantic_model=args.model,
            semantic_limit=args.semantic_limit,
            warnings=warnings,
        )
        if args.rerank:
            suggestions = rerank_relation_suggestions(
                con,
                suggestions,
                query_text="\n".join([args.title, body]),
                model=args.rerank_model,
                warnings=warnings,
            )
        stored = store_relation_suggestions(con, "entry", entry_id, suggestions)
    con.commit()
    print(f"entry:{entry_id}")
    for warning in warnings:
        print(f"WARN {warning}", file=sys.stderr)
    if not args.no_suggest:
        print(f"relation suggestions stored: {stored}")
        for line in _suggestion_lines(suggestions, limit=min(args.suggest_limit, 12)):
            print(line)
        if stored:
            print("review required: run `python cc_memory/mem.py relations` and accept/reject suggestions before final `check`")
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


def cmd_rebuild_embeddings(args: argparse.Namespace) -> int:
    con = connect(args.db)
    init_schema(con)
    model_name = embedding_model_name(args.model)
    model_id = embedding_model_id(model_name)
    nodes: list[tuple[str, str, str, str]] = []
    for typ, row in all_active_nodes(con):
        text = node_text_for_relation(row, typ)
        content_hash = node_content_hash(typ, row["id"], text)
        existing = con.execute(
            "SELECT content_hash FROM node_embeddings WHERE node_type=? AND node_id=? AND model_id=?",
            (typ, row["id"], model_id),
        ).fetchone()
        if existing and existing["content_hash"] == content_hash:
            continue
        nodes.append((typ, row["id"], text, content_hash))

    total = len(all_active_nodes(con))
    skipped = total - len(nodes)
    if not nodes:
        print(f"embedding model: {model_name}")
        print(f"nodes: total={total} embedded=0 skipped={skipped}")
        return 0

    embedded = 0
    last_dim = 0
    last_device = "unknown"
    try:
        for start in range(0, len(nodes), args.batch_size):
            batch = nodes[start : start + args.batch_size]
            payload = call_embed_helper(
                [text for _, _, text, _ in batch],
                mode="doc",
                model=model_name,
                batch_size=args.batch_size,
                timeout=args.timeout,
            )
            vectors = payload.get("vectors") or []
            if len(vectors) != len(batch):
                raise EmbeddingUnavailable(f"embedding helper returned {len(vectors)} vectors for {len(batch)} texts")
            dim = int(payload.get("dim") or (len(vectors[0]) if vectors else 0))
            dtype = str(payload.get("dtype") or "float32")
            device = str(payload.get("device") or "unknown")
            last_dim = dim
            last_device = device
            con.execute(
                """INSERT INTO embedding_models(id,provider,model_name,dim,normalize,device,created_at,metadata_json)
                   VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     provider=excluded.provider,
                     model_name=excluded.model_name,
                     dim=excluded.dim,
                     normalize=excluded.normalize,
                     device=excluded.device,
                     metadata_json=excluded.metadata_json""",
                (
                    model_id,
                    EMBED_PROVIDER,
                    model_name,
                    dim,
                    int(payload.get("normalize", EMBED_NORMALIZE)),
                    device,
                    now(),
                    jdump(
                        {
                            "helper": str(EMBED_HELPER),
                            "python": str(embedding_python()),
                            "dtype": dtype,
                        }
                    ),
                ),
            )
            for (typ, node_id, _text, content_hash), vector in zip(batch, vectors, strict=True):
                if len(vector) != dim:
                    raise EmbeddingUnavailable(f"vector dim mismatch for {typ}:{node_id}: {len(vector)} != {dim}")
                con.execute(
                    """INSERT INTO node_embeddings(node_type,node_id,model_id,content_hash,dim,dtype,vector_blob,created_at)
                       VALUES(?,?,?,?,?,?,?,?)
                       ON CONFLICT(node_type,node_id,model_id) DO UPDATE SET
                         content_hash=excluded.content_hash,
                         dim=excluded.dim,
                         dtype=excluded.dtype,
                         vector_blob=excluded.vector_blob,
                         created_at=excluded.created_at""",
                    (typ, node_id, model_id, content_hash, dim, "float32", vector_to_blob(vector), now()),
                )
                embedded += 1
            con.commit()
    except EmbeddingUnavailable as exc:
        print(f"rebuild-embeddings unavailable: {exc}", file=sys.stderr)
        return 2

    print(f"embedding model: {model_name}")
    print(f"model_id: {model_id}")
    print(f"nodes: total={total} embedded={embedded} skipped={skipped}")
    print(f"vector: dim={last_dim} dtype=float32 normalize={EMBED_NORMALIZE} device={last_device}")
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

    sp = sub.add_parser("suggest")
    sp.add_argument("--title", default="")
    sp.add_argument("--body", default="")
    sp.add_argument("--body-file", type=Path)
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--min-score", type=float, default=6.0)
    sp.add_argument("--semantic", action="store_true", help="merge optional dense semantic candidates from node_embeddings")
    sp.add_argument("--model", default=None, help=f"embedding model (default: {DEFAULT_EMBED_MODEL})")
    sp.add_argument("--semantic-limit", type=int, default=SEMANTIC_DENSE_LIMIT)
    sp.add_argument("--rerank", action="store_true", help="prune and reorder top relation candidates with the optional reranker")
    sp.add_argument("--rerank-model", default=None, help=f"rerank model (default: {DEFAULT_RERANK_MODEL})")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_suggest)

    sp = sub.add_parser("relations")
    sp.add_argument("--all", action="store_true")
    sp.add_argument("--min-score", type=float, default=SUGGESTION_REVIEW_SCORE)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_relations)

    sp = sub.add_parser("review-relation")
    sp.add_argument("id", type=int)
    sp.add_argument("--accept", action="store_true")
    sp.add_argument("--reject", action="store_true")
    sp.add_argument("--type")
    sp.add_argument("--reason")
    sp.set_defaults(func=cmd_review_relation)

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
    sp.add_argument("--semantic", action="store_true", help="store relation suggestions using lexical plus dense semantic candidates")
    sp.add_argument("--model", default=None, help=f"embedding model (default: {DEFAULT_EMBED_MODEL})")
    sp.add_argument("--semantic-limit", type=int, default=SEMANTIC_DENSE_LIMIT)
    sp.add_argument("--rerank", action="store_true", help="prune and reorder top relation candidates with the optional reranker")
    sp.add_argument("--rerank-model", default=None, help=f"rerank model (default: {DEFAULT_RERANK_MODEL})")
    sp.add_argument("--suggest-limit", type=int, default=20)
    sp.add_argument("--suggest-min-score", type=float, default=6.0)
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
    sp.add_argument("--no-suggest", action="store_true", help="disable automatic relation suggestion queue")
    sp.add_argument("--suggest-limit", type=int, default=20)
    sp.add_argument("--suggest-min-score", type=float, default=6.0)
    sp.add_argument("--semantic", action="store_true", help="merge optional dense semantic candidates into relation suggestions")
    sp.add_argument("--model", default=None, help=f"embedding model (default: {DEFAULT_EMBED_MODEL})")
    sp.add_argument("--semantic-limit", type=int, default=SEMANTIC_DENSE_LIMIT)
    sp.add_argument("--rerank", action="store_true", help="prune and reorder top relation candidates with the optional reranker")
    sp.add_argument("--rerank-model", default=None, help=f"rerank model (default: {DEFAULT_RERANK_MODEL})")
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

    sp = sub.add_parser("rebuild-embeddings")
    sp.add_argument("--model", default=None, help=f"embedding model (default: {DEFAULT_EMBED_MODEL})")
    sp.add_argument("--batch-size", type=int, default=8)
    sp.add_argument("--timeout", type=int, default=600)
    sp.set_defaults(func=cmd_rebuild_embeddings)

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
