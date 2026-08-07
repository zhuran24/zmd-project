# -*- coding: utf-8 -*-
"""`.index` 陈旧检测回归:改了卡没重编,消费方必须当场看见一行警告。

事故(2026-08-03):`cards/*.md` 是真相源、`.index/` 是 `build-index` 编出的缓存,
活 hook 消费的是缓存。有人改了卡没跑 build-index,hook 就静默注入旧规则半个月无
人发现。当时的修法只有 CLAUDE.md 里一句纪律("凡改卡必须在主树跑 build-index"),
没有任何机器在查——本文件是补上的那台机器。

手跑:
    python -m pytest -p no:randomly --basetemp=.pytest_tmp/staleness \
        cc_memory_vnext/tests/test_index_staleness_guard.py -q
进门:preflight 记忆 lane 整目录收集 `cc_memory_vnext/tests`(见
`scripts/preflight_gate.py` 的 MEMORY_TEST_DIRS),本文件自动在内。

主证走真链:写真 `.md` -> 真 `build-index` 写真索引文件 -> 真 CLI `context`
(`--require-index --format text`,与两个活 hook 的调用形状一致)-> 读它打给我看
的那段文字。夹具全在 tmp 目录自建,不碰仓库里那份真 `.index`。

三条承重断言,对应守卫的三个性质:陈旧要报(不然守卫是摆设)、新鲜不许报(假阳性
一周内就会被无视掉)、检测自己炸了要闭嘴(hook 路径上宁可漏报不可炸)。
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

VNEXT = Path(__file__).resolve().parents[1]
ZMEM_PATH = VNEXT / "zmem.py"
_MODULE_NAME = "zmem_under_test_staleness"

STALE_MARK = "STALE INDEX"


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


CARD_TEMPLATE = """---
id: {card_id}
kind: pitfall
title: 陈旧探针卡 {card_id}
summary: {summary}
scope:
  domains: [{domain}]
  paths: []
  symbols: []
status: {status}
priority: P2
triggers:
  intents: []
  keywords: [陈旧探针]
  negative_keywords: []
  paths: []
  symbols: []
  error_regex: []
  examples:
    - 陈旧探针
activation:
  layer_hint: L1
  must_know: false
  reason: 陈旧检测回归用探针卡。
provenance:
  op: record
  reason: 测试夹具。
  evidence: ["2026-08-07 陈旧检测回归夹具"]
