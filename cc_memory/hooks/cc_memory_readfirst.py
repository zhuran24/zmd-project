#!/usr/bin/env python3
"""SessionStart hook: inject the cc_memory archive's pinned index.

cc_memory has been a **read-only archive since 2026-08-03** (owner ruling).  New
memory goes to the file-memory layer; this hook's job is no longer "here is how
to use the memory system", it is "here is what the archive still holds, and how
to look something up in it".  The wording follows that: no boot-first
instruction, no impact-before-change instruction, no retrieval-feature pitch.

PROJECT-LOCAL by design (registered in this repo's .claude/settings.local.json, NOT
global): cc_memory is project-scoped, so this hook must only fire for sessions in this
checkout — a global registration would inject this project's memory into unrelated
projects. Path is self-locating from __file__ (cc_memory/hooks/ -> cc_memory/), no
hardcoded absolute path.

READ-ONLY by design. It opens memory.db with mode=ro and never runs `boot` —
because cmd_boot calls touch_watermark()+commit(), and a session-start hook must
not write the db (would race concurrent sessions and consume the cross-session
delta baseline under the hook's session id).

TYPED RENDERING ONLY (2026-08-03, 剪枝 v2 P2 修复批). Each pinned row is rendered
from typed read-only columns — the entry id and its `title` — and nothing else.
It used to render `mem.node_summary()`, whose free-form `index_summary` text was
written under the pre-freeze write protocol and still tells the reader to run
`boot`, use `--semantic`, and mutate the archive with `set-fact` / `add-entry`.
Those sentences arrived in the session as trusted instructions directly under a
header saying the archive is frozen. The database is historical evidence and is
not rewritten to fix this; the rendering layer stops carrying free-form archive
prose into SessionStart instead.

FAIL-OPEN AT THE PROCESS BOUNDARY. Any failure -> exit 0 with no output, so a
missing checkout / locked db / broken helper never disturbs the session. The
boundary is the whole process, not one `try` in the middle of it: every import
and every path computation happens inside `main()`'s guard, and the guard
catches `BaseException` so that a `SystemExit` raised while `mem.py` is executed
also fails open. `sys` is the only module imported outside it, and `sys` cannot
be shadowed by a repository file.

Emits SessionStart additionalContext as JSON (ensure_ascii -> pure ASCII \\uXXXX,
so the console codepage can't mojibake the Chinese).
"""
import sys


def _drop_script_directory_from_import_path() -> None:
    """Stop this hook's own directory from satisfying standard-library imports.

    Python puts the script's directory at the front of ``sys.path`` for a plain
    ``python cc_memory/hooks/cc_memory_readfirst.py`` invocation, so a stray
    ``cc_memory/hooks/json.py`` would be imported instead of the standard
    library's.  The registration is owner configuration and cannot be changed
    from here to pass ``-I`` / ``-P``, so the entry is dropped in-process
    before any other import runs.  Only ``sys`` and ``__file__`` are consulted,
    and neither can be shadowed.

    This is defence in depth, not the fix: the fix is that everything below
    runs inside ``main()``'s fail-open guard.
    """
    cut = max(__file__.rfind("/"), __file__.rfind("\\"))
    if cut < 0:
        return
    here = __file__[:cut]
    if here:
        sys.path[:] = [entry for entry in sys.path if entry != here]


def _pinned_line(row: object) -> str:
    """One pinned entry, rendered from typed read-only columns only.

    ``title`` is a label the archive gives itself; the free-form summary body
    is deliberately not read here (see the module docstring).
    """
    entry_id = str(row["id"])  # type: ignore[index]
    raw_title = row["title"]  # type: ignore[index]
    title = " ".join(str(raw_title or "").split())
    return f"- `{entry_id}` — {title}" if title else f"- `{entry_id}`"


