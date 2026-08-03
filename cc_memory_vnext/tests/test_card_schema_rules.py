# -*- coding: utf-8 -*-
"""卡片 schema 规则回归：pitfall 卡不再被逼着填 error_regex（2026-08-03）。

手跑（两个解释器都要过，hook 用 `python3`、门禁用 `.venv-uvbolt-backup`）：
    python -m pytest -p no:randomly --basetemp=.pytest_tmp/schema \
        cc_memory_vnext/tests/test_card_schema_rules.py -q

旧规则「pitfall 卡必须有非空顶层 error_regex」编码了一个假设：坑是靠报错文本
认出来的。2026-08-03 普查 §3.5 否掉了这个假设（39 次唯一错误召回注入里真阳 3
次，唯一被采纳的那次自己还是假阳性），P2.2 随之把两张噪声卡的 error_regex 清
空——结果其中一张为了绕过本规则被迫改成 `kind: decision`，卡的登记类型开始为
schema 服务而不是为语义服务。本文件钉死放宽后的语义，并顺带钉住 pitfall 之外
的几条校验没被一起放掉。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

VNEXT = Path(__file__).resolve().parents[1]
ZMEM_PATH = VNEXT / "zmem.py"
CARDS_DIR = VNEXT / "cards"
_MODULE_NAME = "zmem_under_test_schema"


def _zmem():
    cached = sys.modules.get(_MODULE_NAME)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, ZMEM_PATH)
    mod = importlib.util.module_from_spec(spec)
    # zmem 用 `from __future__ import annotations` + frozen dataclass，
    # dataclasses 解析注解时会回查 sys.modules[cls.__module__]；先登记再 exec。
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


CARD_TEMPLATE = """---
id: {card_id}
kind: {kind}
title: 探针卡
summary: 只为 schema 校验存在的探针卡。
scope:
  domains: [schema-probe]
  paths: []
  symbols: []
status: active
priority: P2
triggers:
  intents: []
  keywords: [探针]
  negative_keywords: []
  paths: []
  symbols: []
{error_regex_block}  examples:
    - 探针
activation:
  layer_hint: L1
  must_know: false
  reason: 探针卡。
provenance:
  op: record
  reason: 探针。
---
正文。
"""


def _write_card(tmp_path: Path, *, kind: str, error_regex_block: str, card_id: str = "schema-probe") -> Path:
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir(exist_ok=True)
    path = cards_dir / f"{card_id}.md"
    path.write_text(
        CARD_TEMPLATE.format(card_id=card_id, kind=kind, error_regex_block=error_regex_block),
        encoding="utf-8",
    )
    return cards_dir


def _verify(zmem, cards_dir: Path) -> list[str]:
    return zmem.verify_cards(zmem.load_cards(cards_dir))


def test_a_pitfall_card_with_an_empty_error_regex_verifies(zmem, tmp_path: Path) -> None:
    """本批放宽的正是这条：空表是合法形态，不是漏填。"""
    cards_dir = _write_card(tmp_path, kind="pitfall", error_regex_block="  error_regex: []\n")
    assert _verify(zmem, cards_dir) == []


def test_the_universal_triggers_shape_rule_survived_the_relaxation(zmem, tmp_path: Path) -> None:
    """放宽的只是 pitfall 那条 kind 规则；triggers 的形状校验一条没动。

    `triggers.error_regex` 这个键仍然必须在场（可以是空表）——它管的是卡片形
    状完整、不是「坑必须有报错」，两件事别一起放掉。
    """
    cards_dir = _write_card(tmp_path, kind="pitfall", error_regex_block="")
    errors = _verify(zmem, cards_dir)
    assert any("triggers.error_regex must be present" in error for error in errors)


def test_a_pitfall_card_with_an_error_regex_still_verifies(zmem, tmp_path: Path) -> None:
    """放宽不是废除：仍然想靠报错召回的坑卡照常合法。"""
    cards_dir = _write_card(
        tmp_path, kind="pitfall", error_regex_block="  error_regex:\n    - \"probe: boom\"\n"
    )
    assert _verify(zmem, cards_dir) == []


def test_the_other_kind_specific_rules_were_not_relaxed_with_it(zmem, tmp_path: Path) -> None:
    """只动 pitfall 一条；constraint 缺 severity 仍然必须红。"""
    cards_dir = _write_card(tmp_path, kind="constraint", error_regex_block="  error_regex: []\n")
    errors = _verify(zmem, cards_dir)
    assert any("constraint cards require severity" in error for error in errors)


def test_the_branch_stale_card_is_registered_as_the_pitfall_it_is(zmem) -> None:
    """P2.2 把它改成 decision 是为了绕过旧 schema；规则放宽后它归位。"""
    cards = {card.id: card for card in zmem.load_cards(CARDS_DIR)}
    card = cards["memory-db-feature-branch-stale-do-ops-on-main"]
    assert card.meta["kind"] == "pitfall"
    assert zmem.normalize_list(card.meta.get("triggers", {}).get("error_regex")) == []


def test_the_committed_card_deck_verifies_clean(zmem) -> None:
    assert _verify(zmem, CARDS_DIR) == []
