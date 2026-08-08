# -*- coding: utf-8 -*-
"""`zmem analyze-log` 回归:遥测日志终于有人读了。

背景:`logs/activation_decisions.jsonl` 从 2026-07-08 起一直在长(实测 ~1600 条),
但仓库里没有任何工具消费它——"哪张卡从来没被注入过""静默不注入的比例多高"这类
问题一直只能靠猜。本文件钉的是那台读它的机器。

手跑:
    python -m pytest -p no:randomly --basetemp=.pytest_tmp/analyze \
        cc_memory_vnext/tests/test_activation_log_analysis.py -q
进门:preflight 记忆 lane 整目录收集 `cc_memory_vnext/tests`。

承重性质四条:
1. 事件行(`recall_failure`)不是决策行,不许进注入分母——recall 真坏掉的时候,
   把它算进决策会正好把零注入率冲淡,那恰是最该看清的时刻。
2. 从没被注入过的 active 卡要点名。
3. 读不了 / 读到坏行不许炸,退出码恒 0——会让调用方失败的分析工具没人会跑。
4. 只读:跑完日志与卡片一个字节都不许变。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

VNEXT = Path(__file__).resolve().parents[1]
ZMEM_PATH = VNEXT / "zmem.py"
_MODULE_NAME = "zmem_under_test_analyze_log"


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
kind: pitfall
title: 遥测探针卡 {card_id}
summary: 遥测分析回归用探针卡。
scope:
  domains: [{card_id}]
  paths: []
  symbols: []
status: {status}
priority: P2
triggers:
  intents: []
  keywords: [遥测探针]
  negative_keywords: []
  paths: []
  symbols: []
  error_regex: []
  examples:
    - 遥测探针
activation:
  layer_hint: L1
  must_know: false
  reason: 遥测分析回归用探针卡。
provenance:
  op: record
  reason: 测试夹具。
  evidence: ["2026-08-08 遥测分析回归夹具"]
updated_at: "2026-08-08"
---
遥测探针卡正文。
"""


def _write_card(cards_dir: Path, card_id: str, status: str = "active") -> Path:
    cards_dir.mkdir(parents=True, exist_ok=True)
    path = cards_dir / f"{card_id}.md"
    path.write_text(CARD_TEMPLATE.format(card_id=card_id, status=status), encoding="utf-8")
    return path


def _decision(injected, ts="2026-08-08T01:00:00", stale=None):
    record = {
        "ts": ts,
        "frame_digest": "d" * 8,
        "prompt_sha16": "0" * 16,
        "prompt_len": 10,
        "intents": [],
        "domains": [],
        "injected": injected,
    }
    if stale is not None:
        record["stale_index"] = stale
    return json.dumps(record, ensure_ascii=False)


def _injected(card_id, layer="L1", reason="quota:pitfall", score=0.5):
    return {"id": card_id, "layer": layer, "score": score, "reason": reason}


def _write_log(tmp_path: Path, lines: list[str]) -> Path:
    path = tmp_path / "logs" / "activation_decisions.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _run(zmem, log: Path, cards_dir: Path) -> int:
    return zmem.main(["analyze-log", "--log", str(log), "--cards-dir", str(cards_dir)])


# --------------------------------------------------------------------------


def test_a_recall_failure_event_never_enters_the_injection_denominator(zmem) -> None:
    """事件行没有 `injected` 字段,它根本不是一次决策。

    把它算成决策,零注入率会在 recall 真的坏掉时被冲淡——正好是这个数字最该
    刺眼的时候。事件另立一栏,连原因分布一起报。
    """
    lines = [
        _decision([_injected("card-a")]),
        _decision([]),
        json.dumps(
            {
                "event": "recall_failure",
                "ts": "2026-08-08T02:00:00",
                "hook": "UserPromptSubmit",
                "reason": "zmem child could not be run",
            }
        ),
    ]
    summary = zmem.analyze_activation_log(lines, ["card-a"])

    assert summary["decisions"] == 2
    assert summary["zero_injection_decisions"] == 1
    assert summary["zero_injection_rate"] == pytest.approx(0.5)
    assert summary["events"] == {"recall_failure": 1}
    assert summary["event_reasons"]["recall_failure"] == {"zmem child could not be run": 1}


def test_reasons_layers_and_top_cards_are_counted_per_injection(zmem) -> None:
    lines = [
        _decision(
            [
                _injected("card-a", layer="L0", reason="session_start_l0"),
                _injected("card-b", reason="must_know_active_status"),
            ]
        ),
        _decision([_injected("card-a", layer="L0", reason="session_start_l0")]),
    ]
    summary = zmem.analyze_activation_log(lines, ["card-a", "card-b"])

    assert summary["injections"] == 3
    assert summary["reasons"] == {"session_start_l0": 2, "must_know_active_status": 1}
    assert summary["layers"] == {"L0": 2, "L1": 1}
    assert summary["top_cards"] == [("card-a", 2), ("card-b", 1)]
    assert summary["distinct_cards_injected"] == 2


