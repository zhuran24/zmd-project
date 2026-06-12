"""往 ChatGPT Project 文件页 (来源区) 上传包 — 文件页递交通道 (2026-06-12 owner 裁决)。

包不再随消息发附件, 而是上传到 Project 的「来源」文件区; prompt 里指认文件名 + sha256。
本脚本只管上传 + 验证条目出现, 不发送任何消息、不触发生成。

用法 (前置: Edge 带 CDP 9222, start_gpt_automation_chrome.ps1):
    python upload_project_file.py --file <包.zip>
    python upload_project_file.py --file <包.zip> --project-url <URL> --cdp-url http://localhost:9224

退出码: 0=上传成功(来源列表同名条目 +1)  1=环境/参数错误  3=异常(看 attention 截图)
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

CDP_URL = "http://localhost:9222"
PROJECT_URL = "https://chatgpt.com/g/g-p-69b585dfc29c819186b93a166f5266a5-zhong-mo-di/project"

ADD_SOURCE_TEXTS = ["添加源", "添加来源", "Add source", "Add sources", "添加文件", "Add files"]
UPLOAD_MENU_TEXTS = ["上传", "从计算机", "Upload", "computer"]
SOURCES_TAB_TEXTS = ["来源", "Sources", "文件", "Files"]


def log(stage: str, status: str, **kw):
    ts = datetime.now().isoformat(timespec="seconds")
    extra = " ".join(f"{k}={v}" for k, v in kw.items())
    print(f"[{ts}] {stage}: {status} {extra}", flush=True)


def shoot(page, out_dir: Path, tag: str) -> str | None:
    try:
        path = out_dir / f"{tag}.png"
        page.screenshot(path=str(path), full_page=False)
        return str(path)
    except Exception:
        return None


def count_entries(page, filename: str) -> int:
    try:
        return page.locator(f'text="{filename}"').count()
    except Exception:
        return -1


def click_sources_tab(page):
    """项目页默认可能停在「聊天」tab — 切到「来源」tab (找不到也不致命,
    添加源按钮可能本来就在视口里)。"""
    for t in SOURCES_TAB_TEXTS:
        try:
            tab = page.locator(
                f'button:has-text("{t}"), [role="tab"]:has-text("{t}")'
            ).first
            if tab.is_visible(timeout=1500):
                tab.click()
                page.wait_for_timeout(1000)
                log("nav", "sources_tab_clicked", text=t)
                return
        except Exception:
            continue
    log("nav", "sources_tab_not_found_continuing")


def open_file_chooser(page, out_dir: Path):
    """点「添加源」拿原生 file chooser。两种形态都接:
    a) 点按钮直接弹 chooser; b) 点按钮先出菜单, 再点「上传」类菜单项弹 chooser。"""
    add_btn = None
    for t in ADD_SOURCE_TEXTS:
        cand = page.locator(f'button:has-text("{t}"), [role="button"]:has-text("{t}")').first
        try:
            if cand.is_visible(timeout=1500):
                add_btn = cand
                log("upload", "add_source_button_found", text=t)
                break
        except Exception:
            continue
    if add_btn is None:
        shoot(page, out_dir, "attention_no_add_button")
        raise RuntimeError("add-source button not found on project page")

    # 形态 a: 点击直接弹 chooser
    try:
        with page.expect_file_chooser(timeout=5000) as fc:
            add_btn.click()
        log("upload", "chooser_direct")
        return fc.value
    except PWTimeout:
        pass

    # 形态 b: 点击后出菜单, 找「上传」菜单项
    page.wait_for_timeout(800)
    for t in UPLOAD_MENU_TEXTS:
        item = page.locator(
            f'[role="menuitem"]:has-text("{t}"), [role="option"]:has-text("{t}"), '
            f'button:has-text("{t}")'
        ).first
        try:
            if not item.is_visible(timeout=1500):
                continue
            with page.expect_file_chooser(timeout=8000) as fc:
                item.click()
            log("upload", "chooser_via_menu", text=t)
            return fc.value
        except Exception:
            continue
    shoot(page, out_dir, "attention_no_chooser")
    raise RuntimeError("clicked add-source but no file chooser appeared (menu shape changed?)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="path of the package to upload")
    ap.add_argument("--project-url", default=PROJECT_URL)
    ap.add_argument("--cdp-url", default=CDP_URL)
    ap.add_argument("--timeout-minutes", type=float, default=10.0,
                    help="upload settle timeout (entry must appear in the sources list)")
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

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(args.cdp_url)
            ctx = browser.contexts[0]
            page = ctx.new_page()
        except Exception as e:
            log("attach", "FATAL", error=str(e)[:200], hint="run start_gpt_automation_chrome.ps1 first")
            return 1
        try:
            page.goto(args.project_url, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            if "auth" in page.url or "login" in page.url:
                shoot(page, out_dir, "attention_login")
                log("nav", "FATAL", error="redirected to login")
                return 3
            click_sources_tab(page)
            before = count_entries(page, pkg.name)
            log("upload", "entries_before", count=before)

            chooser = open_file_chooser(page, out_dir)
            chooser.set_files(str(pkg))
            log("upload", "file_set", file=pkg.name)

            deadline = time.time() + args.timeout_minutes * 60
            settled = False
            while time.time() < deadline:
                now = count_entries(page, pkg.name)
                if now > max(before, 0):
                    settled = True
                    break
                time.sleep(3)
            shot = shoot(page, out_dir, "final_state")
            if not settled:
                log("upload", "TIMEOUT", error="new entry never appeared in sources list",
                    screenshot=shot)
                return 3
            # 条目出现后再等一拍让后端处理收尾 (zip 显示「文件内容可能无法访问」属正常)
            page.wait_for_timeout(5000)
            log("upload", "ok", entries_now=count_entries(page, pkg.name), screenshot=shot)
            return 0
        except Exception as e:
            shoot(page, out_dir, "attention_fatal")
            log("fatal", "unhandled", error=str(e)[:300])
            return 3
        finally:
            try:
                if len(ctx.pages) > 1:
                    page.close()
                else:
                    page.goto("about:blank")
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
