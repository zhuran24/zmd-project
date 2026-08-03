#!/usr/bin/env python
"""PostToolUse「遇到什么」召回: tool 结果撞上某卡 error_regex -> 注入该卡。

Design: recall-trigger-discussion-20260628.md §4.1 —— PostToolUse 对「拦动作」
太晚,对「撞上后指路下一步」时机正好;卡片的 error_regex 字段专为此设计
(例: git push 撞 non-fast-forward -> 推送冲突卡当场弹)。
observable-commitment-gate: post_tool_use = result_driven_recall。

同会话注入账本(design pro-action 席): 同一张卡本会话只弹一次,账本只活在
建议通道、绝不参与 deny。Fail-safe: 任何异常 exit 0 不注入。

蛇吞尾排除(六月既有不变量,2026-08-03 才落成机制): 读/写本系统自己的治理件
(卡片、回归数据、两套记忆测试、剪枝普查产物)时整条召回跳过 —— 那些文件里
天然就密集写着运行时要匹配的错误文本,一读就自弹,而假命中还会把 seen-once
账本消费掉、把本会话后面真该弹的那一次静默压掉。判据只看 tool_input 里的
路径/命令文本,不看 tool_response(真错误输出里【提到】治理件路径不算),
宁可漏排除、不可误排除。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RESPONSE_TAIL_CHARS = 6000
LEDGER_DIR_NAME = "error_recall_seen"

# 蛇吞尾排除面:本系统自己的治理件。命中即整条召回跳过。
# 都是【带斜杠的目录路径】,普通源码路径撞不上;末尾不带斜杠是为了同时认
# `pytest cc_memory/tests -q` 这种把目录当参数的写法。
GOVERNANCE_MARKERS = (
    "cc_memory_vnext/eval",
    "cc_memory_vnext/cards",
    "cc_memory_vnext/tests",
    "cc_memory/tests",
    ".artifacts/prune_v2_",
)


def governance_target(payload: dict) -> str | None:
    """撞错召回的自我排除闸:这次工具调用碰的是不是本系统自己的治理件?

    返回命中的标记(便于测试/取证),没碰就返回 None。

    只扫 `tool_input` 的顶层字符串值(Bash 的 `command`、Read/Write/Edit 的
    `file_path`、Grep/Glob 的 `path`/`glob` 都在这一层),**不扫 tool_response**
    —— 一条真实报错的输出里完全可能引用到卡片路径,那是真信号,不该被排除。
    嵌套结构(MultiEdit 的 edits 列表等)故意不递归:实现从简,漏排除只是多弹
    一次卡,误排除会静默吃掉真信号。
    """
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    for value in tool_input.values():
        if not isinstance(value, str) or not value:
            continue
        haystack = value.replace("\\", "/")
        for marker in GOVERNANCE_MARKERS:
            if marker in haystack:
                return marker
    return None


def response_text(payload: dict) -> str:
    response = payload.get("tool_response")
    if response is None:
        return ""
    try:
        text = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
    except Exception:
        text = str(response)
    return text[-RESPONSE_TAIL_CHARS:]


def build_error_blob(payload: dict) -> str:
    """The exact text card `error_regex` patterns are matched against.

    Shape, in order, and cards depend on it literally:

        $ <tool_input.command>      <- omitted when the tool had no command
        <tail of tool_response>

    Why the command line (2026-07-03 review): a bare phrase like "no matches"
    is emitted by half the tools in the repo, so cards anchor on the command
    that produced it.

    Why there is **no** cwd line (2026-08-03, reverting the same day's earlier
    change): a `# cwd: <dir>` header was added so one card could tell a
    worktree checkout apart from the main repo. Measured cost: 10 of the 12
    live error-regex cards could then be fired by an ordinary working
    directory string alone, and every such false hit burns that card's
    once-per-session ledger slot — silencing the real hit that comes later.
    The card it served has since dropped error-regex recall entirely (census
    §3.5), so the header buys nothing and is gone. Do not re-add it to give a
    card more context to match on; that is the arms race this batch exits.
    """
    errors_text = response_text(payload)
    if not errors_text:
        return ""
    tool_input = payload.get("tool_input") or {}
    command = str(tool_input.get("command") or "") if isinstance(tool_input, dict) else ""
    return f"$ {command}\n{errors_text}" if command else errors_text


def load_ledger(path: Path) -> set[str]:
    try:
        return set(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_ledger(path: Path, seen: set[str]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sorted(seen), ensure_ascii=False), encoding="utf-8")
    except Exception:
        return


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    try:
        # 蛇吞尾排除必须在建 blob 之前:blob 一旦匹配上就会消费 seen-once
        # 账本,之后再判断就晚了。(放在 try 内,保持"任何异常 exit 0"。)
        if governance_target(payload):
            return 0

        import zmem

        error_blob = build_error_blob(payload)
        if not error_blob:
            return 0
        tool_input = payload.get("tool_input") or {}
        command = str(tool_input.get("command") or "") if isinstance(tool_input, dict) else ""

        index = zmem.load_index(zmem.DEFAULT_INDEX_PATH)

        # Cheap union pre-filter before any packet work.
        any_hit = False
        for card_data in index.get("cards", []):
            meta = zmem.as_dict(card_data.get("meta"))
            triggers = zmem.as_dict(meta.get("triggers"))
            patterns = zmem.normalize_list(triggers.get("error_regex")) + zmem.normalize_list(
                meta.get("error_regex")
            )
            if zmem.error_regex_hit(patterns, [error_blob]):
                any_hit = True
                break
        if not any_hit:
            return 0

        frame = zmem.normalize_frame({"prompt": "", "errors": [error_blob]})
        if command:
            frame = zmem.enrich_frame(frame, index, extra_text=command)
        packet = zmem.compile_context(index, frame, dense_enabled=False)
        hits = [
            item
            for item in packet["layers"].get("L0", [])
            if item.get("reason") == "error_regex_hit"
        ]
        if not hits:
            return 0

        # 白名单清洗 session 再进文件名,防路径穿越(2026-07-03 审查)。
        session_raw = str(payload.get("session_id") or "nosession")
        session = re.sub(r"[^A-Za-z0-9_-]", "_", session_raw)[:32] or "nosession"
        ledger_path = ROOT / "logs" / LEDGER_DIR_NAME / f"{session}.json"
        seen = load_ledger(ledger_path)
        fresh = [item for item in hits if str(item.get("id")) not in seen]
        if not fresh:
            return 0
        seen.update(str(item.get("id")) for item in fresh)
        save_ledger(ledger_path, seen)

        lines = ["# zmem 撞错召回 (error_regex 命中,该错以前踩过):"]
        for item in fresh:
            lines.append(f"- {item['id']} [{item['kind']}/{item['priority']}]")
            if item.get("snippet"):
                lines.append(f"  {item['snippet']}")
        lines.append(
            "(全文: python cc_memory_vnext/zmem.py search \"<关键词>\" ; 本会话同卡只提醒一次)"
        )
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "\n".join(lines),
            }
        }
        sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