def test_an_active_card_that_never_fired_is_named(zmem) -> None:
    lines = [_decision([_injected("card-a")])]
    summary = zmem.analyze_activation_log(lines, ["card-a", "card-silent"])

    assert summary["never_injected_active_cards"] == ["card-silent"]
    assert summary["active_card_count"] == 2


def test_stale_index_true_is_separated_from_the_field_merely_existing(zmem) -> None:
    """`stale_index` 是后加的字段,老记录没有它。

    1/1600 和 1/108 是两个完全不同的结论,所以"为真几次"和"这个字段在几条记录
    上存在"分开报,不许把没有该字段的老记录当成 false 混进分母。
    """
    lines = [
        _decision([_injected("card-a")]),
        _decision([_injected("card-a")], stale=False),
        _decision([_injected("card-a")], stale=True),
    ]
    summary = zmem.analyze_activation_log(lines, ["card-a"])

    assert summary["stale_index_true"] == 1
    assert summary["stale_index_field_present"] == 2


def test_the_time_window_spans_every_record_including_events(zmem) -> None:
    lines = [
        _decision([_injected("card-a")], ts="2026-08-08T05:00:00"),
        json.dumps({"event": "recall_failure", "ts": "2026-07-01T00:00:00", "reason": "x"}),
    ]
    summary = zmem.analyze_activation_log(lines, ["card-a"])

    assert summary["first_ts"] == "2026-07-01T00:00:00"
    assert summary["last_ts"] == "2026-08-08T05:00:00"


def test_a_malformed_line_is_counted_and_the_rest_still_reported(zmem) -> None:
    lines = ["{not json", "", _decision([_injected("card-a")])]
    summary = zmem.analyze_activation_log(lines, ["card-a"])

    assert summary["unparsable_records"] == 1
    assert summary["decisions"] == 1
    assert summary["injections"] == 1


def test_a_missing_log_degrades_to_one_line_and_exit_zero(zmem, tmp_path, capsys) -> None:
    cards_dir = tmp_path / "cards"
    _write_card(cards_dir, "card-a")

    assert _run(zmem, tmp_path / "logs" / "nope.jsonl", cards_dir) == 0
    out = capsys.readouterr().out
    assert "ANALYZE UNAVAILABLE" in out
    assert len(out.strip().splitlines()) == 1


def test_an_unreadable_cards_dir_still_produces_the_log_summary(zmem, tmp_path, capsys) -> None:
    """卡片读不了不该拖垮日志分析——两者是两份独立证据。"""
    log = _write_log(tmp_path, [_decision([_injected("card-a")])])

    assert _run(zmem, log, tmp_path / "no-such-cards") == 0
    out = capsys.readouterr().out
    assert "card roster unavailable" in out
    assert "ACTIVATION LOG" in out
    assert "(card roster unreadable)" in out


def test_the_real_cli_reports_every_required_section(zmem, tmp_path, capsys) -> None:
    cards_dir = tmp_path / "cards"
    _write_card(cards_dir, "card-a")
    _write_card(cards_dir, "card-silent")
    log = _write_log(
        tmp_path,
        [
            _decision([_injected("card-a", reason="must_know_active_status")], stale=True),
            _decision([]),
            json.dumps({"event": "recall_failure", "ts": "2026-08-08T02:00:00", "reason": "boom"}),
        ],
    )

    assert _run(zmem, log, cards_dir) == 0
    out = capsys.readouterr().out
    assert "window" in out
    assert "decisions         : 2" in out
    assert "50.0%" in out
    assert "must_know_active_status" in out
    assert "stale_index=true  : 1" in out
    assert "card-silent" in out
    assert "recall_failure" in out
    assert "boom" in out


def test_analyze_log_writes_nothing(zmem, tmp_path) -> None:
    """只读工具的只读性得有人查:跑完字节和 mtime 都不许动。"""
    cards_dir = tmp_path / "cards"
    _write_card(cards_dir, "card-a")
    log = _write_log(tmp_path, [_decision([_injected("card-a")])])

    def snapshot() -> dict[str, tuple[int, int]]:
        return {
            str(path): (path.stat().st_size, path.stat().st_mtime_ns)
            for path in sorted(tmp_path.rglob("*"))
            if path.is_file()
        }

    before = snapshot()
    assert _run(zmem, log, cards_dir) == 0
    assert snapshot() == before
