# -*- coding: utf-8 -*-
"""记忆写入路由这件事,整副牌只许有一个声音(2026-08-03 冻结批的收尾)。

手跑(两个解释器都要过,hook 用 `python3`、门禁用 `.venv-uvbolt-backup`):
    python -m pytest -p no:randomly --basetemp=.pytest_tmp/routing \\
        cc_memory_vnext/tests/test_memory_routing_card_is_single_voiced.py -q

`memory-three-layer-coexistence-decided` 是 P1、L1、active,而且它的 examples 里
就写着「现在新记忆写哪层」——一句"新记忆写哪层"的提问必然把它推进上下文。冻结那
天卡顶部加了 08-03 修订块,却把 06-30 原文整段留在下面,于是同一张卡在同一个注
入包里既说"cc_memory 是只读档案、新记忆写文件记忆层",又说"新记忆默认进
cc_memory(低摩擦收件箱)"。frontmatter `summary` 更要命——**那才是 L1 真正注入
的那一行**,它里面写的是「新记忆先进 cc_memory 收件箱」(2026-08-03 对抗审查
stale-memory-routing-card)。

所以这里钉两层:
1. 这张卡的 summary 与正文都只留档案口径,旧路由的原句一个不留;
2. 整副活跃牌里没有第二张卡把新记忆往 cc_memory 引——一句话被两张卡说反,读者
   没有办法判断哪张新。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

VNEXT = Path(__file__).resolve().parents[1]
CARDS_DIR = VNEXT / "cards"
ROUTING_CARD = CARDS_DIR / "memory-three-layer-coexistence-decided.md"

# 旧路由的原句。都是 06-30 稿的字面,不是模糊关键词:出现即矛盾,无条件。
STALE_ROUTING_SENTENCES = (
    "新记忆先进 cc_memory 收件箱",
    "新记忆默认进 cc_memory",
    "写入收件箱",
)
# 这句只在「就此作废」的引用里合法——卡必须能指名道姓地废掉旧口径。
QUOTABLE_ONLY_WHEN_RETIRED = "仍现役、可写"


def _frontmatter_summary(text: str) -> str:
    match = re.search(r"^summary:[ \t]*(.*)$", text, flags=re.MULTILINE)
    assert match is not None, "这张卡必须有 frontmatter summary——它就是 L1 注入的那一行"
    return match.group(1)


def test_the_routing_card_exists_and_is_the_one_under_test() -> None:
    assert ROUTING_CARD.is_file(), ROUTING_CARD


@pytest.mark.parametrize("sentence", STALE_ROUTING_SENTENCES)
def test_the_injected_summary_carries_no_stale_write_route(sentence: str) -> None:
    """summary 是 zmem 注入的那一行,先钉它。"""
    summary = _frontmatter_summary(ROUTING_CARD.read_text(encoding="utf-8"))
    assert sentence not in summary, f"summary 仍在陈述旧路由: {sentence}"


def test_the_retired_wording_may_only_appear_as_a_retirement() -> None:
    """`仍现役、可写` 必须紧跟「作废」,否则它读起来仍是当前口径。"""
    summary = _frontmatter_summary(ROUTING_CARD.read_text(encoding="utf-8"))
    if QUOTABLE_ONLY_WHEN_RETIRED in summary:
        tail = summary.split(QUOTABLE_ONLY_WHEN_RETIRED, 1)[1][:40]
        assert "作废" in tail, "旧口径被引用了却没在同一句里被废掉"


def test_the_injected_summary_states_the_archive_route() -> None:
    summary = _frontmatter_summary(ROUTING_CARD.read_text(encoding="utf-8"))
    assert "只读档案" in summary
    assert "新记忆写文件记忆层" in summary


def test_the_card_body_no_longer_routes_new_memory_into_the_archive() -> None:
    """正文里那句「写入分工:新记忆默认进 cc_memory(低摩擦收件箱)」必须没了。"""
    body = ROUTING_CARD.read_text(encoding="utf-8").split("\n---\n", 1)[-1]
    assert "新记忆默认进 cc_memory" not in body
    assert "写入收件箱" not in body
    assert "新记忆写文件记忆层" in body or "新记忆的收件箱" in body


def test_no_active_card_anywhere_routes_new_memory_into_cc_memory() -> None:
    """整副牌层面的同一条:第二张这么说的卡会把这次清理白做。"""
    offenders: list[str] = []
    for card in sorted(CARDS_DIR.glob("*.md")):
        text = card.read_text(encoding="utf-8")
        if re.search(r"^status:\s*active\s*$", text, flags=re.MULTILINE) is None:
            continue
        for sentence in ("新记忆先进 cc_memory", "新记忆默认进 cc_memory"):
            if sentence in text:
                offenders.append(f"{card.name}: {sentence}")
    assert offenders == [], offenders
