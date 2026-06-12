"""往 ChatGPT Project 文件页 (来源区) 上传包 — 文件页递交通道 (2026-06-12 owner 裁决)。

包不再随消息发附件, 而是上传到 Project 的「来源」文件区; prompt 里指认文件名 + sha256。
本脚本只管上传 + 验证条目出现, 不发送任何消息、不触发生成。

引擎 = raw CDP over **page 级 websocket** (HTTP /json/new 开 tab + 直连该 tab 的
ws 端点)。不用 Playwright `connect_over_cdp`: 那走 browser 级 ws, 会被同机
claude-in-chrome 插件会话独占 (2026-06-12 实测, 连 180s 必超时); page 级 ws
与之互不干扰, 插件在不在都能跑。

上传 UI 实测为两级流程 (2026-06-12 插件手操摸清):
    ?tab=sources → 点「+ 添加源」只弹模态框 (拖放区 + 上传/文本输入/Google/Slack)
    → 再点模态框里「上传」才触发隐藏 input[type=file]。
脚本先 JS 劫持 input.click (不真弹原生对话框, 只给目标 input 打标记), 点完「上传」
后对带标记的 input 执行 DOM.setFileInputFiles — 全程不出现原生对话框。

用法 (前置: Edge 带 CDP 9222, start_gpt_automation_chrome.ps1):
    python upload_project_file.py --file <包.zip>

退出码: 0=上传成功(来源列表同名条目 +1)  1=环境/参数错误  3=异常(看 attention 截图)
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import websockets

CDP_HTTP = "http://127.0.0.1:9222"
PROJECT_URL = "https://chatgpt.com/g/g-p-69b585dfc29c819186b93a166f5266a5-zhong-mo-di/project"

ADD_SOURCE_TEXTS = ["添加源", "添加来源", "Add source", "Add sources", "添加文件", "Add files"]
UPLOAD_BTN_TEXTS = ["上传", "Upload"]
DUP_DIALOG_TEXTS = ["已经存在", "已存在", "already exists"]
DUP_OVERWRITE_TEXTS = ["仍然上传", "Upload anyway", "仍然"]
DUP_SKIP_TEXTS = ["跳过", "Skip"]


def log(stage: str, status: str, **kw):
    ts = datetime.now().isoformat(timespec="seconds")
    extra = " ".join(f"{k}={v}" for k, v in kw.items())
    print(f"[{ts}] {stage}: {status} {extra}", flush=True)


def http(method: str, path: str, base: str):
    req = urllib.request.Request(base + path, method=method)
    with urllib.request.urlopen(req, timeout=10) as r:
        body = r.read()
    try:
        return json.loads(body) if body else None
    except json.JSONDecodeError:
        return body.decode("utf-8", "replace")  # /json/close 返回纯文本


class Cdp:
    """单 page 目标的最小 CDP 客户端。"""

    def __init__(self, ws):
        self.ws = ws
        self._id = 0

    async def call(self, method: str, params: dict | None = None, timeout: float = 30.0):
        self._id += 1
        mid = self._id
        await self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while True:
            remain = deadline - time.time()
            if remain <= 0:
                raise TimeoutError(f"CDP {method} timed out")
            msg = json.loads(await asyncio.wait_for(self.ws.recv(), remain))
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"CDP {method}: {msg['error']}")
                return msg.get("result", {})
            # 事件消息直接丢弃 (本工具不依赖事件)

    async def js(self, expression: str, timeout: float = 30.0):
        res = await self.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
            timeout=timeout,
        )
        if res.get("exceptionDetails"):
            raise RuntimeError(f"page JS threw: {json.dumps(res['exceptionDetails'])[:300]}")
        return res.get("result", {}).get("value")

    async def screenshot(self, out_path: Path):
        try:
            res = await self.call("Page.captureScreenshot", {"format": "png"}, timeout=20)
            out_path.write_bytes(base64.b64decode(res["data"]))
            return str(out_path)
        except Exception:
            return None

    async def click_xy(self, x: float, y: float):
        base = {"x": x, "y": y, "button": "left", "clickCount": 1}
        await self.call("Input.dispatchMouseEvent", {"type": "mousePressed", **base})
        await self.call("Input.dispatchMouseEvent", {"type": "mouseReleased", **base})


FIND_BUTTON_JS = """
(() => {{
  const texts = {texts};
  const els = [...document.querySelectorAll('button,[role="button"]')];
  for (const t of texts) {{
    const el = els.find(e => e.offsetParent && (e.innerText || '').trim().includes(t));
    if (el) {{
      const r = el.getBoundingClientRect();
      return {{x: r.x + r.width / 2, y: r.y + r.height / 2, text: t}};
    }}
  }}
  return null;
}})()
"""

GUARD_JS = """
(() => {
  if (window.__ccUploadGuard) return 'already';
  window.__ccUploadGuard = {clicks: 0};
  const orig = HTMLInputElement.prototype.click;
  HTMLInputElement.prototype.click = function (...a) {
    if (this.type === 'file') {
      window.__ccUploadGuard.clicks++;
      document.querySelectorAll('[data-cc-upload-target]')
        .forEach(e => e.removeAttribute('data-cc-upload-target'));
      this.setAttribute('data-cc-upload-target', '1');
      return;  // 不弹原生对话框
    }
    return orig.apply(this, a);
  };
  if (window.showOpenFilePicker) {
    window.showOpenFilePicker = async () => {
      throw new DOMException('cc-upload-guard', 'AbortError');
    };
  }
  return 'installed';
})()
"""


def count_list_entries_js(filename: str) -> str:
    """数「来源列表」里该文件名条目数 — 排除模态框/对话框 (role=dialog) 内的文本,
    否则「文件已存在」对话框里的同名文本会污染计数 (实测假阳性根因)。"""
    return (
        "(() => {"
        "  const inDialog = el => !!el.closest('[role=dialog]');"
        f"  const name = {json.dumps(filename)};"
        "  let n = 0;"
        "  for (const el of document.querySelectorAll('a,div,span,button')) {"
        "    if (inDialog(el)) continue;"
        "    const t = (el.childElementCount === 0 ? (el.textContent || '') : '');"
        "    if (t.trim() === name) n++;"
        "  }"
        "  return n;"
        "})()"
    )


def dialog_present_js() -> str:
    texts = json.dumps(DUP_DIALOG_TEXTS)
    return (
        "(() => {"
        f"  const texts = {texts};"
        "  const body = document.body.innerText || '';"
        "  return texts.some(t => body.includes(t));"
        "})()"
    )


async def find_and_click(cdp: Cdp, texts: list[str], what: str, out_dir: Path) -> str:
    spot = await cdp.js(FIND_BUTTON_JS.format(texts=json.dumps(texts)))
    if not spot:
        await cdp.screenshot(out_dir / f"attention_no_{what}.png")
        raise RuntimeError(f"{what} button not found")
    await cdp.click_xy(spot["x"], spot["y"])
    log("upload", f"{what}_clicked", text=spot["text"])
    return spot["text"]


async def run(args, pkg: Path, out_dir: Path) -> int:
    sources_url = args.project_url.rstrip("/")
    sources_url += ("&" if "?" in sources_url else "?") + "tab=sources"
    base = args.cdp_http.rstrip("/")

    try:
        tab = http("PUT", "/json/new?" + urllib.parse.quote(sources_url, safe=":/?&="), base)
    except Exception as e:
        log("attach", "FATAL", error=str(e)[:200], hint="Edge with CDP up? run start_gpt_automation_chrome.ps1")
        return 1
    tab_id, ws_url = tab["id"], tab["webSocketDebuggerUrl"]
    log("attach", "tab_created", tab=tab_id)

    try:
        async with websockets.connect(ws_url, max_size=64 * 1024 * 1024, open_timeout=20) as ws:
            cdp = Cdp(ws)
            await cdp.call("Page.enable")
            await cdp.call("Runtime.enable")
            await cdp.call("DOM.enable")

            # 等加载 + React 渲染
            deadline = time.time() + 60
            while time.time() < deadline:
                if await cdp.js("document.readyState") == "complete":
                    break
                await asyncio.sleep(1)
            await asyncio.sleep(4)

            url_now = await cdp.js("window.location.href")
            if "auth" in url_now or "login" in url_now:
                await cdp.screenshot(out_dir / "attention_login.png")
                log("nav", "FATAL", error="redirected to login")
                return 3
            log("nav", "sources_page_ready", url=url_now[:90])

            before = await cdp.js(count_list_entries_js(pkg.name))
            log("upload", "entries_before", count=before)

            await cdp.js(GUARD_JS)
            await find_and_click(cdp, ADD_SOURCE_TEXTS, "add_source", out_dir)
            await asyncio.sleep(1.5)  # 等「添加源」模态框渲染
            await find_and_click(cdp, UPLOAD_BTN_TEXTS, "upload_button", out_dir)
            await asyncio.sleep(0.8)

            guard_clicks = await cdp.js("window.__ccUploadGuard.clicks")
            if not guard_clicks:
                await cdp.screenshot(out_dir / "attention_no_input_click.png")
                log("upload", "FATAL", error="upload button did not drive a file input (UI changed?)")
                return 3

            # 对被标记的 input 喂文件 (DOM.setFileInputFiles 自带 change 事件)
            obj = await cdp.call(
                "Runtime.evaluate",
                {"expression": "document.querySelector('input[data-cc-upload-target]')"},
            )
            object_id = obj.get("result", {}).get("objectId")
            if not object_id:
                await cdp.screenshot(out_dir / "attention_no_tagged_input.png")
                log("upload", "FATAL", error="tagged file input not found")
                return 3
            await cdp.call("DOM.getDocument", {"depth": 0})
            node = await cdp.call("DOM.requestNode", {"objectId": object_id})
            await cdp.call(
                "DOM.setFileInputFiles",
                {"files": [str(pkg)], "nodeId": node["nodeId"]},
            )
            log("upload", "file_set", file=pkg.name)

            # 同名时 ChatGPT 弹「文件已经存在」对话框 (跳过 / 仍然上传)。先短轮询看它出不出现。
            dup = False
            dup_deadline = time.time() + 20
            while time.time() < dup_deadline:
                if await cdp.js(dialog_present_js()):
                    dup = True
                    break
                if isinstance(before, int):
                    now = await cdp.js(count_list_entries_js(pkg.name))
                    if isinstance(now, int) and now > before:
                        break  # 全新文件名: 列表直接 +1, 不会弹对话框
                await asyncio.sleep(2)

            if dup:
                # 上传管道已验证 (ChatGPT 收下文件、算名、判重)。按策略收尾对话框。
                if args.on_duplicate == "overwrite":
                    await find_and_click(cdp, DUP_OVERWRITE_TEXTS, "dup_overwrite", out_dir)
                else:
                    await find_and_click(cdp, DUP_SKIP_TEXTS, "dup_skip", out_dir)
                await asyncio.sleep(3)
                shot = await cdp.screenshot(out_dir / "final_state.png")
                log("upload", "ok_duplicate", on_duplicate=args.on_duplicate,
                    note="same-name file already in sources; upload pipeline verified", screenshot=shot)
                return 0

            deadline = time.time() + args.timeout_minutes * 60
            settled = False
            while time.time() < deadline:
                now = await cdp.js(count_list_entries_js(pkg.name))
                if isinstance(now, int) and isinstance(before, int) and now > before:
                    settled = True
                    break
                await asyncio.sleep(3)
            shot = await cdp.screenshot(out_dir / "final_state.png")
            if not settled:
                log("upload", "TIMEOUT", error="new entry never appeared in sources list", screenshot=shot)
                return 3
            await asyncio.sleep(5)  # 让后端处理收尾 (zip 显示「文件内容可能无法访问」属正常)
            log("upload", "ok", entries_now=await cdp.js(count_list_entries_js(pkg.name)), screenshot=shot)
            return 0
    except Exception as e:
        log("fatal", "unhandled", error=str(e)[:300])
        return 3
    finally:
        try:
            http("GET", "/json/close/" + tab_id, base)
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="path of the package to upload")
    ap.add_argument("--project-url", default=PROJECT_URL)
    ap.add_argument("--cdp-http", default=CDP_HTTP,
                    help="CDP HTTP 端点 (page 级 ws 由此发现; 不走 browser 级 ws)")
    ap.add_argument("--timeout-minutes", type=float, default=10.0,
                    help="upload settle timeout (entry must appear in the sources list)")
    ap.add_argument("--on-duplicate", choices=["skip", "overwrite"], default="skip",
                    help="同名文件已在来源里时: skip=点跳过(默认,保持幂等) / overwrite=点仍然上传(造新版本)")
    ap.add_argument("--out-dir", help="screenshots/evidence dir; default 补丁包/gpt_deliveries/<ts>_project_upload")
    args = ap.parse_args()

    pkg = Path(args.file).resolve()
    if not pkg.is_file():
        log("init", "FATAL", error=f"file not found: {pkg}")
        return 1
    repo_root = Path(__file__).resolve().parents[3]
    out_dir = Path(args.out_dir) if args.out_dir else (
        repo_root / "补丁包" / "gpt_deliveries"
        / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_project_upload")
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    log("init", "start", file=pkg.name, size_mb=round(pkg.stat().st_size / 1024 / 1024, 1),
        out_dir=str(out_dir))
    return asyncio.run(run(args, pkg, out_dir))


if __name__ == "__main__":
    sys.exit(main())
