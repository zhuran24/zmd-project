"""GPT Pro 外发全流程自动化: 发包 + 发 prompt + 等完成 + 收交付。

引擎 (2026-06-12 重写) = **raw CDP over page 级 websocket** (与 upload_project_file.py
同范式), 不再用 Playwright `connect_over_cdp`。原因 (当天实锤, 协议级 trace 钉死):
Playwright 的 browser 级连接会对浏览器里**每一个**打开的页面做完整初始化
(attach 全部 target + 给每个 frame 建 isolated world); 任何一个"病页" (如 B 站这类
iframe 高频轮换的视频站) 都会让 `Page.createIsolatedWorld` 撞上 "No frame for
given id found", 初始化 promise 永久挂起 → connect 直到超时。page 级 ws 只跟自己
的 tab 说话, 其它页什么状态都无关; 下载捕获用一条**裸 browser 级 ws** (browser-ws
本身健康, 病的只是 Playwright 的全量初始化)。

发包通道 (--package-channel, 2026-06-12 owner 裁决默认 sources):
    sources    = 包上传到 Project 文件页「来源区」(子进程调 upload_project_file.py,
                 网页端专用), 消息只发纯文字 prompt — prompt 必须自己指认文件区包
                 文件名 + sha256。发送前自动 --list 验证 prompt 指认的包真在文件区
                 (prompt-only 模式缺包 fail-closed)。默认先按白名单清旧快照,
                 --keep-old-snapshots 关闭清理。
    attachment = 旧模式: 包随消息当附件发 (会话内传大附件疑似风控诱因, 仅留作备选)。

用法:
    python dispatch_gpt_task.py --prompt-file prompt.md                   # prompt-only (包已在文件区)
    python dispatch_gpt_task.py --package X.zip --prompt-file prompt.md  # 传包+发送
    python dispatch_gpt_task.py --pack --prompt-file prompt.md           # 打包再发 (sources 下自动唯一名)
    python dispatch_gpt_task.py --resume https://chatgpt.com/.../c/<id>  # 重连续等/补收

输出 (--out-dir, 默认 补丁包/gpt_deliveries/<时间戳>/):
    final_reply.md     GPT 最后回复全文
    <附件原名>          回复里的全部文件附件
    run_log.jsonl      各阶段时间戳/状态 (心跳每分钟一条, 可 tail 监控)
    attention_*.png/html  非预期状态的现场截图 + DOM dump (托底用)

退出码: 0=交付到手  2=完成但无附件(看 final_reply.md)  3=异常需托底  4=超时
        5=疑似降级  1=环境错误

完成检测 (双信号 + 稳定窗口):
    信号1 = 停止生成按钮消失; 信号2 = 最后一条回复文本长度连续 STABLE_TICKS 次轮询不变。
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

import websockets

CDP_URL = "http://localhost:9222"
APP_CDP_URL = "http://localhost:9224"
PROJECT_URL = "https://chatgpt.com/g/g-p-69b585dfc29c819186b93a166f5266a5-zhong-mo-di/project"
CONV_URL_RE = re.compile(r"/c/[0-9a-f-]{10,}")

POLL_SECONDS = 10
STABLE_TICKS = 3
HEARTBEAT_TICKS = 6  # 每 ~1 分钟一条心跳日志

MODEL_BTN_TEXTS = ["专业", "Pro", "进阶"]
ERROR_TEXTS = ["出错了", "Something went wrong", "网络错误"]
FILE_EXT_RE = re.compile(
    r"\.(zip|7z|tar|gz|tgz|md|py|json|patch|diff|txt|csv|log|whl)(\?|$)", re.I
)

RESCUE_PROMPT = (
    "刚才下载附件时返回 404——沙盒文件应该已被回收。"
    "请重新运行生成步骤重建该文件,并再次作为文件附件给出(文件名保持不变)。回复简短即可。"
)

DOWNGRADE_RETRY_PROMPT = (
    "上一条回复的生成时间异常短,怀疑没有走完整的 Pro 推理。"
    "请重新完整执行原任务:重新分析、重新生成全部交付文件,不要复用上一次的结论。"
)


def http(method: str, path: str, base: str):
    req = urllib.request.Request(base + path, method=method)
    with urllib.request.urlopen(req, timeout=10) as r:
        body = r.read()
    try:
        return json.loads(body) if body else None
    except json.JSONDecodeError:
        return body.decode("utf-8", "replace")  # /json/close 返回纯文本


class Reporter:
    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = out_dir / "run_log.jsonl"
        self.attention_count = 0

    def log(self, stage: str, status: str, **kw):
        entry = {"ts": datetime.now().isoformat(timespec="seconds"), "stage": stage, "status": status, **kw}
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        try:
            print(f"[{entry['ts']}] {stage}: {status} {kw if kw else ''}", flush=True)
        except Exception:
            pass  # stdout 管道断开 (head 类) / GBK 控制台编码失败都不该杀进程 — run_log 是真相源

    async def attention(self, page, stage: str, reason: str):
        """非预期状态: 截图 + DOM dump + 日志, 供托底接手。不抛异常。"""
        self.attention_count += 1
        tag = f"attention_{self.attention_count:02d}_{stage}"
        shot = dump = url = None
        if page is not None:
            try:
                shot = await page.screenshot(self.out_dir / f"{tag}.png")
            except Exception:
                shot = None
            try:
                html = await page.js("document.documentElement.outerHTML", timeout=15)
                if html:
                    p = self.out_dir / f"{tag}.html"
                    p.write_text(html, encoding="utf-8")
                    dump = str(p)
            except Exception:
                dump = None
            try:
                url = await page.url()
            except Exception:
                url = None
        self.log(stage, "NEEDS_ATTENTION", reason=reason, screenshot=shot, dom_dump=dump, url=url)


class PageCdp:
    """单 page 目标的最小 CDP 客户端 (与 upload_project_file.Cdp 同范式)。"""

    def __init__(self, ws, http_base: str, tab_id: str | None, owns_tab: bool):
        self.ws = ws
        self.http_base = http_base
        self.tab_id = tab_id
        self.owns_tab = owns_tab
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

    async def js(self, expression: str, timeout: float = 30.0):
        res = await self.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
            timeout=timeout,
        )
        if res.get("exceptionDetails"):
            raise RuntimeError(f"page JS threw: {json.dumps(res['exceptionDetails'])[:300]}")
        return res.get("result", {}).get("value")

    async def navigate(self, url: str, settle_seconds: float = 3.0):
        await self.call("Page.navigate", {"url": url}, timeout=60)
        await asyncio.sleep(settle_seconds)

    async def url(self) -> str:
        return (await self.js("window.location.href", timeout=10)) or ""

    async def alive(self) -> bool:
        try:
            await self.js("document.readyState", timeout=8)
            return True
        except Exception:
            return False

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

    async def insert_text(self, text: str):
        await self.call("Input.insertText", {"text": text}, timeout=60)

    async def close(self):
        try:
            await self.ws.close()
        except Exception:
            pass
        if self.owns_tab and self.tab_id:
            try:
                pages = http("GET", "/json/list", self.http_base) or []
                others = [t for t in pages if t.get("type") == "page" and t.get("id") != self.tab_id]
                if others:
                    http("GET", "/json/close/" + self.tab_id, self.http_base)
                # 自己是最后一个 page: 关掉会把浏览器带退 — 留着不动
            except Exception:
                pass


# --------------------------------------------------------------------------- #
# attach / tab 管理
# --------------------------------------------------------------------------- #
async def _connect_page(http_base: str, ws_url: str, tab_id: str | None, owns_tab: bool) -> PageCdp:
    ws = await websockets.connect(ws_url, max_size=64 * 1024 * 1024, open_timeout=20)
    page = PageCdp(ws, http_base, tab_id, owns_tab)
    await page.call("Page.enable")
    await page.call("Runtime.enable")
    return page


async def attach_page(http_base: str, rep: Reporter) -> PageCdp:
    """浏览器通道: /json/new 开自己的 tab (owns=True)。
    ChatGPT 桌面 App (Electron) 不支持 /json/new — 复用主窗口页面 (owns=False,
    结束时不能关它, 关了 App 就空了)。"""
    try:
        tab = http("PUT", "/json/new", http_base)
        if isinstance(tab, dict) and tab.get("webSocketDebuggerUrl"):
            return await _connect_page(http_base, tab["webSocketDebuggerUrl"], tab.get("id"), True)
    except Exception:
        pass
    targets = http("GET", "/json/list", http_base) or []
    pages = [t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
    if not pages:
        raise RuntimeError(f"no attachable page target on {http_base}")
    pages.sort(key=lambda t: ("chatgpt.com" not in (t.get("url") or "")))
    t = pages[0]
    return await _connect_page(http_base, t["webSocketDebuggerUrl"], t.get("id"), False)


async def attach_with_fallback(args, rep: Reporter) -> PageCdp:
    """主通道失败自动落 App (9224; owner 裁决第三托底不需逐次点头)。
    raw page-ws 没有 Playwright 的全浏览器初始化, attach 失败 = 端点真不可用。"""
    try:
        page = await attach_page(args.cdp_url, rep)
        rep.log("attach", "ok", cdp_url=args.cdp_url, owns_tab=page.owns_tab)
        return page
    except Exception as e:
        rep.log("attach", "failed", cdp_url=args.cdp_url, error=str(e)[:200])
    if "9224" in args.cdp_url:
        raise RuntimeError("attach failed on App channel; no further fallback")
    page = await attach_page(APP_CDP_URL, rep)
    rep.log("attach", "fallback_ok", cdp_url=APP_CDP_URL, owns_tab=page.owns_tab,
            note="primary endpoint unavailable — using App channel")
    return page


def cleanup_stale_tabs(http_base: str, keep_tab_id: str | None, rep: Reporter):
    """只清理下载残留页 (/mnt/data 404 之类) — 连的是用户日常 Edge 主实例,
    绝不能动用户自己开的标签页。"""
    closed = 0
    try:
        for t in http("GET", "/json/list", http_base) or []:
            if t.get("id") == keep_tab_id or t.get("type") != "page":
                continue
            url = t.get("url") or ""
            if "/mnt/data" in url:
                try:
                    http("GET", "/json/close/" + t["id"], http_base)
                    closed += 1
                except Exception:
                    pass
    except Exception:
        pass
    if closed:
        rep.log("init", "stale_download_tabs_closed", count=closed)


def close_same_conversation_tabs(http_base: str, conv_url: str,
                                 keep_tab_id: str | None, rep: Reporter):
    """resume 前回收同一会话的旧 tab (异常退出留现场的 owns_tab=False tab,
    现场截图/DOM 早已落盘, resume 时即无保留价值)。只按 /c/<conv-id> 精确匹配,
    同会话重复 tab 关掉零损失, 绝不动其它页面。"""
    m = CONV_URL_RE.search(conv_url or "")
    if not m:
        return
    conv_id = m.group(0)
    closed = 0
    try:
        for t in http("GET", "/json/list", http_base) or []:
            if t.get("id") == keep_tab_id or t.get("type") != "page":
                continue
            if conv_id in (t.get("url") or ""):
                try:
                    http("GET", "/json/close/" + t["id"], http_base)
                    closed += 1
                except Exception:
                    pass
    except Exception:
        pass
    if closed:
        rep.log("init", "stale_conversation_tabs_closed", count=closed, conv_id=conv_id)


def cleanup_project_tabs(http_base: str) -> int:
    """--cleanup-tabs 运维模式: 关闭本 Project 下所有 chatgpt 会话/项目页 tab。
    只在确认无在途 dispatch 任务时手动跑 (在途任务的 tab 也会被关, 不可区分)。
    匹配按 project id 前缀 (URL 可能带或不带 -zhong-mo-di slug 尾巴)。"""
    project_prefix = PROJECT_URL.split("-zhong-mo-di")[0]
    closed = 0
    for t in http("GET", "/json/list", http_base) or []:
        if t.get("type") != "page":
            continue
        url = t.get("url") or ""
        if url.startswith(project_prefix):
            print(f"closing: {url[:110]}")
            try:
                http("GET", "/json/close/" + t["id"], http_base)
                closed += 1
            except Exception as e:
                print(f"  close failed: {e}")
    print(f"closed {closed} project tab(s)")
    return closed


# --------------------------------------------------------------------------- #
# 页面状态 JS 探针
# --------------------------------------------------------------------------- #
def _find_button_js(texts: list[str]) -> str:
    return (
        "(() => {"
        f"  const texts = {json.dumps(texts)};"
        "  const els = [...document.querySelectorAll('button,[role=\"button\"]')];"
        "  for (const t of texts) {"
        "    const el = els.find(e => e.offsetParent && (e.innerText || '').trim().includes(t));"
        "    if (el) {"
        "      const r = el.getBoundingClientRect();"
        "      return {x: r.x + r.width / 2, y: r.y + r.height / 2, text: t};"
        "    }"
        "  }"
        "  return null;"
        "})()"
    )


_STOP_VISIBLE_JS = (
    "(() => {"
    "  if (document.querySelector('button[data-testid=\"stop-button\"]')) return true;"
    "  for (const lbl of ['停止', 'Stop streaming', 'Stop generating']) {"
    "    if ([...document.querySelectorAll('button[aria-label]')]"
    "        .some(b => (b.getAttribute('aria-label') || '').includes(lbl))) return true;"
    "  }"
    "  return false;"
    "})()"
)

_LAST_ASSISTANT_JS = (
    "(() => {"
    "  const msgs = document.querySelectorAll('div[data-message-author-role=\"assistant\"]');"
    "  if (!msgs.length) return {count: 0, text: '', slug: ''};"
    "  const last = msgs[msgs.length - 1];"
    "  return {count: msgs.length, text: last.innerText || '',"
    "          slug: last.getAttribute('data-message-model-slug') || ''};"
    "})()"
)

_LAST_TURN_TEXT_JS = (
    "(() => {"
    "  const msgs = document.querySelectorAll('div[data-message-author-role=\"assistant\"]');"
    "  if (!msgs.length) return '';"
    "  const last = msgs[msgs.length - 1];"
    "  const art = last.closest('article');"
    "  return (art || last).innerText || '';"
    "})()"
)

_THINKING_RE = re.compile(r"(思考[用耗]?时?\s*\d+|Thought for\s+\d+[^\n]{0,20}|Reasoned for\s+\d+[^\n]{0,20})")


def _error_banner_js() -> str:
    return (
        "(() => {"
        f"  const texts = {json.dumps(ERROR_TEXTS)};"
        "  const body = document.body ? (document.body.innerText || '') : '';"
        "  return texts.find(t => body.includes(t)) || '';"
        "})()"
    )


_COMPOSER_READY_JS = "(() => !!document.querySelector('#prompt-textarea'))()"

_SEND_READY_JS = (
    "(() => {"
    "  const b = document.querySelector('button[data-testid=\"send-button\"]');"
    "  if (!b) return 'absent';"
    "  return b.disabled ? 'disabled' : 'ready';"
    "})()"
)

_SEND_BTN_SPOT_JS = (
    "(() => { const b = document.querySelector('button[data-testid=\"send-button\"]');"
    "  if (!b || b.disabled) return null; const r = b.getBoundingClientRect();"
    "  return {x: r.x + r.width / 2, y: r.y + r.height / 2}; })()"
)

_SEND_BTN_JS_CLICK_JS = (
    "(() => { const b = document.querySelector('button[data-testid=\"send-button\"]');"
    "  if (!b || b.disabled) return false; b.click(); return true; })()"
)

_COMPOSER_TEXT_LEN_JS = (
    "(() => { const c = document.querySelector('#prompt-textarea');"
    "  return c ? (c.innerText || '').trim().length : -1; })()"
)


async def _click_send_verified(page: PageCdp, rep: Reporter, stage: str,
                               url_switch_counts: bool = True) -> bool:
    """点击发送并验证真发出去了 (composer 清空或 URL 切到会话页)。

    后台 tab 上 Input.dispatchMouseEvent 的合成点击会被 compositor 静默丢弃
    (2026-06-13 owner 破案: 平时新 tab 默认前台所以没踩; owner 同窗口期切走
    活动 tab → dispatch tab 变后台 → 坐标点击无效, 提示词留在 composer 里
    全程没发出去)。三层升级: 坐标点击 → JS element.click() (渲染进程内派发,
    不依赖前台) → /json/activate 拉前台再坐标点击。"""
    for attempt in (1, 2, 3):
        try:
            if attempt == 1:
                spot = await page.js(_SEND_BTN_SPOT_JS, timeout=10)
                if not spot:
                    return False
                await page.click_xy(spot["x"], spot["y"])
            elif attempt == 2:
                clicked = await page.js(_SEND_BTN_JS_CLICK_JS, timeout=10)
                if not clicked:
                    # 按钮没了/禁用 — 可能上一层其实已发出, 交给验证判定
                    pass
            else:
                if page.tab_id:
                    try:
                        http("GET", "/json/activate/" + page.tab_id, page.http_base)
                        await asyncio.sleep(1)
                    except Exception:
                        pass
                spot = await page.js(_SEND_BTN_SPOT_JS, timeout=10)
                if spot:
                    await page.click_xy(spot["x"], spot["y"])
        except Exception as e:
            rep.log(stage, "send_click_error", attempt=attempt, error=str(e)[:120])
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                remaining = await page.js(_COMPOSER_TEXT_LEN_JS, timeout=10)
                if isinstance(remaining, (int, float)) and 0 <= remaining < 10:
                    if attempt > 1:
                        rep.log(stage, "send_recovered", attempt=attempt)
                    return True
                if url_switch_counts:
                    u = await page.url()
                    if CONV_URL_RE.search(u):
                        if attempt > 1:
                            rep.log(stage, "send_recovered", attempt=attempt)
                        return True
            except Exception:
                pass
            await asyncio.sleep(2)
        rep.log(stage, "send_not_confirmed", attempt=attempt,
                note="composer still holds text; escalating click strategy")
    return False


async def _last_assistant(page: PageCdp) -> dict:
    try:
        v = await page.js(_LAST_ASSISTANT_JS, timeout=10)
        if isinstance(v, dict):
            return v
    except Exception:
        pass
    return {"count": 0, "text": "", "slug": ""}


async def assert_logged_in(page: PageCdp, rep: Reporter) -> bool:
    u = await page.url()
    if "auth" in u or "login" in u:
        await rep.attention(page, "login", "redirected to login page — log in once in that browser")
        return False
    return True


# 目标模型 = 「智能水平」菜单里 role=menuitemradio 文本 "Pro 扩展" (= Pro·进阶/扩展模式)。
# 该菜单 (2026-06-14 实地探明) 项: 极速/均衡/高级/超高/Pro 扩展/GPT-5.5, 选中项 aria-checked=true。
# 模型按钮 (aria-haspopup=menu) 的可见文本 = 当前选中项, 故按钮文本即可判当前模型。
TARGET_MODEL_TEXT = "Pro 扩展"

_MODEL_BTN_RECT_JS = (
    "(() => {"
    "  const bs=[...document.querySelectorAll("
    "    'button[aria-haspopup=menu],[role=button][aria-haspopup=menu]')];"
    "  for (const b of bs) {"
    "    const t=(b.innerText||'').trim();"
    "    if (/GPT|Pro|进阶|专业|扩展|5\\.5|Auto|自动/i.test(t) && t.length<40) {"
    "      const r=b.getBoundingClientRect();"
    "      return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2,text:t});"
    "    }"
    "  }"
    "  return null;"
    "})()"
)

_PRO_RADIO_RECT_JS = (
    "(() => {"
    "  const its=[...document.querySelectorAll('[role=menuitemradio]')];"
    "  for (const it of its) {"
    "    if ((it.innerText||'').trim().startsWith('Pro 扩展')) {"
    "      const r=it.getBoundingClientRect();"
    "      return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2,"
    "        checked:it.getAttribute('aria-checked')});"
    "    }"
    "  }"
    "  return null;"
    "})()"
)


async def _model_button(page: PageCdp) -> dict | None:
    raw = await page.js(_MODEL_BTN_RECT_JS, timeout=10)
    try:
        return json.loads(raw) if raw else None
    except (TypeError, ValueError):
        return None


async def verify_model(page: PageCdp, rep: Reporter):
    """检查当前模型, 若不是 Pro 扩展则打开「智能水平」菜单切过去 (owner 2026-06-14:
    上传完包后必须确认/修正模型再发, 不能只警告)。已对则 no-op (按钮文本即当前模型)。"""
    info = await _model_button(page)
    if info is None:
        await rep.attention(page, "model",
                            "model selector button not found — verify manually; proceeding")
        return
    if TARGET_MODEL_TEXT in info["text"]:
        rep.log("model", "ok", current=info["text"])
        return
    # 不对 → 打开菜单切到 Pro 扩展 (真实 pointer; .click() 对 Radix 菜单不可靠)
    rep.log("model", "wrong_model", current=info["text"], target=TARGET_MODEL_TEXT)
    await page.click_xy(info["x"], info["y"])
    await asyncio.sleep(1.2)
    raw = await page.js(_PRO_RADIO_RECT_JS, timeout=10)
    try:
        opt = json.loads(raw) if raw else None
    except (TypeError, ValueError):
        opt = None
    if opt is None:
        await page.press_escape()
        await rep.attention(page, "model",
                            f"Pro 扩展 option not found in model menu (current={info['text']});"
                            " verify manually")
        return
    if opt.get("checked") == "true":
        # 按钮文本与选中项不一致但 radio 已勾选 — 关菜单按已对处理
        await page.press_escape()
        rep.log("model", "ok_radio_checked", current=info["text"])
        return
    await page.click_xy(opt["x"], opt["y"])
    await asyncio.sleep(1.0)
    after = await _model_button(page)
    if after is not None and TARGET_MODEL_TEXT in after["text"]:
        rep.log("model", "switched_to_pro", from_model=info["text"], to=after["text"])
    else:
        await rep.attention(page, "model",
                            "model switch to Pro 扩展 not confirmed "
                            f"(now={after['text'] if after else '?'}); verify manually")


async def fill_and_send(page: PageCdp, prompt_text: str, rep: Reporter) -> str:
    for _ in range(30):
        if await page.js(_COMPOSER_READY_JS, timeout=10):
            break
        await asyncio.sleep(1)
    focused = await page.js(
        "(() => { const c = document.querySelector('#prompt-textarea');"
        "  if (!c) return false; c.focus(); return true; })()", timeout=10)
    if not focused:
        raise RuntimeError("composer #prompt-textarea not found")
    await page.insert_text(prompt_text)
    await asyncio.sleep(1)
    rep.log("prompt", "filled", chars=len(prompt_text))
    ready = await page.js(_SEND_BTN_SPOT_JS, timeout=10)
    if not ready:
        raise RuntimeError("send button not found/enabled after fill")
    if not await _click_send_verified(page, rep, "send"):
        await rep.attention(page, "send", "send click never took effect (composer still holds prompt after 3 strategies)")
        raise RuntimeError("send click never took effect")
    conv_url = ""
    deadline = time.time() + 60
    while time.time() < deadline:
        conv_url = await page.url()
        if CONV_URL_RE.search(conv_url):
            break
        await asyncio.sleep(2)
    if not CONV_URL_RE.search(conv_url):
        # 假 URL (如 project?tab=sources) 不能外流 — 会污染 revive 导航 / --resume 提示
        await rep.attention(page, "send", "URL did not switch to a conversation within 60s")
        conv_url = ""
    rep.log("send", "sent", conversation_url=conv_url or "unknown")
    return conv_url


async def send_followup(page: PageCdp, text: str, rep: Reporter) -> bool:
    """追问 (404 救援 / 降级重试)。返回是否真发出去了 — 以前点不到发送按钮也
    照记 followup_sent, 下游就干等一个永远不来的回复直到烧满超时。"""
    focused = False
    for _ in range(15):
        focused = await page.js(
            "(() => { const c = document.querySelector('#prompt-textarea');"
            "  if (!c) return false; c.focus(); return true; })()", timeout=10)
        if focused:
            break
        await asyncio.sleep(1)
    if not focused:
        rep.log("followup", "send_failed", error="composer #prompt-textarea not found")
        return False
    await page.insert_text(text)
    await asyncio.sleep(0.5)
    spot = None
    for _ in range(10):
        spot = await page.js(_SEND_BTN_SPOT_JS, timeout=10)
        if spot:
            break
        await asyncio.sleep(1)
    if not spot:
        rep.log("followup", "send_failed", error="send button not found/enabled after fill")
        return False
    if not await _click_send_verified(page, rep, "followup", url_switch_counts=False):
        rep.log("followup", "send_failed", error="send click never took effect (3 strategies)")
        return False
    rep.log("followup", "sent", chars=len(text))
    return True


async def _revive_page(page: PageCdp, last_url: str, rep: Reporter, reason: str) -> PageCdp:
    """网络抖动/渲染挂死恢复: 自有 tab → 关旧开新同 URL; App 主窗口 → 原地重导航。"""
    http_base = page.http_base
    owns = page.owns_tab
    if owns:
        try:
            await page.close()
        except Exception:
            pass
        try:
            new_page = await attach_page(http_base, rep)
            await new_page.navigate(last_url, settle_seconds=3)
            rep.log("waiting", "page_revived", reason=reason, url=last_url)
            return new_page
        except Exception as e:
            rep.log("waiting", "page_revive_failed", error=str(e)[:150])
            return page
    try:
        await page.navigate(last_url, settle_seconds=3)
        rep.log("waiting", "page_reloaded_in_place", reason=reason)
    except Exception as e:
        rep.log("waiting", "page_revive_failed", error=str(e)[:150])
        # ws 可能已断 — 重连同一 target
        try:
            new_page = await attach_page(http_base, rep)
            await new_page.navigate(last_url, settle_seconds=3)
            rep.log("waiting", "page_reattached", reason=reason)
            return new_page
        except Exception as e2:
            rep.log("waiting", "page_reattach_failed", error=str(e2)[:150])
    return page


async def wait_done(page: PageCdp, rep: Reporter, timeout_hours: float,
                    min_assistant_count: int = 1, conv_url: str = "",
                    project_url: str = PROJECT_URL):
    """返回 (status, page); status = 'done' | 'timeout' | 'attention'。
    page 可能被换新 — 调用方必须用返回的 page 继续。"""
    deadline = time.time() + timeout_hours * 3600
    start = time.time()
    stable = 0
    last_len = -1
    tick = 0
    dead_ticks = 0
    revives = 0
    last_url = conv_url
    while time.time() < deadline:
        tick += 1
        if not await page.alive():
            dead_ticks += 1
            if dead_ticks >= 2:  # 连续 ~20s 无响应才动手
                if revives >= 3:
                    await rep.attention(page, "waiting", "page unresponsive after 3 revives — network likely down")
                    return "attention", page
                page = await _revive_page(page, last_url or project_url, rep, "page unresponsive")
                revives += 1
                dead_ticks = 0
                stable, last_len = 0, -1
            await asyncio.sleep(POLL_SECONDS)
            continue
        dead_ticks = 0
        try:
            u = await page.url()
            # 会话锚定 (2026-06-12): 已知自己的会话 URL 时, 当前页漂到**别的**
            # 会话 (owner 手动切换/误导航) 就主动导航回去, 绝不跟随漂移 —
            # 跟着读别人的页面会误判完成并收走别的会话的附件 (face 3 串线事故)。
            if conv_url and u and CONV_URL_RE.search(u) and not u.startswith(conv_url):
                rep.log("waiting", "anchored_back_to_conversation", drifted_to=u[:90])
                await page.navigate(conv_url, settle_seconds=5)
                stable, last_len = 0, -1
                u = conv_url
            if u:
                last_url = u
        except Exception:
            pass
        if not await assert_logged_in(page, rep):
            return "attention", page
        try:
            generating = bool(await page.js(_STOP_VISIBLE_JS, timeout=10))
        except Exception:
            generating = False
        info = await _last_assistant(page)
        cur_len = len(info["text"])
        has_turn = info["count"] >= min_assistant_count
        if not generating and has_turn and cur_len == last_len:
            stable += 1
            if stable >= STABLE_TICKS:
                marker = ""
                try:
                    m = _THINKING_RE.search(await page.js(_LAST_TURN_TEXT_JS, timeout=10) or "")
                    marker = m.group(0) if m else ""
                except Exception:
                    pass
                rep.log("waiting", "done", elapsed_s=int(time.time() - start), reply_chars=cur_len,
                        thinking_marker=marker or "none")
                return "done", page
        else:
            stable = 0
        if not generating and cur_len == 0 and time.time() - start > 300:
            try:
                banner = await page.js(_error_banner_js(), timeout=10)
            except Exception:
                banner = ""
            if banner:
                await rep.attention(page, "waiting", f"error banner detected: {banner}")
                return "attention", page
        last_len = cur_len
        if tick % HEARTBEAT_TICKS == 0:
            rep.log("waiting", "heartbeat", elapsed_s=int(time.time() - start),
                    generating=generating, reply_chars=cur_len)
        await asyncio.sleep(POLL_SECONDS)
    await rep.attention(page, "waiting", f"timed out after {timeout_hours}h")
    return "timeout", page


# --------------------------------------------------------------------------- #
# 收交付
# --------------------------------------------------------------------------- #
class DownloadWatch:
    """裸 browser 级 ws 捕获下载 (Browser.setDownloadBehavior allowAndName)。
    browser-ws 本身健康 — Playwright 病的是全量初始化, 不是这条 ws。

    setDownloadBehavior 是**浏览器全局**状态: 生效期间用户在任何标签页手动下载
    都会落进 out_dir 并改名 GUID — 所以 (a) 退出时必须复位回 default, 否则关掉
    脚本后用户的 Edge 下载继续静默消失进交付目录; (b) wait_begin 按 frame_id
    过滤, 只认自己页面触发的下载, 不抢用户同窗口期的手动下载。"""

    def __init__(self, http_base: str, out_dir: Path, frame_id: str | None = None):
        self.http_base = http_base
        self.out_dir = out_dir
        self.frame_id = frame_id
        self.ws = None
        self._id = 1000

    async def __aenter__(self):
        info = http("GET", "/json/version", self.http_base)
        self.ws = await websockets.connect(info["webSocketDebuggerUrl"],
                                           max_size=16 * 1024 * 1024, open_timeout=15)
        await self._call("Browser.setDownloadBehavior",
                         {"behavior": "allowAndName", "downloadPath": str(self.out_dir),
                          "eventsEnabled": True})
        return self

    async def __aexit__(self, *exc):
        try:
            await self._call("Browser.setDownloadBehavior",
                             {"behavior": "default", "eventsEnabled": False})
        except Exception:
            pass  # 复位尽力而为; ws 已断时只能靠浏览器重启兜底
        try:
            await self.ws.close()
        except Exception:
            pass

    async def _call(self, method: str, params: dict):
        self._id += 1
        mid = self._id
        await self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        deadline = time.time() + 15
        while time.time() < deadline:
            msg = json.loads(await asyncio.wait_for(self.ws.recv(), deadline - time.time()))
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"CDP {method}: {msg['error']}")
                return msg.get("result", {})

    async def wait_begin(self, seconds: float) -> dict | None:
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                msg = json.loads(await asyncio.wait_for(self.ws.recv(), deadline - time.time()))
            except (asyncio.TimeoutError, TimeoutError):
                return None
            if msg.get("method") == "Browser.downloadWillBegin":
                p = msg["params"]
                if self.frame_id and p.get("frameId") and p["frameId"] != self.frame_id:
                    continue  # 别的页面 (含用户手动) 的下载 — 不是我们点出来的
                return {"guid": p["guid"], "name": p.get("suggestedFilename") or "download.bin"}
        return None

    async def wait_finish(self, guid: str, seconds: float) -> str:
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                msg = json.loads(await asyncio.wait_for(self.ws.recv(), deadline - time.time()))
            except (asyncio.TimeoutError, TimeoutError):
                return "timeout"
            if msg.get("method") == "Browser.downloadProgress" and msg["params"].get("guid") == guid:
                st = msg["params"].get("state")
                if st in ("completed", "canceled"):
                    return st
        return "timeout"


def _candidates_js() -> str:
    """枚举最后一条 assistant 消息里的文件附件候选。
    锚文本可能是中文描述 — 不能只靠扩展名, 结构 class 是更可靠判据 (V81 实测)。"""
    return (
        "(() => {"
        "  const msgs = document.querySelectorAll('div[data-message-author-role=\"assistant\"]');"
        "  if (!msgs.length) return [];"
        "  const last = msgs[msgs.length - 1];"
        "  const out = [];"
        "  const seen = new Set();"
        "  for (const el of last.querySelectorAll('a,button')) {"
        "    const href = el.getAttribute('href') || '';"
        "    const label = (el.innerText || '').trim();"
        "    const cls = el.getAttribute('class') || '';"
        "    const extRe = /\\.(zip|7z|tar|gz|tgz|md|py|json|patch|diff|txt|csv|log|whl)(\\?|$)/i;"
        "    const fileLike = extRe.test(href) || extRe.test(label) || href.includes('sandbox')"
        "      || cls.includes('behavior-btn') || cls.includes('decorated-link');"
        "    if (!fileLike) continue;"
        "    if (!label && !href) continue;"
        "    const key = label || href;"
        "    if (seen.has(key)) continue;"
        "    seen.add(key);"
        "    out.push({idx: out.length, href, label, cls});"
        "  }"
        "  return out;"
        "})()"
    )


def _candidate_rect_js(idx: int) -> str:
    """按 _candidates_js 同样的枚举顺序重算第 idx 个候选的中心坐标 (点击前实时取)。"""
    return (
        "(() => {"
        "  const msgs = document.querySelectorAll('div[data-message-author-role=\"assistant\"]');"
        "  if (!msgs.length) return null;"
        "  const last = msgs[msgs.length - 1];"
        "  const seen = new Set();"
        "  let i = 0;"
        "  for (const el of last.querySelectorAll('a,button')) {"
        "    const href = el.getAttribute('href') || '';"
        "    const label = (el.innerText || '').trim();"
        "    const cls = el.getAttribute('class') || '';"
        "    const extRe = /\\.(zip|7z|tar|gz|tgz|md|py|json|patch|diff|txt|csv|log|whl)(\\?|$)/i;"
        "    const fileLike = extRe.test(href) || extRe.test(label) || href.includes('sandbox')"
        "      || cls.includes('behavior-btn') || cls.includes('decorated-link');"
        "    if (!fileLike) continue;"
        "    if (!label && !href) continue;"
        "    const key = label || href;"
        "    if (seen.has(key)) continue;"
        "    seen.add(key);"
        f"    if (i === {idx}) {{"
        "      el.scrollIntoView({block: 'center'});"
        "      const r = el.getBoundingClientRect();"
        "      return {x: r.x + r.width / 2, y: r.y + r.height / 2};"
        "    }"
        "    i++;"
        "  }"
        "  return null;"
        "})()"
    )


async def _click_confirm_if_visible(page: PageCdp, rep: Reporter) -> bool:
    spot = await page.js(_find_button_js(["打开链接", "Open link"]), timeout=8)
    if spot:
        await page.click_xy(spot["x"], spot["y"])
        rep.log("collect", "confirmed_external_link_dialog")
        return True
    return False


async def _download_via_click(page: PageCdp, idx: int, out_dir: Path, rep: Reporter) -> Path | None:
    frame_id = None
    try:
        frame_id = (await page.call("Page.getFrameTree"))["frameTree"]["frame"]["id"]
    except Exception:
        pass  # 拿不到就不过滤 (退回旧行为), 下载捕获照常工作
    try:
        async with DownloadWatch(page.http_base, out_dir, frame_id) as watch:
            begin = None
            for attempt in range(1, 4):
                if attempt >= 2 and page.tab_id:
                    # 后台 tab 的坐标点击被 compositor 静默丢弃 (与发送侧
                    # _click_send_verified 同根因); 第二次尝试起先拉前台再点。
                    try:
                        http("GET", "/json/activate/" + page.tab_id, page.http_base)
                        await asyncio.sleep(1)
                        rep.log("collect", "tab_activated_for_download", attempt=attempt)
                    except Exception:
                        pass
                if not await _click_confirm_if_visible(page, rep):
                    spot = await page.js(_candidate_rect_js(idx), timeout=10)
                    if not spot:
                        rep.log("collect", "click_blocked", attempt=attempt, error="candidate rect not found")
                        await page.press_escape()
                        continue
                    await asyncio.sleep(0.3)
                    await page.click_xy(spot["x"], spot["y"])
                    await asyncio.sleep(0.5)
                    await _click_confirm_if_visible(page, rep)
                begin = await watch.wait_begin(12)
                if begin:
                    break
                rep.log("collect", "click_retry", attempt=attempt)
            if not begin:
                rep.log("collect", "click_download_failed", error="no downloadWillBegin after 3 clicks")
                await page.press_escape()
                return None
            state = await watch.wait_finish(begin["guid"], 180)
            if state != "completed":
                rep.log("collect", "click_download_failed",
                        error=f"download did not complete (state={state})")
                return None
            src = out_dir / begin["guid"]  # allowAndName 模式落盘名 = guid
            target = out_dir / begin["name"]
            if target.exists():
                target = out_dir / f"{int(time.time())}_{begin['name']}"
            src.rename(target)
            return target
    except Exception as e:
        rep.log("collect", "click_download_failed", error=str(e)[:200])
        try:
            await page.press_escape()
        except Exception:
            pass
        return None


async def _download_via_fetch(page: PageCdp, href: str, name: str, out_dir: Path, rep: Reporter) -> Path | None:
    try:
        b64 = await page.js(
            "(async () => {"
            f"  const r = await fetch({json.dumps(href)}, {{credentials: 'include'}});"
            "  if (!r.ok) throw new Error('HTTP ' + r.status);"
            "  const buf = await r.arrayBuffer();"
            "  let bin = '';"
            "  const bytes = new Uint8Array(buf);"
            "  for (let i = 0; i < bytes.length; i += 0x8000)"
            "    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));"
            "  return btoa(bin);"
            "})()",
            timeout=120,
        )
        target = out_dir / name
        target.write_bytes(base64.b64decode(b64))
        return target
    except Exception as e:
        rep.log("collect", "fetch_download_failed", href=href[:120], error=str(e)[:200])
        return None


async def collect(page: PageCdp, out_dir: Path, rep: Reporter, expect_model: str = "pro"):
    """收回复。第三个返回值 model_mismatch=True 表示回复的 model-slug 不含期望模型
    (收到的实际模型不对/疑似降级) —— 调用方据此并入 suspected_downgrade 走 exit 5
    (与生成时长降级判据互补: 发送时 verify_model 校验选择器, 这里复核实际出稿模型)。"""
    info = await _last_assistant(page)
    text = info["text"]
    (out_dir / "final_reply.md").write_text(text, encoding="utf-8")
    slug = info["slug"]
    model_mismatch = bool(expect_model and slug and expect_model not in slug.lower())
    rep.log("collect", "reply_saved", chars=len(text), model_slug=slug or "unknown",
            model_ok=not model_mismatch)
    if model_mismatch:
        await rep.attention(page, "collect",
                            f"reply model slug '{slug}' does not contain '{expect_model}' — "
                            "Pro may have been silently downgraded; review the deliverable critically")
    if info["count"] == 0:
        await rep.attention(page, "collect", "no assistant message found")
        return 0, 0, model_mismatch

    candidates = await page.js(_candidates_js(), timeout=15) or []
    rep.log("collect", "file_links_found", count=len(candidates),
            labels=[c["label"][:60] for c in candidates])

    got = 0
    for c in candidates:
        target = await _download_via_click(page, c["idx"], out_dir, rep)
        if target is None and (c["href"] or "").startswith("http"):
            name = c["label"] if FILE_EXT_RE.search(c["label"]) else f"attachment_{got + 1}"
            target = await _download_via_fetch(page, c["href"], name, out_dir, rep)
        if target is None:
            await rep.attention(page, "collect", f"could not download attachment: {c['label'] or c['href'][:80]}")
            continue
        info2 = {"file": target.name, "bytes": target.stat().st_size}
        if target.suffix == ".zip":
            info2["zip_ok"] = zipfile.is_zipfile(target)
            if info2["zip_ok"]:
                with zipfile.ZipFile(target) as zf:
                    info2["zip_entries"] = len(zf.namelist())
        rep.log("collect", "attachment_saved", **info2)
        got += 1
    return got, len(candidates), model_mismatch


# --------------------------------------------------------------------------- #
# attachment 通道 (旧模式备选): 包随消息发附件
# --------------------------------------------------------------------------- #
async def upload_files(page: PageCdp, paths: list[Path], rep: Reporter):
    """composer 附件上传: DOM.setFileInputFiles 喂真实路径 (composer 附件管道
    与来源区不同, 历史上 Playwright set_input_files 即此姿势, 一直可用)。"""
    doc = await page.call("DOM.getDocument", {"depth": 1})
    root_id = doc["root"]["nodeId"]
    found = await page.call("DOM.querySelectorAll",
                            {"nodeId": root_id, "selector": "input[type=file]"})
    node_ids = found.get("nodeIds") or []
    if not node_ids:
        raise RuntimeError("no file input found on page")
    str_paths = [str(p) for p in paths]
    attached = False
    for nid in node_ids:
        try:
            await page.call("DOM.setFileInputFiles", {"files": str_paths, "nodeId": nid}, timeout=60)
        except Exception:
            continue
        name_js = (
            "(() => document.body && document.body.innerText.includes("
            + json.dumps(paths[0].name) + "))()"
        )
        deadline = time.time() + 15
        while time.time() < deadline:
            if await page.js(name_js, timeout=10):
                attached = True
                break
            await asyncio.sleep(1)
        if attached:
            break
    if not attached:
        raise RuntimeError("setFileInputFiles on every candidate input, attachment card never appeared")
    rep.log("upload", "attached", files=[p.name for p in paths])

    deadline = time.time() + 600
    while time.time() < deadline:
        try:
            if (await page.js(_SEND_READY_JS, timeout=10)) == "ready":
                await asyncio.sleep(3)
                rep.log("upload", "ready")
                return
        except Exception:
            pass
        await asyncio.sleep(2)
    raise RuntimeError("upload did not become ready within 10 min")


# --------------------------------------------------------------------------- #
# 打包 / sources 通道 (子进程, 与浏览器层无关)
# --------------------------------------------------------------------------- #
def pack_repo(repo_root: Path, rep: Reporter, unique_name: bool = False) -> Path:
    """跑全项目单包构建脚本, 返回产出 zip 路径。

    unique_name=True (sources 通道默认): 把 builder 的固定名输出立刻复制成
    sha 前缀唯一名 (zmd_snapshot_<sha8>.zip) — 固定名输出会被并发会话的重打
    覆盖 (2026-06-12 r7 实测), 唯一名把这轮的字节钉死。"""
    builder = repo_root / "cc_context" / "review" / "build_v80_single_win.py"
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [sys.executable, str(builder)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"pack failed: {proc.stderr[-500:]}")
    pkg = sha = None
    for line in proc.stdout.splitlines():
        if line.startswith("package: "):
            pkg = Path(line.split("package: ", 1)[1].strip())
        elif line.startswith("sha256: "):
            sha = line.split("sha256: ", 1)[1].strip()
    if pkg is None or not pkg.is_file():
        raise RuntimeError(f"pack output not found in builder stdout: {proc.stdout[-300:]}")
    if unique_name and sha:
        unique = pkg.with_name(f"zmd_snapshot_{sha[:8]}.zip")
        if not unique.exists():
            unique.write_bytes(pkg.read_bytes())
        pkg = unique
    rep.log("pack", "built", package=str(pkg), sha256=sha,
            size_mb=round(pkg.stat().st_size / 1024 / 1024, 1))
    return pkg


def _reuse_tab_args(page: "PageCdp | None", args) -> list[str]:
    """dispatch 的 page 与 sources 上传同端点 (Edge 9222) 时, 让上传/枚举子进程复用
    dispatch 已开的 tab、且传完不关 — 一页到底, 不开空页不关页 (owner 2026-06-14)。
    dispatch 此刻阻塞等子进程, 其 page-ws 空闲, 子进程另开一条 ws 操作同 tab 不冲突。
    App 通道 (9224) 上传仍走 9222 网页端, tab 不通用 → 不复用 (子进程自开自关)。"""
    if (page is not None and page.tab_id
            and page.http_base.rstrip("/") == args.sources_cdp_http.rstrip("/")):
        return ["--reuse-tab-id", page.tab_id, "--no-close"]
    return []


def upload_to_sources(packages: list[Path], args, rep: Reporter, out_dir: Path,
                      page: "PageCdp | None" = None) -> bool:
    """sources 通道: 子进程调 upload_project_file.py 把包传到 Project 文件页来源区。
    **上传永远走网页端 (--sources-cdp-http), 与发送通道解耦** — App 的文件上传
    流程与网页端不同, 绝不能对 App 跑 (owner 2026-06-12 裁决)。
    page 同端点时复用其 tab (见 _reuse_tab_args)。"""
    uploader = Path(__file__).resolve().parent / "upload_project_file.py"
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    reuse = _reuse_tab_args(page, args)
    for i, pkg in enumerate(packages):
        cmd = [sys.executable, str(uploader), "--file", str(pkg),
               "--cdp-http", args.sources_cdp_http,
               "--project-url", args.project_url,
               "--out-dir", str(out_dir / f"sources_upload_{i}")] + reuse
        if i == 0 and not args.keep_old_snapshots:
            cmd.append("--replace")
        rep.log("sources_upload", "start", file=pkg.name,
                replace=(i == 0 and not args.keep_old_snapshots))
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env)
        tail = (proc.stdout or "").strip().splitlines()[-8:]
        rep.log("sources_upload", "done" if proc.returncode == 0 else "FAILED",
                file=pkg.name, exit_code=proc.returncode, tail=" | ".join(tail))
        if proc.returncode != 0:
            return False
    return True


def list_sources(args, rep: Reporter, out_dir: Path,
                 page: "PageCdp | None" = None) -> list[str] | None:
    """--list 枚举文件区 .zip 文件名 (网页端 page-ws)。None = 枚举本身失败。
    page 同端点时复用其 tab (不开空页)。"""
    uploader = Path(__file__).resolve().parent / "upload_project_file.py"
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [sys.executable, str(uploader), "--list",
         "--cdp-http", args.sources_cdp_http,
         "--project-url", args.project_url,
         "--out-dir", str(out_dir / "sources_list")] + _reuse_tab_args(page, args),
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    for line in (proc.stdout or "").splitlines():
        if line.startswith("SOURCES_JSON:"):
            try:
                return json.loads(line[len("SOURCES_JSON:"):])
            except json.JSONDecodeError:
                break
    rep.log("sources_list", "FAILED", exit_code=proc.returncode,
            tail=" | ".join((proc.stdout or "").strip().splitlines()[-4:]))
    return None


def verify_prompt_packages_in_sources(prompt_text: str, args, rep: Reporter,
                                      out_dir: Path, just_uploaded: bool,
                                      page: "PageCdp | None" = None) -> bool:
    """发送前防呆 (2026-06-12 教训: 假设包还在就发, 实际早被误删 → 白发一单):
    prompt 里指认的每个 .zip 必须真的在文件区。just_uploaded=True 时枚举失败仅
    WARN (上传子进程刚自验过持久化); prompt-only 模式枚举失败 = fail-closed。"""
    mentioned = sorted(set(re.findall(r"[\w.\-]+\.zip", prompt_text)))
    if not mentioned:
        return True
    names = list_sources(args, rep, out_dir, page=page)
    if names is None:
        if just_uploaded:
            rep.log("sources_verify", "WARN_list_failed",
                    note="上传子进程已自验持久化, 继续; 但 --list 失败值得查")
            return True
        rep.log("sources_verify", "FATAL", error="cannot enumerate Sources to verify prompt packages")
        return False
    missing = [n for n in mentioned if n not in names]
    rep.log("sources_verify", "ok" if not missing else "FATAL",
            mentioned=mentioned, in_sources=names, missing=missing)
    return not missing


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
async def run_dispatch(args, rep: Reporter, out_dir: Path, repo_root: Path) -> int:
    try:
        page = await attach_with_fallback(args, rep)
    except Exception as e:
        rep.log("attach", "FATAL", error=str(e)[:300],
                hint="run start_gpt_automation_chrome.ps1 first (browser and/or -App)")
        return 1
    if page.owns_tab:
        cleanup_stale_tabs(page.http_base, page.tab_id, rep)
    conv_url = args.resume or ""
    try:
        if args.resume:
            close_same_conversation_tabs(page.http_base, args.resume, page.tab_id, rep)
            await page.navigate(args.resume, settle_seconds=5)
            if not await assert_logged_in(page, rep):
                return 3
        else:
            packages = [Path(x).resolve() for x in args.package]
            for pkg in packages:
                if not pkg.is_file():
                    rep.log("init", "FATAL", error=f"package not found: {pkg}")
                    return 1
            if args.pack:
                packages.insert(0, pack_repo(repo_root, rep,
                                             unique_name=args.package_channel == "sources"))
            prompt_text = Path(args.prompt_file).read_text(encoding="utf-8")
            if args.package_channel == "sources":
                for pkg in packages:
                    if pkg.name not in prompt_text:
                        rep.log("sources_upload", "WARN_prompt_missing_filename",
                                file=pkg.name,
                                hint="prompt 没提到该包文件名 — GPT 可能找不到包, 确认 brief 指认正确")
                if packages and not upload_to_sources(packages, args, rep, out_dir, page=page):
                    await rep.attention(page, "sources_upload", "file-area upload failed — see sources_upload_* logs")
                    return 3
                if not verify_prompt_packages_in_sources(prompt_text, args, rep, out_dir,
                                                         just_uploaded=bool(packages), page=page):
                    await rep.attention(page, "sources_verify",
                                        "prompt-referenced package missing from Sources — upload it first")
                    return 3
            await page.navigate(args.project_url, settle_seconds=3)
            if not await assert_logged_in(page, rep):
                return 3
            await verify_model(page, rep)
            if args.package_channel == "attachment" and packages:
                await upload_files(page, packages, rep)
            conv_url = await fill_and_send(page, prompt_text, rep)

        gen_start = time.time()
        status, page = await wait_done(page, rep, args.timeout_hours, conv_url=conv_url,
                                       project_url=args.project_url)
        if not conv_url:
            # 发送时 URL 没及时切换 — 等待期 SPA 多半已经切了, 现在补记 (供 --resume / 重试导航)
            try:
                u = await page.url()
                if CONV_URL_RE.search(u):
                    conv_url = u
                    rep.log("send", "conversation_url_recovered", conversation_url=u)
            except Exception:
                pass
        if status == "timeout":
            page.owns_tab = False  # 留现场: 超时 tab 不回收, 便于 --resume / 手动续
            return 4
        if status == "attention":
            page.owns_tab = False
            return 3
        # 后台 tab 节流防呆 (2026-06-12 owner 抓的): 两个 dispatch 并发时, 被节流
        # 的后台 tab 前端停止渲染 DOM (停在回复第一个字符), GPT 服务端照常生成完;
        # done 判定后读到异常短回复 = 渲染挂起而非真短回复 → 重导航强制重渲染再读。
        try:
            _la = await _last_assistant(page)
            if len(_la.get("text", "")) < 50:
                rep.log("collect", "stalled_render_suspected", chars=len(_la.get("text", "")))
                refresh_url = conv_url or (await page.url())
                if refresh_url and CONV_URL_RE.search(refresh_url):
                    await page.navigate(refresh_url, settle_seconds=8)
                    _la2 = await _last_assistant(page)
                    rep.log("collect", "stalled_render_reread", chars=len(_la2.get("text", "")))
        except Exception:
            pass
        gen_elapsed = int(time.time() - gen_start)
        suspected_downgrade = False
        if args.min_gen_seconds and not args.resume:
            tries = 0
            while gen_elapsed < args.min_gen_seconds and tries < args.downgrade_retries:
                tries += 1
                rep.log("downgrade", "suspected_retrying", elapsed_s=gen_elapsed, retry=tries)
                # 刷新 = 重导航到会话 URL; 不知道会话 URL 时刷当前页 — 绝不能退到
                # project 主页, 那会把重试 prompt 发成一个全新会话 (丢上下文)
                refresh_url = conv_url
                if not refresh_url:
                    try:
                        refresh_url = await page.url()
                    except Exception:
                        refresh_url = ""
                if refresh_url:
                    await page.navigate(refresh_url, settle_seconds=5)
                n_before = (await _last_assistant(page))["count"]
                if not await send_followup(page, DOWNGRADE_RETRY_PROMPT, rep):
                    rep.log("downgrade", "retry_send_failed",
                            note="按疑似降级收尾 (exit 5), 交付不可信")
                    break
                gen_start = time.time()
                status, page = await wait_done(page, rep, args.timeout_hours,
                                               min_assistant_count=n_before + 1, conv_url=conv_url,
                                               project_url=args.project_url)
                if status != "done":
                    return 4 if status == "timeout" else 3
                gen_elapsed = int(time.time() - gen_start)
            if gen_elapsed < args.min_gen_seconds:
                suspected_downgrade = True
                await rep.attention(page, "downgrade",
                                    f"still finishing in {gen_elapsed}s after {args.downgrade_retries} "
                                    "retries — suspected silent Pro limit; "
                                    "FALLBACK: clipboard handoff for owner manual send")
        got, found, model_mismatch = await collect(page, out_dir, rep)
        if model_mismatch and args.min_gen_seconds:
            suspected_downgrade = True
            rep.log("downgrade", "model_slug_mismatch_escalated",
                    note="收到的回复 model-slug 不含 'pro' — 接收侧复核判降级, 按 exit 5 处置")
        rescue = 0
        while got == 0 and found > 0 and rescue < 2:
            rescue += 1
            if page.owns_tab:
                cleanup_stale_tabs(page.http_base, page.tab_id, rep)
            rep.log("rescue", "requesting_regeneration", attempt=rescue)
            n_before = (await _last_assistant(page))["count"]
            if not await send_followup(page, RESCUE_PROMPT, rep):
                await rep.attention(page, "rescue", "rescue followup could not be sent — "
                                    "attachments stay uncollected, resume manually")
                break
            status, page = await wait_done(page, rep, min(args.timeout_hours, 0.5),
                                           min_assistant_count=n_before + 1, conv_url=conv_url,
                                           project_url=args.project_url)
            if status != "done":
                return 4 if status == "timeout" else 3
            got, found, model_mismatch = await collect(page, out_dir, rep)
            if model_mismatch and args.min_gen_seconds:
                suspected_downgrade = True
        if page.owns_tab:
            cleanup_stale_tabs(page.http_base, page.tab_id, rep)
        # links_found 让 exit 2 的两种情况可区分: 真没附件 vs 附件在但没下下来
        rep.log("finish", "ok" if got else "no_attachments", attachments=got,
                links_found=found, rescues=rescue, suspected_downgrade=suspected_downgrade)
        if suspected_downgrade:
            page.owns_tab = False  # 交付不可信, 留现场
            return 5
        if not got:
            # 没收到附件 ≠ 没有附件 (可能是渲染挂起/读取误判) — 关掉现场会把
            # 还没下载的交付窗口带走 (2026-06-12 owner 抓的)。留 tab 便于复查。
            page.owns_tab = False
            rep.log("finish", "tab_kept_open", reason="no_attachments_collected")
            return 2
        return 0
    except Exception as e:
        await rep.attention(page, "fatal", f"unhandled: {e}")
        page.owns_tab = False  # 异常退出留现场
        return 3
    finally:
        await page.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", action="store_true", help="build the full-project single zip first and upload it")
    ap.add_argument("--package", action="append", default=[], help="zip to upload; repeatable")
    ap.add_argument("--package-channel", choices=["sources", "attachment"], default="sources",
                    help="发包通道: sources=上传 Project 文件页来源区+纯文字 prompt (默认, owner 裁决); "
                         "attachment=包随消息发附件 (旧模式备选)")
    ap.add_argument("--keep-old-snapshots", action="store_true",
                    help="sources 通道默认会先按白名单清掉来源区旧快照包 (保留依赖包); 加本旗标关闭清理")
    ap.add_argument("--prompt-file", help="markdown file with the prompt text")
    ap.add_argument("--resume", help="existing conversation URL: skip upload/send, just wait+collect")
    ap.add_argument("--out-dir", help="default: 补丁包/gpt_deliveries/<timestamp>")
    ap.add_argument("--project-url", default=PROJECT_URL)
    ap.add_argument("--cdp-url", default=CDP_URL,
                    help="发送通道 CDP HTTP 端点; 默认 Edge 9222 (失败自动落 App 9224), "
                         "App 通道传 http://localhost:9224 (先跑 start 脚本 -App)")
    ap.add_argument("--sources-cdp-http", default="http://localhost:9222",
                    help="文件区上传/枚举专用 web CDP 端点 — 上传只能走网页端 (App 上传流程不同), "
                         "与发送通道 --cdp-url 解耦")
    ap.add_argument("--timeout-hours", type=float, default=3.5)
    ap.add_argument("--min-gen-seconds", type=int, default=300,
                    help="生成耗时下限 (秒, 默认 300 — owner 经验: 真实审查/实现任务要 30min+, "
                         "5min 内完成 = 极大概率被静默降级)。轻量测试传 0 关闭")
    ap.add_argument("--downgrade-retries", type=int, default=1,
                    help="疑似降级时自动 重新导航+要求重新完整执行 的次数 (默认 1)")
    ap.add_argument("--cleanup-tabs", action="store_true",
                    help="运维模式: 关闭本 Project 下所有 chatgpt tab 后退出 "
                         "(⚠️ 在途任务的 tab 也会被关 — 仅在确认无在途 dispatch 时跑)")
    args = ap.parse_args()

    if args.cleanup_tabs:
        cleanup_project_tabs(args.cdp_url)
        return 0

    if not args.resume and not args.prompt_file:
        ap.error("either --resume, or --prompt-file (optionally with --pack/--package)")
    if (not args.resume and not args.package and not args.pack
            and args.package_channel == "attachment"):
        ap.error("attachment channel needs --pack/--package; "
                 "prompt-only send is a sources-channel mode (package already in the file area)")

    repo_root = Path(__file__).resolve().parents[3]
    # resolve() 必须有: out_dir 会喂给 Browser.setDownloadBehavior 的 downloadPath,
    # Edge 进程解析不了相对路径 (cwd 不是 repo root), 相对路径 = 下载全部 canceled
    out_dir = Path(args.out_dir).resolve() if args.out_dir else (
        repo_root / "补丁包" / "gpt_deliveries" / datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    rep = Reporter(out_dir)
    rep.log("init", "start", mode="resume" if args.resume else "dispatch",
            out_dir=str(out_dir), engine="raw-page-cdp")
    return asyncio.run(run_dispatch(args, rep, out_dir, repo_root))


if __name__ == "__main__":
    sys.exit(main())
