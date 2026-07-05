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

决策(owner 2026-07-03 裁决:高危类不弹人工审核框,改「默认阻止+限时重发确认」):
- 绝对 deny : git add -A|--all|-u|.  /  git commit -a|-am|--all
         (共享 .git/index 铁律,卡 concurrent-session-shared-index-hazard;
          无任何放行通道,不被 proof/账本/文本标记/重发压掉;
          但受下述多会话总开关辖制——单会话时形状本身不生效)
- 默认阻止+重发确认 : git push --force / rm -rf / Remove-Item -Recurse -Force /
         无 pathspec plain commit(worktree 私有 index 除外) / 冻结工件 Write|Edit。
         第一次一律 deny + 抛回自查问题(「你确定这不是别的会话的产物吗?」),
         同一会话在 RESEND_WINDOW_SECONDS(120s)内【原样重发同一命令】= 确认,放行。
         ZMEM_PROOF 覆盖 domain 或 ALLOW_RISK_GATE 标记仍可直接放行(冻结工件除外,
         它只认重发确认——freeze-ritual 必须是有意识动作)。

多会话总开关(owner 2026-07-06 指令):所有并发会话动机的形状(git-add-broad /
git-commit-all / git-commit-no-pathspec / git-push-force / rm-rf /
remove-item-recurse-force)只在检测到多个 CC 会话时生效——单会话没有「共享 index
被别人 staged / 误删他会话产物」的冲突对象,不该拦。检测两探针:
① CLI 进程计数(Win32_Process 数所有 claude.exe,反向排除 Claude Desktop 特征
   路径 AnthropicClaude;.local/bin 与自更新 AppData/.../claude-code/current 两条
   真实 CLI 路径都计入,未知新路径也计入——退化方向=过度保护,不是漏保护);
② 进程数=1 时再看本项目 transcript 目录近 30min 有无其他会话活跃(覆盖「会话刚
   退出、staged 残留还躺在共享 index」的窗口);三态:无法判定(transcript 缺失/
   未落盘/异常)≠ 确认没有,按多会话处理。
探针异常/连自己都数不到 → 一律按多会话处理(此处 fail 方向与 hook 总体 fail-open
相反:检测 bug 不得静默关掉整条防线)。frozen-artifact-write 与并发无关,不受此
开关影响,单会话照拦。

单会话残留 staged 检查(owner 2026-07-06 追加,堵「会话退出>30min 但它 staged 的
东西还躺在共享 index」的口子):单会话判定后,commit 类形状不直接放行,先查这次
提交的真实打包面——空才放行;非空或查不出来 → 走「默认阻止+重发确认」
(git-commit-stale-staged),deny 消息里带清单便于自查。范围(2026-07-06 codex
对抗审查后收紧):裸 commit、宽 pathspec(./通配/magic)、--include/-i 都视同
「会打包既有 staged」→ 查 diff --cached;commit -a 的打包面还含 tracked 工作区
改动与 intent-to-add → 查 status --porcelain(排除 untracked)。只有带精确
pathspec 且无 -a/-i 的提交不查;add 类不查(关口设在 commit);worktree 私有
index 豁免。未知长选项的空格分参按「不是 pathspec」保守处理。已知限制(接受):
短选项附着参数含 a/i(如 -Fmsg-a.txt)会被误抓 -a/-i → 多一道确认,方向安全。

