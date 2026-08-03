# -*- coding: utf-8 -*-
"""注入载荷回归:注 frontmatter summary,不注 body 首行(2026-08-03 普查 §3.4 第 1 项)。

不接 CI(preflight 快 lane 只跑 src/tests);手跑:
    python -m pytest -p no:randomly --basetemp=.pytest_tmp/payload \
        cc_memory_vnext/tests/test_injection_payload.py -q

旧实现 `body.splitlines()[0]` 对「正文以 markdown 标题开头」的卡片注出的是标题
标记本身(或空串)——普查实测占全部注入的 24.2%。本文件钉死新语义:
summary 优先、缺失时回退到首个非空非标题正文行、两者都没有才为空。

**主证走整条真链**(2026-08-03 审查 ⑤ 打回后改的):写真的 `.md` 卡片文件 ->
`load_cards` 真解析 YAML frontmatter -> `build_index_data` 真建索引 ->
`compile_context` 真编包 -> `format_packet_text` 真渲染成注给我看的那段文字。
上一版只手造 dict 直接调 `card_snippet()`,于是把 YAML loader 改成丢掉 summary、
或把 renderer 改成根本不输出 snippet,5 个测试照样全绿——链路两头都没咬住。
现在这两种改法都会当场红。

注:本文件要 PyYAML(卡片 frontmatter 是 YAML,`load_frontmatter` 没有它直接抛
ZmemError)。生产 hook 用 `python3` 跑、那个解释器一直装着;2026-08-03 给
`.venv-uvbolt-backup` 也补了 pyyaml==6.0.3,两个解释器现在都能跑这套测试。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

VNEXT = Path(__file__).resolve().parents[1]
ZMEM_PATH = VNEXT / "zmem.py"
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


@pytest.fixture(scope="module")
def zmem():
    return _zmem()


def _card(body: str, summary: str | None = None, card_id: str = "payload-probe") -> dict:
    """内存态卡,只给纯函数边界用;端到端用例一律走 _write_card。"""
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


CARD_TEMPLATE = """---
id: {card_id}
kind: constraint
title: 载荷探针卡 {card_id}
severity: high
{summary_block}scope:
  domains: [{domain}]
  paths: [cc_memory_vnext/cards/*.md]
  symbols: []
status: active
priority: P1
triggers:
  intents: []
  keywords: [载荷探针]
  negative_keywords: []
  paths: [cc_memory_vnext/cards/*.md]
  symbols: []
  error_regex: []
  examples:
    - 载荷探针
activation:
  layer_hint: L1
  must_know: false
  reason: 载荷回归用探针卡。
provenance:
  op: record
  reason: 测试夹具。
  evidence: ["2026-08-03 注入载荷回归夹具"]
updated_at: "2026-08-03"
---
{body}
"""


def _write_card(cards_dir: Path, card_id: str, body: str, summary_block: str = "", domain: str = "payload-probe") -> Path:
    cards_dir.mkdir(parents=True, exist_ok=True)
    path = cards_dir / f"{card_id}.md"
    path.write_text(
        CARD_TEMPLATE.format(card_id=card_id, body=body, summary_block=summary_block, domain=domain),
        encoding="utf-8",
    )
    return path


def _packet_for(zmem, cards_dir: Path):
    """真链:真实 .md -> YAML frontmatter -> index -> packet。"""
    cards = zmem.load_cards(cards_dir)
    index = zmem.build_index_data(cards)
    frame = zmem.normalize_frame({"prompt": "载荷探针", "paths": ["cc_memory_vnext/cards/foo.md"]})
    return zmem.compile_context(index, frame)


def _entry(packet, card_id):
    entries = packet["layers"]["L0"] + packet["layers"]["L1"] + packet["layers"]["L2"]
    hits = [item for item in entries if item["id"] == card_id]
    assert hits, f"探针卡未被召回: {packet['layers']}"
    return hits[0]


# --- 端到端主证(写真卡文件 -> 真 YAML -> 真 packet -> 真渲染) ---------------


def test_frontmatter_summary_reaches_the_rendered_packet(zmem, tmp_path):
    cards_dir = tmp_path / "cards"
    _write_card(
        cards_dir,
        "payload-probe-summary",
        body="# 正文标题\n\n正文第一段。",
        summary_block="summary: 必须被注入的那句话。\n",
    )
    packet = _packet_for(zmem, cards_dir)
    entry = _entry(packet, "payload-probe-summary")
    assert entry["snippet"] == "必须被注入的那句话。"
    assert not entry["snippet"].startswith("#")
    # 渲染器是真正注给我看的那一步:载荷必须真的出现在它的输出里。
    rendered = zmem.format_packet_text(packet)
    assert "必须被注入的那句话。" in rendered
    assert "# 正文标题" not in rendered


def test_block_scalar_summary_survives_yaml_and_is_folded_to_one_line(zmem, tmp_path):
    """块标量 summary 经 YAML 解析后自带换行,渲染器一行一条,必须折回单行。"""
    cards_dir = tmp_path / "cards"
    _write_card(
        cards_dir,
        "payload-probe-block",
        body="正文。",
        summary_block="summary: |\n  第一行\n  第二行\n",
    )
    packet = _packet_for(zmem, cards_dir)
    entry = _entry(packet, "payload-probe-block")
    assert entry["snippet"] == "第一行 第二行"
    rendered = zmem.format_packet_text(packet)
    assert "  第一行 第二行" in rendered
    # 折行失败会让 snippet 自己占两行,把 packet「一行一条」的格式撑破。
    assert "\n第二行" not in rendered


def test_card_without_summary_falls_back_to_real_prose_end_to_end(zmem, tmp_path):
    cards_dir = tmp_path / "cards"
    _write_card(cards_dir, "payload-probe-nosummary", body="# 正文标题\n\n正文第一段。\n第二段。")
    packet = _packet_for(zmem, cards_dir)
    entry = _entry(packet, "payload-probe-nosummary")
    assert entry["snippet"] == "正文第一段。"
    assert "正文第一段。" in zmem.format_packet_text(packet)


def test_summary_wins_over_body_when_both_exist_end_to_end(zmem, tmp_path):
    """旧实现注的是 body 首行;这条把「谁赢」钉死在真链上。"""
    cards_dir = tmp_path / "cards"
    _write_card(
        cards_dir,
        "payload-probe-both",
        body="正文首行不该被注入。",
        summary_block="summary: summary 才是载荷。\n",
    )
    packet = _packet_for(zmem, cards_dir)
    entry = _entry(packet, "payload-probe-both")
    assert entry["snippet"] == "summary 才是载荷。"
    rendered = zmem.format_packet_text(packet)
    assert "正文首行不该被注入。" not in rendered


def test_real_repo_cards_all_carry_a_nonempty_payload(zmem):
    """仓库里真在用的卡:注出来不许是空串,也不许是 markdown 标题标记。"""
    empty, heading = [], []
    for card in zmem.load_cards(VNEXT / "cards"):
        snippet = zmem.card_snippet({"meta": card.meta, "body": card.body})
        if not snippet:
            empty.append(card.id)
        elif snippet.lstrip().startswith("#"):
            heading.append(card.id)
    assert not empty, f"这些卡注出来是空的: {empty}"
    assert not heading, f"这些卡注出来是标题标记: {heading}"


# --- 纯函数层的边界(补充,不替代上面的端到端) -----------------------------


def test_snippet_prefers_frontmatter_summary(zmem):
    card = _card("# 正文标题\n\n正文第一段。", summary="这是真正要被注入的载荷。")
    assert zmem.card_snippet(card) == "这是真正要被注入的载荷。"


def test_snippet_falls_back_to_first_non_heading_body_line(zmem):
    card = _card("# 正文标题\n\n正文第一段。\n第二段。")
    assert zmem.card_snippet(card) == "正文第一段。"


def test_snippet_empty_only_when_card_has_nothing_to_say(zmem):
    assert zmem.card_snippet(_card("")) == ""
    assert zmem.card_snippet(_card("# 只有标题\n## 还是标题\n")) == ""


def test_snippet_folds_block_scalar_summary_to_one_line(zmem):
    # 渲染器一行一个 snippet,块标量 summary 必须折回单行。
    card = _card("正文", summary="第一行\n第二行")
    assert zmem.card_snippet(card) == "第一行 第二行"
