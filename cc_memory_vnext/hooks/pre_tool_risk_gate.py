#!/usr/bin/env python
"""PreToolUse 高危窄门 (MVP-1a + observable-commitment-gate 的 proof 检查)。

Design 依据:
- recall-trigger-discussion-20260628.md 命门: PreToolUse 执行前只能 deny/ask,
  「动作前温和召回」不存在 -> 本 hook 只做窄阻断,绝不做泛化召回、绝不碰 bm25。
- observable-commitment-gate-20260628.md: pre_tool_use = deny_or_ask_without_proof。
  ask 类动作若近期有覆盖相应 domain 的 ZMEM_PROOF(zmem search 落的
  logs/proofs.jsonl)则放行 —— 闸只查 proof 在不在,零 LLM。

解析策略(2026-07-03 对抗审查后重写): 不再用「git 后紧跟子命令」正则 + 全局剥
引号(会被 `git -C x add -A`、`git add "."` 绕过,也会把 echo 字符串误伤)。改为
quote-aware 分段 tokenize,跳过 git 全局选项后定位真实子命令,再按 token 判定。

决策:
- deny : git add -A|--all|-u|.  /  git commit -a|-am|--all
         (共享 .git/index 铁律,卡 concurrent-session-shared-index-hazard;
          deny 是绝对的,不被 proof/账本/文本标记压掉)
- ask  : git push --force / rm -rf / Remove-Item -Recurse -Force / 无 pathspec
         plain commit(worktree 私有 index 除外) / 冻结工件 Write|Edit
         其中前四类可被 ZMEM_PROOF 解锁;冻结工件永远 ask。
- ALLOW_RISK_GATE 标记只把 ask 降为 allow(人工明示),对 deny 无效。

Fail-open: 检测/解析失败一律放行,绝不挡正常工具流。
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROOF_LOG = ROOT / "logs" / "proofs.jsonl"
DECISION_LOG = ROOT / "logs" / "risk_gate_decisions.jsonl"
PROOF_TTL_SIGNED = 45 * 60
PROOF_TTL_UNSIGNED = 10 * 60  # 未署名 proof 只当「同一意图链」的短窗近似
PROOF_TAIL_BYTES = 64 * 1024

# 目录限定的冻结工件(后缀边界匹配,不再按裸 basename 误伤 fixtures)
FROZEN_REL_PATHS = (
    "rules/canonical_rules.json",
    "rules/preprocess_plan.json",
    "data/preprocessed/mandatory_exact_instances.json",
)
# 仓库根级冻结工件: basename 命中还须同目录有 PROJECT_LOCK.md(根标记,worktree 也成立)
FROZEN_ROOT_BASENAMES = {"generic_io_requirements.json", "candidate_placements.json"}

GIT_DOMAINS = {"git-concurrency", "workspace-hygiene", "cc-memory-git"}
FS_DOMAINS = {"workspace-hygiene"}

GIT_GLOBAL_OPTS_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}
COMMIT_OPTS_WITH_ARG = {"-m", "-F", "-t", "-c", "-C", "--author", "--date", "--fixup", "--squash"}
COMMAND_WRAPPERS = {"sudo", "command", "time", "nohup", "&"}


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


def ask_or_unlock(msg: str, shape: str, session: str, domains: set[str], hatch: bool) -> None:
    """ask 类出口: ALLOW_RISK_GATE 人工标记或 ZMEM_PROOF 覆盖可放行;deny 永不走这里。"""
    if hatch:
        emit_allow("escape-hatch:" + shape)
    if recent_proof_covers(domains, session):
        emit_allow("proof-covered:" + shape)
    emit_decision("ask", msg, shape, session)


def recent_proof_covers(domains: set[str], session: str) -> bool:
    """署名且同 session 的 proof 45min 内有效;未署名 proof 只给 10min 短窗。

    身份不明(当前 payload 无 session_id)时不认任何署名 proof —— 否则任意历史
    会话的 proof 都能解锁本会话(2026-07-03 审查 blocker)。
    """
    try:
        if not PROOF_LOG.exists():
            return False
        with PROOF_LOG.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - PROOF_TAIL_BYTES))
            tail = handle.read().decode("utf-8", errors="replace")
        now = datetime.datetime.now()
        for line in tail.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            proof_session = str(record.get("session") or "")
            if proof_session:
                if not session or proof_session != session:
                    continue
                ttl = PROOF_TTL_SIGNED
            else:
                ttl = PROOF_TTL_UNSIGNED
            try:
                ts = datetime.datetime.fromisoformat(str(record.get("ts")))
            except Exception:
                continue
            if (now - ts).total_seconds() > ttl:
                continue
            if domains & {str(d) for d in record.get("domains") or []}:
                return True
    except Exception:
        return False
    return False


def tokenize_segments(cmd: str) -> list[list[str]]:
    """quote-aware 最小 tokenizer: 按未引号的 ;|&、换行分段,段内按空白分 token。

    引号内容保留在 token 里(去掉引号字符本身),所以 `git add "."` 的 pathspec
    是 token ".",而 `echo "git add -A"` 的整句是单个 token、不会被当命令。
    """
    segments: list[list[str]] = []
    tokens: list[str] = []
    current: list[str] = []
    quote = ""
    has_content = False

    def flush_token() -> None:
        nonlocal current, has_content
        if has_content:
            tokens.append("".join(current))
        current = []
        has_content = False

    def flush_segment() -> None:
        nonlocal tokens
        flush_token()
        if tokens:
            segments.append(tokens)
        tokens = []

    for ch in cmd:
        if quote:
            if ch == quote:
                quote = ""
            else:
                current.append(ch)
                has_content = True
            continue
        if ch in "'\"":
            quote = ch
            has_content = True  # 空引号也算内容,如 ""
            continue
        if ch in ";|&\n":
            flush_segment()
            continue
        if ch.isspace():
            flush_token()
            continue
        current.append(ch)
        has_content = True
    flush_segment()
    return segments


def leading_command_index(tokens: list[str], name: str) -> int:
    """name 只有作为段首命令(允许 sudo/env 赋值等前缀)才算数,防 echo 字面量误伤。"""
    i = 0
    while i < len(tokens):
        token = tokens[i]
        low = token.lower()
        if low in COMMAND_WRAPPERS or ("=" in token and not token.startswith("-") and i == 0):
            i += 1
            continue
        base = low.replace("\\", "/").rsplit("/", 1)[-1]
        if base in (name, name + ".exe"):
            return i
        return -1
    return -1


def git_subcommand(tokens: list[str], git_index: int) -> tuple[str, list[str]]:
    """跳过 git 全局选项(-C <dir>/-c <kv>/--git-dir=... 等)定位真实子命令。"""
    j = git_index + 1
    while j < len(tokens):
        token = tokens[j]
        if token in GIT_GLOBAL_OPTS_WITH_ARG:
            j += 2
            continue
        if any(token.startswith(opt + "=") for opt in GIT_GLOBAL_OPTS_WITH_ARG):
            j += 1
            continue
        if token.startswith("-"):
            j += 1
            continue
        return token.lower(), tokens[j + 1 :]
    return "", []


def commit_has_pathspec(rest: list[str]) -> bool:
    i = 0
    while i < len(rest):
        token = rest[i]
        if token == "--":
            return i < len(rest) - 1
        if token in COMMIT_OPTS_WITH_ARG:
            i += 2
            continue
        if any(token.startswith(opt + "=") for opt in COMMIT_OPTS_WITH_ARG):
            i += 1
            continue
        if token.startswith("-"):
            i += 1
            continue
        return True  # 位置参数 = pathspec
    return False


def combined_flag_has(token: str, letters: str) -> bool:
    return token.startswith("-") and not token.startswith("--") and any(c in token[1:] for c in letters)


def check_shell(cmd: str, session: str, cwd: str) -> None:
    hatch = "ALLOW_RISK_GATE" in cmd
    in_worktree = "/.claude/worktrees/" in cwd.replace("\\", "/").lower()

    for tokens in tokenize_segments(cmd):
        gi = leading_command_index(tokens, "git")
        if gi >= 0:
            sub, rest = git_subcommand(tokens, gi)
            if sub == "add":
                if any(t in ("-A", "--all", "-u", "--update", ".", "./") for t in rest):
                    emit_decision(
                        "deny",
                        "⚠️ 本 repo 多会话共享 .git/index,git add -A/./-u 会把别的会话的改动扫进来"
                        "(卡 concurrent-session-shared-index-hazard)。改用精确 pathspec 逐个 add"
                        " 自己负责的文件。",
                        "git-add-broad",
                        session,
                    )
            elif sub == "commit":
                if any(t == "--all" or combined_flag_has(t, "a") for t in rest if t != "--"):
                    emit_decision(
                        "deny",
                        "⚠️ git commit -a/-am 绕过 pathspec 纪律,在共享 index 下会连别人 staged 的"
                        "一起提交(卡 concurrent-session-shared-index-hazard)。先 git status --short"
                        " 核对,再用带精确 pathspec 的提交。",
                        "git-commit-all",
                        session,
                    )
                if not commit_has_pathspec(rest) and not in_worktree:
                    ask_or_unlock(
                        "本 repo 共享 .git/index,无 pathspec 的裸 commit 可能把别的会话 staged 的"
                        "文件一起带走(卡 concurrent-session-shared-index-hazard)。先 git status"
                        " --short 确认 staged 只有自己的,或改带 pathspec 提交;查库拿 proof:"
                        " python cc_memory_vnext/zmem.py search \"提交 并发会话 暂存\"",
                        "git-commit-no-pathspec",
                        session,
                        GIT_DOMAINS,
                        hatch,
                    )
            elif sub == "push":
                if any(t in ("--force", "-f", "--force-with-lease") for t in rest):
                    ask_or_unlock(
                        "高危: git push --force 不可逆,且本 repo 有并发会话在推同一主线。先查库:"
                        " python cc_memory_vnext/zmem.py search \"push 冲突 并发会话\" 拿 ZMEM_PROOF"
                        "(署名 45min/未署名 10min 内有效),或人工确认放行。",
                        "git-push-force",
                        session,
                        GIT_DOMAINS,
                        hatch,
                    )
            continue

        ri = leading_command_index(tokens, "rm")
        if ri >= 0:
            flags = [t for t in tokens[ri + 1 :] if t.startswith("-")]
            recursive = any(t == "--recursive" or combined_flag_has(t, "rR") for t in flags)
            force = any(t == "--force" or combined_flag_has(t, "f") for t in flags)
            if recursive and force:
                ask_or_unlock(
                    "高危: rm 递归强删。确认目标不含别的会话的工作产物/检查点;查库:"
                    " python cc_memory_vnext/zmem.py search \"并发会话 工作区 删除\" 拿 ZMEM_PROOF,"
                    "或人工确认。",
                    "rm-rf",
                    session,
                    FS_DOMAINS,
                    hatch,
                )

        low_tokens = [t.lower() for t in tokens]
        if any(t == "remove-item" for t in low_tokens):
            has_recurse = any(t.startswith("-recurse") for t in low_tokens)
            has_force = any(t.startswith("-force") for t in low_tokens)
            if has_recurse and has_force:
                ask_or_unlock(
                    "高危: Remove-Item -Recurse -Force 递归强删。确认目标不含别的会话的工作产物/"
                    "检查点;查库: python cc_memory_vnext/zmem.py search \"并发会话 工作区 删除\""
                    " 拿 ZMEM_PROOF,或人工确认。",
                    "remove-item-recurse-force",
                    session,
                    FS_DOMAINS,
                    hatch,
                )

    emit_allow("no-dangerous-shape")


def check_file_write(file_path: str, session: str) -> None:
    normalized = file_path.replace("\\", "/")
    low = normalized.lower()
    frozen_hit = ""
    for rel in FROZEN_REL_PATHS:
        if low == rel or low.endswith("/" + rel):
            frozen_hit = rel
            break
    if not frozen_hit:
        basename = low.rsplit("/", 1)[-1]
        if basename in FROZEN_ROOT_BASENAMES:
            parent = Path(normalized).parent
            try:
                if (parent / "PROJECT_LOCK.md").exists():
                    frozen_hit = basename
            except Exception:
                frozen_hit = ""
    if frozen_hit:
        emit_decision(
            "ask",
            f"⚠️ {frozen_hit} 是被字节级 hash 钉死的冻结工件(PROJECT_LOCK/freeze-ritual)。"
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
        cwd = str(payload.get("cwd") or "")

        if tool_name in {"Bash", "PowerShell"}:
            cmd = str(tool_input.get("command") or "")
            if not cmd:
                emit_allow("emptycmd")
            check_shell(cmd, session, cwd)
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
