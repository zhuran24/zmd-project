"""探针: 喂文件后「添加源」模态框长什么样 — 找缺失的确认步骤。

背景 (2026-06-12): 字节注入通道已通 (页面内 sha256 一致、行菜单出现「下载」),
但刷新后条目消失 → 怀疑模态框还有一步确认 (如「添加」按钮) 没点。
本探针: 喂一个小 zip 后分时间点抓 dialog DOM + 全页可见按钮, 落盘人工看。
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import websockets

sys.path.insert(0, str(Path(__file__).resolve().parent))
from upload_project_file import (  # noqa: E402
    ADD_SOURCE_TEXTS,
    CDP_HTTP,
    GUARD_JS,
    FEED_INPUT_JS,
    PROJECT_URL,
    UPLOAD_BTN_TEXTS,
    Cdp,
    find_and_click,
    http,
    inject_file_into_page,
    log,
    sha256_of,
    wait_sources_rendered,
)

DUMP_JS = """
(() => {
  const dialogs = [...document.querySelectorAll('[role=dialog]')].map(d => d.outerHTML);
  const buttons = [...document.querySelectorAll('button,[role=button]')]
    .filter(e => e.offsetParent)
    .map(e => ({text: (e.innerText || '').trim().slice(0, 60),
                aria: e.getAttribute('aria-label') || '',
                disabled: e.disabled || e.getAttribute('aria-disabled') === 'true'}));
  return JSON.stringify({dialogs, buttons});
})()
"""


async def drain_events(cdp: Cdp, seconds: float, net_log: dict):
    """边等边收 CDP 事件, 记录网络请求 (url/method/status) — 看上传/挂载哪步失败。"""
    deadline = time.time() + seconds
    while True:
        remain = deadline - time.time()
        if remain <= 0:
            break
        try:
            msg = json.loads(await asyncio.wait_for(cdp.ws.recv(), remain))
        except (asyncio.TimeoutError, TimeoutError):
            break
        m = msg.get("method")
        p = msg.get("params", {})
        if m == "Network.requestWillBeSent":
            net_log[p["requestId"]] = {
                "url": p["request"]["url"][:160], "method": p["request"]["method"],
                "status": None, "t": round(time.time(), 1)}
        elif m == "Network.responseReceived":
            e = net_log.setdefault(p["requestId"], {"url": p["response"]["url"][:160],
                                                    "method": "?", "t": round(time.time(), 1)})
            e["status"] = p["response"]["status"]
        elif m == "Network.loadingFailed":
            e = net_log.setdefault(p["requestId"], {"url": "?", "method": "?",
                                                    "t": round(time.time(), 1)})
            e["status"] = f"FAILED:{p.get('errorText', '?')}"


async def snap(cdp: Cdp, out_dir: Path, tag: str):
    raw = await cdp.js(DUMP_JS)
    data = json.loads(raw)
    (out_dir / f"{tag}_dialogs.html").write_text(
        "\n\n<!-- ===== dialog split ===== -->\n\n".join(data["dialogs"]) or "(no dialog)",
        encoding="utf-8")
    (out_dir / f"{tag}_buttons.json").write_text(
        json.dumps(data["buttons"], ensure_ascii=False, indent=1), encoding="utf-8")
    await cdp.screenshot(out_dir / f"{tag}.png")
    log("probe", f"snap_{tag}", dialogs=len(data["dialogs"]), buttons=len(data["buttons"]))


async def main() -> int:
    pkg = Path(sys.argv[1]).resolve()
    out_dir = Path(sys.argv[2]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    sources_url = PROJECT_URL + "?tab=sources"

    tab = http("PUT", "/json/new", CDP_HTTP)
    tab_id, ws_url = tab["id"], tab["webSocketDebuggerUrl"]
    try:
        async with websockets.connect(ws_url, max_size=64 * 1024 * 1024, open_timeout=20) as ws:
            cdp = Cdp(ws)
            net_log: dict = {}
            await cdp.call("Page.enable")
            await cdp.call("Runtime.enable")
            await cdp.call("Network.enable")
            await cdp.call("Page.navigate", {"url": sources_url})
            if await wait_sources_rendered(cdp, out_dir):
                return 3
            if not await inject_file_into_page(cdp, pkg, sha256_of(pkg)):
                return 3
            await cdp.js(GUARD_JS)
            await find_and_click(cdp, ADD_SOURCE_TEXTS, "add_source", out_dir)
            await drain_events(cdp, 1.5, net_log)
            await snap(cdp, out_dir, "t0_modal_open")
            net_log.clear()  # 只留喂文件之后的请求
            await find_and_click(cdp, UPLOAD_BTN_TEXTS, "upload_button", out_dir)
            await drain_events(cdp, 0.8, net_log)
            fed = await cdp.js(FEED_INPUT_JS)
            log("probe", "fed", result=fed)
            await drain_events(cdp, 3, net_log)
            await snap(cdp, out_dir, "t1_fed_3s")
            await drain_events(cdp, 9, net_log)
            await snap(cdp, out_dir, "t2_fed_12s")
            await drain_events(cdp, 18, net_log)
            await snap(cdp, out_dir, "t3_fed_30s")
            interesting = [e for e in net_log.values()
                           if e["method"] not in ("GET", "?") or "backend-api" in e["url"]
                           or (e.get("status") and not isinstance(e["status"], int))]
            (out_dir / "net_log.json").write_text(
                json.dumps(sorted(interesting, key=lambda e: e["t"]),
                           ensure_ascii=False, indent=1), encoding="utf-8")
            log("probe", "net_log_written", total=len(net_log), interesting=len(interesting))
            # 不点任何收尾按钮, 现场留给人工判读; tab 在 finally 里关
            return 0
    finally:
        try:
            http("GET", "/json/close/" + tab_id, CDP_HTTP)
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
