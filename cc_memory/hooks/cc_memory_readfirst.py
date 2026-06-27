#!/usr/bin/env python3
"""SessionStart hook: inject cc_memory's pinned "Read first" meta-memory tier.

PROJECT-LOCAL by design (registered in this repo's .claude/settings.local.json, NOT
global): cc_memory is project-scoped, so this hook must only fire for sessions in this
checkout — a global registration would inject this project's memory into unrelated
projects. Path is self-locating from __file__ (cc_memory/hooks/ -> cc_memory/), no
hardcoded absolute path.

READ-ONLY by design. It opens memory.db with mode=ro and reuses mem.node_summary
to format the pinned entries EXACTLY like `mem.py boot` does, but WITHOUT running
boot — because cmd_boot calls touch_watermark()+commit(), and a session-start hook
must not write the db (would race concurrent sessions and consume the cross-session
delta baseline under the hook's session id).

Emits SessionStart additionalContext as JSON (ensure_ascii -> pure ASCII \\uXXXX,
so the console codepage can't mojibake the Chinese). Any failure -> exit 0 with no
output, so a missing checkout / locked db never disturbs the session.
"""
import importlib.util
import json
import os
import pathlib
import sqlite3
import sys

CC = str(pathlib.Path(__file__).resolve().parent.parent)  # .../cc_memory/hooks/ -> .../cc_memory
MEM = os.path.join(CC, "mem.py")
DB = os.path.join(CC, "memory.db")


def nothing() -> None:
    sys.exit(0)


def main() -> None:
    if not (os.path.exists(MEM) and os.path.exists(DB)):
        nothing()
    try:
        spec = importlib.util.spec_from_file_location("_ccmem_ro", MEM)
        mem = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mem)
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT id FROM entries WHERE pinned=1 AND status='active' ORDER BY id LIMIT 20"
        ).fetchall()
    except Exception:
        nothing()

    if not rows:
        nothing()

    lines = ["## Read first"]
    for r in rows:
        try:
            summ = mem.node_summary(con, "entry", r["id"])
        except Exception:
            summ = ""
        lines.append(f"- `{r['id']}` — {summ}")
    block = "\n".join(lines).rstrip()

    # Content discoverability (Layer A: the "what content exists" index). The Read-first
    # manuals tell cc HOW to use memory, but not WHAT topics exist -> it won't search for
    # them. Inject a live, auto-counted domain map so any relevant topic triggers a search.
    # Generated from the db each session -> always fresh, never a stale hand-copy. New ids
    # auto-assign by prefix; an unrecognised family surfaces as "其他:<prefix>" (= add a domain).
    toc = ""
    try:
        ids = [r["id"] for r in con.execute("SELECT id FROM facts WHERE status='active'")]
        ids += [r["id"] for r in con.execute("SELECT id FROM entries WHERE status='active'")]
        DOMAINS = {
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
            for name, prefixes in DOMAINS.items():
                if nid.startswith(prefixes):
                    return name
            return "其他:" + nid.split("-")[0]

        counts: dict[str, int] = {}
        for nid in ids:
            d = _dom(nid)
            counts[d] = counts.get(d, 0) + 1
        if counts:
            ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
            domain_line = " · ".join(f"{k}({n})" for k, n in ordered)
            toc = (
                "\n\n## cc_memory 还覆盖这些方面(碰到相关话题,先 "
                "`python cc_memory/mem.py search <词>` 再动手,别只信上下文里现有的):\n" + domain_line
            )
    except Exception:
        toc = ""

    # Read-only maintenance surfacing (hook backstop layer-1, D项): show at session start
    # whether memory is dirty / has pending review / last finalize failed, so the state is
    # visible without manually running boot. Stays mode=ro — never writes (unlike boot,
    # which would touch_watermark+commit and race concurrent sessions).
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
        "以下为 cc_memory 常驻「元记忆」层(pinned,优先级高于项目内容记忆,每会话开始自动注入)。"
        "这是讲「如何正确使用记忆系统本身」的操作手册,改系统级行为前先看;"
        "完整规则用 python cc_memory/mem.py read <id> --body 取全文。"
    )
    ctx = header + "\n\n" + block + toc + maint
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": ctx,
        }
    }))


if __name__ == "__main__":
    main()
