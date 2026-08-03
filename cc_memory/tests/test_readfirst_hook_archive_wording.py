# -*- coding: utf-8 -*-
"""SessionStart hook 的档案口径 + 严格 fail-open(2026-08-03 冻结批)。

手跑(两个解释器都要过,hook 用 `python3`、门禁用 `.venv-uvbolt-backup`):
    python -m pytest -p no:randomly --basetemp=.pytest_tmp/readfirst \\
        cc_memory/tests/test_readfirst_hook_archive_wording.py -q

owner 2026-08-03 把 cc_memory 冻结成只读档案后,这个 hook 每次会话开头都还在替
它说话——所以它说什么就是全系统的默认口径。本文件钉两件事:

1. **口径**:注入文案说"只读档案 / 新记忆写文件记忆层 / find 是跨层入口",
   且不再有 boot-first、impact-before-change、检索特性推销那三句旧引导。
2. **fail-open 是实测真话**:hook 是活代码,任何异常都必须 exit 0 且不打印,
   否则每个新会话都被它带崩。走真实 CLI 子进程,把 hook 复制到 tmp 树,让
   mem.py / memory.db 各种缺失与损坏真的发生(沿用 P2.1 批立的形态——
   monkeypatch 直调 main() 咬不住这些路径)。

全部 fixture 化:复制出来的 hook 自定位到 tmp 树的 cc_memory/,真实 memory.db
一个字节都不碰。
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

CC_MEMORY = Path(__file__).resolve().parents[1]
HOOK_PATH = CC_MEMORY / "hooks" / "cc_memory_readfirst.py"
MEM_PATH = CC_MEMORY / "mem.py"
REAL_DB = CC_MEMORY / "memory.db"

INTERPRETERS = [sys.executable, "/usr/bin/python3"]


def _run(hook: Path, interpreter: str = sys.executable) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [interpreter, str(hook)], capture_output=True, text=True, timeout=60
    )


def _stage(tmp_path: Path, *, with_db: bool = True, db_bytes: bytes | None = None) -> Path:
    """A tmp cc_memory/ the copied hook will self-locate into."""
    root = tmp_path / "cc_memory"
    (root / "hooks").mkdir(parents=True)
    hook = root / "hooks" / "cc_memory_readfirst.py"
    shutil.copy2(HOOK_PATH, hook)
    shutil.copy2(MEM_PATH, root / "mem.py")
    if with_db:
        if db_bytes is None:
            shutil.copy2(REAL_DB, root / "memory.db")
        else:
            (root / "memory.db").write_bytes(db_bytes)
    return hook


def _context(result: subprocess.CompletedProcess[str]) -> str:
    payload = json.loads(result.stdout)
    return payload["hookSpecificOutput"]["additionalContext"]


# --- 1. 档案口径 -------------------------------------------------------------


@pytest.mark.parametrize("interpreter", INTERPRETERS)
def test_the_injected_text_says_the_archive_is_read_only(tmp_path: Path, interpreter: str) -> None:
    result = _run(_stage(tmp_path), interpreter)
    assert result.returncode == 0, result.stderr
    context = _context(result)
    assert "只读档案" in context
    assert "2026-08-03" in context
    assert "文件记忆层" in context


@pytest.mark.parametrize("interpreter", INTERPRETERS)
def test_the_injected_text_points_at_find_as_the_cross_layer_entry(
    tmp_path: Path, interpreter: str
) -> None:
    context = _context(_run(_stage(tmp_path), interpreter))
    assert "mem.py find" in context


def test_the_old_promotional_guidance_is_gone() -> None:
    """三句旧引导:先 boot / 改前 impact / 检索特性推销。

    断言打在 hook 源码上而不是渲染结果上,因为渲染结果里还混着档案条目自己的
    摘要文本(那是库内容、归档案订正管),这里只管 hook 自己说的话。
    """
    text = HOOK_PATH.read_text(encoding="utf-8")
    for retired in ("改记忆系统自身行为前先读", "main win", "再动手", "prefer it", "别只信上下文"):
        assert retired not in text, retired
    # 「rerank/语义检索」还在,那是档案条目的分域标签,不是引导语。
    assert "rerank/语义检索" in text


def test_the_hook_module_docstring_records_the_freeze() -> None:
    text = HOOK_PATH.read_text(encoding="utf-8")
    assert "read-only archive since 2026-08-03" in text


# --- 2. fail-open ------------------------------------------------------------


@pytest.mark.parametrize("interpreter", INTERPRETERS)
def test_a_missing_database_is_silent_and_zero(tmp_path: Path, interpreter: str) -> None:
    result = _run(_stage(tmp_path, with_db=False), interpreter)
    assert result.returncode == 0
    assert result.stdout == ""


def test_a_corrupt_database_is_silent_and_zero(tmp_path: Path) -> None:
    result = _run(_stage(tmp_path, db_bytes=b"this is not a database"))
    assert result.returncode == 0
    assert result.stdout == ""


def test_a_database_without_the_entries_table_is_silent_and_zero(tmp_path: Path) -> None:
    hook = _stage(tmp_path, db_bytes=b"")
    connection = sqlite3.connect(hook.parent.parent / "memory.db")
    connection.execute("CREATE TABLE unrelated (x INTEGER)")
    connection.commit()
    connection.close()
    result = _run(hook)
    assert result.returncode == 0
    assert result.stdout == ""


def test_a_missing_mem_module_is_silent_and_zero(tmp_path: Path) -> None:
    hook = _stage(tmp_path)
    (hook.parent.parent / "mem.py").unlink()
    result = _run(hook)
    assert result.returncode == 0
    assert result.stdout == ""


def test_an_unimportable_mem_module_is_silent_and_zero(tmp_path: Path) -> None:
    hook = _stage(tmp_path)
    (hook.parent.parent / "mem.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    result = _run(hook)
    assert result.returncode == 0
    assert result.stdout == ""


def test_an_ascii_only_terminal_does_not_break_the_chinese_payload(tmp_path: Path) -> None:
    """LC_ALL=C 之类:注入文案是中文,编码不得炸成非零退出。"""
    import os

    hook = _stage(tmp_path)
    env = dict(os.environ, LC_ALL="C", LANG="C", PYTHONIOENCODING="ascii")
    result = subprocess.run([sys.executable, str(hook)], capture_output=True, text=True, env=env, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "" or "additionalContext" in result.stdout


def test_the_hook_never_changes_the_database_bytes(tmp_path: Path) -> None:
    """boot 会 touch_watermark+commit;hook 必须不改库——冻结后更是如此。

    只钉主库字节。sqlite 的 `mode=ro` 仍会落 `-wal`/`-shm` 侧车(见
    test_cross_layer_find 的第 4 条),那是 sqlite 的行为、不是这个 hook 在写记忆。
    """
    hook = _stage(tmp_path)
    database = hook.parent.parent / "memory.db"
    before = database.read_bytes()
    assert _run(hook).returncode == 0
    assert database.read_bytes() == before
