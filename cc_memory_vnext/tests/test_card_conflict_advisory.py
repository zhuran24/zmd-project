# -*- coding: utf-8 -*-
"""卡片冲突分桶回归：判据从「整个 scope 三元组逐字相同」放宽到「同 kind + domains 相交」。

旧判据在 `verify_cards` 的 error 路径上，用 `scope_key`（domains/paths/symbols
三个列表全都逐字相等）分桶——真实卡集里从来没有两张卡满足过它，所以这段代码写
下来就一直是摆设，一次也没触发过。放宽后（2026-08-08 台账处方）它在 53 张真卡
上一次报出 61 对。

61 对里绝大多数不是冲突，是邻居：两张都谈 `certified-exact` 的 decision 卡没有
矛盾，只是同一个大题目下的两条决策。所以放宽的这一支走 **advisory 通道**——报
出来、不参与 verify 的通过/失败判定；旧的严格判据留在 error 路径上原样不动。理
由在 `conflict_advisories` 的 docstring 里：拿一个宽到会捞邻居的桶去红一条门
（本批刚把 `zmem verify` 接进 preflight 记忆 lane），就是拿分桶当判决。

手跑：
    python -m pytest -p no:randomly --basetemp=.pytest_tmp/conflict \
        cc_memory_vnext/tests/test_card_conflict_advisory.py -q
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

VNEXT = Path(__file__).resolve().parents[1]
ZMEM_PATH = VNEXT / "zmem.py"
_MODULE_NAME = "zmem_under_test_conflict"


def _zmem():
    cached = sys.modules.get(_MODULE_NAME)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, ZMEM_PATH)
    mod = importlib.util.module_from_spec(spec)
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
title: 冲突探针卡 {card_id}
summary: 冲突分桶回归用探针卡。
scope:
  domains: [{domains}]
  paths: [{paths}]
  symbols: []
status: {status}
priority: P2
triggers:
  intents: []
  keywords: [冲突探针]
  negative_keywords: []
  paths: []
  symbols: []
  error_regex: []
  examples:
    - 冲突探针
activation:
  layer_hint: L1
  must_know: false
  reason: 冲突分桶回归用探针卡。
provenance:
  op: record
  reason: 测试夹具。
  evidence: ["2026-08-08 冲突分桶回归夹具"]
{relations}updated_at: "2026-08-08"
---
冲突探针卡正文。
"""


def _write_card(
    cards_dir: Path,
    card_id: str,
    *,
    kind: str = "decision",
    domains: str = "probe-domain",
    paths: str = "",
    status: str = "active",
    supersedes: str | None = None,
) -> None:
    cards_dir.mkdir(parents=True, exist_ok=True)
    relations = ""
    if supersedes is not None:
        relations = f"relations:\n  supersedes: [{supersedes}]\n"
    (cards_dir / f"{card_id}.md").write_text(
        CARD_TEMPLATE.format(
            card_id=card_id,
            kind=kind,
            domains=domains,
            paths=paths,
            status=status,
            relations=relations,
        ),
        encoding="utf-8",
    )


def _cards(zmem, cards_dir: Path):
    return zmem.load_cards(cards_dir)


# --------------------------------------------------------------------------


def test_the_relaxed_bucket_fires_where_the_strict_one_never_did(zmem, tmp_path) -> None:
    """两张卡 domains 相交、kind 相同，但 scope 三元组并不逐字相同。

    这正是旧判据漏掉的整类：`scope_key` 要 domains/paths/symbols 全等，真实卡
    里两张谈同一件事的卡几乎不可能连 paths 都一模一样，所以它从未触发。
    """
    cards_dir = tmp_path / "cards"
    _write_card(cards_dir, "probe-left", domains="alpha, beta", paths='"src/a.py"')
    _write_card(cards_dir, "probe-right", domains="beta, gamma", paths='"src/b.py"')
    cards = _cards(zmem, cards_dir)

    assert zmem.verify_cards(cards) == [], "严格判据这一支必须还是沉默的"
    advisories = zmem.conflict_advisories(cards)
    assert len(advisories) == 1
    assert "probe-left / probe-right" in advisories[0]
    assert "[beta]" in advisories[0]