Fail-open: 检测/解析失败一律放行,绝不挡正常工具流(多会话探针除外,见上)。
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROOF_LOG = ROOT / "logs" / "proofs.jsonl"
DECISION_LOG = ROOT / "logs" / "risk_gate_decisions.jsonl"
PENDING_DIR = ROOT / "logs" / "risk_gate_pending"
PROOF_TTL_SIGNED = 45 * 60
PROOF_TTL_UNSIGNED = 10 * 60  # 未署名 proof 只当「同一意图链」的短窗近似
PROOF_TAIL_BYTES = 64 * 1024
RESEND_WINDOW_SECONDS = 120  # 默认阻止后,同会话同命令的重发确认窗口
SESSION_RECENT_WINDOW_SECONDS = 30 * 60  # 刚退出的会话留在共享 index 的 staged 残留仍算风险窗口
# Claude Desktop(Electron)安装目录特征——进程计数用【反向排除】:排除已知 Desktop,
# 其余 claude.exe(含 .local/bin 与自更新的 AppData/Roaming/Claude/claude-code/current
# 两条真实 CLI 路径)一律计为 CC 会话。未知新路径的退化方向 = 多计 → 过度保护,
# 好过正向白名单漏计 → 漏保护(2026-07-06 对抗审查 major finding)。
DESKTOP_PATH_MARKER = "anthropicclaude"

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
# git commit 的空格分参选项(长短都列;漏列的未知长选项由 commit_pathspec_kind 的
# 保守吞参规则兜底——2026-07-06 codex 对抗审查 blocker:--message 的参数曾被误当 pathspec)
COMMIT_OPTS_WITH_ARG = {
    "-m", "-F", "-t", "-c", "-C",
    "--message", "--file", "--template", "--author", "--date", "--cleanup",
    "--fixup", "--squash", "--reuse-message", "--reedit-message",
    "--trailer", "--pathspec-from-file",
}
# 宽 pathspec:覆盖面等效"全部",会把 index/工作区里别人的残留一并打包
BROAD_PATHSPEC_TOKENS = {".", "./", "*", ":", ":/", ":.", "..", "../"}
# git commit 的已知无参长选项:不吞下一个 token(否则 --only own.py 这类安全提交
# 会被误当无 pathspec 错拦)。漏列的未知长选项仍走保守吞参(错拦可重发,不漏拦)。
COMMIT_LONG_OPTS_NO_ARG = {
    "--all", "--amend", "--allow-empty", "--allow-empty-message", "--branch",
    "--dry-run", "--edit", "--include", "--interactive", "--long", "--no-edit",
    "--no-gpg-sign", "--no-post-rewrite", "--no-signoff", "--no-status",
    "--no-verify", "--null", "--only", "--patch", "--porcelain", "--quiet",
    "--reset-author", "--short", "--signoff", "--status", "--verbose", "--verify",
}
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


def _sanitize_session(session: str) -> str:
    cleaned = "".join(c if (c.isalnum() or c in "_-") else "_" for c in session)[:32]
    return cleaned or "nosession"


def _pending_path(session: str) -> Path:
    return PENDING_DIR / (_sanitize_session(session) + ".json")


def pending_token(session: str, shape: str, key_text: str) -> str:
    normalized = " ".join(key_text.split())
    return hashlib.sha256(f"{session}|{shape}|{normalized}".encode("utf-8")).hexdigest()[:16]


def pending_recent(session: str, token: str) -> bool:
    try:
        data = json.loads(_pending_path(session).read_text(encoding="utf-8"))
        ts = datetime.datetime.fromisoformat(str(data.get(token)))
        return (datetime.datetime.now() - ts).total_seconds() <= RESEND_WINDOW_SECONDS
    except Exception:
        return False