updated_at: "2026-08-07"
---
陈旧探针卡正文。
"""

PROBE_ID = "staleness-probe-a"


def _write_card(cards_dir: Path, card_id: str, summary: str = "探针载荷。", status: str = "active") -> Path:
    cards_dir.mkdir(parents=True, exist_ok=True)
    path = cards_dir / f"{card_id}.md"
    # domain 跟着 id 走:两张同 scope 的 active 卡会被 verify 判成未声明的冲突。
    path.write_text(
        CARD_TEMPLATE.format(card_id=card_id, summary=summary, domain=card_id, status=status),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def corpus(zmem, tmp_path, capsys):
    """一份自建的小卡集 + 刚编好的索引,即"新鲜"的定义。"""
    cards_dir = tmp_path / "cards"
    index_path = tmp_path / ".index" / "cards_index.json"
    _write_card(cards_dir, PROBE_ID)
    _write_card(cards_dir, "staleness-probe-b")
    assert _build(zmem, cards_dir, index_path) == 0
    capsys.readouterr()
    return cards_dir, index_path


def _build(zmem, cards_dir: Path, index_path: Path) -> int:
    return zmem.main(["build-index", "--cards-dir", str(cards_dir), "--index", str(index_path)])


def _context(zmem, cards_dir: Path, index_path: Path, fmt: str = "text") -> int:
    """与活 hook 同形状的调用:--require-index + 指定 layers。"""
    return zmem.main(
        [
            "context",
            "--require-index",
            "--cards-dir",
            str(cards_dir),
            "--index",
            str(index_path),
            "--layers",
            "L0,L1",
            "--format",
            fmt,
            "--prompt",
            "陈旧探针",
        ]
    )


# --- 陈旧要报 ---------------------------------------------------------------


def test_edited_card_makes_context_warn(zmem, corpus, capsys):
    """改任一张卡的字节 = 索引陈旧,警告必须出现在注给我看的那段文字里。"""
    cards_dir, index_path = corpus
    _write_card(cards_dir, PROBE_ID, summary="改过的载荷,索引里还是旧的。")

    assert _context(zmem, cards_dir, index_path) == 0
    out = capsys.readouterr().out
    assert STALE_MARK in out, out
    assert "build-index" in out
    # 警告不许把 packet 顶掉:陈旧的召回仍然要送达,只是带着标签。
    assert PROBE_ID in out


def test_added_card_makes_context_warn(zmem, corpus, capsys):
    cards_dir, index_path = corpus
    _write_card(cards_dir, "staleness-probe-c")

    assert _context(zmem, cards_dir, index_path) == 0
    assert STALE_MARK in capsys.readouterr().out


def test_deleted_card_makes_context_warn(zmem, corpus, capsys):
    cards_dir, index_path = corpus
    (cards_dir / "staleness-probe-b.md").unlink()

    assert _context(zmem, cards_dir, index_path) == 0
    assert STALE_MARK in capsys.readouterr().out


def test_retiring_a_card_to_nonactive_makes_context_warn(zmem, corpus, capsys):
    """退役一张卡不改动 active 卡集,但它是一次 cards/ 编辑,同样要判陈旧。"""
    cards_dir, index_path = corpus
    _write_card(cards_dir, "staleness-probe-b", status="archived")

    assert _context(zmem, cards_dir, index_path) == 0
    assert STALE_MARK in capsys.readouterr().out


def test_index_without_cards_digest_cannot_prove_it_is_current(zmem, corpus, capsys):
    """旧 builder 编出来的索引没有指纹字段:它证明不了自己是新的,按陈旧报。"""
    cards_dir, index_path = corpus
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index.pop("cards_digest")
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    assert _context(zmem, cards_dir, index_path) == 0
    assert STALE_MARK in capsys.readouterr().out


def test_json_format_carries_the_warning_too(zmem, corpus, capsys):
    """机器消费方也要能读到,不能只有文本渲染有。"""
    cards_dir, index_path = corpus
    _write_card(cards_dir, PROBE_ID, summary="改过的载荷。")

    assert _context(zmem, cards_dir, index_path, fmt="json") == 0
    packet = json.loads(capsys.readouterr().out)
    assert any(STALE_MARK in line for line in packet["warnings"]), packet.get("warnings")


# --- 新鲜不许报 -------------------------------------------------------------


def test_freshly_built_index_produces_no_warning(zmem, corpus, capsys):
    cards_dir, index_path = corpus

    assert _context(zmem, cards_dir, index_path) == 0
    out = capsys.readouterr().out
    assert STALE_MARK not in out, out
    # 空 packet 也能"无警告"通过,所以顺手钉住这一跑真的召回了东西。
    assert PROBE_ID in out


def test_fresh_json_packet_has_no_warnings_key(zmem, corpus, capsys):
    """新鲜时 packet 形状与加守卫之前逐字节一致,既有 JSON 消费方不受影响。"""
    cards_dir, index_path = corpus

    assert _context(zmem, cards_dir, index_path, fmt="json") == 0
    assert "warnings" not in json.loads(capsys.readouterr().out)


def test_mtime_churn_alone_is_not_stale(zmem, corpus, capsys):
    """判据是内容不是 mtime:git checkout 会重写 mtime 而不动内容。

    mtime 口径下这一跑必红,而它每次切分支都会发生——假阳性一周内就会让人把警
    告当噪音无视掉,守卫也就白装了。
    """
    cards_dir, index_path = corpus
    card = cards_dir / f"{PROBE_ID}.md"
    card.write_text(card.read_text(encoding="utf-8"), encoding="utf-8")
    os.utime(card, (0, 0))

    assert _context(zmem, cards_dir, index_path) == 0
    assert STALE_MARK not in capsys.readouterr().out


def test_rebuilding_clears_the_warning(zmem, corpus, capsys):
    """警告指的那条命令必须真能消掉它,否则它就是个关不掉的红灯。"""
    cards_dir, index_path = corpus
    _write_card(cards_dir, PROBE_ID, summary="改过的载荷。")
    assert _context(zmem, cards_dir, index_path) == 0
    assert STALE_MARK in capsys.readouterr().out

    assert _build(zmem, cards_dir, index_path) == 0
    capsys.readouterr()
    assert _context(zmem, cards_dir, index_path) == 0
    assert STALE_MARK not in capsys.readouterr().out


# --- 检测自己炸了要闭嘴 -----------------------------------------------------


def test_checker_exception_degrades_to_silence(zmem, corpus, capsys, monkeypatch):
    """检测抛异常 = 无警告、退出码不变、packet 照常送达。

    hook 路径上漏报只是回到今天的状态,炸掉却会让整条召回消失(hook 见非零退出
    码就跳过注入)。所以这里钉的是"宁可漏报不可炸"。
    """
    cards_dir, index_path = corpus
    _write_card(cards_dir, PROBE_ID, summary="改过的载荷,但检测会炸。")

    def boom(*args, **kwargs):
        raise RuntimeError("staleness check exploded")

    monkeypatch.setattr(zmem, "index_staleness_reason", boom)

    assert _context(zmem, cards_dir, index_path) == 0
    out = capsys.readouterr().out
    assert STALE_MARK not in out, out
    assert PROBE_ID in out


def test_stale_context_never_rebuilds_the_index(zmem, corpus, capsys):
    """advisory-only:守卫只说话,绝不代替 owner 重编缓存。"""
    cards_dir, index_path = corpus
    before = index_path.read_bytes()
    _write_card(cards_dir, PROBE_ID, summary="改过的载荷。")

    assert _context(zmem, cards_dir, index_path) == 0
    assert STALE_MARK in capsys.readouterr().out
    assert index_path.read_bytes() == before


# --- verify 出口 ------------------------------------------------------------


def test_verify_reports_stale_index_without_failing(zmem, corpus, capsys):
    """verify 的判决是卡片质量;缓存该重编说明不了卡片有问题,所以只报不判败。"""
    cards_dir, index_path = corpus
    _write_card(cards_dir, PROBE_ID, summary="改过的载荷。")

    code = zmem.main(["verify", "--cards-dir", str(cards_dir), "--index", str(index_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "VERIFY OK" in out
    assert STALE_MARK in out


def test_verify_stays_quiet_when_index_is_fresh(zmem, corpus, capsys):
    cards_dir, index_path = corpus

    assert zmem.main(["verify", "--cards-dir", str(cards_dir), "--index", str(index_path)]) == 0
    assert STALE_MARK not in capsys.readouterr().out


def test_verify_with_no_index_at_all_is_not_a_staleness_report(zmem, tmp_path, capsys):
    """根本没编过索引 ≠ 索引陈旧,别把两件事混成一句话。"""
    cards_dir = tmp_path / "cards"
    _write_card(cards_dir, PROBE_ID)

    code = zmem.main(["verify", "--cards-dir", str(cards_dir), "--index", str(tmp_path / "nope.json")])
    out = capsys.readouterr().out
    assert code == 0
    assert STALE_MARK not in out
