"""探测自动化 Chrome 对「终末地」Project 的登录态。exit 0 = 已登录。"""
import sys

from playwright.sync_api import sync_playwright

from dispatch_gpt_task import CDP_URL, PROJECT_URL, SEL

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL)
    page = b.contexts[0].new_page()
    try:
        page.goto(PROJECT_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        if "auth" in page.url or "login" in page.url:
            print("NOT_LOGGED_IN")
            sys.exit(1)
        page.locator(SEL["composer"]).wait_for(state="visible", timeout=15000)
        print("LOGGED_IN")
        sys.exit(0)
    finally:
        page.close()
