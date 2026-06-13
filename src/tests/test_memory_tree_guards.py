# -*- coding: utf-8 -*-
"""Regression guards for the warn-only memory-tree checks added 2026-06-14:
harness↔cc_context co-maintained drift + archived-node bare prose refs.

These are the two forcing functions for the 2026-06-14 蛀虫 cleanup's top two
recurring failure modes (two-tree divergence + archive-slimming dangling refs).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_SCRIPT = REPO / "scripts" / "check_memory_tree.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_memory_tree", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _node(d: Path, filename: str, body: str) -> None:
    slug = filename[:-3]
    (d / filename).write_text(f"---\nname: {slug}\n---\n{body}\n", encoding="utf-8")


def test_normalize_crosstree_equates_wikilink_styles() -> None:
    m = _load()
    assert m._normalize_crosstree("见 [[browser-pitfalls]] 终诊") == m._normalize_crosstree(
        "见 harness memory「browser-pitfalls」 终诊"
    )


def test_archived_dangling_flags_then_clears(tmp_path: Path) -> None:
    m = _load()
    arch = tmp_path / "arch"
    arch.mkdir()
    mem = tmp_path / "mem"
    mem.mkdir()
    _node(arch, "old-thing.md", "archived body")
    _node(mem, "live.md", "见 old-thing 的历史记录")
    warns = m._check_archived_dangling(mem, set(), archive_dir=arch)
    assert warns and "old-thing" in warns[0]
    # 标注 (已归档) 后清零
    _node(mem, "live.md", "见 old-thing(已归档) 的历史记录")
    assert not m._check_archived_dangling(mem, set(), archive_dir=arch)


def test_archived_dangling_skips_wikilink_and_active(tmp_path: Path) -> None:
    m = _load()
    arch = tmp_path / "arch"
    arch.mkdir()
    mem = tmp_path / "mem"
    mem.mkdir()
    _node(arch, "old-thing.md", "archived body")
    # [[ ]] 形式归 link check, 本 lint 跳过
    _node(mem, "live.md", "见 [[old-thing]] 的记录")
    assert not m._check_archived_dangling(mem, set(), archive_dir=arch)
    # slug 同时在活树 (known) -> 不算 archive_only
    _node(mem, "live2.md", "见 old-thing 的记录")
    assert not m._check_archived_dangling(mem, {"old-thing"}, archive_dir=arch)


def test_harness_mirror_drift_and_clean(tmp_path: Path) -> None:
    m = _load()
    mem = tmp_path / "mem"
    mem.mkdir()
    harn = tmp_path / "harn"
    harn.mkdir()
    name = "no-workflow-use-chrome-gpt-review.md"  # one of _CO_MAINTAINED
    (mem / name).write_text("内容 见 harness memory「x」", encoding="utf-8")
    (harn / name).write_text("内容 见 [[x]]", encoding="utf-8")
    # 仅跨树 wikilink 风格差异 -> 规范化后一致 -> 无 drift
    assert not m._check_harness_mirror(mem, harness_dir=harn)
    # 真内容 drift -> warn
    (harn / name).write_text("内容 见 [[x]] 外加一整块新东西", encoding="utf-8")
    warns = m._check_harness_mirror(mem, harness_dir=harn)
    assert warns and name in warns[0]


def test_harness_mirror_skips_when_unreachable(tmp_path: Path) -> None:
    m = _load()
    mem = tmp_path / "mem"
    mem.mkdir()
    assert m._check_harness_mirror(mem, harness_dir=tmp_path / "nonexistent") == []
