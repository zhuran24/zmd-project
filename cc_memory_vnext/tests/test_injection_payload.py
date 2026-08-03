# -*- coding: utf-8 -*-
"""注入载荷回归:注 frontmatter summary,不注 body 首行(2026-08-03 普查 §3.4 第 1 项)。

不接 CI(preflight 快 lane 只跑 src/tests);手跑:
    python -m pytest -p no:randomly --basetemp=.pytest_tmp/payload \
        cc_memory_vnext/tests/test_injection_payload.py -q

旧实现 `body.splitlines()[0]` 对「正文以 markdown 标题开头」的卡片注出的是标题
标记本身(或空串)——普查实测占全部注入的 24.2%。本文件钉死新语义:
summary 优先、缺失时回退到首个非空非标题正文行、两者都没有才为空。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ZMEM_PATH = Path(__file__).resolve().parents[1] / "zmem.py"
_MODULE_NAME = "zmem_under_test_payload"


def _zmem():
    cached = sys.modules.get(_MODULE_NAME)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, ZMEM_PATH)
    mod = importlib.util.module_from_spec(spec)
    # zmem 用 `from __future__ import annotations` + frozen dataclass,
    # dataclasses 解析注解时会回查 sys.modules[cls.__module__];先登记再 exec。
    sys.modules[_MODULE_NAME] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(_MODULE_NAME, None)
        raise
    return mod


def _card(body: str, summary: str | None = None, card_id: str = "payload-probe") -> dict:
    meta = {
        "id": card_id,
        "kind": "constraint",
        "title": "载荷探针卡",
        "priority": "P1",
        "status": "active",
        "scope": {"domains": ["memory-system"], "paths": ["cc_memory_vnext/cards/*.md"], "symbols": []},
        "triggers": {"examples": ["载荷探针"]},
        "activation": {},
    }
    if summary is not None:
        meta["summary"] = summary
    return {"id": card_id, "path": f"cards/{card_id}.md", "digest": "0" * 64, "meta": meta, "body": body, "terms": []}


def test_snippet_prefers_frontmatter_summary():
    zmem = _zmem()
    card = _card("# 正文标题\n\n正文第一段。", summary="这是真正要被注入的载荷。")
    assert zmem.card_snippet(card) == "这是真正要被注入的载荷。"


def test_snippet_falls_back_to_first_non_heading_body_line():
    zmem = _zmem()
    card = _card("# 正文标题\n\n正文第一段。\n第二段。")
    assert zmem.card_snippet(card) == "正文第一段。"


def test_snippet_empty_only_when_card_has_nothing_to_say():
    zmem = _zmem()
    assert zmem.card_snippet(_card("")) == ""
    assert zmem.card_snippet(_card("# 只有标题\n## 还是标题\n")) == ""


def test_snippet_folds_block_scalar_summary_to_one_line():
    zmem = _zmem()
    # 渲染器一行一个 snippet,块标量 summary 必须折回单行。
    card = _card("正文", summary="第一行\n第二行")
    assert zmem.card_snippet(card) == "第一行 第二行"


def test_heading_led_card_injects_non_empty_payload_end_to_end():
    """回归主证:正文以标题行开头的卡,注入后 snippet 非空(旧实现在这里注出 '# 正文标题')。"""
    zmem = _zmem()
    index = {"cards": [_card("# 正文标题\n\n正文第一段。", summary="必须被注入的那句话。")]}
    frame = zmem.normalize_frame({"prompt": "改卡片", "paths": ["cc_memory_vnext/cards/foo.md"]})
    packet = zmem.compile_context(index, frame)
    entries = packet["layers"]["L0"] + packet["layers"]["L1"] + packet["layers"]["L2"]
    hit = [item for item in entries if item["id"] == "payload-probe"]
    assert hit, f"探针卡未被召回: {packet['layers']}"
    assert hit[0]["snippet"] == "必须被注入的那句话。"
    assert not hit[0]["snippet"].startswith("#")
