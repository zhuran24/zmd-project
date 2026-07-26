#!/usr/bin/env python3
"""Slim project memory system.

One source of truth: cc_memory/memory.db.
Generated Markdown under cc_memory/exports/ is disposable view output.
"""
from __future__ import annotations

import argparse
import array
import contextlib
import datetime as _dt
import hashlib
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import time
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
# Dual-boot machine: the same repo is worked from Windows and CachyOS, so the helper venv and
# the shared HF cache live at different per-OS paths. Env vars always override these defaults.
if os.name == "nt":
    _DEFAULT_HELPER_VENV_PYTHON = r"C:\Users\22957\zmd_embed_ab\venv\Scripts\python.exe"
    DEFAULT_HF_HOME = r"E:\caches\huggingface"
else:
    _DEFAULT_HELPER_VENV_PYTHON = str(Path.home() / "zmd_embed_linux" / "venv" / "bin" / "python")
    DEFAULT_HF_HOME = "/mnt/wd_external/caches/huggingface"
DEFAULT_EMBED_PYTHON = Path(os.environ.get("CC_MEMORY_EMBED_PYTHON", _DEFAULT_HELPER_VENV_PYTHON))
DEFAULT_EMBED_MODEL = os.environ.get("CC_MEMORY_EMBED_MODEL", "microsoft/harrier-oss-v1-0.6b")
EMBED_HELPER = Path(os.environ.get("CC_MEMORY_EMBED_HELPER", str(MEM_DIR / "embed_helper.py")))
EMBED_PROVIDER = "sentence-transformers"
EMBED_NORMALIZE = 1
DEFAULT_RERANK_PYTHON = Path(os.environ.get("CC_MEMORY_RERANK_PYTHON", _DEFAULT_HELPER_VENV_PYTHON))
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
PRUNE_DEFAULT_REPORT = ROOT / ".prune" / "prune_scan_report.json"
PRUNE_SCAN_SCHEMA = "prune-scan-v2-two-tier"
# Tier 1 — deterministic: a native strong signal (graph edge / resolved path) makes the
# flag ≈ a real problem, so these enter the cleanable-candidate pool (split by safety_lock).
PRUNE_DETERMINISTIC_FLAGS = [
    "relink_candidate",   # was orphan: disposition is ADD edges (widen, recoverable) — never delete
    "active_superseded",  # active node that is the target of a SUPERSEDES edge
    "dead_ref",           # body references a missing repo path AND clears all 3 benign exclusions
]
# Tier 2 — advisory (FYI only): the signal is a weak proxy (cosine / size / name match), so
# these NEVER enter the candidate pool and imply ZERO disposition. Pure attention pointers.
PRUNE_ADVISORY_FLAGS = [
    "duplicate",                    # cosine proves similar, not redundant
    "oversized",                    # large != mixed/disposable
    "cross_layer_overlap_concern",  # was archive_candidate: same-name vnext card + body-cosine gate (half-migration drift)
    "dead_ref_uncertain",           # missing path but inside a history-record / externalized artifact / prose example
]
PRUNE_DUPLICATE_COSINE = 0.92
# Third-meeting final spec: a bare name match may be a collision (same name, different meaning), so
# the overlap concern only surfaces when source body <-> card body cosine also clears this gate.
# Matches that cannot be verified (no fresh embedding / helper unavailable) or fall below the gate
# are suppressed into report notes — an advisory miss is the safe failure direction here.
PRUNE_OVERLAP_COSINE = 0.80
PRUNE_OVERSIZED_BYTES = 4096
PRUNE_RELINK_MIN_AGE_DAYS = 7  # a just-created orphan may simply not have been linked yet
PRUNE_MAIN_BRANCH = "main"
PRUNE_LOCK_KINDS = {"rule", "verdict", "fact"}
# memory-store data files: dirty here is usually read-watermark noise (boot/read touch the DB) and
# does NOT manufacture false positives, so it is SOFT (warn) not a hard block — see prune_parse_dirty.
PRUNE_DIRTY_SOFT = ("cc_memory/memory.db", "cc_memory/exports/MEMORY.md")
# artifacts some lightweight distributions externalize; absence is expected, not a dead ref
PRUNE_EXTERNALIZED_ARTIFACTS = ("data/preprocessed/candidate_placements.json",)
PRUNE_SELF_ID_RE = re.compile(r"prun(?:e|ing)", re.IGNORECASE)
PRUNE_TITLE_REDLINE_RE = re.compile(
    r"\b(?:not|never|deprecated|obsolete|contradict(?:s|ion)?|conflict|opposite|deny|negative)\b|"
    r"(?:反例|冲突|矛盾|禁止|不要|不得|不是|相反|否定|废弃)",
    re.IGNORECASE,
)
# done/completed/history markers: a dead path inside such a record is expected provenance
PRUNE_HISTORY_RECORD_RE = re.compile(
    r"\b(?:fixed|resolved|done|closed|landed|merged|shipped|completed|reverted|superseded)\b|"
    r"(?:已修复|已解决|已完成|已合并|已落地|已归档|已关闭|已废弃|历史留痕|留痕|provenance)",
    re.IGNORECASE,
)
# example markers right before a path: illustrative, not a load-bearing reference
PRUNE_PROSE_EXAMPLE_RE = re.compile(
    r"(?:e\.g\.|i\.e\.|such as|for example|例如|比如|形如|举例|诸如|譬如|like)[^\n]*$",
    re.IGNORECASE,
)
PRUNE_PATH_RE = re.compile(
    r"(?<![\w:/])("
    r"[A-Za-z]:[\\/][^\s`'\"<>|]+|"
    r"(?:\.{1,2}[\\/])?[A-Za-z0-9_.\-]+(?:[\\/][A-Za-z0-9_.\-]+)+"
    r")"
)

# finalize (single收口本体): one drain at a time via a file lease; concurrent hook
# triggers no-op and let the holder pick up the latest mutations.
FINALIZE_LEASE = MEM_DIR / ".finalize.lock"
FINALIZE_LEASE_STALE = 900  # seconds; a finalize older than this is presumed stuck -> steal
FINALIZE_MAX_DRAIN = 4      # bounded re-run if new mutations land mid-finalize
# check_db emits this exact substring for the "high-score pending need review" error;
# that is normal workflow state (not corruption), so finalize must not treat it as a
# structural failure / async-wake trigger.
REVIEW_MARK = "pending relation suggestions need review"


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


def cross_session_preamble(con: sqlite3.Connection, session_id: str) -> None:
    """Print unread changes by OTHER sessions since this session's watermark,
    WITHOUT advancing it (design B: only `boot` marks them read). Query commands
    call this so ANY lookup surfaces concurrent writes. Best-effort — a notice
    must never break the host command."""
    try:
        delta = session_delta(con, session_id)
    except Exception:
        return
    if not delta:  # None (fresh, no baseline) or [] (caught up) -> stay quiet
        return
    print(
        f"## Heads-up — {len(delta)} unread change(s) by OTHER sessions since your "
        f"last boot (run `boot` to review + mark read):"
    )
    for m in delta[:20]:
        print(f"  - [{(m['session_id'] or '')[:8]}] {m['op']} {m['target_type']}:{m['target_id']}  ({m['created_at']})")
    if len(delta) > 20:
        print(f"  - ... {len(delta) - 20} more")
    print("")


