"""GPT Pro 外发全流程自动化: 发包 + 发 prompt + 等完成 + 收交付。

发包通道 (--package-channel, 2026-06-12 owner 裁决默认 sources):
    sources    = 包上传到 Project 文件页「来源区」(子进程调 upload_project_file.py,
                 page 级 CDP, 分块灌字节), 消息只发纯文字 prompt — prompt 必须自己
                 指认文件区包文件名 + sha256 (本脚本不代写)。默认先按白名单清旧快照
                 (保留依赖包), --keep-old-snapshots 关闭清理。同名已在 → 幂等跳过。
    attachment = 旧模式: 包随消息当附件发 (会话内传大附件疑似风控诱因, 仅留作备选)。

用法:
    # 前置: 专用 Chrome 已起 (start_gpt_automation_chrome.ps1, 首次需手动登录一次)
    python dispatch_gpt_task.py --package X.zip --prompt-file prompt.md   # 默认 sources 通道
    python dispatch_gpt_task.py --pack --prompt-file prompt.md            # 打包再发 (sources 下自动改唯一名)
    python dispatch_gpt_task.py --package X.zip --prompt-file p.md --package-channel attachment
    python dispatch_gpt_task.py --resume https://chatgpt.com/.../c/<id>   # 重连续等/补收

输出 (--out-dir, 默认 补丁包/gpt_deliveries/<时间戳>/):
    final_reply.md     GPT 最后回复全文
    <附件原名>          回复里的全部文件附件
    run_log.jsonl      各阶段时间戳/状态 (心跳每分钟一条, 可 tail 监控)
    attention_*.png/html  非预期状态的现场截图 + DOM dump (托底用)

退出码: 0=交付到手  2=完成但无附件(看 final_reply.md)  3=异常需托底  4=超时  1=环境错误

完成检测 (双信号 + 稳定窗口):
    信号1 = 停止生成按钮消失; 信号2 = 最后一条回复文本长度连续 STABLE_TICKS 次轮询不变。
    两信号同时满足才判完成。「继续生成」按钮出现会自动点击。
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

CDP_URL = "http://localhost:9222"
PROJECT_URL = "https://chatgpt.com/g/g-p-69b585dfc29c819186b93a166f5266a5-zhong-mo-di/project"
CONV_URL_RE = re.compile(r"/c/[0-9a-f-]{10,}")

POLL_SECONDS = 10
STABLE_TICKS = 3
HEARTBEAT_TICKS = 6  # 每 ~1 分钟一条心跳日志

SEL = {
    "composer": "#prompt-textarea",
    "send_btn": 'button[data-testid="send-button"]',
    "stop_btn": 'button[data-testid="stop-button"]',
    "assistant_msg": 'div[data-message-author-role="assistant"]',
    "file_input": 'input[type="file"]',
    "model_btn_texts": ["专业", "Pro", "进阶"],
    "error_texts": ["出错了", "Something went wrong", "网络错误"],
}
FILE_EXT_RE = re.compile(
    r"\.(zip|7z|tar|gz|tgz|md|py|json|patch|diff|txt|csv|log|whl)(\?|$)", re.I
)


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
        print(f"[{entry['ts']}] {stage}: {status} {kw if kw else ''}", flush=True)

    def attention(self, page, stage: str, reason: str):
        """非预期状态: 截图 + DOM dump + 日志, 供托底接手。不抛异常。"""
        self.attention_count += 1
        tag = f"attention_{self.attention_count:02d}_{stage}"
        shot, dump = None, None
        try:
            shot = str(self.out_dir / f"{tag}.png")
            page.screenshot(path=shot, full_page=False)
        except Exception:
            shot = None
        try:
            dump = str(self.out_dir / f"{tag}.html")
            Path(dump).write_text(page.content(), encoding="utf-8")
        except Exception:
            dump = None
        self.log(stage, "NEEDS_ATTENTION", reason=reason, screenshot=shot, dom_dump=dump, url=page.url)


def attach(p, cdp_url: str = CDP_URL):
    """返回 (ctx, page, owns_page)。浏览器通道开自己的新 tab (owns=True);
    ChatGPT 桌面 App (Electron, 9224) 不支持 new_page — 复用主窗口页面
    (owns=False, 结束时不能关它, 关了 App 就空了)。"""
    browser = p.chromium.connect_over_cdp(cdp_url)
    if not browser.contexts:
        raise RuntimeError("no browser context on " + cdp_url)
    ctx = browser.contexts[0]
    try:
        page = ctx.new_page()
        return ctx, page, True
    except Exception:
        if not ctx.pages:
            raise RuntimeError("cannot create a page and none exists on " + cdp_url)
        return ctx, ctx.pages[0], False


def cleanup_stale_tabs(ctx, page, rep: Reporter):
    """只清理下载残留页 (/mnt/data 404 之类) — 连的是用户日常 Edge 主实例,
    绝不能动用户自己开的 chatgpt 标签页。脚本自己的 page 由 finally 自关。"""
    closed = 0
    for pg in list(ctx.pages):
        if pg is page:
            continue
        try:
            if "/mnt/data" in pg.url:
                pg.close()
                closed += 1
        except Exception:
            pass
    if closed:
        rep.log("init", "stale_download_tabs_closed", count=closed)


def assert_logged_in(page, rep: Reporter) -> bool:
    if "auth" in page.url or "login" in page.url:
        rep.attention(page, "login", "redirected to login page — log in once in the automation Chrome")
        return False
    return True


def verify_model(page, rep: Reporter):
    for text in SEL["model_btn_texts"]:
        try:
            if page.locator(f'button:has-text("{text}")').first.is_visible(timeout=2000):
                rep.log("model", "ok", matched=text)
                return
        except Exception:
            continue
    rep.attention(page, "model", "model selector text does not look like Pro — verify manually; proceeding anyway")


def upload_files(page, paths: list[Path], rep: Reporter):
    inputs = page.locator(SEL["file_input"])
    n = inputs.count()
    if n == 0:
        raise RuntimeError("no file input found on page")
    str_paths = [str(p) for p in paths]
    attached = False
    for i in range(n):
        try:
            inputs.nth(i).set_input_files(str_paths)
        except Exception:
            continue
        try:
            page.locator(f'text="{paths[0].name}"').first.wait_for(state="visible", timeout=15000)
            attached = True
            break
        except PWTimeout:
            continue
    if not attached:
        raise RuntimeError("set_input_files on every candidate input, attachment card never appeared")
    rep.log("upload", "attached", files=[p.name for p in paths], input_index=i)

    deadline = time.time() + 600
    while time.time() < deadline:
        try:
            if page.locator(f'{SEL["send_btn"]}:not([disabled])').count() > 0:
                time.sleep(3)
                rep.log("upload", "ready")
                return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError("upload did not become ready within 10 min")


def fill_and_send(page, prompt_text: str, rep: Reporter) -> str:
    page.locator(SEL["composer"]).click()
    page.keyboard.insert_text(prompt_text)
    time.sleep(1)
    rep.log("prompt", "filled", chars=len(prompt_text))
    page.locator(SEL["send_btn"]).click()
    try:
        page.wait_for_url(CONV_URL_RE, timeout=60000)
    except PWTimeout:
        rep.attention(page, "send", "URL did not switch to a conversation within 60s")
    conv_url = page.url
    rep.log("send", "sent", conversation_url=conv_url)
    return conv_url


RESCUE_PROMPT = (
    "刚才下载附件时返回 404——沙盒文件应该已被回收。"
    "请重新运行生成步骤重建该文件,并再次作为文件附件给出(文件名保持不变)。回复简短即可。"
)

DOWNGRADE_RETRY_PROMPT = (
    "上一条回复的生成时间异常短,怀疑没有走完整的 Pro 推理。"
    "请重新完整执行原任务:重新分析、重新生成全部交付文件,不要复用上一次的结论。"
)


def send_followup(page, text: str, rep: Reporter):
    page.locator(SEL["composer"]).click()
    page.keyboard.insert_text(text)
    time.sleep(0.5)
    page.locator(SEL["send_btn"]).click()
    rep.log("rescue", "followup_sent", chars=len(text))


def _close_stray_download_tabs(page):
    """点击 sandbox 链接会开出 /mnt/data 新标签页 (常 404), 收完顺手关掉。"""
    for pg in list(page.context.pages):
        if pg is page:
            continue
        try:
            if "/mnt/data" in pg.url or pg.url.rstrip("/").endswith((".zip", ".7z", ".tar", ".gz")):
                pg.close()
        except Exception:
            pass


def _stop_visible(page) -> bool:
    try:
        if page.locator(SEL["stop_btn"]).count() > 0:
            return True
        for label in ("停止", "Stop streaming", "Stop generating"):
            if page.locator(f'button[aria-label*="{label}"]').count() > 0:
                return True
    except Exception:
        pass
    return False


def _last_assistant_text(page) -> str:
    try:
        msgs = page.locator(SEL["assistant_msg"])
        if msgs.count() == 0:
            return ""
        return msgs.last.inner_text(timeout=5000)
    except Exception:
        return ""


def _last_model_slug(page) -> str:
    """回复 DOM 上的模型标识。注意: Pro 静默降级时这里可能照样写 pro (路由层
    降级不改前端元数据), 只作参考记录, 真正的降级检测靠行为侧信号 (生成耗时)。"""
    try:
        msgs = page.locator(SEL["assistant_msg"])
        if msgs.count():
            return msgs.last.get_attribute("data-message-model-slug") or ""
    except Exception:
        pass
    return ""


_THINKING_RE = re.compile(r"(思考[用耗]?时?\s*\d+|Thought for\s+\d+[^\n]{0,20}|Reasoned for\s+\d+[^\n]{0,20})")


def _thinking_marker(page) -> str:
    """抓 Pro 回复的思考块时长文本 (行为旁证, 降级模型不会有长思考块)。"""
    try:
        turn = page.locator(SEL["assistant_msg"]).last.locator("xpath=ancestor::article[1]")
        scope = turn if turn.count() else page.locator(SEL["assistant_msg"]).last
        m = _THINKING_RE.search(scope.inner_text(timeout=5000) or "")
        return m.group(0) if m else ""
    except Exception:
        return ""


def _page_alive(page) -> bool:
    try:
        page.evaluate("document.readyState")
        return True
    except Exception:
        return False


def _revive_page(page, rep: Reporter, reason: str):
    """网络抖动/渲染进程挂死导致页面卡住的恢复 (owner 处方): 同 URL 新开一个
    页面, 关掉老的。比 page.reload 可靠 — 渲染进程挂死时 reload 自己也会卡。
    恢复失败 (网络还断着) 则返回旧 page, 下一拍再试。"""
    url = page.url
    ctx = page.context
    new_page = None
    try:
        new_page = ctx.new_page()
        new_page.goto(url, wait_until="domcontentloaded", timeout=60000)
        new_page.wait_for_timeout(3000)
    except Exception as e:
        rep.log("waiting", "page_revive_failed", error=str(e)[:150])
        if new_page is not None:
            try:
                new_page.close()
            except Exception:
                pass
        # App (Electron) 通道开不了新页 — 退而求其次试 reload
        try:
            page.reload(wait_until="domcontentloaded", timeout=60000)
            rep.log("waiting", "page_reloaded_in_place", reason=reason)
        except Exception:
            pass
        return page
    try:
        page.close()
    except Exception:
        pass
    rep.log("waiting", "page_revived", reason=reason, url=url)
    return new_page


def wait_done(page, rep: Reporter, timeout_hours: float, min_assistant_count: int = 1):
    """返回 (status, page); status = 'done' | 'timeout' | 'attention'。
    page 可能被换新 — 页面卡住时同 URL 重开, 调用方必须用返回的 page 继续。
    min_assistant_count: 完成判定要求 assistant 消息数达到该值 — 发送/救援后必须
    等到新回复出现, 否则旧消息的稳定文本会被误判为完成。"""
    deadline = time.time() + timeout_hours * 3600
    start = time.time()
    stable = 0
    last_len = -1
    tick = 0
    dead_ticks = 0
    revives = 0
    while time.time() < deadline:
        tick += 1
        if not _page_alive(page):
            dead_ticks += 1
            if dead_ticks >= 2:  # 连续 ~20s 无响应才动手, 单拍抖动不折腾
                if revives >= 3:
                    rep.attention(page, "waiting", "page unresponsive after 3 revives — network likely down")
                    return "attention", page
                page = _revive_page(page, rep, "page unresponsive")
                revives += 1
                dead_ticks = 0
                stable, last_len = 0, -1
            time.sleep(POLL_SECONDS)
            continue
        dead_ticks = 0
        if not assert_logged_in(page, rep):
            return "attention", page
        generating = _stop_visible(page)
        text = _last_assistant_text(page)
        cur_len = len(text)
        has_turn = page.locator(SEL["assistant_msg"]).count() >= min_assistant_count
        if not generating and has_turn and cur_len == last_len:
            stable += 1
            if stable >= STABLE_TICKS:
                rep.log("waiting", "done", elapsed_s=int(time.time() - start), reply_chars=cur_len,
                        thinking_marker=_thinking_marker(page) or "none")
                return "done", page
        else:
            stable = 0
        if not generating and cur_len == 0 and time.time() - start > 300:
            for t in SEL["error_texts"]:
                if page.locator(f'text="{t}"').count() > 0:
                    rep.attention(page, "waiting", f"error banner detected: {t}")
                    return "attention", page
        last_len = cur_len
        if tick % HEARTBEAT_TICKS == 0:
            rep.log("waiting", "heartbeat", elapsed_s=int(time.time() - start),
                    generating=generating, reply_chars=cur_len)
        time.sleep(POLL_SECONDS)
    rep.attention(page, "waiting", f"timed out after {timeout_hours}h")
    return "timeout", page


def _download_via_click(page, link, out_dir: Path, rep: Reporter) -> Path | None:
    """点击附件, 在 CDP 浏览器层捕获下载 (Browser.setDownloadBehavior 直接落盘到
    out_dir, 任何标签页触发都能抓到 — Playwright 的 page/context download 事件在
    「新标签页秒开秒关触发下载」场景下收不到)。点击带重试: resume 重载后的页面
    JS handler 可能未挂载, 首次点击会无反应。"""
    session = page.context.browser.new_browser_cdp_session()
    state: dict = {}

    def on_begin(e):
        if "guid" not in state:
            state["guid"] = e["guid"]
            state["name"] = e.get("suggestedFilename") or "download.bin"

    def on_progress(e):
        if e.get("guid") == state.get("guid"):
            if e.get("state") == "completed":
                state["done"] = True
            elif e.get("state") == "canceled":
                state["canceled"] = True

    session.on("Browser.downloadWillBegin", on_begin)
    session.on("Browser.downloadProgress", on_progress)
    session.send(
        "Browser.setDownloadBehavior",
        {"behavior": "allowAndName", "downloadPath": str(out_dir), "eventsEnabled": True},
    )
    confirm = page.locator('button:has-text("打开链接"), button:has-text("Open link")').first

    def _click_confirm_if_visible(wait_ms: int) -> bool:
        try:
            confirm.wait_for(state="visible", timeout=wait_ms)
            confirm.click()
            rep.log("collect", "confirmed_external_link_dialog")
            return True
        except Exception:
            return False

    try:
        for attempt in range(1, 4):
            # 上一轮点击可能弹出的「外部网站」确认框还挡在屏上 — 先处理它,
            # 否则重试 click 会被 modal 拦截 hit-target 卡到超时
            if not _click_confirm_if_visible(1000):
                try:
                    link.click(timeout=10000)
                except Exception as e:
                    rep.log("collect", "click_blocked", attempt=attempt, error=str(e)[:120])
                    page.keyboard.press("Escape")
                    continue
                _click_confirm_if_visible(4000)
            t0 = time.time()
            while time.time() - t0 < 12 and "guid" not in state:
                page.wait_for_timeout(400)
            if "guid" in state:
                break
            rep.log("collect", "click_retry", attempt=attempt)
        if "guid" not in state:
            rep.log("collect", "click_download_failed", error="no downloadWillBegin after 3 clicks")
            page.keyboard.press("Escape")
            return None
        t0 = time.time()
        while time.time() - t0 < 180 and not state.get("done") and not state.get("canceled"):
            page.wait_for_timeout(500)
        if not state.get("done"):
            rep.log("collect", "click_download_failed",
                    error=f"download did not complete (canceled={state.get('canceled', False)})")
            return None
        src = out_dir / state["guid"]  # allowAndName 模式落盘名 = guid
        target = out_dir / state["name"]
        if target.exists():
            target = out_dir / f"{int(time.time())}_{state['name']}"
        src.rename(target)
        return target
    except Exception as e:
        rep.log("collect", "click_download_failed", error=str(e)[:200])
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        return None
    finally:
        try:
            session.detach()
        except Exception:
            pass


def _download_via_fetch(page, href: str, name: str, out_dir: Path, rep: Reporter) -> Path | None:
    try:
        b64 = page.evaluate(
            """async (url) => {
                const r = await fetch(url, {credentials: 'include'});
                if (!r.ok) throw new Error('HTTP ' + r.status);
                const buf = await r.arrayBuffer();
                let bin = '';
                const bytes = new Uint8Array(buf);
                for (let i = 0; i < bytes.length; i += 0x8000)
                    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
                return btoa(bin);
            }""",
            href,
        )
        target = out_dir / name
        target.write_bytes(base64.b64decode(b64))
        return target
    except Exception as e:
        rep.log("collect", "fetch_download_failed", href=href[:120], error=str(e)[:200])
        return None


def collect(page, out_dir: Path, rep: Reporter, expect_model: str = "pro"):
    text = _last_assistant_text(page)
    (out_dir / "final_reply.md").write_text(text, encoding="utf-8")
    slug = _last_model_slug(page)
    rep.log("collect", "reply_saved", chars=len(text), model_slug=slug or "unknown")
    if expect_model and slug and expect_model not in slug.lower():
        rep.attention(page, "collect",
                      f"reply model slug '{slug}' does not contain '{expect_model}' — "
                      "Pro may have been silently downgraded; review the deliverable critically")

    msgs = page.locator(SEL["assistant_msg"])
    if msgs.count() == 0:
        rep.attention(page, "collect", "no assistant message found")
        return 0
    # sandbox 文件的渲染形态至少有三种, 都要覆盖:
    #   <a href="...">name.zip</a>             经典链接
    #   <a class="decorated-link">...</a>      无 href, JS 点击下载
    #   <button class="behavior-btn">...</button> 内联文件引用
    # 锚文本可能是中文描述 (「下载 V81 审查交付 zip」) 而非文件名 — 不能只靠
    # 扩展名匹配, 结构 class (behavior-btn / decorated-link) 是更可靠的判据
    # (V81 实测: 只按扩展名漏掉 3 个附件里的 2 个, 恰好包括完整包)。
    last = msgs.last
    candidates = []
    seen_labels = set()
    for css in ("a", "button"):
        elems = last.locator(css)
        for i in range(elems.count()):
            el = elems.nth(i)
            try:
                href = el.get_attribute("href") or ""
                label = (el.inner_text() or "").strip()
                cls = el.get_attribute("class") or ""
            except Exception:
                continue
            file_like = (
                FILE_EXT_RE.search(href) or FILE_EXT_RE.search(label)
                or "sandbox" in href
                or "behavior-btn" in cls or "decorated-link" in cls
            )
            if not file_like:
                continue
            if not label and not href:
                continue  # 空文本按钮 (代码块「复制」等) 不是文件
            key = label or href
            if key in seen_labels:
                continue
            seen_labels.add(key)
            candidates.append((el, href, label))
    rep.log("collect", "file_links_found", count=len(candidates),
            labels=[c[2][:60] for c in candidates])

    got = 0
    for link, href, label in candidates:
        target = _download_via_click(page, link, out_dir, rep)
        if target is None and href.startswith("http"):
            name = label if FILE_EXT_RE.search(label) else f"attachment_{got + 1}"
            target = _download_via_fetch(page, href, name, out_dir, rep)
        if target is None:
            rep.attention(page, "collect", f"could not download attachment: {label or href[:80]}")
            continue
        info = {"file": target.name, "bytes": target.stat().st_size}
        if target.suffix == ".zip":
            info["zip_ok"] = zipfile.is_zipfile(target)
            if info["zip_ok"]:
                with zipfile.ZipFile(target) as zf:
                    info["zip_entries"] = len(zf.namelist())
        rep.log("collect", "attachment_saved", **info)
        got += 1
    return got, len(candidates)


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


def upload_to_sources(packages: list[Path], args, rep: Reporter, out_dir: Path) -> bool:
    """sources 通道: 子进程调 upload_project_file.py 把包传到 Project 文件页来源区。
    子进程用 page 级 CDP websocket, 与本脚本的 Playwright browser 级连接互不干扰。
    返回 True=全部成功 (含同名幂等跳过)。"""
    uploader = Path(__file__).resolve().parent / "upload_project_file.py"
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    for i, pkg in enumerate(packages):
        cmd = [sys.executable, str(uploader), "--file", str(pkg),
               "--cdp-http", args.cdp_url,
               "--project-url", args.project_url,
               "--out-dir", str(out_dir / f"sources_upload_{i}")]
        # 仅第一个包做旧快照清理 (白名单保留依赖包); 后续包追加不再清
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
                    help="CDP 端点; 浏览器通道默认 9222, ChatGPT 桌面 App 通道传 http://localhost:9224 (先跑 start 脚本 -App)")
    ap.add_argument("--timeout-hours", type=float, default=3.5)
    ap.add_argument("--min-gen-seconds", type=int, default=300,
                    help="生成耗时下限 (秒, 默认 300 — owner 经验: 真实审查/实现任务要 30min+, 5min 内完成 = 极大概率被静默降级; 2026-06-11 实测 70s 降级回复溜过旧 60s 判据成 exit 2)。轻量测试传 0 关闭")
    ap.add_argument("--downgrade-retries", type=int, default=1,
                    help="疑似降级时自动 刷新页面+要求重新完整执行 的次数 (默认 1); 用尽仍快则报 attention 建议换 Edge")
    args = ap.parse_args()

    if not args.resume and not ((args.package or args.pack) and args.prompt_file):
        ap.error("either --resume, or --prompt-file plus --pack/--package")

    repo_root = Path(__file__).resolve().parents[3]
    out_dir = Path(args.out_dir) if args.out_dir else (
        repo_root / "补丁包" / "gpt_deliveries" / datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    rep = Reporter(out_dir)
    rep.log("init", "start", mode="resume" if args.resume else "dispatch", out_dir=str(out_dir))

    with sync_playwright() as p:
        try:
            ctx, page, owns_page = attach(p, args.cdp_url)
        except Exception as e:
            rep.log("attach", "FATAL", error=str(e)[:300],
                    hint="run start_gpt_automation_chrome.ps1 first")
            return 1
        rep.log("attach", "ok", cdp_url=args.cdp_url, owns_page=owns_page)
        cleanup_stale_tabs(ctx, page, rep)
        try:
            if args.resume:
                page.goto(args.resume, wait_until="domcontentloaded")
                page.wait_for_timeout(5000)
                if not assert_logged_in(page, rep):
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
                if args.package_channel == "sources" and packages:
                    # 文件区通道: 先把包传上来源区 (子进程, page 级 CDP), 消息只发纯文字。
                    # prompt 应已指认文件区包文件名 + sha256 — 这里做一道防呆提醒。
                    for pkg in packages:
                        if pkg.name not in prompt_text:
                            rep.log("sources_upload", "WARN_prompt_missing_filename",
                                    file=pkg.name,
                                    hint="prompt 没提到该包文件名 — GPT 可能找不到包, 确认 brief 指认正确")
                    if not upload_to_sources(packages, args, rep, out_dir):
                        rep.attention(page, "sources_upload", "file-area upload failed — see sources_upload_* logs")
                        return 3
                page.goto(args.project_url, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                if not assert_logged_in(page, rep):
                    return 3
                page.locator(SEL["composer"]).wait_for(state="visible", timeout=30000)
                verify_model(page, rep)
                if args.package_channel == "attachment" and packages:
                    upload_files(page, packages, rep)
                fill_and_send(page, prompt_text, rep)

            gen_start = time.time()
            status, page = wait_done(page, rep, args.timeout_hours)
            if status == "timeout":
                return 4
            if status == "attention":
                return 3
            gen_elapsed = int(time.time() - gen_start)
            # 疑似静默降级 (owner 经验: 真实任务完整生成 <1min 极大概率被限) →
            # 阶梯处置: 刷新页面 + 要求重新完整执行; 用尽重试仍快 → attention 建议换 Edge
            suspected_downgrade = False
            if args.min_gen_seconds and not args.resume:
                tries = 0
                while gen_elapsed < args.min_gen_seconds and tries < args.downgrade_retries:
                    tries += 1
                    rep.log("downgrade", "suspected_retrying", elapsed_s=gen_elapsed, retry=tries)
                    page.reload(wait_until="domcontentloaded")
                    page.wait_for_timeout(5000)
                    n_before = page.locator(SEL["assistant_msg"]).count()
                    send_followup(page, DOWNGRADE_RETRY_PROMPT, rep)
                    gen_start = time.time()
                    status, page = wait_done(page, rep, args.timeout_hours,
                                             min_assistant_count=n_before + 1)
                    if status != "done":
                        return 4 if status == "timeout" else 3
                    gen_elapsed = int(time.time() - gen_start)
                if gen_elapsed < args.min_gen_seconds:
                    suspected_downgrade = True
                    rep.attention(page, "downgrade",
                                  f"still finishing in {gen_elapsed}s after {args.downgrade_retries} "
                                  "retries — suspected silent Pro limit on this automation Chrome; "
                                  "FALLBACK: re-dispatch via the Claude-in-Chrome plugin channel "
                                  "(Edge, already logged in) — Claude handles that directly")
            got, found = collect(page, out_dir, rep)
            # 救援: 找到了附件候选却一个都没下载到 (sandbox 文件回收后 404),
            # 让 GPT 重新生成一次再收。最多两轮。
            rescue = 0
            while got == 0 and found > 0 and rescue < 2:
                rescue += 1
                _close_stray_download_tabs(page)
                rep.log("rescue", "requesting_regeneration", attempt=rescue)
                n_before = page.locator(SEL["assistant_msg"]).count()
                send_followup(page, RESCUE_PROMPT, rep)
                status, page = wait_done(page, rep, min(args.timeout_hours, 0.5),
                                         min_assistant_count=n_before + 1)
                if status != "done":
                    return 4 if status == "timeout" else 3
                got, found = collect(page, out_dir, rep)
            _close_stray_download_tabs(page)
            rep.log("finish", "ok" if got else "no_attachments", attachments=got, rescues=rescue,
                    suspected_downgrade=suspected_downgrade)
            if suspected_downgrade:
                return 5
            return 0 if got else 2
        except Exception as e:
            rep.attention(page, "fatal", f"unhandled: {e}")
            return 3
        finally:
            try:
                _close_stray_download_tabs(page)
                if not owns_page:
                    pass  # App 通道复用主窗口页面, 关了 App 就空了 — 留在原地
                elif len(page.context.pages) <= 1:
                    # 自己是最后一个 tab: 关掉会把整个浏览器带退、CDP 断 — 留空白页保活
                    page.goto("about:blank")
                else:
                    page.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