def record_pending(session: str, token: str) -> None:
    try:
        path = _pending_path(session)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
        now = datetime.datetime.now()
        pruned: dict[str, str] = {}
        for key, value in data.items():
            try:
                if (now - datetime.datetime.fromisoformat(str(value))).total_seconds() <= RESEND_WINDOW_SECONDS:
                    pruned[key] = str(value)
            except Exception:
                continue
        pruned[token] = now.isoformat(timespec="seconds")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(pruned, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def stop_or_unlock(
    question: str,
    shape: str,
    session: str,
    domains: set[str] | None,
    hatch: bool,
    key_text: str,
    proof_query: str = "",
) -> None:
    """高危(非绝对 deny)出口:默认阻止,发起方自查确认后限时重发放行。

    owner 2026-07-03 裁决:不弹人工审核框——第一次一律 deny + 抛回自查问题,
    同一会话在 RESEND_WINDOW_SECONDS 内【原样重发同一命令】= 确认,放行。
    ALLOW_RISK_GATE 与 ZMEM_PROOF(若给了 domains)仍可直接放行;
    绝对 deny(git add -A 等)不走这里、无任何放行通道。
    """
    if hatch:
        emit_allow("escape-hatch:" + shape)
    if domains and recent_proof_covers(domains, session):
        emit_allow("proof-covered:" + shape)
    token = pending_token(session, shape, key_text)
    if pending_recent(session, token):
        _log_decision({"decision": "resend_confirmed_allow", "shape": shape, "session": session})
        emit_allow("resend-confirmed:" + shape)
    record_pending(session, token)
    hint = (
        f';或先 python cc_memory_vnext/zmem.py search "{proof_query}" 拿 ZMEM_PROOF'
        if proof_query and domains
        else ""
    )
    emit_decision(
        "deny",
        f"⛔ 已默认阻止(高危: {shape})。先自查一遍:{question}"
        f" 确认无误 → {RESEND_WINDOW_SECONDS} 秒内【原样重发同一命令】即放行"
        f"(只认本会话、同一命令){hint}。",
        shape + ":await-resend",
        session,
    )


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


def commit_pathspec_kind(rest: list[str], base_dir: str = "") -> str:
    """"none" = 无 pathspec;"broad" = 有但覆盖面宽(./通配/magic/目录,会打包
    范围内别人的残留);"precise" = 精确到文件的 pathspec。

    未知长选项(--xxx)可能带空格分参:紧随其后的裸 token 无法判定是选项参数还是
    pathspec → 保守当选项参数吞掉(已知无参长选项除外,见 COMMIT_LONG_OPTS_NO_ARG)。
    fail 方向:宁把 pathspec 当没有(多过一道检查,可重发确认),不把选项参数当
    pathspec(跳过检查 = 漏保护;2026-07-06 codex 对抗审查 blocker:git commit
    --message "x" 曾被判为带 pathspec 直接放行)。

    目录 pathspec(按 base_dir 解析后 isdir)判 broad:git commit -- src 会打包
    src 下所有改动、含别人 staged 的(2026-07-06 codex 复核 major)。"""
    specs: list[str] = []
    i = 0
    after_ddash = False
    while i < len(rest):
        token = rest[i]
        if after_ddash:
            specs.append(token)
            i += 1
            continue
        if token == "--":
            after_ddash = True
            i += 1
            continue
        if token in COMMIT_OPTS_WITH_ARG:
            i += 2
            continue
        if any(token.startswith(opt + "=") for opt in COMMIT_OPTS_WITH_ARG):
            i += 1
            continue
        if token.startswith("--"):
            if token in COMMIT_LONG_OPTS_NO_ARG:
                i += 1
            elif i + 1 < len(rest) and not rest[i + 1].startswith("-"):
                i += 2  # 未知长选项 + 疑似参数:保守吞掉
            else:
                i += 1
            continue
        if token.startswith("-") and token != "-":
            i += 1
            continue
        specs.append(token)
        i += 1
    if not specs:
        return "none"
    for spec in specs:
        if spec in BROAD_PATHSPEC_TOKENS or spec.startswith(":(") or any(ch in spec for ch in "*?["):
            return "broad"
        try:
            if base_dir and os.path.isdir(os.path.join(base_dir, spec)):
                return "broad"  # 目录 pathspec:打包目录下全部改动
        except Exception:
            return "broad"  # 路径判定失败按宽处理(保守)
    return "precise"


def combined_flag_has(token: str, letters: str) -> bool:
    return token.startswith("-") and not token.startswith("--") and any(c in token[1:] for c in letters)


_MULTI_SESSION_CACHE: bool | None = None  # 本次 hook 进程内探针结果缓存(True=多会话/不确定)


def _count_cli_processes() -> int:
    """数本机活着的 Claude Code CLI 进程:所有 claude.exe,反向排除 Claude Desktop
    特征路径;拿不到 ExecutablePath 的照计(多计 → 保护开启)。返回 0 = 检测异常
    (至少本会话自己该在列),由调用方按多会话 fail-safe 处理。"""
    ps = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-CimInstance Win32_Process -Filter \"Name='claude.exe'\" | "
            "Select-Object ProcessId,ExecutablePath | ConvertTo-Json -Compress",
        ],
        capture_output=True,
        text=True,
        timeout=8,
    )
    raw = (ps.stdout or "").strip()
    if not raw:
        return 0
    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return 0
    count = 0
    for proc in parsed:
        path = str((proc or {}).get("ExecutablePath") or "").replace("\\", "/").lower()
        if DESKTOP_PATH_MARKER in path:
            continue
        count += 1
    return count