def get_meta(con: sqlite3.Connection, key: str, default: str = "") -> str:
    row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(con: sqlite3.Connection, key: str, value: Any) -> None:
    con.execute(
        "INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )


def max_mutation_id(con: sqlite3.Connection) -> int:
    return int(con.execute("SELECT COALESCE(MAX(id), 0) AS m FROM mutations").fetchone()["m"])


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
    # WAL lets a read-only session (boot/readfirst hook) and a writer (a finalize
    # drain) coexist without "database is locked"; agent-teams run concurrent
    # sessions. -wal/-shm are .gitignored; pre-commit truncates the WAL so the
    # committed memory.db stays self-contained. busy_timeout absorbs the brief
    # contention window during a drain. memory.db lives on C: (local) — WAL-safe.
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA busy_timeout = 30000")
    return con


def connect_readonly(db: Path = DEFAULT_DB) -> sqlite3.Connection:
    """Open the memory DB for diagnostics that must not mutate SQLite state."""
    db = Path(db)
    if not db.exists():
        raise SystemExit(f"memory db not found: {db}")
    con = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
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
        # Write only when absent: an existing-but-different value is real schema DRIFT
        # that check_db must catch — never silently auto-upgrade it. (Also makes
        # init_schema side-effect-free on an existing db, so `check` doesn't write.)
        "INSERT OR IGNORE INTO meta(key,value) VALUES('schema_version', ?)",
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
    hf_home = env.get("HF_HOME") or DEFAULT_HF_HOME
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
    hf_home = env.get("HF_HOME") or DEFAULT_HF_HOME
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
                   status=CASE WHEN relation_suggestions.status IN ('accepted','rejected') THEN relation_suggestions.status ELSE 'pending' END,
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


def prune_name_key(value: str) -> str:
    value = (value or "").strip().lower().replace("\\", "/")
    value = re.sub(r"\.md$", "", value)
    value = re.sub(r"[^\w\u3400-\u9fff]+", "-", value)
    return re.sub(r"-+", "-", value).strip("-")


def prune_cosine_threshold(value: str) -> float:
    try:
        threshold = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid cosine threshold: {value!r}") from exc
    if not math.isfinite(threshold) or not -1.0 <= threshold <= 1.0:
        raise argparse.ArgumentTypeError("cosine threshold must be finite and between -1 and 1")
    return threshold


def prune_node_ref(typ: str, node_id: str) -> str:
    return f"{typ}:{node_id}"


def prune_is_self_id(node_id: str) -> bool:
    return PRUNE_SELF_ID_RE.search(node_id or "") is not None


def prune_node_from_row(typ: str, row: sqlite3.Row) -> dict[str, Any]:
    meta = jload(row["metadata_json"], {})
    if typ == "fact":
        title = f"{row['subject']} {row['predicate']}".strip()
        body = row["value"] or ""
        kind = "fact"
        confidence = (row["confidence"] or "medium").lower()
        pinned = False
        subject = row["subject"]
    else:
        title = row["title"] or ""
        body = row["body"] or ""
        kind = str(meta.get("kind") or meta.get("type") or "entry").lower()
        confidence = str(meta.get("confidence") or "medium").lower()
        pinned = bool(row["pinned"])
        subject = ""
    return {
        "type": typ,
        "id": row["id"],
        "ref": prune_node_ref(typ, row["id"]),
        "row": row,
        "title": title,
        "body": body,
        "text": node_text_for_relation(row, typ),
        "status": row["status"],
        "kind": kind,
        "confidence": confidence,
        "pinned": pinned,
        "subject": subject,
        "created_at": row["created_at"],
        "body_bytes": len(body.encode("utf-8")),
    }


def prune_active_nodes(con: sqlite3.Connection) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for typ, query in (
        ("fact", "SELECT * FROM facts WHERE status='active' ORDER BY id"),
        ("entry", "SELECT * FROM entries WHERE status='active' ORDER BY id"),
    ):
        for row in con.execute(query):
            if prune_is_self_id(row["id"]):
                continue
            nodes.append(prune_node_from_row(typ, row))
    return sorted(nodes, key=lambda n: n["ref"])


def prune_edge_count(
    con: sqlite3.Connection,
    node: dict[str, Any],
    direction: str,
    *,
    hard_only: bool = False,
    exclude_edge_types: set[str] | None = None,
) -> int:
    if direction == "in":
        sql = "SELECT count(*) AS n FROM edges WHERE target_type=? AND target_id=?"
    else:
        sql = "SELECT count(*) AS n FROM edges WHERE source_type=? AND source_id=?"
    params: tuple[Any, ...] = (node["type"], node["id"])
    if hard_only:
        sql += " AND hard=1"
    if exclude_edge_types:
        ordered = sorted(exclude_edge_types)
        sql += f" AND edge_type NOT IN ({','.join('?' for _ in ordered)})"
        params = params + tuple(ordered)
    return int(con.execute(sql, params).fetchone()["n"])


def prune_safety_lock(
    con: sqlite3.Connection,
    node: dict[str, Any],
    *,
    ignore_incoming_edge_types: set[str] | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    # active_superseded relies on the incoming SUPERSEDES edge as its SIGNAL, so that edge
    # must not also count as a lock reason — other incoming edges still lock for review.
    incoming = prune_edge_count(con, node, "in", exclude_edge_types=ignore_incoming_edge_types)
    if node["pinned"]:
        reasons.append("pinned")
    if incoming > 0:
        reasons.append(f"incoming_edges={incoming}")
    if node["kind"] in PRUNE_LOCK_KINDS:
        reasons.append(f"kind={node['kind']}")
    if node["confidence"] == "high":
        reasons.append("confidence=high")
    if node["status"] != "active":
        reasons.append(f"status={node['status']}")
    return {"locked": bool(reasons), "reasons": reasons}


def prune_pair_safety_lock(left: dict[str, Any], right: dict[str, Any], left_lock: dict[str, Any], right_lock: dict[str, Any]) -> dict[str, Any]:
    reasons = [f"{left['ref']}: {reason}" for reason in left_lock["reasons"]]
    reasons.extend(f"{right['ref']}: {reason}" for reason in right_lock["reasons"])
    return {"locked": bool(reasons), "reasons": reasons}


def prune_record(
    *,
    item_id: str,
    flag: str,
    signals: list[str],
    raw_metrics: dict[str, Any],
    safety_lock: dict[str, Any],
    confidence: str,
    evidence_snippet: str,
) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "layer": "cc_memory",
        "flag": flag,
        "signals": signals,
        "raw_metrics": raw_metrics,
        "safety_lock": safety_lock,
        "confidence": confidence,
        "evidence_snippet": evidence_snippet,
    }


def prune_empty_report_sections() -> dict[str, Any]:
    return {
        "deterministic": {flag: {"locked_review_only": [], "candidates": []} for flag in PRUNE_DETERMINISTIC_FLAGS},
        "advisory": {flag: [] for flag in PRUNE_ADVISORY_FLAGS},
    }


def prune_add_deterministic(sections: dict[str, Any], record: dict[str, Any]) -> None:
    # safety_lock still gates: a high-value node (pinned / kind-lock / high-conf / extra incoming
    # edges) lands in locked_review_only instead of the actionable candidate pool.
    section = "locked_review_only" if record["safety_lock"]["locked"] else "candidates"
    sections["deterministic"][record["flag"]][section].append(record)


def prune_add_advisory(sections: dict[str, Any], record: dict[str, Any]) -> None:
    # advisory flags are FYI-only and never become candidates, so they carry no locked/unlocked split.
    sections["advisory"][record["flag"]].append(record)


def prune_parse_ts(value: str | None) -> _dt.datetime | None:
    try:
        parsed = _dt.datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    # normalize to aware-UTC so age subtraction never mixes naive/aware (legacy rows may lack a tz)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed


def prune_node_age_days(node: dict[str, Any], ref_now: _dt.datetime | None) -> int | None:
    created = prune_parse_ts(node.get("created_at"))
    if created is None or ref_now is None:
        return None
    return max(0, (ref_now - created).days)


def prune_path_is_externalized(path: str) -> bool:
    norm = (path or "").replace("\\", "/").lstrip("./").lower()
    for art in PRUNE_EXTERNALIZED_ARTIFACTS:
        a = art.lower()
        if norm == a or norm.endswith("/" + a):
            return True
    return False


def prune_has_edge_between(con: sqlite3.Connection, left: dict[str, Any], right: dict[str, Any], edge_type: str) -> bool:
    row = con.execute(
        """
        SELECT 1 FROM edges
        WHERE edge_type=?
          AND (
            (source_type=? AND source_id=? AND target_type=? AND target_id=?)
            OR
            (source_type=? AND source_id=? AND target_type=? AND target_id=?)
          )
        LIMIT 1
        """,
        (
            edge_type,
            left["type"], left["id"], right["type"], right["id"],
            right["type"], right["id"], left["type"], left["id"],
        ),
    ).fetchone()
    return row is not None


def prune_vector_from_blob(blob: bytes, dim: int) -> list[float] | None:
    try:
        arr = array.array("f")
        arr.frombytes(blob)
    except (TypeError, ValueError):
        return None
    if len(arr) != dim:
        return None
    return [float(x) for x in arr]


def prune_vector_norm(vector: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vector))


