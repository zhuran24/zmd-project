"""探测 ChatGPT 桌面 App (Electron) 的 CDP 通道与 DOM 同构性。

前置: App 以 --remote-debugging-port=9224 启动 (见 README App 通道段)。
验证: Playwright 可 attach + 页面 URL + composer/assistant 选择器是否与网页版同构。
"""
import sys

from playwright.sync_api import sync_playwright

from dispatch_gpt_task import SEL

APP_CDP_URL = "http://localhost:9224"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(APP_CDP_URL)
    print("contexts:", len(b.contexts))
    found_composer = False
    for ctx in b.contexts:
        for pg in ctx.pages:
            url = pg.url
            composer = pg.locator(SEL["composer"]).count()
            assistant = pg.locator(SEL["assistant_msg"]).count()
            print(f"page: {url[:100]}")
            print(f"  composer: {composer}  assistant_msgs: {assistant}")
            if composer:
                found_composer = True
    print("DOM_ISOMORPHIC:", found_composer)
    sys.exit(0 if found_composer else 1)
