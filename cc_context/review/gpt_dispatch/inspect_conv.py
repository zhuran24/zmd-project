"""临时诊断: dump 会话最后一条 assistant 消息里附件卡片的 DOM 结构。"""
import re
import sys

from playwright.sync_api import sync_playwright

from dispatch_gpt_task import CDP_URL, SEL

url = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL)
    page = b.contexts[0].new_page()
    try:
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(6000)
        msgs = page.locator(SEL["assistant_msg"])
        print("assistant msgs:", msgs.count())
        if msgs.count() == 0:
            sys.exit(1)
        # 整条消息的"轮次"容器通常是 assistant_msg 的上层; 附件卡片可能渲染在正文容器之外
        turn = msgs.last.locator("xpath=ancestor::article[1]")
        scope = turn if turn.count() else msgs.last
        html = scope.inner_html()
        print("turn html chars:", len(html))
        idx = html.find("result.zip")
        print("result.zip at:", idx)
        if idx >= 0:
            print("--- context around result.zip ---")
            print(html[max(0, idx - 1500): idx + 800])
        else:
            print("--- whole html (first 4000) ---")
            print(html[:4000])
        # 候选可点元素统计
        for css in ("a[href]", "button", '[role="button"]'):
            loc = scope.locator(css)
            print(f"{css}: {loc.count()}")
            for i in range(min(loc.count(), 10)):
                el = loc.nth(i)
                txt = (el.inner_text() or "").strip().replace("\n", "|")[:60]
                aria = el.get_attribute("aria-label") or ""
                print(f"  [{i}] text={txt!r} aria={aria!r}")
    finally:
        page.close()