def prune_embedding_rows_by_model(con: sqlite3.Connection, nodes: list[dict[str, Any]]) -> dict[str, list[tuple[dict[str, Any], list[float], float]]]:
    nodes_by_key = {(node["type"], node["id"]): node for node in nodes}
    by_model: dict[str, list[tuple[dict[str, Any], list[float], float]]] = defaultdict(list)
    for row in con.execute(
        """
        SELECT node_type,node_id,model_id,content_hash,dim,dtype,vector_blob
        FROM node_embeddings
        ORDER BY model_id,node_type,node_id
        """
    ):
        node = nodes_by_key.get((row["node_type"], row["node_id"]))
        if node is None or row["dtype"] != "float32":
            continue
        expected_hash = node_content_hash(node["type"], node["id"], node["text"])
        if row["content_hash"] != expected_hash:
            continue
        vector = prune_vector_from_blob(row["vector_blob"], int(row["dim"]))
        if vector is None or not vector or not all(math.isfinite(value) for value in vector):
            continue
        norm_v = prune_vector_norm(vector)
        if not math.isfinite(norm_v) or norm_v == 0.0:
            continue
        by_model[row["model_id"]].append((node, vector, norm_v))
    return by_model


def prune_pair_cosines(con: sqlite3.Connection, nodes: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for model_id, rows in prune_embedding_rows_by_model(con, nodes).items():
        for i, (left, left_vector, left_norm) in enumerate(rows):
            for right, right_vector, right_norm in rows[i + 1 :]:
                if len(left_vector) != len(right_vector):
                    continue
                dot = sum(a * b for a, b in zip(left_vector, right_vector, strict=True))
                cosine = dot / (left_norm * right_norm)
                left_ref, right_ref = sorted([left["ref"], right["ref"]])
                key = (left_ref, right_ref)
                old = best.get(key)
                if old is None or cosine > old["cosine"]:
                    first, second = (left, right) if left["ref"] == left_ref else (right, left)
                    best[key] = {
                        "left": first,
                        "right": second,
                        "cosine": cosine,
                        "model_id": model_id,
                    }
    return best


def prune_duplicate_denial_reasons(con: sqlite3.Connection, left: dict[str, Any], right: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if left["kind"] != right["kind"]:
        reasons.append(f"kind_mismatch:{left['kind']}!={right['kind']}")
    if left["type"] == "fact" and right["type"] == "fact" and left["subject"] != right["subject"]:
        reasons.append(f"fact_subject_mismatch:{left['subject']}!={right['subject']}")
    if prune_has_edge_between(con, left, right, "CONTRADICTS"):
        reasons.append("contradicts_edge")
    if PRUNE_TITLE_REDLINE_RE.search(left["title"]) or PRUNE_TITLE_REDLINE_RE.search(right["title"]):
        reasons.append("title_redline_word")
    return reasons


def prune_duplicate_records(con: sqlite3.Connection, nodes: list[dict[str, Any]], *, threshold: float) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for pair in prune_pair_cosines(con, nodes).values():
        cosine = float(pair["cosine"])
        if cosine < threshold:
            continue
        left = pair["left"]
        right = pair["right"]
        if prune_has_edge_between(con, left, right, "SUPERSEDES"):
            continue
        if prune_duplicate_denial_reasons(con, left, right):
            continue
        left_lock = prune_safety_lock(con, left)
        right_lock = prune_safety_lock(con, right)
        records.append(
            prune_record(
                item_id=f"{left['ref']} <-> {right['ref']}",
                flag="duplicate",
                signals=[
                    f"semantic cosine {cosine:.4f} >= {threshold:.2f}",
                    f"same kind: {left['kind']}",
                    "no SUPERSEDES edge between pair",
                ],
                raw_metrics={
                    "left": left["ref"],
                    "right": right["ref"],
                    "cosine": round(cosine, 6),
                    "threshold": threshold,
                    "model_id": pair["model_id"],
                },
                safety_lock=prune_pair_safety_lock(left, right, left_lock, right_lock),
                confidence="high" if cosine >= 0.97 else "med",
                evidence_snippet=f"{left['ref']}: {short(left['body'], 140)} || {right['ref']}: {short(right['body'], 140)}",
            )
        )
    return records


def prune_path_candidate(raw: str) -> str:
    return raw.strip().strip("`'\"()[]{}<>").rstrip(".,;:，。；：")


def prune_missing_repo_paths(text: str) -> list[dict[str, Any]]:
    root_resolved = ROOT.resolve()
    info: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for match in PRUNE_PATH_RE.finditer(text or ""):
        raw = prune_path_candidate(match.group(1))
        if not raw or "://" in raw or "*" in raw:
            continue
        path = Path(raw)
        if path.is_absolute():
            candidate = path
        else:
            first = raw.replace("\\", "/").split("/", 1)[0]
            if first not in {
                ".",
                "cc_memory",
                "cc_memory_vnext",
                "data",
                "docs",
                "rules",
                "scripts",
                "specs",
                "src",
                "tests",
            }:
                continue
            candidate = ROOT / raw
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        # boundary: only paths genuinely INSIDE the repo can be dead repo refs — a sibling dir with a
        # shared name prefix or a `..` escape must NOT be treated as a missing in-repo path.
        if not resolved.is_relative_to(root_resolved):
            continue
        key = raw.replace("\\", "/")
        preceding = text[max(0, match.start() - 40):match.start()]
        is_prose = PRUNE_PROSE_EXAMPLE_RE.search(preceding) is not None
        rec = info.get(key)
        if rec is None:
            info[key] = {"exists": candidate.exists(), "all_prose": is_prose}
            order.append(key)
        else:
            # a path counts as a prose example only if EVERY occurrence is illustrative
            rec["all_prose"] = rec["all_prose"] and is_prose
    return [
        {"path": key, "prose_example": info[key]["all_prose"]}
        for key in order
        if not info[key]["exists"]
    ]


def prune_active_superseded_records(con: sqlite3.Connection, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for node in nodes:
        superseders = list(
            con.execute(
                "SELECT source_type,source_id FROM edges WHERE edge_type='SUPERSEDES' AND target_type=? AND target_id=? ORDER BY source_type,source_id",
                (node["type"], node["id"]),
            )
        )
        if not superseders:
            continue
        superseder_refs = [f"{r['source_type']}:{r['source_id']}" for r in superseders]
        records.append(
            prune_record(
                item_id=node["ref"],
                flag="active_superseded",
                signals=["status=active but target of SUPERSEDES from " + ", ".join(superseder_refs[:5])],
                raw_metrics={
                    "incoming_supersedes": len(superseders),
                    "superseders": superseder_refs[:10],
                    "disposition": "review_for_status_archived",
                },
                safety_lock=prune_safety_lock(con, node, ignore_incoming_edge_types={"SUPERSEDES"}),
                confidence="high",
                evidence_snippet=short(node["body"], 240),
            )
        )
    return records


def prune_dead_ref_records(con: sqlite3.Connection, nodes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split missing-path references into a deterministic dead_ref tier and an advisory tier.

    A missing path is a deterministic dead_ref ONLY when all three benign explanations are
    ruled out: (1) the node is a history/done record (dead path = expected provenance),
    (2) the path is a known externalized artifact (absence expected), (3) the path occurs
    only as a prose example. If any holds, the path is downgraded to advisory (zero action).
    """
    deterministic: list[dict[str, Any]] = []
    advisory: list[dict[str, Any]] = []
    for node in nodes:
        missing = prune_missing_repo_paths(node["body"])
        if not missing:
            continue
        is_history = PRUNE_HISTORY_RECORD_RE.search(f"{node['title']}\n{node['body']}") is not None
        live: list[str] = []
        benign: list[tuple[str, str]] = []
        for item in missing:
            path = item["path"]
            if is_history:
                benign.append((path, "history/done record — dead path is expected provenance"))
            elif prune_path_is_externalized(path):
                benign.append((path, "externalized artifact — absence is expected"))
            elif item["prose_example"]:
                benign.append((path, "prose example — illustrative, not load-bearing"))
            else:
                live.append(path)
        if live:
            deterministic.append(
                prune_record(
                    item_id=node["ref"],
                    flag="dead_ref",
                    signals=[
                        "body references missing repo path(s): " + ", ".join(live[:5]),
                        "cleared all 3 benign exclusions (history-record / externalized-artifact / prose-example)",
                    ],
                    raw_metrics={"missing_paths": live[:10], "disposition": "fix_or_remove_reference"},
                    safety_lock=prune_safety_lock(con, node),
                    confidence="high",
                    evidence_snippet=short(node["body"], 240),
                )
            )
        if benign:
            advisory.append(
                prune_record(
                    item_id=node["ref"],
                    flag="dead_ref_uncertain",
                    signals=[f"missing path '{p}' downgraded to advisory: {why}" for p, why in benign[:5]],
                    raw_metrics={"downgraded_paths": [{"path": p, "reason": why} for p, why in benign[:10]]},
                    safety_lock=prune_safety_lock(con, node),
                    confidence="low",
                    evidence_snippet=short(node["body"], 240),
                )
            )
    return deterministic, advisory


def prune_relink_records(
    con: sqlite3.Connection,
    nodes: list[dict[str, Any]],
    *,
    min_age_days: int,
    ref_now: _dt.datetime | None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for node in nodes:
        if prune_edge_count(con, node, "in") != 0 or prune_edge_count(con, node, "out") != 0:
            continue
        age_days = prune_node_age_days(node, ref_now)
        if age_days is None or age_days < min_age_days:
            # fail-closed: an unparseable age cannot prove the orphan is old enough, and a too-fresh
            # orphan may simply not have been linked yet — neither belongs in the actionable pool
            continue
        age_signal = f"age {age_days}d >= {min_age_days}d"
        records.append(
            prune_record(
                item_id=node["ref"],
                flag="relink_candidate",
                signals=["zero incoming edges", "zero outgoing edges", age_signal],
                raw_metrics={
                    "incoming_edges": 0,
                    "outgoing_edges": 0,
                    "age_days": age_days,
                    "min_age_days": min_age_days,
                    "disposition": "add_edges_not_delete",
                },
                safety_lock=prune_safety_lock(con, node),
                confidence="med",
                evidence_snippet=short(node["body"], 240),
            )
        )
    return records


def prune_oversized_records(con: sqlite3.Connection, nodes: list[dict[str, Any]], *, threshold: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for node in nodes:
        if node["type"] != "entry" or node["body_bytes"] < threshold:
            continue
        body = node["body"]
        heading_count = len(re.findall(r"(?m)^#{1,4}\s+", body))
        bullet_count = len(re.findall(r"(?m)^\s*(?:[-*+]|\d+\.)\s+", body))
        paragraph_count = len([part for part in re.split(r"\n\s*\n", body.strip()) if part.strip()])
        mixed_markers = int(heading_count >= 2) + int(bullet_count >= 6) + int(paragraph_count >= 5)
        if mixed_markers == 0:
            continue
        records.append(
            prune_record(
                item_id=node["ref"],
                flag="oversized",
                signals=[
                    f"body_bytes {node['body_bytes']} >= {threshold}",
                    f"mixed-topic markers: headings={heading_count}, bullets={bullet_count}, paragraphs={paragraph_count}",
                ],
                raw_metrics={
                    "body_bytes": node["body_bytes"],
                    "threshold": threshold,
                    "heading_count": heading_count,
                    "bullet_count": bullet_count,
                    "paragraph_count": paragraph_count,
                },
                safety_lock=prune_safety_lock(con, node),
                confidence="med",
                evidence_snippet=short(node["body"], 240),
            )
        )
    return records


def prune_embedding_staleness(con: sqlite3.Connection, nodes: list[dict[str, Any]]) -> dict[str, int]:
    # A node is "fresh" only if it has a current-content-hash embedding (prune_embedding_rows_by_model
    # already drops hash-mismatched rows). Stale/missing embeddings can only cause false-NEGATIVES in
    # the advisory duplicate flag, never false-positives — so this is a soft warning, not a hard gate.
    by_model = prune_embedding_rows_by_model(con, nodes)
    fresh = {(node["type"], node["id"]) for rows in by_model.values() for node, _vec, _norm in rows}
    total = len(nodes)
    stale = sum(1 for node in nodes if (node["type"], node["id"]) not in fresh)
    return {"total": total, "fresh": total - stale, "stale": stale}


def prune_is_real_repo_db(db: Path) -> bool:
    try:
        return db.resolve() == (ROOT / "cc_memory" / "memory.db").resolve()
    except OSError:
        return False


def prune_git(*args: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            text=True,
            capture_output=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)
    return proc.returncode, proc.stdout or ""


def prune_preflight_decision(
    *,
    branch: str | None,
    status_ok: bool,
    dirty: list[str],
    soft_dirty: list[str],
    require_branch: str,
    allow_dirty: bool,
) -> dict[str, Any]:
    # Asymmetric fail-closed: conditions that MANUFACTURE false positives (wrong branch, unreadable
    # git status, or uncommitted truth-source / repo-path changes) hard-block; conditions that only
    # risk false-negatives or are benign noise (a dirty memory.db) are surfaced as soft warnings.
    on_main = branch == require_branch
    clean = bool(branch) and on_main and status_ok and not dirty
    reasons: list[str] = []
    if not branch:
        reasons.append("could not determine git branch; the scanner resolves paths against the physical checkout")
    elif not on_main:
        reasons.append(
            f"on branch '{branch}', not '{require_branch}'; physical checkout diverges from main → systematic false positives"
        )
    if not status_ok:
        reasons.append("could not read `git status`; cannot verify a clean checkout (fail-closed)")
    if dirty:
        reasons.append("uncommitted tracked changes to truth-source / repo paths: " + ", ".join(dirty[:10]))
    warnings: list[str] = []
    if soft_dirty:
        warnings.append(
            "uncommitted changes to memory-store data files (likely read-watermark; scan reflects uncommitted memory state): "
            + ", ".join(soft_dirty[:10])
        )
    return {
        "branch": branch,
        "require_branch": require_branch,
        "on_main": on_main,
        "status_ok": status_ok,
        "dirty": dirty[:20],
        "soft_dirty": soft_dirty[:20],
        "clean": clean,
        "allow_dirty": allow_dirty,
        "blocked": (not clean) and (not allow_dirty),
        "reasons": reasons,
        "warnings": warnings,
    }


def prune_parse_dirty(status_ok: bool, status_text: str) -> tuple[list[str], list[str]]:
    """Split `git status --porcelain` into (hard_dirty, soft_dirty).

    Untracked (??) entries are ignored — they can only cause dead_ref false-negatives. Changes to the
    memory-store data files (PRUNE_DIRTY_SOFT) are soft (read-watermark noise). Everything else tracked
    is hard: a truth-source / repo-path divergence that manufactures false positives.
    """
    hard: list[str] = []
    soft: list[str] = []
    if not status_ok:
        return hard, soft
    for line in status_text.splitlines():
        if not line.strip() or line.startswith("??"):
            continue
        code = line[:2].strip()
        path = line[3:].strip().strip('"')
        if " -> " in path:  # rename: "old -> new"
            path = path.split(" -> ", 1)[1].strip().strip('"')
        norm = path.replace("\\", "/")
        entry = f"{code} {norm}"
        if norm in PRUNE_DIRTY_SOFT:
            soft.append(entry)
        else:
            hard.append(entry)
    return hard, soft


def prune_branch_preflight(*, require_branch: str, allow_dirty: bool) -> dict[str, Any]:
    rc, out = prune_git("rev-parse", "--abbrev-ref", "HEAD")
    branch = out.strip() if rc == 0 and out.strip() else None
    rc2, status = prune_git("status", "--porcelain")
    status_ok = rc2 == 0
    hard_dirty, soft_dirty = prune_parse_dirty(status_ok, status)
    return prune_preflight_decision(
        branch=branch,
        status_ok=status_ok,
        dirty=hard_dirty,
        soft_dirty=soft_dirty,
        require_branch=require_branch,
        allow_dirty=allow_dirty,
    )


def prune_card_semantic_text(text: str) -> str:
    """Card content without the YAML frontmatter block — the semantic body to embed."""
    if text.startswith("---"):
        lines = text.splitlines()
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1 :]).strip()
    return text.strip()


def prune_vnext_card_names(cards_dir: Path) -> tuple[dict[str, str], dict[str, str], list[str]]:
    notes: list[str] = []
    names: dict[str, str] = {}
    texts: dict[str, str] = {}
    if not cards_dir.exists():
        return names, texts, [f"cross_layer_overlap skipped: cards dir not found: {cards_dir}"]
    for path in sorted(cards_dir.glob("*.md")):
        candidates = [path.stem]
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            notes.append(f"cross_layer_overlap skipped unreadable card {path.name}: {exc}")
            continue
        texts[path.name] = prune_card_semantic_text(text)
        for line in text.splitlines()[:120]:
            stripped = line.strip()
            lower = stripped.lower()
            if lower.startswith(("id:", "title:")):
                candidates.append(stripped.split(":", 1)[1].strip().strip("'\""))
            elif stripped.startswith("# "):
                candidates.append(stripped[2:].strip())
        for candidate in candidates:
            key = prune_name_key(candidate)
            if key:
                names.setdefault(key, path.name)
    return names, texts, notes


def prune_embed_card_texts(texts: list[str]) -> list[list[float]]:
    """Embed card bodies live with the current default model (same doc mode as rebuild-embeddings).

    Raises EmbeddingUnavailable on any helper failure so the caller can suppress the affected
    name-matches into notes — an advisory miss is the safe failure direction for this flag.
    """
    payload = call_embed_helper(texts, mode="doc")
    vectors = payload.get("vectors") or []
    if len(vectors) != len(texts):
        raise EmbeddingUnavailable(f"embedding helper returned {len(vectors)} vectors for {len(texts)} card texts")
    try:
        converted = [[float(x) for x in vector] for vector in vectors]
    except (TypeError, ValueError) as exc:
        raise EmbeddingUnavailable(f"embedding helper returned a non-numeric card vector: {exc}") from exc
    if any(not vector or not all(math.isfinite(value) for value in vector) for vector in converted):
        raise EmbeddingUnavailable("embedding helper returned an empty or non-finite card vector")
    return converted


def prune_cross_layer_overlap_records(
    con: sqlite3.Connection,
    nodes: list[dict[str, Any]],
    *,
    cards_dir: Path,
    cosine_threshold: float,
) -> tuple[list[dict[str, Any]], list[str]]:
    # Renamed from archive_candidate: a same-name vnext card does not authorize archiving — it only
    # flags a possible half-finished migration. Neutral name + advisory tier = no implied disposition.
    # Third-meeting final spec: a bare name match may be a collision, so the concern only surfaces
    # when source body <-> card body cosine also clears the gate; unverifiable or below-gate matches
    # are suppressed into notes instead of records.
    card_names, card_texts, notes = prune_vnext_card_names(cards_dir)
    if not card_names:
        return [], notes
    if not math.isfinite(cosine_threshold) or not -1.0 <= cosine_threshold <= 1.0:
        notes.append(f"cross_layer_overlap suppressed: invalid cosine threshold {cosine_threshold!r}")
        return [], notes
    matches: list[tuple[dict[str, Any], str, str, str]] = []
    for node in nodes:
        keys = [(prune_name_key(node["id"]), "id")]
        if node["title"]:
            keys.append((prune_name_key(node["title"]), "title"))
        for key, source in keys:
            if key and key in card_names:
                matches.append((node, key, source, card_names[key]))
                break
    if not matches:
        return [], notes
    model_id = embedding_model_id(embedding_model_name())
    fresh_vectors = {
        (n["type"], n["id"]): (vector, norm)
        for n, vector, norm in prune_embedding_rows_by_model(con, [m[0] for m in matches]).get(model_id, [])
    }
    verifiable: list[tuple[dict[str, Any], str, str, str]] = []
    for node, key, source, card_name in matches:
        if (node["type"], node["id"]) in fresh_vectors:
            verifiable.append((node, key, source, card_name))
        else:
            notes.append(
                f"cross_layer_overlap suppressed (cosine gate unverifiable): {node['ref']} <-> {card_name}: "
                f"no fresh {model_id} embedding — run rebuild-embeddings"
            )
    if not verifiable:
        return [], notes
    card_order = sorted({card_name for _node, _key, _source, card_name in verifiable})
    try:
        card_vectors = prune_embed_card_texts([card_texts.get(name, "") for name in card_order])
    except EmbeddingUnavailable as exc:
        refs = ", ".join(f"{node['ref']}<->{card_name}" for node, _key, _source, card_name in verifiable)
        notes.append(
            f"cross_layer_overlap suppressed (cosine gate unverifiable): embed helper unavailable "
            f"({short(str(exc), 200)}); {len(verifiable)} name-match(es) not surfaced: {refs}"
        )
        return [], notes
    card_vector_by_name = dict(zip(card_order, card_vectors, strict=True))
    records: list[dict[str, Any]] = []
    for node, key, source, card_name in verifiable:
        node_vector, node_norm = fresh_vectors[(node["type"], node["id"])]
        card_vector = card_vector_by_name[card_name]
        card_norm = prune_vector_norm(card_vector)
        if (
            len(card_vector) != len(node_vector)
            or not math.isfinite(node_norm)
            or not math.isfinite(card_norm)
            or node_norm == 0.0
            or card_norm == 0.0
        ):
            notes.append(
                f"cross_layer_overlap suppressed (cosine gate unverifiable): {node['ref']} <-> {card_name}: "
                f"incomparable vectors (node dim {len(node_vector)}, card dim {len(card_vector)})"
            )
            continue
        numerator = sum(a * b for a, b in zip(node_vector, card_vector, strict=True))
        denominator = node_norm * card_norm
        if not math.isfinite(numerator) or not math.isfinite(denominator) or denominator <= 0.0:
            notes.append(
                f"cross_layer_overlap suppressed (cosine gate unverifiable): {node['ref']} <-> {card_name}: "
                "non-finite or non-positive cosine components"
            )
            continue
        cosine = numerator / denominator
        if not math.isfinite(cosine):
            notes.append(
                f"cross_layer_overlap suppressed (cosine gate unverifiable): {node['ref']} <-> {card_name}: "
                "non-finite cosine"
            )
            continue
        if cosine < cosine_threshold:
            notes.append(
                f"cross_layer_overlap suppressed (below cosine gate): {node['ref']} <-> {card_name}: "
                f"body cosine {cosine:.4f} < {cosine_threshold:.2f} — likely same-name collision, not overlap"
            )
            continue
        records.append(
            prune_record(
                item_id=node["ref"],
                flag="cross_layer_overlap_concern",
                signals=[
                    f"active cc_memory node shares a name with vnext card: {card_name}",
                    f"source body <-> card body cosine {cosine:.4f} >= {cosine_threshold:.2f}",
                ],
                raw_metrics={
                    "matched_key": key,
                    "matched_by": source,
                    "matched_card": card_name,
                    "body_cosine": round(cosine, 6),
                    "cosine_threshold": cosine_threshold,
                    "embedding_model": model_id,
                },
                safety_lock=prune_safety_lock(con, node),
                confidence="high" if source == "id" else "med",
                evidence_snippet=short(node["body"], 240),
            )
        )
    return records, notes


def build_prune_scan_report(
    con: sqlite3.Connection,
    *,
    db: Path,
    cards_dir: Path,
    duplicate_threshold: float,
    oversized_bytes: int,
    relink_min_age_days: int,
    overlap_cosine_threshold: float,
    preflight: dict[str, Any],
) -> dict[str, Any]:
    nodes = prune_active_nodes(con)
    ref_now = prune_parse_ts(now())
    sections = prune_empty_report_sections()
    notes = [
        "read-only diagnostic scan; no memory mutations, schema changes, LLM calls, or automatic disposition",
        "two-tier: deterministic flags enter the cleanable-candidate pool; advisory flags are FYI-only and imply no action",
        "candidate pool hard-excludes ids containing prune/pruning",
    ]
    for warning in preflight.get("warnings", []):
        notes.append("preflight (soft): " + warning)
    # --- deterministic tier: native strong signal (graph edge / resolved path) → cleanable candidates ---
    for record in prune_relink_records(con, nodes, min_age_days=relink_min_age_days, ref_now=ref_now):
        prune_add_deterministic(sections, record)
    for record in prune_active_superseded_records(con, nodes):
        prune_add_deterministic(sections, record)
    dead_ref_records, dead_ref_advisory = prune_dead_ref_records(con, nodes)
    for record in dead_ref_records:
        prune_add_deterministic(sections, record)
    # --- advisory tier: weak proxy (cosine / size / name) → FYI only, zero implied action ---
    for record in prune_duplicate_records(con, nodes, threshold=duplicate_threshold):
        prune_add_advisory(sections, record)
    for record in prune_oversized_records(con, nodes, threshold=oversized_bytes):
        prune_add_advisory(sections, record)
    overlap_records, overlap_notes = prune_cross_layer_overlap_records(
        con, nodes, cards_dir=cards_dir, cosine_threshold=overlap_cosine_threshold
    )
    notes.extend(overlap_notes)
    for record in overlap_records:
        prune_add_advisory(sections, record)
    for record in dead_ref_advisory:
        prune_add_advisory(sections, record)
    # soft warning only: stale embeddings cause false-NEGATIVES in the advisory duplicate flag, never false-positives
    embedding_staleness = prune_embedding_staleness(con, nodes)
    if embedding_staleness["stale"]:
        notes.append(
            f"embedding staleness (soft): {embedding_staleness['stale']}/{embedding_staleness['total']} "
            "active nodes lack a current-hash embedding; advisory duplicate detection may under-report — run rebuild-embeddings"
        )
    for flag_sections in sections["deterministic"].values():
        for records in flag_sections.values():
            records.sort(key=lambda r: r["item_id"])
    for records in sections["advisory"].values():
        records.sort(key=lambda r: r["item_id"])
    return {
        "generated_at": now(),
        "schema_version": PRUNE_SCAN_SCHEMA,
        "db": str(db),
        "layer": "cc_memory",
        "preflight": preflight,
        "deterministic": sections["deterministic"],
        "advisory": sections["advisory"],
        "raw_metrics": {
            "active_candidate_nodes": len(nodes),
            "duplicate_cosine_threshold": duplicate_threshold,
            "oversized_bytes_threshold": oversized_bytes,
            "relink_min_age_days": relink_min_age_days,
            "overlap_cosine_threshold": overlap_cosine_threshold,
            "cards_dir": str(cards_dir),
            "embedding_staleness": embedding_staleness,
        },
        "notes": notes,
    }


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


def gpu_embedding_available() -> bool:
    """Cheap check (no model load): is the embedding venv python present?"""
    try:
        return embedding_python().exists()
    except OSError:
        return False


def embeddings_stale_count(con: sqlite3.Connection, model: str | None = None) -> int:
    """Active nodes whose current content has no up-to-date embedding for the model.

    Same staleness test cmd_rebuild_embeddings uses to decide what to re-embed, so a
    non-zero count means `--semantic` would miss those nodes until a rebuild."""
    model_id = embedding_model_id(embedding_model_name(model))
    stale = 0
    for typ, row in all_active_nodes(con):
        text = node_text_for_relation(row, typ)
        content_hash = node_content_hash(typ, row["id"], text)
        existing = con.execute(
            "SELECT content_hash FROM node_embeddings WHERE node_type=? AND node_id=? AND model_id=?",
            (typ, row["id"], model_id),
        ).fetchone()
        if not existing or existing["content_hash"] != content_hash:
            stale += 1
    return stale


def maintenance_report(con: sqlite3.Connection, model: str | None = None) -> dict[str, Any]:
    """Backstop state surfaced at boot / Stop hook: is memory dirty (mutated since the
    last finalize), how did the last finalize go, how many suggestions await review,
    how many embeddings are stale, is the GPU embed env even present."""
    mx = max_mutation_id(con)
    last_fin = int(get_meta(con, "last_finalized_mutation_id", "0") or 0)
    return {
        "dirty": mx > last_fin,
        "max_mutation_id": mx,
        "last_finalized_mutation_id": last_fin,
        "last_finalized_at": get_meta(con, "last_finalized_at", ""),
        "last_finalize_status": get_meta(con, "last_finalize_status", ""),
        "last_finalize_error": get_meta(con, "last_finalize_error", ""),
        "pending_suggestions": len(pending_relation_suggestions(con)),
        "stale_embeddings": embeddings_stale_count(con, model),
        "gpu_available": gpu_embedding_available(),
    }


class _LeaseBusy(RuntimeError):
    """Another finalize holds the drain lease."""


@contextlib.contextmanager
def finalize_lease(path: Path = FINALIZE_LEASE, stale_seconds: int = FINALIZE_LEASE_STALE) -> Any:
    """Single-holder file lease so concurrent hook-triggered finalizes don't stack GPU
    rebuilds / writers.

    Each holder writes a unique PID+nonce token. A lease whose mtime is older than
    stale_seconds is presumed stuck and stolen — so a *live* holder must `renew()`
    (yielded) within that window to keep ownership. Release only deletes the lock if it
    still carries OUR token, so a holder that was stolen-from never deletes the thief's
    fresh lock (which would otherwise let a third writer in)."""
    token = f"{os.getpid()}-{time.time_ns()}".encode()

    def _create() -> None:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            os.write(fd, token)
        finally:
            os.close(fd)

    acquired = False
    try:
        try:
            _create()
        except FileExistsError:
            try:
                age = time.time() - path.stat().st_mtime
            except OSError:
                age = 0.0
            if age <= stale_seconds:
                raise _LeaseBusy()
            with contextlib.suppress(OSError):  # steal only a demonstrably-stale lock
                path.unlink()
            try:
                _create()
            except FileExistsError:
                raise _LeaseBusy()
        acquired = True

        def renew() -> None:
            with contextlib.suppress(OSError):
                os.utime(path, None)

        yield renew
    finally:
        if acquired:
            with contextlib.suppress(OSError):
                if path.read_bytes() == token:  # only delete a lock we still own
                    path.unlink()


def _finalize_rebuild(args: argparse.Namespace) -> str:
    """Run rebuild-embeddings in an ISOLATED subprocess so a GPU/driver crash can't take
    down the finalize itself. Returns a short status, never raises."""
    cmd = [sys.executable, str(Path(__file__).resolve()), "--db", str(args.db), "rebuild-embeddings"]
    if getattr(args, "model", None):
        cmd += ["--model", args.model]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=args.gpu_timeout)
    except subprocess.TimeoutExpired:
        return "timeout"
    except OSError as exc:
        return f"spawn_error:{exc}"
    if proc.returncode == 0:
        return "ok"
    if proc.returncode == 2:
        return "unavailable"  # EmbeddingUnavailable -> GPU venv/model missing
    return f"error_rc{proc.returncode}"


def _checkpoint_wal(db: Path) -> str:
    """Fold the WAL back into memory.db so the on-disk file is self-contained for
    `git add` (memory.db is git-tracked; -wal/-shm are .gitignored).

    wal_checkpoint(TRUNCATE) reports BUSY via its RETURN ROW (busy, log_frames,
    checkpointed_frames) — NOT via an exception — when another connection holds a read
    lock. We pace retries ourselves with a SHORT busy_timeout (not connect()'s 30s, which
    would make each attempt block up to 30s under contention); return 'busy' if it never
    fully drains, so the caller can surface that committed rows may still sit in -wal."""
    try:
        con = sqlite3.connect(str(db))
    except sqlite3.Error:
        return "busy"
    try:
        con.execute("PRAGMA busy_timeout = 200")  # fail fast; the retry loop sets the cadence
        for _ in range(20):
            row = con.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            con.commit()
            if row is not None and int(row[0]) == 0 and int(row[1]) == int(row[2]):
                return "ok"
            time.sleep(0.12)
        return "busy"
    except sqlite3.Error:
        return "busy"
    finally:
        with contextlib.suppress(sqlite3.Error):
            con.close()


def _run_finalize(args: argparse.Namespace, renew: Any = None) -> int:
    status = "ok"
    gpu_status = "skipped"
    rc = 0
    check_lines: list[str] = []
    structural: list[str] = []
    iterations = 0
    final_max = 0
    while iterations < FINALIZE_MAX_DRAIN:
        iterations += 1
        if renew is not None:
            renew()  # keep our lease fresh so a long drain isn't seen as stale & stolen
        con = connect(args.db)
        init_schema(con)
        snapshot = max_mutation_id(con)
        con.close()  # hold no db handle across the GPU subprocess

        if not args.no_gpu:
            gpu_status = _finalize_rebuild(args)

        con = connect(args.db)
        try:
            rc, check_lines = check_db(con, export_path=args.export)  # also writes the export
        except Exception as exc:  # disk full / export perm error / unexpected sqlite -> not a GPU degrade
            status = "finalize_error"
            check_lines = [f"ERROR finalize check/export failed: {exc}"]
            structural = list(check_lines)
            with contextlib.suppress(sqlite3.Error):
                set_meta(con, "last_finalize_status", status)
                set_meta(con, "last_finalize_error", check_lines[0][:500])
                con.commit()
            con.close()
            break
        structural = [ln for ln in check_lines if ln.startswith("ERROR") and REVIEW_MARK not in ln]
        if structural:
            status = "check_fail"
        elif rc != 0:
            status = "pending_review"
        elif not args.no_gpu and gpu_status != "ok":
            status = "degraded:" + gpu_status
        else:
            status = "ok"
        # Advance the finalized-watermark only when the store is healthy; on a structural
        # failure leave it behind so boot/Stop keep flagging 'dirty', not just the status.
        if status != "check_fail":
            set_meta(con, "last_finalized_mutation_id", snapshot)
        set_meta(con, "last_finalized_at", now())
        set_meta(con, "last_finalize_status", status)
        set_meta(con, "last_finalize_error", " ".join(structural)[:500])
        con.commit()
        final_max = max_mutation_id(con)
        con.close()
        if final_max <= snapshot:
            break

    wal = _checkpoint_wal(args.db)
    if wal == "busy":
        # data is safe in -wal, but the on-disk file isn't self-contained yet
        if status in ("ok", "pending_review"):
            status = "wal_busy"
        with contextlib.suppress(sqlite3.Error):
            con = connect(args.db)
            set_meta(con, "last_finalize_status", status)
            set_meta(
                con,
                "last_finalize_error",
                "wal_checkpoint busy: committed rows may still be in cc_memory/memory.db-wal; "
                "rerun finalize when other sessions are idle before committing memory.db",
            )
            con.commit()
            con.close()

    print(f"finalize: iterations={iterations} gpu={gpu_status} wal={wal} mutation_id={final_max} status={status}")
    print("\n".join(check_lines))
    # Exit policy (tuned for asyncRewake on PostToolUse):
    #   structural corruption / finalize crash -> exit 2 (wake the model; must be fixed)
    #   GPU degraded / WAL not folded            -> exit 1 (logged + surfaced at boot)
    #   pending review / ok                       -> exit 0 (Stop hook nags about pending)
    if status in ("check_fail", "finalize_error"):
        return 2
    if status.startswith("degraded") or status == "wal_busy":
        return 1
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    try:
        with finalize_lease() as renew:
            return _run_finalize(args, renew)
    except _LeaseBusy:
        print("finalize: another run holds the lease; skipping (it will pick up the latest mutations)")
        return 0


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
    rep = maintenance_report(con)
    print("## Maintenance (hook backstop)")
    if rep["dirty"]:
        print(
            f"- dirty: YES — memory mutated since last finalize "
            f"(mutations {rep['last_finalized_mutation_id']}→{rep['max_mutation_id']}); "
            f"run `python cc_memory/mem.py finalize`"
        )
    else:
        print("- dirty: no (finalized through latest mutation)")
    last_at = f" @ {rep['last_finalized_at']}" if rep["last_finalized_at"] else ""
    print(f"- last finalize: {rep['last_finalize_status'] or 'never'}{last_at}")
    if rep["last_finalize_error"]:
        print(f"  - last error: {short(rep['last_finalize_error'], 160)}")
    print(f"- pending suggestions to review: {rep['pending_suggestions']}")
    stale_note = f"- stale embeddings: {rep['stale_embeddings']}"
    if not rep["gpu_available"]:
        stale_note += "  [GPU embed python MISSING — `--semantic` recall degraded until restored]"
    elif rep["stale_embeddings"]:
        stale_note += "  (run `python cc_memory/mem.py rebuild-embeddings`)"
    print(stale_note)
    orphans = con.execute(
        "SELECT COUNT(*) AS n FROM ("
        " SELECT id FROM facts WHERE status='active' UNION ALL SELECT id FROM entries WHERE status='active'"
        ") nodes WHERE NOT EXISTS ("
        " SELECT 1 FROM edges e WHERE e.hard=1 AND (e.source_id=nodes.id OR e.target_id=nodes.id))"
    ).fetchone()["n"]
    n_total = counts.get("facts", 0) + counts.get("entries", 0)
    if orphans:
        pct = f" ({orphans * 100 // n_total}%)" if n_total else ""
        print(
            f"- under-linked: {orphans}/{n_total} active nodes have ZERO hard edges{pct} — relation "
            f"review rubber-stamps soft RELATED_TO; add the DEPENDS_ON/SUPERSEDES you know "
            f"(impact propagation skips orphans). see cc-memory-crud-gotchas."
        )
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
    print("## Semantic + rerank retrieval (optional GPU layer, P1/P2)")
    print("- `--semantic` (on suggest/add-entry/set-fact) adds dense recall: finds concept/synonym matches that lexical misses. RELIABLE — this is the main win; prefer it.")
    print("- `--rerank` adds a cross-encoder that prunes false-positives. STRICT/conservative: great when the draft is specific & content-rich, but it over-prunes SHORT/ABSTRACT queries (can return nothing). Add it only for specific drafts, not vague one-line queries.")
    print("- run `python cc_memory/mem.py rebuild-embeddings` after adding nodes so `--semantic` can retrieve them (incremental by content hash).")
    print("- candidates still pass the review gate; loads GPU models (slower) and silently falls back to lexical-only if the GPU venv is absent.")
    print("")
    if rc:
        print("## Check failures")
        print("\n".join(check_lines))
    touch_watermark(con, sid)
    con.commit()
    return rc


def cmd_search(args: argparse.Namespace) -> int:
    con = connect(args.db)
    cross_session_preamble(con, session_id_for(args))
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
    cross_session_preamble(con, session_id_for(args))
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
    cross_session_preamble(con, session_id_for(args))
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
    # NOTE: no cross_session_preamble here — suggest emits machine-readable JSON on stdout,
    # and a text preamble would corrupt JSON consumers. The cross-session notice rides only
    # on the human-readable query commands (search / read / impact).
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


def cmd_prune_scan(args: argparse.Namespace) -> int:
    real_db = prune_is_real_repo_db(args.db)
    if real_db:
        preflight = prune_branch_preflight(require_branch=args.require_branch, allow_dirty=args.allow_dirty)
        if preflight["blocked"]:
            sys.stderr.write("prune scan refused (dirty-branch self-check, fail-closed):\n")
            for reason in preflight["reasons"]:
                sys.stderr.write(f"  - {reason}\n")
            sys.stderr.write("  fix: run on a clean `main`, or pass --allow-dirty to override (report may be polluted).\n")
            return 2
    else:
        preflight = {
            "enforced": False,
            "reason": "non-default --db; dirty-branch gate applies only to the canonical repo memory.db",
        }
    con = connect_readonly(args.db)
    try:
        report = build_prune_scan_report(
            con,
            db=args.db,
            cards_dir=args.cards_dir,
            duplicate_threshold=args.duplicate_cosine_threshold,
            oversized_bytes=args.oversized_bytes,
            relink_min_age_days=args.relink_min_age_days,
            overlap_cosine_threshold=args.overlap_cosine_threshold,
            preflight=preflight,
        )
    finally:
        con.close()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"prune scan report: {args.out}")
    if real_db:
        print(f"preflight: branch={preflight['branch']} clean={preflight['clean']} allow_dirty={preflight['allow_dirty']}")
    print("deterministic (cleanable candidates, safety_lock-gated):")
    for flag in PRUNE_DETERMINISTIC_FLAGS:
        grouped = report["deterministic"][flag]
        print(f"- {flag}: locked_review_only={len(grouped['locked_review_only'])} candidates={len(grouped['candidates'])}")
    print("advisory (FYI only, no action implied):")
    for flag in PRUNE_ADVISORY_FLAGS:
        print(f"- {flag}: {len(report['advisory'][flag])}")
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


def cmd_supersede(args: argparse.Namespace) -> int:
    """Mark <old> superseded by <new>: archive the old node (status='superseded' -> hidden
    from active-filtered views like boot/semantic/relation-discovery, but still found by
    search/read) and record a hard SUPERSEDES edge new->old. One command for the genuine
    "a belief changed, replace it" case — incl. entries, which `add-entry` cannot archive
    (no --status). For a mere correction/refinement of the SAME fact, use `--force` instead."""
    con = connect(args.db)
    new = resolve_node(con, args.new)
    old = resolve_node(con, args.old)
    if not new:
        raise SystemExit(f"unknown new node: {args.new}")
    if not old:
        raise SystemExit(f"unknown old node: {args.old}")
    if new == old:
        raise SystemExit("new and old must differ")
    new_type, new_id = new
    old_type, old_id = old
    table = "facts" if old_type == "fact" else "entries"
    con.execute(f"UPDATE {table} SET status='superseded', updated_at=? WHERE id=?", (now(), old_id))
    add_edge_row(con, new_type, new_id, "SUPERSEDES", old_type, old_id, reason=args.reason or "supersede")
    record_mutation(con, session_id_for(args), "supersede", old_type, old_id)
    con.commit()
    print(f"superseded: {new_type}:{new_id} --SUPERSEDES--> {old_type}:{old_id} (old status=superseded; still searchable, hidden from boot/semantic)")
    return 0


def archive_db_path(main_db: Path) -> Path:
    return Path(main_db).with_name("memory_archive.db")


def _ensure_archive_schema(main_con: sqlite3.Connection, arc_con: sqlite3.Connection) -> None:
    """Create facts/entries/edges in the archive db by copying the live schema DDL
    (idempotent, no seed). The archive connection runs with foreign_keys OFF so a moved
    node's source_event_id (whose event stays in the main db) does not trip an FK check."""
    for table in ("facts", "entries", "edges"):
        row = main_con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        if row and row["sql"]:
            arc_con.execute(row["sql"].replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1))
    arc_con.commit()


def _node_edge_rows(con: sqlite3.Connection, typ: str, nid: str) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM edges WHERE (source_type=? AND source_id=?) OR (target_type=? AND target_id=?)",
        (typ, nid, typ, nid),
    ).fetchall()


def _insert_row(con: sqlite3.Connection, table: str, row: sqlite3.Row, *, skip: tuple[str, ...] = (), conflict: str = "OR REPLACE") -> None:
    cols = [c for c in row.keys() if c not in skip]
    con.execute(
        f"INSERT {conflict} INTO {table}({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
        tuple(row[c] for c in cols),
    )


def cmd_archive(args: argparse.Namespace) -> int:
    """HARD-archive: MOVE a node (+ its edges) out of memory.db into a side
    memory_archive.db, then delete it from the main db. Unlike soft archive
    (status='archived', which stays searchable and clutters the main db), the node is
    gone from every main-db query incl. `search` — but preserved and restorable via
    `unarchive`. Copy-then-delete order => no data loss if interrupted. The embedding is
    dropped (regenerable on restore via finalize)."""
    con = connect(args.db)
    node = resolve_node(con, args.id)
    if not node:
        raise SystemExit(f"unknown node: {args.id}")
    typ, nid = node
    table = "facts" if typ == "fact" else "entries"
    node_row = con.execute(f"SELECT * FROM {table} WHERE id=?", (nid,)).fetchone()
    edges = _node_edge_rows(con, typ, nid)

    arc_path = archive_db_path(args.db)
    arc = sqlite3.connect(arc_path)
    arc.row_factory = sqlite3.Row
    arc.execute("PRAGMA foreign_keys = OFF")
    try:
        _ensure_archive_schema(con, arc)
        _insert_row(arc, table, node_row)  # copy node first
        for e in edges:
            _insert_row(arc, "edges", e, skip=("id",), conflict="OR IGNORE")
        arc.commit()
    finally:
        arc.close()

    con.execute(f"DELETE FROM {table} WHERE id=?", (nid,))
    con.execute("DELETE FROM edges WHERE (source_type=? AND source_id=?) OR (target_type=? AND target_id=?)", (typ, nid, typ, nid))
    con.execute("DELETE FROM node_embeddings WHERE node_type=? AND node_id=?", (typ, nid))
    con.execute("DELETE FROM relation_suggestions WHERE (source_type=? AND source_id=?) OR (target_type=? AND target_id=?)", (typ, nid, typ, nid))
    record_mutation(con, session_id_for(args), "hard-archive", typ, nid)
    con.commit()
    print(f"hard-archived: {typ}:{nid} -> {arc_path.name} ({len(edges)} edge(s)); gone from main db (incl. search). restore: `unarchive {nid}`")
    return 0


def cmd_unarchive(args: argparse.Namespace) -> int:
    """Restore a hard-archived node (+ its edges) from memory_archive.db back into
    memory.db. Run `finalize` afterwards to re-embed it for --semantic."""
    con = connect(args.db)
    arc_path = archive_db_path(args.db)
    if not arc_path.exists():
        raise SystemExit(f"no archive db at {arc_path}")
    arc = sqlite3.connect(arc_path)
    arc.row_factory = sqlite3.Row
    arc.execute("PRAGMA foreign_keys = OFF")
    nid = norm(args.id)
    found: tuple[str, str, sqlite3.Row] | None = None
    for typ, table in (("fact", "facts"), ("entry", "entries")):
        row = arc.execute(f"SELECT * FROM {table} WHERE id=?", (nid,)).fetchone()
        if row:
            found = (typ, table, row)
            break
    if not found:
        arc.close()
        raise SystemExit(f"not in archive: {args.id}")
    typ, table, node_row = found
    edges = _node_edge_rows(arc, typ, nid)
    _insert_row(con, table, node_row)  # restore into main (FK ON; its event stayed in main)
    for e in edges:
        _insert_row(con, "edges", e, skip=("id",), conflict="OR IGNORE")
    record_mutation(con, session_id_for(args), "unarchive", typ, nid)
    con.commit()
    arc.execute(f"DELETE FROM {table} WHERE id=?", (nid,))
    arc.execute("DELETE FROM edges WHERE (source_type=? AND source_id=?) OR (target_type=? AND target_id=?)", (typ, nid, typ, nid))
    arc.commit()
    arc.close()
    print(f"unarchived: {typ}:{nid} restored to main db ({len(edges)} edge(s)). run `finalize` to re-embed for --semantic.")
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

    sp = sub.add_parser("prune", help="read-only cc_memory maintenance diagnostics")
    prune_sub = sp.add_subparsers(dest="prune_cmd", required=True)
    scan = prune_sub.add_parser("scan", help="scan cc_memory and write a grouped read-only pruning report")
    scan.add_argument("--out", type=Path, default=PRUNE_DEFAULT_REPORT)
    scan.add_argument("--cards-dir", type=Path, default=ROOT / "cc_memory_vnext" / "cards")
    scan.add_argument("--duplicate-cosine-threshold", type=prune_cosine_threshold, default=PRUNE_DUPLICATE_COSINE)
    scan.add_argument("--oversized-bytes", type=int, default=PRUNE_OVERSIZED_BYTES)
    scan.add_argument("--relink-min-age-days", type=int, default=PRUNE_RELINK_MIN_AGE_DAYS)
    scan.add_argument("--overlap-cosine-threshold", type=prune_cosine_threshold, default=PRUNE_OVERLAP_COSINE)
    scan.add_argument("--require-branch", default=PRUNE_MAIN_BRANCH)
    scan.add_argument("--allow-dirty", action="store_true", help="override the dirty-branch fail-closed gate (report may be polluted)")
    scan.set_defaults(func=cmd_prune_scan)

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

    sp = sub.add_parser("supersede", help="archive <old> (status=superseded) + record new --SUPERSEDES--> old; for genuine belief replacement, not in-place correction")
    sp.add_argument("new", help="the already-created replacement node id")
    sp.add_argument("old", help="the node id being superseded (gets archived)")
    sp.add_argument("--reason")
    sp.set_defaults(func=cmd_supersede)

    sp = sub.add_parser("archive", help="HARD-archive: move a node (+edges) out of memory.db into memory_archive.db (gone from main incl. search; restorable with unarchive)")
    sp.add_argument("id")
    sp.set_defaults(func=cmd_archive)

    sp = sub.add_parser("unarchive", help="restore a hard-archived node from memory_archive.db back into memory.db (then run finalize)")
    sp.add_argument("id")
    sp.set_defaults(func=cmd_unarchive)

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

    sp = sub.add_parser(
        "finalize",
        help="single收口本体: (GPU rebuild) -> check -> export -> record state, under a drain lease",
    )
    sp.add_argument("--no-gpu", action="store_true", help="skip GPU embedding rebuild (pre-commit / CI gate use)")
    sp.add_argument("--model", default=None, help=f"embedding model (default: {DEFAULT_EMBED_MODEL})")
    sp.add_argument("--gpu-timeout", type=int, default=700, help="seconds before the GPU rebuild subprocess is killed")
    sp.set_defaults(func=cmd_finalize)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
