#!/usr/bin/env python
"""PostToolUse「遇到什么」召回: tool 结果撞上某卡 error_regex -> 注入该卡。

Design: recall-trigger-discussion-20260628.md §4.1 —— PostToolUse 对「拦动作」
太晚,对「撞上后指路下一步」时机正好;卡片的 error_regex 字段专为此设计
(例: git push 撞 non-fast-forward -> 推送冲突卡当场弹)。
observable-commitment-gate: post_tool_use = result_driven_recall。

同会话注入账本(design pro-action 席): 同一张卡本会话只弹一次,账本只活在
建议通道、绝不参与 deny。Fail-safe: 任何异常 exit 0 不注入。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RESPONSE_TAIL_CHARS = 6000
LEDGER_DIR_NAME = "error_recall_seen"


def response_text(payload: dict) -> str:
    response = payload.get("tool_response")
    if response is None:
        return ""
    try:
        text = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
    except Exception:
        text = str(response)
    return text[-RESPONSE_TAIL_CHARS:]


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
        import zmem

        errors_text = response_text(payload)
        if not errors_text:
            return 0

        index = zmem.load_index(zmem.DEFAULT_INDEX_PATH)

        # Cheap union pre-filter before any packet work.
        any_hit = False
        for card_data in index.get("cards", []):
            meta = zmem.as_dict(card_data.get("meta"))
            triggers = zmem.as_dict(meta.get("triggers"))
            patterns = zmem.normalize_list(triggers.get("error_regex")) + zmem.normalize_list(
                meta.get("error_regex")
            )
            if zmem.error_regex_hit(patterns, [errors_text]):
                any_hit = True
                break
        if not any_hit:
            return 0

        tool_input = payload.get("tool_input") or {}
        command = str(tool_input.get("command") or "") if isinstance(tool_input, dict) else ""
        frame = zmem.normalize_frame({"prompt": "", "errors": [errors_text]})
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

        session = str(payload.get("session_id") or "nosession")
        ledger_path = ROOT / "logs" / LEDGER_DIR_NAME / f"{session[:32]}.json"
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
