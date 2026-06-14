"""往 ChatGPT Project 文件页 (来源区) 上传包 — 文件页递交通道 (2026-06-12 owner 裁决)。

包不再随消息发附件, 而是上传到 Project 的「来源」文件区; prompt 里指认文件名 + sha256。
本脚本只管上传 + 验证条目真正持久化, 不发送任何消息、不触发生成。

引擎 = raw CDP over **page 级 websocket** (HTTP /json/new 开 tab + 直连该 tab 的
ws 端点)。不用 Playwright `connect_over_cdp`: 那走 browser 级 ws, 会被同机
claude-in-chrome 插件会话独占 (2026-06-12 实测, 连 180s 必超时); page 级 ws
与之互不干扰, 插件在不在都能跑。

字节通道 (2026-06-12 重写): **不再用 `DOM.setFileInputFiles`** — 它对来源区上传
只让前端读到文件名 (乐观占位/同名判重都触发), 但 17.6MB 包的字节从未真正进上传
管道 (spinner 转 104s、刷新后文件消失)。现行法 = 把真实字节分块 base64 灌进页面
(Runtime.evaluate + atob), 在页面内构造**内存背书**的 File (并在页面内算 SHA-256
与本地比对), 再 `DataTransfer` 喂给被劫持标记的 input + 派发 change — 上传管道
读到的就是渲染进程内存里的真字节, 与手动选文件路径完全一致。

上传 UI 实测为两级流程 (2026-06-12 插件手操摸清):
    ?tab=sources → 点「+ 添加源」只弹模态框 (拖放区 + 上传/文本输入/Google/Slack)
    → 再点模态框里「上传」才触发隐藏 input[type=file]。
脚本先 JS 劫持 input.click (不真弹原生对话框, 只给目标 input 打标记), 点完「上传」
后对带标记的 input 喂内存 File — 全程不出现原生对话框。

真完成判据 (2026-06-12 网络抓包定): 喂文件后前端走四步管道
    POST /backend-api/files (注册) → PUT <blob>/raw (字节, 201)
    → POST /backend-api/files/process_upload_stream → POST /backend-api/projects/<id>/files (挂载)
**挂载 POST 返回 200 才算真完成** — 脚本在 page-ws 上直接监听网络事件等它。
教训: 上传期间不要捅 UI、更不能看到行菜单出「下载」就立刻刷新 — 挂载是管道最后
一步, 刷新会掐断 in-flight 挂载请求 → 文件上传成功却没挂到 Project, 刷新后消失
(2026-06-12 实测两次对照坐实)。UI 侧信号仅作收尾复核: 挂载 200 后刷新页面,
条目仍在 + 行菜单出「下载」(owner 判据: 上传中是「移除」, 传完才是「下载/删除」)。

用法 (前置: Edge 带 CDP 9222, start_gpt_automation_chrome.ps1):
    python upload_project_file.py --file <包.zip> [--replace]
    python upload_project_file.py --list                  # 只读: 枚举来源区 .zip
    python upload_project_file.py --delete-name <文件名>  # 精确删指定名条目

退出码: 0=上传成功(挂载 200 + 刷新后条目仍在)  1=环境/参数错误  3=异常(看 attention 截图)
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import re
import sys
import time
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
DOWNLOAD_ITEM_TEXTS = ["下载", "Download"]

INJECT_CHUNK_RAW_BYTES = 1024 * 1024  # 1MB 原始字节/块 → ~1.37MB base64, 远低于 CDP 消息上限


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


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Cdp:
    """单 page 目标的最小 CDP 客户端。事件不丢弃, 缓冲进 self.events
    (NetWatch 靠它追上传管道的网络里程碑)。"""

    def __init__(self, ws):
        self.ws = ws
        self._id = 0
        self.events: list[dict] = []

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
            if msg.get("method"):
                self.events.append(msg)

    async def pump_events(self, seconds: float):
        """纯收事件 seconds 秒 (不发命令), 进 self.events。"""
        deadline = time.time() + seconds
        while True:
            remain = deadline - time.time()
            if remain <= 0:
                return
            try:
                msg = json.loads(await asyncio.wait_for(self.ws.recv(), remain))
            except (asyncio.TimeoutError, TimeoutError):
                return
            if msg.get("method"):
                self.events.append(msg)

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

    async def hover_xy(self, x: float, y: float):
        await self.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})

    async def click_xy(self, x: float, y: float):
        await self.hover_xy(x, y)
        base = {"x": x, "y": y, "button": "left", "clickCount": 1}
        await self.call("Input.dispatchMouseEvent", {"type": "mousePressed", **base})
        await self.call("Input.dispatchMouseEvent", {"type": "mouseReleased", **base})

    async def press_escape(self):
        for t in ("keyDown", "keyUp"):
            await self.call("Input.dispatchKeyEvent",
                            {"type": t, "key": "Escape", "code": "Escape",
                             "windowsVirtualKeyCode": 27})


class NetWatch:
    """从 CDP 网络事件提取上传管道里程碑 (2026-06-12 抓包确认的四步):
    register → blob_put → process → attach。attach 200 = 真完成。"""

    MILESTONE_ORDER = ["register", "blob_put", "process", "attach"]

    def __init__(self, project_url: str):
        m = re.search(r"(g-p-[0-9a-f]+)", project_url)
        self.gizmo = m.group(1) if m else None
        self.reqs: dict[str, dict] = {}
        self.milestones: dict[str, object] = {}

    def _classify(self, e: dict):
        url, method, status = e.get("url", ""), e.get("method", ""), e.get("status")
        if status is None:
            return
        name = None
        if "oaiusercontent.com" in url and method == "PUT":
            name = "blob_put"
        elif "/backend-api/files/process_upload_stream" in url:
            name = "process"
        elif url.endswith("/backend-api/files") and method == "POST":
            name = "register"
        elif (self.gizmo and f"/backend-api/projects/{self.gizmo}/files" in url
              and method == "POST"):
            name = "attach"
        if name and name not in self.milestones:
            self.milestones[name] = status
            log("pipeline", name, code=status)

    def process(self, events: list[dict]):
        for msg in events:
            m, p = msg.get("method"), msg.get("params", {})
            if m == "Network.requestWillBeSent":
                self.reqs[p["requestId"]] = {
                    "url": p["request"]["url"], "method": p["request"]["method"]}
            elif m == "Network.responseReceived":
                e = self.reqs.setdefault(
                    p["requestId"], {"url": p["response"]["url"], "method": ""})
                e["status"] = p["response"]["status"]
                self._classify(e)
            elif m == "Network.loadingFailed":
                e = self.reqs.get(p["requestId"])
                if e is not None and "status" not in e:
                    e["status"] = f"FAILED:{p.get('errorText', '?')}"
                    self._classify(e)
        events.clear()

    def failed_milestone(self):
        for name, st in self.milestones.items():
            if not isinstance(st, int) or st >= 400:
                return name, st
        return None

    def attach_ok(self) -> bool:
        return self.milestones.get("attach") == 200


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

INJECT_INIT_JS = "(() => { window.__ccUp = {chunks: [], size: 0}; return 'ok'; })()"


def inject_chunk_js(b64: str) -> str:
    return (
        "(() => {"
        f"  const s = atob({json.dumps(b64)});"
        "  const a = new Uint8Array(s.length);"
        "  for (let i = 0; i < s.length; i++) a[i] = s.charCodeAt(i);"
        "  window.__ccUp.chunks.push(a);"
        "  window.__ccUp.size += a.length;"
        "  return window.__ccUp.size;"
        "})()"
    )


def build_file_js(filename: str) -> str:
    """页面内把已灌入的分块拼成 Blob → 算 SHA-256 → 构造内存背书 File。"""
    return (
        "(async () => {"
        "  const blob = new Blob(window.__ccUp.chunks, {type: 'application/zip'});"
        "  const dig = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer());"
        "  const hex = [...new Uint8Array(dig)].map(b => b.toString(16).padStart(2, '0')).join('');"
        f"  window.__ccUp.file = new File([blob], {json.dumps(filename)}, {{type: 'application/zip'}});"
        "  window.__ccUp.chunks = null;"
        "  return JSON.stringify({size: blob.size, sha256: hex});"
        "})()"
    )


FEED_INPUT_JS = (
    "(() => {"
    "  const input = document.querySelector('input[data-cc-upload-target]');"
    "  if (!input) return 'no-input';"
    "  if (!window.__ccUp || !window.__ccUp.file) return 'no-file';"
    "  const dt = new DataTransfer();"
    "  dt.items.add(window.__ccUp.file);"
    "  input.files = dt.files;"
    "  input.dispatchEvent(new Event('change', {bubbles: true}));"
    "  return 'fed:' + input.files.length;"
    "})()"
)


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


def action_button_for_name_js(filename: str) -> str:
    """定位「文件名 == filename」那一行的「源文件操作」按钮中心坐标。
    **按文件名精确匹配** (==, 非 includes), 绝不会命中别的文件 (如依赖包) 的按钮。"""
    return (
        "(() => {"
        f"  const target = {json.dumps(filename)};"
        "  for (const op of document.querySelectorAll('button[aria-label=\"源文件操作\"],"
        "       button[aria-label=\"Source file actions\"]')) {"
        "    let el = op, name = null;"
        "    for (let i = 0; i < 6 && el; i++) {"
        "      el = el.parentElement;"
        "      if (!el) break;"
        "      const m = (el.innerText || '').match(/[\\w.\\-]+\\.zip/);"
        "      if (m) { name = m[0]; break; }"
        "    }"
        "    if (name === target) {"
        "      const r = op.getBoundingClientRect();"
        "      return {x: r.x + r.width / 2, y: r.y + r.height / 2};"
        "    }"
        "  }"
        "  return null;"
        "})()"
    )


def menu_item_texts_js() -> str:
    """枚举当前弹出菜单里所有可见项的文本 (空数组 = 菜单没开)。"""
    return (
        "(() => {"
        "  const els = [...document.querySelectorAll('[role=menuitem],[role=option]')]"
        "    .filter(e => e.offsetParent);"
        "  return JSON.stringify(els.map(e => (e.innerText || '').trim()).filter(Boolean));"
        "})()"
    )


def menu_delete_spot_js() -> str:
    """在已弹出的操作菜单里定位「删除」项中心坐标 (只认菜单项, 不误点别处)。"""
    return (
        "(() => {"
        "  const texts = ['删除', 'Delete'];"
        "  const els = [...document.querySelectorAll('[role=menuitem],[role=option],button')]"
        "    .filter(e => e.offsetParent);"
        "  for (const t of texts) {"
        "    const el = els.find(e => (e.innerText || '').trim() === t);"
        "    if (el) { const r = el.getBoundingClientRect();"
        "      return {x: r.x + r.width / 2, y: r.y + r.height / 2}; }"
        "  }"
        "  return null;"
        "})()"
    )


def list_source_zip_names_js() -> str:
    """枚举来源区里所有 .zip 文件名 (排除对话框文本)。"""
    return (
        "(() => {"
        "  const inDialog = el => !!el.closest('[role=dialog]');"
        "  const names = new Set();"
        "  for (const el of document.querySelectorAll('a,div,span,button')) {"
        "    if (inDialog(el) || el.childElementCount !== 0) continue;"
        "    const t = (el.textContent || '').trim();"
        "    if (/^[\\w.\\-]+\\.zip$/.test(t)) names.add(t);"
        "  }"
        "  return JSON.stringify([...names]);"
        "})()"
    )


async def open_row_menu_items(cdp: Cdp, filename: str) -> list[str] | None:
    """点该行「源文件操作」按钮弹菜单, 返回菜单项文本列表并 Escape 收掉菜单。
    返回 None = 该行按钮不存在 (条目消失); 返回 [] = 按钮在但菜单没弹出来。"""
    spot = await cdp.js(action_button_for_name_js(filename))
    if not spot:
        return None
    items: list[str] = []
    for _attempt in range(2):  # 实测有时首点只 hover 出图标, 菜单没出 → 重试一次
        await cdp.hover_xy(spot["x"], spot["y"])
        await asyncio.sleep(0.3)
        await cdp.click_xy(spot["x"], spot["y"])
        await asyncio.sleep(0.8)
        raw = await cdp.js(menu_item_texts_js())
        try:
            items = json.loads(raw) if raw else []
        except (json.JSONDecodeError, TypeError):
            items = []
        if items:
            break
    await cdp.press_escape()
    await asyncio.sleep(0.4)
    return items


async def menu_confirms_download(cdp: Cdp, filename: str) -> bool | None:
    """开一次该行菜单看「下载」在不在 (owner 判据: 上传中是「移除」, 传完才是
    「下载/删除」)。**只在上传已结束后调用** — 上传期间捅 UI 有干扰风险。
    返回 True/False; None = 菜单没能打开 (UI 抖动, 不可下结论)。"""
    items = await open_row_menu_items(cdp, filename)
    if not items:
        return None
    has_dl = any(t in DOWNLOAD_ITEM_TEXTS for t in items)
    log("verify", "menu_check", items="/".join(items), download=has_dl)
    return has_dl


async def wait_sources_rendered(cdp: Cdp, out_dir: Path) -> int:
    """等来源区真正渲染 — SPA 客户端渲染, readyState complete 不代表右侧列表已出来
    (实测撞到过整片空白就操作 → count=0/按钮找不到)。轮询到「添加源」按钮真出现,
    再多等让已有列表条目渲染 (条目比按钮出得慢)。返回 0=ok, 3=失败。"""
    deadline = time.time() + 60
    while time.time() < deadline:
        url_now = await cdp.js("window.location.href") or ""
        if "auth" in url_now or "login" in url_now:
            await cdp.screenshot(out_dir / "attention_login.png")
            log("nav", "FATAL", error="redirected to login")
            return 3
        if await cdp.js(FIND_BUTTON_JS.format(texts=json.dumps(ADD_SOURCE_TEXTS))):
            await asyncio.sleep(4)  # 让已有列表条目渲染完 (否则 entries/删除枚举数到 0)
            log("nav", "sources_page_ready", url=url_now[:90])
            return 0
        await asyncio.sleep(1.5)
    await cdp.screenshot(out_dir / "attention_sources_not_rendered.png")
    log("nav", "FATAL", error="sources panel did not render (添加源 not found in 60s)")
    return 3


async def delete_sources_except(cdp: Cdp, keep_names: list[str], out_dir: Path) -> int:
    """删除来源区所有 .zip 条目, **白名单 keep_names 里的除外** (默认=依赖包)。
    对「旧快照包名字与新包不同」鲁棒: 不靠同名匹配, 而是保留白名单、清其余。"""
    keep = set(keep_names)
    deleted = 0
    announced = False
    for _ in range(20):  # 上限护栏
        raw = await cdp.js(list_source_zip_names_js())
        try:
            names = json.loads(raw) if raw else []
        except (json.JSONDecodeError, TypeError):
            names = []
        targets = [n for n in names if n not in keep]
        if not announced:
            # 动手前把目标清单亮出来 — 白名单语义会删掉**期间新出现**的文件
            # (2026-06-12 事故: owner 测试窗口期手传的 r7 包被清, 靠本地副本救回)
            log("replace", "delete_targets", targets=json.dumps(targets, ensure_ascii=False),
                keep=json.dumps(sorted(keep), ensure_ascii=False))
            announced = True
        if not targets:
            break
        n = await delete_named_sources(cdp, targets[0], out_dir)
        if n == 0:
            log("replace", "delete_no_progress", filename=targets[0])
            break
        deleted += n
    return deleted


async def delete_named_sources(cdp: Cdp, filename: str, out_dir: Path) -> int:
    """删除文件区里**所有**文件名 == filename 的条目 (精确匹配, 不碰其它文件)。
    返回删除条数。删除 UI 实测 (2026-06-12): 点该行「源文件操作」按钮 → 弹菜单
    (下载/删除) → 点「删除」**立即生效、无确认框**。"""
    deleted = 0
    for _ in range(10):  # 上限护栏: 同名最多删 10 个
        before = await cdp.js(count_list_entries_js(filename))
        if not isinstance(before, int) or before <= 0:
            break
        spot = await cdp.js(action_button_for_name_js(filename))
        if not spot:
            break
        # 点操作按钮弹菜单; 实测有时首点只 hover 出图标, 菜单没出 → 重试一次
        del_spot = None
        for attempt in range(2):
            await cdp.hover_xy(spot["x"], spot["y"])
            await asyncio.sleep(0.3)
            await cdp.click_xy(spot["x"], spot["y"])
            await asyncio.sleep(0.8)
            del_spot = await cdp.js(menu_delete_spot_js())
            if del_spot:
                break
            log("delete", "menu_retry", filename=filename, attempt=attempt + 1)
        if not del_spot:
            await cdp.screenshot(out_dir / "attention_no_delete_item.png")
            log("delete", "FATAL", error="action menu opened but 删除 item not found")
            raise RuntimeError("delete menu item not found")
        await cdp.click_xy(del_spot["x"], del_spot["y"])
        await asyncio.sleep(1.5)
        after = await cdp.js(count_list_entries_js(filename))
        if isinstance(after, int) and after < before:
            deleted += 1
            log("delete", "removed_one", filename=filename, remaining=after)
        else:
            log("delete", "no_progress", filename=filename, before=before, after=after)
            break
    return deleted


async def inject_file_into_page(cdp: Cdp, pkg: Path, expected_sha: str) -> bool:
    """分块把包字节灌进页面并构造内存 File; 页面内 SHA-256 与本地比对。"""
    await cdp.js(INJECT_INIT_JS)
    sent = 0
    total = pkg.stat().st_size
    t0 = time.time()
    with pkg.open("rb") as f:
        while True:
            data = f.read(INJECT_CHUNK_RAW_BYTES)
            if not data:
                break
            b64 = base64.b64encode(data).decode("ascii")
            sent = await cdp.js(inject_chunk_js(b64), timeout=60)
    if sent != total:
        log("inject", "FATAL", error=f"page received {sent} bytes, expected {total}")
        return False
    raw = await cdp.js(build_file_js(pkg.name), timeout=120)
    info = json.loads(raw)
    if info["sha256"] != expected_sha or info["size"] != total:
        log("inject", "FATAL", error="in-page sha256/size mismatch",
            page_sha=info["sha256"][:16], local_sha=expected_sha[:16],
            page_size=info["size"], local_size=total)
        return False
    log("inject", "file_built_in_page", size=info["size"], sha256=info["sha256"][:16],
        seconds=round(time.time() - t0, 1))
    return True


async def run(args, pkg: Path | None, out_dir: Path) -> int:
    sources_url = args.project_url.rstrip("/")
    sources_url += ("&" if "?" in sources_url else "?") + "tab=sources"
    base = args.cdp_http.rstrip("/")

    opened_tab = False
    if args.reuse_tab_id:
        # 复用调用方已开的 tab — 不开空页 (owner 2026-06-14)。调用方在阻塞等本子进程,
        # 其 page-ws 此刻空闲, 我们另开一条 ws 连同一 tab 操作, 不冲突; 结束不关 (no_close)。
        try:
            targets = http("GET", "/json/list", base) or []
            match = next((t for t in targets if t.get("id") == args.reuse_tab_id
                          and t.get("webSocketDebuggerUrl")), None)
            if not match:
                log("attach", "FATAL", error=f"reuse-tab-id {args.reuse_tab_id} not in /json/list")
                return 1
            tab_id, ws_url = match["id"], match["webSocketDebuggerUrl"]
        except Exception as e:
            log("attach", "FATAL", error=str(e)[:200], hint="reuse-tab-id lookup failed")
            return 1
        log("attach", "tab_reused", tab=tab_id)
    else:
        try:
            tab = http("PUT", "/json/new", base)  # 开空 tab; 导航走显式 Page.navigate
            tab_id, ws_url = tab["id"], tab["webSocketDebuggerUrl"]  # 非 dict 返回也算端点不可用
        except Exception as e:
            log("attach", "FATAL", error=str(e)[:200], hint="Edge with CDP up? run start_gpt_automation_chrome.ps1")
            return 1
        opened_tab = True
        log("attach", "tab_created", tab=tab_id)
    print("KEPT_TAB_ID:" + tab_id, flush=True)  # 调用方据此复用同一 tab 发送

    try:
        async with websockets.connect(ws_url, max_size=64 * 1024 * 1024, open_timeout=20) as ws:
            cdp = Cdp(ws)
            await cdp.call("Page.enable")
            await cdp.call("Runtime.enable")
            await cdp.call("Network.enable")  # NetWatch 靠网络事件观测上传管道
            # 显式导航 — 靠 /json/new?<url> 的查询参数导航实测会卡在 about:blank
            await cdp.call("Page.navigate", {"url": sources_url})
            rc = await wait_sources_rendered(cdp, out_dir)
            if rc:
                return rc

            # ---- 运维模式: 只读枚举 / 精确删除, 不上传 ----
            if args.list:
                raw = await cdp.js(list_source_zip_names_js())
                names = json.loads(raw) if raw else []
                shot = await cdp.screenshot(out_dir / "sources_list.png")
                log("list", "ok", zips=json.dumps(names, ensure_ascii=False), screenshot=shot)
                print("SOURCES_JSON:" + json.dumps(names, ensure_ascii=False), flush=True)
                return 0
            if args.delete_name:
                n = await delete_named_sources(cdp, args.delete_name, out_dir)
                shot = await cdp.screenshot(out_dir / "after_delete.png")
                log("delete", "done", filename=args.delete_name, deleted=n, screenshot=shot)
                return 0

            assert pkg is not None
            local_sha = sha256_of(pkg)
            log("init", "sha256", file=pkg.name, sha256=local_sha)

            # --replace: 传新包前先删旧快照。**按白名单保留依赖包、删其余所有 .zip**
            # (不靠同名 — 旧快照包版本名可能与新包不同, owner 2026-06-12 指正)。
            if args.replace:
                n = await delete_sources_except(cdp, args.keep, out_dir)
                log("replace", "old_snapshots_deleted", count=n, kept_whitelist=args.keep)
                await cdp.screenshot(out_dir / "after_delete.png")

            before = await cdp.js(count_list_entries_js(pkg.name))
            log("upload", "entries_before", count=before)

            # 先把字节灌进页面 (秒级), 再走 UI 点击流, 模态框开着的时间最短
            if not await inject_file_into_page(cdp, pkg, local_sha):
                await cdp.screenshot(out_dir / "attention_inject_failed.png")
                return 3

            await cdp.js(GUARD_JS)
            await find_and_click(cdp, ADD_SOURCE_TEXTS, "add_source", out_dir)
            await asyncio.sleep(1.5)  # 等「添加源」面板 / 隐藏 file input 就绪
            # 现行 UI (2026-06-14 实测): 点「添加源」直接驱动相邻隐藏 input[type=file],
            # 已无第二级「上传」按钮。先看 guard 是否已被点中; 没有再退回旧的两级
            # 「上传」按钮流 (老版本兼容)。
            guard_clicks = await cdp.js("window.__ccUploadGuard.clicks")
            if not guard_clicks:
                spot = await cdp.js(FIND_BUTTON_JS.format(texts=json.dumps(UPLOAD_BTN_TEXTS)))
                if spot:
                    await cdp.click_xy(spot["x"], spot["y"])
                    log("upload", "upload_button_clicked", text=spot["text"])
                    await asyncio.sleep(0.8)
                    guard_clicks = await cdp.js("window.__ccUploadGuard.clicks")
            if not guard_clicks:
                await cdp.screenshot(out_dir / "attention_no_input_click.png")
                log("upload", "FATAL", error="add_source did not drive a file input; no upload button (UI changed?)")
                return 3

            # 喂文件前清空事件缓冲 — 此后的网络事件全归上传管道观测
            cdp.events.clear()
            watch = NetWatch(args.project_url)

            fed = await cdp.js(FEED_INPUT_JS)
            if fed != "fed:1":
                await cdp.screenshot(out_dir / "attention_feed_failed.png")
                log("upload", "FATAL", error=f"feeding in-page File failed: {fed}")
                return 3
            log("upload", "file_fed", file=pkg.name)

            # 等真完成 = 挂载 POST 200。期间**不捅任何 UI** — 上传中开行菜单/提前
            # 刷新会干扰乃至掐断 in-flight 挂载请求, 文件传上去了却没挂到 Project
            # (2026-06-12 两次对照实测坐实)。同名对话框是页面自己弹的, 前 25s 顺带处理。
            deadline = time.time() + args.timeout_minutes * 60
            dup_window_end = time.time() + 25
            dup_handled = False
            while time.time() < deadline:
                await cdp.pump_events(2.0)
                watch.process(cdp.events)
                bad = watch.failed_milestone()
                if bad:
                    shot = await cdp.screenshot(out_dir / "attention_pipeline_failed.png")
                    log("upload", "FAIL", error=f"pipeline {bad[0]} -> {bad[1]}", screenshot=shot)
                    return 3
                if watch.attach_ok():
                    break
                if (not dup_handled and time.time() < dup_window_end
                        and await cdp.js(dialog_present_js())):
                    dup_handled = True
                    if args.on_duplicate == "overwrite":
                        await find_and_click(cdp, DUP_OVERWRITE_TEXTS, "dup_overwrite", out_dir)
                        log("upload", "dup_overwrite", note="续等挂载信号")
                    else:
                        await find_and_click(cdp, DUP_SKIP_TEXTS, "dup_skip", out_dir)
                        await asyncio.sleep(2)
                        shot = await cdp.screenshot(out_dir / "final_state.png")
                        log("upload", "ok_duplicate_skipped",
                            note="同名文件已在来源区, 按策略跳过(幂等)", screenshot=shot)
                        return 0

            if not watch.attach_ok():
                # 兜底: API 形状变了收不到挂载信号时, 退回 owner 的 UI 判据
                dl = await menu_confirms_download(cdp, pkg.name)
                if dl:
                    log("upload", "WARN", note="网络判据未命中(API 形状变了?), UI 判据「下载」"
                        "通过; 多等 15s 让挂载落地后继续复核")
                    await cdp.pump_events(15)
                    watch.process(cdp.events)
                else:
                    shot = await cdp.screenshot(out_dir / "attention_never_completed.png")
                    log("upload", "FAIL", error="attach signal never seen and 下载 menu item absent",
                        screenshot=shot)
                    return 3
            log("upload", "pipeline_complete", milestones=json.dumps(watch.milestones))

            # 收尾复核: 刷新后条目仍在 (失败模式 = 占位被回收, 刷新后消失)
            # + 行菜单出「下载」。此时上传已结束, 捅 UI 安全。
            await cdp.call("Page.navigate", {"url": sources_url})
            rc = await wait_sources_rendered(cdp, out_dir)
            if rc:
                return rc
            persisted = await cdp.js(count_list_entries_js(pkg.name))
            if not isinstance(persisted, int) or persisted < 1:
                await asyncio.sleep(10)  # 后端最终一致性余量, 再数一次
                persisted = await cdp.js(count_list_entries_js(pkg.name))
            shot = await cdp.screenshot(out_dir / "final_state.png")
            if not isinstance(persisted, int) or persisted < 1:
                log("upload", "FAIL", error="entry gone after reload (attach lost?)", screenshot=shot)
                return 3
            dl = await menu_confirms_download(cdp, pkg.name)
            if dl is False:
                log("upload", "WARN", note="刷新后条目在但菜单无「下载」— 可能后端仍在处理, 看截图")
            log("upload", "ok", entries_after_reload=persisted, menu_download=dl,
                sha256=local_sha, screenshot=shot)
            return 0
    except Exception as e:
        log("fatal", "unhandled", error=str(e)[:300])
        return 3
    finally:
        # 只关自己开的 tab; 复用调用方 tab 或 --no-close 时留着给下一步 (发送) 用
        if opened_tab and not args.no_close:
            try:
                http("GET", "/json/close/" + tab_id, base)
            except Exception:
                pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="path of the package to upload")
    ap.add_argument("--list", action="store_true",
                    help="只读运维模式: 枚举来源区所有 .zip 文件名 + 截图, 不做任何修改")
    ap.add_argument("--delete-name",
                    help="运维模式: 精确删除来源区里该文件名的所有条目 (不上传)")
    ap.add_argument("--project-url", default=PROJECT_URL)
    ap.add_argument("--cdp-http", default=CDP_HTTP,
                    help="CDP HTTP 端点 (page 级 ws 由此发现; 不走 browser 级 ws)")
    ap.add_argument("--timeout-minutes", type=float, default=10.0,
                    help="真完成信号超时 (等挂载 POST 200; 收不到时退回行菜单「下载」UI 判据)")
    ap.add_argument("--on-duplicate", choices=["skip", "overwrite"], default="skip",
                    help="同名文件已在来源里时: skip=点跳过(默认,保持幂等) / overwrite=点仍然上传(造新版本)")
    ap.add_argument("--replace", action="store_true",
                    help="传新包前先删掉来源里所有旧快照包 (保留 --keep 白名单, 默认依赖包); "
                         "对旧快照包改名鲁棒, 实现「新快照替换旧快照、依赖包保留」每轮工作流")
    ap.add_argument("--keep", action="append", default=None,
                    help="--replace 时**保留不删**的文件名白名单 (可重复); 默认 = 依赖包 zmd_py313_linux_x86_64.zip")
    ap.add_argument("--reuse-tab-id", default=None,
                    help="复用调用方已开的 tab (按 id 连其 page-ws), 不再 PUT /json/new 开空 tab; "
                         "配 --no-close 让上传后页面留给下一步 (发送) 复用 (owner 2026-06-14 裁决: 别开空页传完就关)")
    ap.add_argument("--no-close", action="store_true",
                    help="结束时不关 tab (留给调用方继续用); 复用 tab 时本就不该关")
    ap.add_argument("--out-dir", help="screenshots/evidence dir; default 补丁包/gpt_deliveries/<ts>_project_upload")
    args = ap.parse_args()

    if args.keep is None:
        args.keep = ["zmd_py313_linux_x86_64.zip"]  # 依赖包默认永不删

    pkg = None
    if not args.list and not args.delete_name:
        if not args.file:
            log("init", "FATAL", error="--file required unless --list/--delete-name")
            return 1
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
    if pkg:
        log("init", "start", file=pkg.name, size_mb=round(pkg.stat().st_size / 1024 / 1024, 1),
            out_dir=str(out_dir))
    else:
        log("init", "start", mode="list" if args.list else f"delete:{args.delete_name}",
            out_dir=str(out_dir))
    return asyncio.run(run(args, pkg, out_dir))


if __name__ == "__main__":
    sys.exit(main())