def _recent_other_session_transcript(transcript_path: str) -> bool | None:
    """本项目 transcript 目录里除本会话外是否有近期活跃的会话(顶层 <uuid>.jsonl;
    子代理 transcript 在 <uuid>/ 子目录里,不参与计数)。覆盖「会话刚退出、staged
    残留还躺在共享 index」的窗口。

    三态语义(2026-07-06 对抗审查 major finding:「无法判定」不得折叠成「确认无
    其他会话」):True = 确认有近期其他会话;False = 探测完成、确认没有;
    None = 无法判定(transcript_path 缺失 / 文件未落盘 / 读取异常),调用方必须
    按多会话 fail-safe 处理。"""
    try:
        if not transcript_path:
            return None
        me = Path(transcript_path)
        if not me.is_file():
            return None
        now = time.time()
        for sibling in me.parent.glob("*.jsonl"):
            if sibling.name == me.name:
                continue
            if now - sibling.stat().st_mtime <= SESSION_RECENT_WINDOW_SECONDS:
                return True
    except Exception:
        return None
    return False


def concurrency_shape_active(shape: str, session: str, transcript_path: str) -> bool:
    """并发会话冲突形状的总开关(owner 2026-07-06):确认单会话(唯一 CLI 进程且近
    30min 无其他会话 transcript)→ 形状不生效,记 single_session_skip 后放行;
    多会话或检测不确定 → 形状照常生效。

    fail 方向与 hook 总体的 fail-open 相反:探针异常/连自己都数不到 → 按多会话
    处理,否则检测 bug 会静默关掉整条防线。frozen-artifact-write 与并发无关,
    不走本开关。只在命中危险形状时才被调用(lazy),正常命令零探针开销。
    """
    global _MULTI_SESSION_CACHE
    if _MULTI_SESSION_CACHE is None:
        multi = True
        probe = "failsafe"
        try:
            n = _count_cli_processes()
            if n >= 2:
                probe = f"procs={n}"
            elif n == 1:
                recent = _recent_other_session_transcript(transcript_path)
                if recent is None:
                    probe = "procs=1,transcript-probe-unavailable"  # 无法判定 → 维持多会话
                else:
                    multi = recent
                    probe = "procs=1,recent-transcript" if recent else "procs=1"
            else:
                probe = "procs=0(anomaly)"
        except Exception as exc:
            probe = "probe-error:" + type(exc).__name__
        _MULTI_SESSION_CACHE = multi
        _dbg("SESSION_PROBE " + probe + " -> multi=" + str(multi))
    if not _MULTI_SESSION_CACHE:
        _log_decision({"decision": "single_session_skip", "shape": shape, "session": session})
    return _MULTI_SESSION_CACHE


def git_dash_c_dir(tokens: list[str], git_index: int) -> str:
    """提取 git 全局 -C <dir> 的目标目录(多个 -C 按 git 语义相对叠加)。"" = 无 -C。"""
    j = git_index + 1
    result = ""
    while j < len(tokens):
        token = tokens[j]
        if token == "-C" and j + 1 < len(tokens):
            result = os.path.join(result, tokens[j + 1]) if result else tokens[j + 1]
            j += 2
            continue
        if token in GIT_GLOBAL_OPTS_WITH_ARG:
            j += 2
            continue
        if any(token.startswith(opt + "=") for opt in GIT_GLOBAL_OPTS_WITH_ARG):
            j += 1
            continue
        if token.startswith("-"):
            j += 1
            continue
        break
    return result


