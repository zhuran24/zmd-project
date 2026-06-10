"""第二层探测: browser 级 CDP Target.getTargets 看 App 全部 target (含隐藏的)。"""
import json

from playwright.sync_api import sync_playwright

APP_CDP_URL = "http://localhost:9224"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(APP_CDP_URL)
    session = b.new_browser_cdp_session()
    targets = session.send("Target.getTargets")
    infos = targets.get("targetInfos", [])
    print(f"targets: {len(infos)}")
    for t in infos:
        print(json.dumps({k: t.get(k) for k in ("type", "url", "title", "attached")},
                         ensure_ascii=False))
