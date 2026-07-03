#!/usr/bin/env python
"""PreToolUse 高危窄门 (MVP-1a + observable-commitment-gate 的 proof 检查)。

Design 依据:
- recall-trigger-discussion-20260628.md 命门: PreToolUse 执行前只能 deny/ask,
  「动作前温和召回」不存在 -> 本 hook 只做窄阻断,绝不做泛化召回、绝不碰 bm25。
- observable-commitment-gate-20260628.md: pre_tool_use = deny_or_ask_without_proof。
  ask 类动作若本会话近期有覆盖相应 domain 的 ZMEM_PROOF(zmem search 落的
  logs/proofs.jsonl)则放行 —— 闸只查 proof 在不在,零 LLM。

形状(只认结构信号: 命令前缀/token/path,先剥引号防 echo 误伤):
- deny : git add -A|--all|.  /  git commit -a|-am|--all   (共享 .git/index 铁律,
         见卡 concurrent-session-shared-index-hazard; deny 永不被账本/proof 压掉)
- ask  : git push --force|-f / rm -rf / Remove-Item -Recurse -Force  (proof 可解)
- ask  : Write/Edit 冻结工件(freeze-ritual 必须是有意识动作; proof 不解锁)

放行口子: 命令含 ALLOW_RISK_GATE。检测失败一律 fail-open。
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROOF_LOG = ROOT / "logs" / "proofs.jsonl"
DECISION_LOG = ROOT / "logs" / "risk_gate_decisions.jsonl"
PROOF_TTL_SECONDS = 45 * 60

FROZEN_BASENAMES = {
    "canonical_rules.json",
    "preprocess_plan.json",
    "mandatory_exact_instances.json",
    "generic_io_requirements.json",
    "candidate_placements.json",
}

GIT_DOMAINS = {"git-concurrency", "workspace-hygiene", "cc-memory-git"}
FS_DOMAINS = {"workspace-hygiene"}


def _dbg(msg: str) -> None:
    try:
        with open(
            os.path.join(tempfile.gettempdir(), "pre_tool_risk_gate.log"), "a", encoding="utf-8"
        ) as f:
            f.write(time.strftime("%H:%M:%S ") + msg + "\n")
    except Exception:
        pass


def _log_decision(record: dict) -> None:
    try:
        DECISION_LOG.parent.mkdir(parents=True, exist_ok=True)
        record["ts"] = datetime.datetime.now().isoformat(timespec="seconds")
        with DECISION_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def emit_allow(reason: str = "allow") -> None:
    _dbg("ALLOW(" + reason + ")")
    sys.exit(0)


def emit_decision(decision: str, msg: str, shape: str, session: str) -> None:
    _dbg(decision.upper() + "(" + shape + ")")
    _log_decision({"decision": decision, "shape": shape, "session": session})
    out = json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": msg,
            }
        },
        ensure_ascii=False,
    )
    sys.stdout.buffer.write(out.encode("utf-8"))
    sys.exit(0)


def recent_proof_covers(domains: set[str], session: str) -> bool:
    """本会话(或未署名)45 分钟内、domain 有交集的 ZMEM_PROOF 即视为已查库。"""
    try:
        if not PROOF_LOG.exists():
            return False
        now = datetime.datetime.now()
        for line in PROOF_LOG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            proof_session = str(record.get("session") or "")
            if proof_session and session and proof_session != session:
                continue
            try:
                ts = datetime.datetime.fromisoformat(str(record.get("ts")))
            except Exception:
                continue
            if (now - ts).total_seconds() > PROOF_TTL_SECONDS:
                continue
            if domains & {str(d) for d in record.get("domains") or []}:
                return True
    except Exception:
        return False
    return False


def flag_token_hit(args_text: str, flags: tuple[str, ...]) -> bool:
    return any(re.search(rf"(?:^|\s){re.escape(flag)}(?=\s|$)", args_text) for flag in flags)


def check_shell(cmd: str, session: str) -> None:
    if "ALLOW_RISK_GATE" in cmd:
        emit_allow("escape-hatch")
    bare = re.sub(r"'[^']*'|\"[^\"]*\"", " ", cmd)
    low = bare.lower()

    add_match = re.search(r"\bgit\s+add\s+([^\n;|&]*)", bare)
    if add_match and flag_token_hit(add_match.group(1), ("-A", "--all", ".", "-u")):
        emit_decision(
            "deny",
            "⚠️ 本 repo 多会话共享 .git/index,git add -A/./-u 会把别的会话的改动扫进来"
            "(卡 concurrent-session-shared-index-hazard)。改用精确 pathspec 逐个 add 自己"
            "负责的文件;确属有意为之则在命令里加注释标记 ALLOW_RISK_GATE。",
            "git-add-broad",
            session,
        )

    commit_match = re.search(r"\bgit\s+commit\s+([^\n;|&]*)", bare)
    if commit_match and flag_token_hit(commit_match.group(1), ("-a", "-am", "--all")):
        emit_decision(
            "deny",
            "⚠️ git commit -a/-am 绕过 pathspec 纪律,在共享 index 下会连别人 staged 的一起"
            "提交(卡 concurrent-session-shared-index-hazard)。先 git status --short 核对,"
            "再用带精确 pathspec 的提交;确需如此加 ALLOW_RISK_GATE。",
            "git-commit-all",
            session,
        )

    push_match = re.search(r"\bgit\s+push\b([^\n;|&]*)", bare)
    if push_match and flag_token_hit(push_match.group(1), ("--force", "-f", "--force-with-lease")):
        if recent_proof_covers(GIT_DOMAINS, session):
            emit_allow("proof-covered:git-push-force")
        emit_decision(
            "ask",
            "高危: git push --force 不可逆,且本 repo 有并发会话在推同一主线。先"
            " `python cc_memory_vnext/zmem.py search \"push 冲突\"` 查库拿 ZMEM_PROOF"
            "(45 分钟内有效)再来,或人工确认放行。",
            "git-push-force",
            session,
        )

    rm_match = re.search(r"(?:^|[\s;|&(])rm\s+((?:-\S+\s+)*)", bare)
    if rm_match:
        rm_flags = rm_match.group(1).split()
        if any(
            token.startswith("-") and "f" in token.lower() and "r" in token.lower()
            for token in rm_flags
        ):
            if recent_proof_covers(FS_DOMAINS, session):
                emit_allow("proof-covered:rm-rf")
            emit_decision(
                "ask",
                "高危: rm -rf 递归强删。确认目标路径不含别的会话的工作产物/检查点;先"
                " zmem search 拿 ZMEM_PROOF 或人工确认。",
                "rm-rf",
                session,
            )

    if re.search(r"\bremove-item\b", low) and "-recurse" in low and "-force" in low:
        if recent_proof_covers(FS_DOMAINS, session):
            emit_allow("proof-covered:remove-item")
        emit_decision(
            "ask",
            "高危: Remove-Item -Recurse -Force 递归强删。确认目标路径不含别的会话的"
            "工作产物/检查点;先 zmem search 拿 ZMEM_PROOF 或人工确认。",
            "remove-item-recurse-force",
            session,
        )

    emit_allow("no-dangerous-shape")


def check_file_write(file_path: str, session: str) -> None:
    normalized = file_path.replace("\\", "/").lower()
    basename = normalized.rsplit("/", 1)[-1]
    if basename in FROZEN_BASENAMES:
        emit_decision(
            "ask",
            f"⚠️ {basename} 是被字节级 hash 钉死的冻结工件(PROJECT_LOCK/freeze-ritual)。"
            "改它必须走完整 freeze-ritual: 更新 pinned hash -> 重生成依赖产物 -> 重跑 gate;"
            "reseal 按 LF 字节算 sha、绝不 write_text 直写。确认要走 ritual 再放行。",
            "frozen-artifact-write",
            session,
        )
    emit_allow("not-frozen")


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        emit_allow("nostdin")
    try:
        tool_name = str(payload.get("tool_name") or "")
        tool_input = payload.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            tool_input = {}
        session = str(payload.get("session_id") or "")

        if tool_name in {"Bash", "PowerShell"}:
            cmd = str(tool_input.get("command") or "")
            if not cmd:
                emit_allow("emptycmd")
            check_shell(cmd, session)
        elif tool_name in {"Write", "Edit"}:
            file_path = str(tool_input.get("file_path") or "")
            if not file_path:
                emit_allow("nopath")
            check_file_write(file_path, session)
    except SystemExit:
        raise
    except Exception:
        emit_allow("error-failopen")
    emit_allow("fallthrough")


if __name__ == "__main__":
    main()