def _build_payload() -> str | None:
    """The SessionStart JSON line, or ``None`` when there is nothing to say."""
    _drop_script_directory_from_import_path()

    import importlib.util
    import json
    import os
    import pathlib
    import sqlite3

    cc = str(pathlib.Path(__file__).resolve().parent.parent)  # cc_memory/hooks/ -> cc_memory
    mem_path = os.path.join(cc, "mem.py")
    db_path = os.path.join(cc, "memory.db")

    if not (os.path.exists(mem_path) and os.path.exists(db_path)):
        return None

    spec = importlib.util.spec_from_file_location("_ccmem_ro", mem_path)
    if spec is None or spec.loader is None:
        return None
    mem = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mem)
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, title FROM entries WHERE pinned=1 AND status='active' ORDER BY id LIMIT 20"
    ).fetchall()

    if not rows:
        return None

    # cc-memory-meta-index is ALSO injected as a vnext L0 card (full text) at SessionStart;
    # skip it here to kill the only true session-start double-injection (2026-06-28 整合清理).
    vnext_l0_dup = {"cc-memory-meta-index"}
    lines = ["## 档案里被 pin 的条目"]
    for row in rows:
        if row["id"] in vnext_l0_dup:
            continue
        lines.append(_pinned_line(row))
    block = "\n".join(lines).rstrip()

    # Content discoverability (Layer A: the "what content exists" index). The Read-first
    # manuals tell cc HOW to use memory, but not WHAT topics exist -> it won't search for
    # them. Inject a live, auto-counted domain map so any relevant topic triggers a search.
    # Generated from the db each session -> always fresh, never a stale hand-copy. New ids
    # auto-assign by prefix; an unrecognised family folds into "长尾".
    toc = ""
    try:
        ids = [r["id"] for r in con.execute("SELECT id FROM facts WHERE status='active'")]
        ids += [r["id"] for r in con.execute("SELECT id FROM entries WHERE status='active'")]
        domains = {
            "cc-memory系统": ("cc-memory", "cc_memory", "fact-", "memory-", "memory_", "concurrent",
                           "multi-session", "deleted-memory", "commit-session", "clipboard", "insight-digest"),
            "P1.2证明/认证": ("p1-2", "soundness", "close-kernel", "boundary", "setter-barrier", "arch-layering", "followup"),
            "codex/协作工作流": ("codex", "workflow", "agents-team", "symmetric-tasks"),
            "rerank/语义检索": ("rerank", "reranker", "semantic"),
            "owner偏好/裁决": ("owner-", "pref-", "feedback-"),
            "precompact/压缩": ("precompact",),
            "离线判据": ("offline-mode",),
            "下载与外部规范": ("hf-", "google-"),
        }

        def _dom(nid: str) -> str:
            for name, prefixes in domains.items():
                if nid.startswith(prefixes):
                    return name
            return "长尾"  # 未命中命名域的散尾, 折叠成一桶 (2026-06-28: 原 "其他:<prefix>" 单条噪声, 稀释顶部)

        counts: dict[str, int] = {}
        for nid in ids:
            d = _dom(nid)
            counts[d] = counts.get(d, 0) + 1
        if counts:
            tail = counts.pop("长尾", 0)  # 散尾排末尾、压成一行, 不混进按计数排序
            ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
            parts = [f"{k}({n})" for k, n in ordered]
            if tail:
                parts.append(f"长尾({tail})")
            domain_line = " · ".join(parts)
            toc = (
                "\n\n## 档案里还存着这些方面(要查:`python cc_memory/mem.py search <词>`;"
                "只知道 id 不知道在哪层:`python cc_memory/mem.py find <id>`):\n" + domain_line
            )
    except Exception:
        toc = ""

    # Maintenance surfacing, kept for one reason after the freeze: an archive left
    # dirty or half-finalized is a real defect, and nobody runs boot on an archive
    # any more, so this is the only place it would surface. Stays mode=ro — never
    # writes (unlike boot, which would touch_watermark+commit and race sessions).
    maint = ""
    try:
        mx = mem.max_mutation_id(con)
        last_fin = int(mem.get_meta(con, "last_finalized_mutation_id", "0") or 0)
        last_status = mem.get_meta(con, "last_finalize_status", "")
        pending = len(mem.pending_relation_suggestions(con))
        flags = []
        if mx > last_fin:
            flags.append(f"DIRTY:{mx - last_fin} 条改动未 finalize → `python cc_memory/mem.py finalize`")
        if pending:
            flags.append(f"{pending} 条关系建议待审 → `python cc_memory/mem.py relations`")
        if last_status and last_status not in ("ok", "pending_review"):
            flags.append(f"上次 finalize 状态: {last_status}")
        if flags:
            maint = "\n\n## cc_memory 维护提醒(hook 兜底)\n" + "\n".join(f"- {f}" for f in flags)
    except Exception:
        maint = ""

    header = (
        "cc_memory = 只读档案层(2026-08-03 冻结,owner 拍板)。新记忆写文件记忆层;"
        "这里只供考古,全文 `python cc_memory/mem.py read <id> --body`。存着这些:"
    )
    ctx = header + "\n\n" + block + toc + maint
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": ctx,
        }
    })


def main() -> int:
    """The whole hook, inside one fail-open boundary.

    ``BaseException`` is deliberate rather than sloppy: ``SystemExit`` raised
    while the repository-local ``mem.py`` is executed is exactly one of the
    startup failures this hook promises to swallow, and it is not an
    ``Exception``.
    """
    try:
        payload = _build_payload()
        if payload is not None:
            sys.stdout.write(payload + "\n")
            sys.stdout.flush()
    except BaseException:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
