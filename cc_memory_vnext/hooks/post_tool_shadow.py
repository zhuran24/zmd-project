#!/usr/bin/env python
"""PostToolUse shadow hook: measure derived-ops recall, inject NOTHING.

Design: recall-trigger-discussion-20260628.md「先测后建」(measurement 席 5 步):
装影子 hook 算投影+跑编译,只记录「本会注入哪些卡」,一张不真注;用真实
transcript 数据量出「prompt 没注、动作会注」的真实载荷,再决定建多大。

Projection (deterministic, zero-LLM, prompt=""):
- file tools  -> frame.paths = [tool_input.file_path]
- shell tools -> enrich_frame(extra_text=command) 抽 paths/index symbols/风险动词 intents
- tool_response tail -> frame.errors (error_regex 影子测量)

Fail-safe: any exception exits 0 silently; telemetry must never break tools.
Log: logs/shadow_activations.jsonl (gitignored).
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FILE_PATH_TOOLS = {"Edit", "Write", "Read", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}
SPAWN_TOOLS = {"Task", "Agent", "Workflow"}
RESPONSE_TAIL_CHARS = 6000


def response_text(payload: dict) -> str:
    response = payload.get("tool_response")
    if response is None:
        return ""
    try:
        text = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
    except Exception:
        text = str(response)
    return text[-RESPONSE_TAIL_CHARS:]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    try:
        import zmem

        tool_name = str(payload.get("tool_name") or "")
        tool_input = payload.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            tool_input = {}

        frame: dict = {"prompt": "", "intents": [], "paths": [], "symbols": []}
        extra_text = ""
        if tool_name in FILE_PATH_TOOLS:
            file_path = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
            if file_path:
                frame["paths"] = [file_path]
        elif tool_name in SHELL_TOOLS:
            extra_text = str(tool_input.get("command") or "")
        elif tool_name in SPAWN_TOOLS:
            frame["symbols"] = [s for s in (str(tool_input.get("subagent_type") or ""),) if s]

        errors_text = response_text(payload)
        if errors_text:
            # 与 error_recall 同构: 命令前缀拼进 errors,影子测的即真投影。
            frame["errors"] = [f"$ {extra_text}\n{errors_text}" if extra_text else errors_text]

        index = zmem.load_index(zmem.DEFAULT_INDEX_PATH)
        normalized = zmem.normalize_frame(frame)
        if extra_text:
            # prompt stays "" so bm25/keyword noise is structurally zero
            # (pro-action 席); extra_text feeds paths/symbols/risk-verb intents.
            normalized = zmem.enrich_frame(normalized, index, extra_text=extra_text)

        packet = zmem.compile_context(index, normalized, dense_enabled=False)
        would_inject = [
            {"id": item.get("id"), "layer": layer, "reason": item.get("reason")}
            for layer in ("L0", "L1")
            for item in packet["layers"].get(layer, [])
        ]
        zmem.append_jsonl(
            ROOT / "logs" / "shadow_activations.jsonl",
            {
                "ts": datetime.datetime.now().isoformat(timespec="seconds"),
                "session": str(payload.get("session_id") or ""),
                "tool": tool_name,
                "frame": {
                    "paths": normalized.get("paths", []),
                    "intents": normalized.get("intents", []),
                    "symbols": normalized.get("symbols", []),
                    "errors_len": len(errors_text),
                },
                "would_inject": would_inject,
            },
        )
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