def test_a_declared_relation_silences_the_advisory(zmem, tmp_path) -> None:
    """卡已经说清楚两者什么关系，就没什么可提醒的了。"""
    cards_dir = tmp_path / "cards"
    _write_card(cards_dir, "probe-left")
    _write_card(cards_dir, "probe-right", supersedes="probe-left")

    assert zmem.conflict_advisories(_cards(zmem, cards_dir)) == []


def test_two_kinds_in_one_domain_are_not_a_pair(zmem, tmp_path) -> None:
    """一条决策和一个坑谈同一个 domain 是常态，不是冲突。"""
    cards_dir = tmp_path / "cards"
    _write_card(cards_dir, "probe-left", kind="decision")
    _write_card(cards_dir, "probe-right", kind="pitfall")

    assert zmem.conflict_advisories(_cards(zmem, cards_dir)) == []


def test_disjoint_domains_are_not_a_pair(zmem, tmp_path) -> None:
    cards_dir = tmp_path / "cards"
    _write_card(cards_dir, "probe-left", domains="alpha")
    _write_card(cards_dir, "probe-right", domains="beta")

    assert zmem.conflict_advisories(_cards(zmem, cards_dir)) == []


def test_a_superseded_card_is_not_a_live_pair(zmem, tmp_path) -> None:
    """退役的卡不参与注入，也就没有和谁抢地盘的问题。"""
    cards_dir = tmp_path / "cards"
    _write_card(cards_dir, "probe-left")
    _write_card(cards_dir, "probe-right", status="superseded")

    assert zmem.conflict_advisories(_cards(zmem, cards_dir)) == []


def test_a_pair_is_reported_once_with_every_shared_domain(zmem, tmp_path) -> None:
    cards_dir = tmp_path / "cards"
    _write_card(cards_dir, "probe-left", domains="alpha, beta, gamma")
    _write_card(cards_dir, "probe-right", domains="beta, gamma, delta")
    advisories = zmem.conflict_advisories(_cards(zmem, cards_dir))

    assert len(advisories) == 1
    assert "[beta, gamma]" in advisories[0]


def test_advisories_never_change_the_verify_verdict(zmem, tmp_path, capsys) -> None:
    """通道分离是本条的全部意义：报得出来，且退出码还是 0。"""
    cards_dir = tmp_path / "cards"
    _write_card(cards_dir, "probe-left", domains="alpha, beta", paths='"src/a.py"')
    _write_card(cards_dir, "probe-right", domains="beta", paths='"src/b.py"')

    code = zmem.main(
        [
            "verify",
            "--cards-dir",
            str(cards_dir),
            "--index",
            str(tmp_path / ".index" / "cards_index.json"),
        ]
    )
    out = capsys.readouterr().out

    assert code == 0
    assert "VERIFY OK" in out
    assert "CONFLICT ADVISORY: 1 active same-kind overlapping pair(s)" in out


def test_the_conflict_limit_truncates_and_says_so(zmem, tmp_path, capsys) -> None:
    cards_dir = tmp_path / "cards"
    for name in ("a", "b", "c"):
        _write_card(cards_dir, f"probe-{name}", paths=f'"src/{name}.py"')

    code = zmem.main(
        [
            "verify",
            "--cards-dir",
            str(cards_dir),
            "--index",
            str(tmp_path / ".index" / "cards_index.json"),
            "--conflict-limit",
            "1",
        ]
    )
    out = capsys.readouterr().out

    assert code == 0
    assert "CONFLICT ADVISORY: 3 active same-kind overlapping pair(s)" in out
    assert "… 2 more" in out
