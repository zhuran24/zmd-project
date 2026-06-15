"""导出一条 ChatGPT 会话的全部消息 (user + assistant), 不止最后一条回复。

复用 dispatch_gpt_task 的 raw-CDP page + 后端会话 JSON 直读 (_BACKEND_CONV_JS),
取回 mapping 里全部节点, 按 create_time 排序后逐条 dump。需 Edge 9222 已登录。

用法: python dump_conversation.py <conversation_url> <out_file.md>
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from dispatch_gpt_task import Reporter, _BACKEND_CONV_JS, attach_page


async def main() -> int:
    url = sys.argv[1]
    out = Path(sys.argv[2])
    conv_id = url.rstrip("/").split("/c/")[-1].split("?")[0]
    out.parent.mkdir(parents=True, exist_ok=True)
    rep = Reporter(out.parent)
    page = await attach_page("http://localhost:9222", rep)
    try:
        await page.navigate(url, settle_seconds=5)
        raw = await page.js(_BACKEND_CONV_JS.replace("__CONV_ID__", conv_id), timeout=30)
        payload = json.loads(raw) if isinstance(raw, str) else {}
        if not payload.get("ok"):
            print(f"BACKEND_FAIL status={payload.get('status')} err={payload.get('error')}")
            return 1
        nodes = [n for n in payload.get("nodes", []) if isinstance(n, dict)]
        nodes.sort(key=lambda n: n.get("create_time") or 0)
        chunks: list[str] = []
        kept = 0
        for n in nodes:
            txt = "\n".join(p for p in n.get("parts", []) if isinstance(p, str)).strip()
            if not txt:
                continue
            kept += 1
            role = n.get("role", "?")
            ct = n.get("content_type", "")
            chunks.append(f"\n\n===== #{kept} [{role}] (content_type={ct}) =====\n{txt}")
        out.write_text("".join(chunks).lstrip(), encoding="utf-8", newline="\n")
        print(f"wrote {kept} message-nodes (of {len(nodes)} total) -> {out}")
        return 0
    finally:
        await page.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