def _staged_entries(repo_dir: str, base_cwd: str) -> list[str] | None:
    """列共享 index 里已 staged 的路径(HEAD vs index)。

    三态:[] = 确认购物车是空的;非空 list = 有 staged 内容;None = 无法判定
    (git 失败/超时/不是仓库),调用方按「有残留」保守处理。"""
    try:
        result = subprocess.run(
            ["git", "-C", repo_dir or ".", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            timeout=8,
            cwd=base_cwd or None,
        )
        if result.returncode != 0:
            return None
        return [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    except Exception:
        return None


def _dirty_entries_for_commit_all(repo_dir: str, base_cwd: str) -> list[str] | None:
    """commit -a 的真实打包面 = staged + 已跟踪文件的工作区改动(含 intent-to-add),
    不止 diff --cached(2026-07-06 codex 对抗审查:add -N 与 tracked 工作区改动都
    躲过 cached diff 但会被 -a 提交)。status --porcelain 排除 ??(untracked 不被
    -a 打包)。None = 无法判定,按有残留保守处理。"""
    try:
        result = subprocess.run(
            ["git", "-C", repo_dir or ".", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=8,
            cwd=base_cwd or None,
        )
        if result.returncode != 0:
            return None
        entries = []
        for line in (result.stdout or "").splitlines():
            if not line.strip() or line.startswith("??"):
                continue
            entries.append(line[3:].strip() if len(line) > 3 else line.strip())
        return entries
    except Exception:
        return None


def stale_staged_check(
    tokens: list[str],
    git_index: int,
    session: str,
    cwd: str,
    hatch: bool,
    cmd: str,
    commit_all: bool = False,
) -> None:
    """单会话下 commit 类形状的残留关卡:打包面非空/查不出来 → 重发确认。

    已退出会话留在共享 index / 工作区的内容不会随会话消失;超出 transcript 30min
    窗口后多会话探针看不到它,这里直接看「购物车里有没有东西」兜底(owner
    2026-07-06)。裸/宽 pathspec/--include 提交查 staged;commit -a 查完整打包面
    (staged + tracked 工作区改动)。"""
    repo_dir = git_dash_c_dir(tokens, git_index)
    if commit_all:
        entries = _dirty_entries_for_commit_all(repo_dir, cwd)
        what = "commit -a 会打包的内容(staged + 已跟踪文件的工作区改动)"
    else:
        entries = _staged_entries(repo_dir, cwd)
        what = "staged 内容"
    if entries == []:
        return  # 确认购物车是空的,放行
    if entries is None:
        listing = f"(git 查询失败,无法列出{what}——按有残留保守处理)"
    else:
        shown = ", ".join(entries[:5]) + ("…" if len(entries) > 5 else "")
        listing = f"{what}共 {len(entries)} 个路径: {shown}"
    stop_or_unlock(
        f"当前虽是单会话,但{listing}。这些都是你本回合自己弄的吗?(已退出会话的"
        "残留不会自动消失,会被这次提交一起打包;不是你的就先 git status --short 核对、"
        "git restore --staged 清掉,或改用带精确 pathspec 的提交)",
        "git-commit-stale-staged",
        session,
        GIT_DOMAINS,
        hatch,
        cmd,
        "提交 并发会话 暂存 残留",
    )


def check_shell(cmd: str, session: str, cwd: str, transcript_path: str) -> None:
    hatch = "ALLOW_RISK_GATE" in cmd
    in_worktree = "/.claude/worktrees/" in cwd.replace("\\", "/").lower()

    for tokens in tokenize_segments(cmd):
        gi = leading_command_index(tokens, "git")
        if gi >= 0:
            sub, rest = git_subcommand(tokens, gi)
            if sub == "add":
                if any(t in ("-A", "--all", "-u", "--update", ".", "./") for t in rest) and concurrency_shape_active(
                    "git-add-broad", session, transcript_path
                ):
                    emit_decision(
                        "deny",
                        "⚠️ 本 repo 多会话共享 .git/index,git add -A/./-u 会把别的会话的改动扫进来"
                        "(卡 concurrent-session-shared-index-hazard)。改用精确 pathspec 逐个 add"
                        " 自己负责的文件。",
                        "git-add-broad",
                        session,
                    )
            elif sub == "commit":
                # 旗标只认 -- 之前的 token:-- 之后全是 pathspec,文件名 -a_file.py /
                # -i_file.py 不是选项(2026-07-06 codex 复核 minor)
                ddash_at = rest.index("--") if "--" in rest else len(rest)
                opts = rest[:ddash_at]
                has_all_flag = any(t == "--all" or combined_flag_has(t, "a") for t in opts)
                # --include/-i 语义 = 指定 pathspec 之外还打包既有 staged 内容 → 视同裸提交
                has_include = any(t == "--include" or combined_flag_has(t, "i") for t in opts)
                # 无 pathspec、宽 pathspec(./通配/magic/目录)、--include 都会打包别人的残留
                dcv = git_dash_c_dir(tokens, gi)
                base_dir = os.path.join(cwd, dcv) if (dcv and cwd) else (dcv or cwd)
                effectively_plain = (
                    commit_pathspec_kind(rest, base_dir) != "precise" or has_include
                ) and not in_worktree
                if has_all_flag and concurrency_shape_active("git-commit-all", session, transcript_path):
                    emit_decision(
                        "deny",
                        "⚠️ git commit -a/-am 绕过 pathspec 纪律,在共享 index 下会连别人 staged 的"
                        "一起提交(卡 concurrent-session-shared-index-hazard)。先 git status --short"
                        " 核对,再用带精确 pathspec 的提交。",
                        "git-commit-all",
                        session,
                    )
                if effectively_plain and concurrency_shape_active(
                    "git-commit-no-pathspec", session, transcript_path
                ):
                    stop_or_unlock(
                        "本 repo 共享 .git/index——这次提交不带精确 pathspec(裸提交/宽 pathspec/"
                        "--include 都会打包 index 里既有的 staged 内容),你确定 staged 里只有你"
                        "自己的改动、不会把【别的会话】的文件一起提交吗?(git status --short"
                        " 看一眼,或改带精确 pathspec 提交)",
                        "git-commit-no-pathspec",
                        session,
                        GIT_DOMAINS,
                        hatch,
                        cmd,
                        "提交 并发会话 暂存",
                    )
                # 走到这 = 单会话跳过(多会话在上面已 exit)。commit 类形状仍要过
                # 残留关卡:已退出会话留在共享 index/工作区的内容不随会话消失。
                # -a 优先(其打包面 = staged + tracked 工作区改动,是超集)。
                if has_all_flag and not in_worktree:
                    stale_staged_check(tokens, gi, session, cwd, hatch, cmd, commit_all=True)
                elif effectively_plain:
                    stale_staged_check(tokens, gi, session, cwd, hatch, cmd)
            elif sub == "push":
                if any(t in ("--force", "-f", "--force-with-lease") for t in rest) and concurrency_shape_active(
                    "git-push-force", session, transcript_path
                ):
                    stop_or_unlock(
                        "强推不可逆,且本 repo 有并发会话在推同一主线——你确定不会覆盖掉"
                        "【别的会话/别处】已经推上去的提交吗?",
                        "git-push-force",
                        session,
                        GIT_DOMAINS,
                        hatch,
                        cmd,
                        "push 冲突 并发会话",
                    )
            continue

        ri = leading_command_index(tokens, "rm")
        if ri >= 0:
            flags = [t for t in tokens[ri + 1 :] if t.startswith("-")]
            recursive = any(t == "--recursive" or combined_flag_has(t, "rR") for t in flags)
            force = any(t == "--force" or combined_flag_has(t, "f") for t in flags)
            if recursive and force and concurrency_shape_active("rm-rf", session, transcript_path):
                stop_or_unlock(
                    "递归强删——你确定要删的目标不是【别的会话】的工作产物/检查点吗?"
                    "(本机常有并发会话共用工作区)",
                    "rm-rf",
                    session,
                    FS_DOMAINS,
                    hatch,
                    cmd,
                    "并发会话 工作区 删除",
                )

        low_tokens = [t.lower() for t in tokens]
        if any(t == "remove-item" for t in low_tokens):
            has_recurse = any(t.startswith("-recurse") for t in low_tokens)
            has_force = any(t.startswith("-force") for t in low_tokens)
            if has_recurse and has_force and concurrency_shape_active(
                "remove-item-recurse-force", session, transcript_path
            ):
                stop_or_unlock(
                    "递归强删——你确定要删的目标不是【别的会话】的工作产物/检查点吗?"
                    "(本机常有并发会话共用工作区)",
                    "remove-item-recurse-force",
                    session,
                    FS_DOMAINS,
                    hatch,
                    cmd,
                    "并发会话 工作区 删除",
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
        stop_or_unlock(
            f"{frozen_hit} 是被字节级 hash 钉死的冻结工件——你确定要改它、并走完整"
            " freeze-ritual(更新 pinned hash -> 重生成依赖产物 -> 重跑 gate;LF 字节算 sha、"
            "绝不 write_text 直写)吗?",
            "frozen-artifact-write",
            session,
            None,  # 冻结工件不认 proof,只认重发确认(ritual 必须是有意识动作)
            False,  # 文件写没有命令文本,无 hatch 通道
            file_path,
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
        transcript_path = str(payload.get("transcript_path") or "")

        if tool_name in {"Bash", "PowerShell"}:
            cmd = str(tool_input.get("command") or "")
            if not cmd:
                emit_allow("emptycmd")
            check_shell(cmd, session, cwd, transcript_path)
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
