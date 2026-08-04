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


# --- 1b. 类型化渲染:pinned 行不再透传档案自己的 free-form 摘要 -----------------


@pytest.mark.parametrize("interpreter", INTERPRETERS)
def test_the_pinned_lines_render_the_typed_title(tmp_path: Path, interpreter: str) -> None:
    """真库的 pinned 条目按 `id — title` 渲染,标题就是 entries.title 那一列。"""
    context = _context(_run(_stage(tmp_path), interpreter))
    assert "- `memory-runtime-protocol` — Slim memory runtime protocol" in context


@pytest.mark.parametrize("interpreter", INTERPRETERS)
def test_the_old_write_protocol_never_reaches_the_session(
    tmp_path: Path, interpreter: str
) -> None:
    """冻结前写的 index_summary 还在库里(档案是史料,不改),但不许被注进会话。

    `memory-runtime-protocol` 的摘要原文是「新会话 boot;查询 search/read
    --body/--semantic;改记忆 impact/read → set-fact/add-entry --force(订正)/
    supersede(真取代)→ finalize」——整句都是旧写协议,渲染在冻结横幅底下就成了
    当前指令。这条钉住它不再出现(2026-08-03 对抗审查 stale-pinned-session-payload)。
    """
    context = _context(_run(_stage(tmp_path), interpreter))
    for stale in ("新会话 boot", "--semantic", "set-fact", "add-entry", "supersede"):
        assert stale not in context, stale


def test_a_pinned_entry_whose_summary_is_an_instruction_renders_only_its_title(
    tmp_path: Path,
) -> None:
    """合成一条摘要写满写命令的 pinned 条目,证明这条守卫真的会咬。"""
    hook = _stage(tmp_path)
    connection = sqlite3.connect(hook.parent.parent / "memory.db")
    connection.execute(
        "INSERT OR REPLACE INTO entries "
        "(id, title, body, status, pinned, metadata_json, created_at, updated_at) "
        "VALUES (?, ?, ?, 'active', 1, ?, ?, ?)",
        (
            "aaa-probe-entry",
            "probe title only",
            "先跑 boot 再 set-fact --force 然后 add-entry",
            json.dumps({"index_summary": "新会话 boot;set-fact/add-entry --force;--semantic"}),
            "2026-08-03T00:00:00Z",
            "2026-08-03T00:00:00Z",
        ),
    )
    connection.commit()
    connection.close()
    context = _context(_run(hook))
    assert "- `aaa-probe-entry` — probe title only" in context
    for stale in ("新会话 boot", "set-fact", "add-entry", "--semantic"):
        assert stale not in context, stale


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


@pytest.mark.parametrize("interpreter", INTERPRETERS)
def test_a_shadowed_stdlib_module_beside_the_hook_never_runs(
    tmp_path: Path, interpreter: str
) -> None:
    """hook 自己的目录被踢出 sys.path,`hooks/json.py` 压根轮不到被 import。

    以脚本方式跑 hook 时,Python 把 hook 所在目录放在 sys.path 最前面,所以
    `cc_memory/hooks/json.py` 会先于标准库被 import。旧版本这个 import 在任何
    guard 之外,一个 RuntimeError 就让 SessionStart 拿到 rc=1 + traceback
    (2026-08-03 对抗审查 sessionstart-fail-open)。现在两道防线:路径先被摘掉
    (这条),摘不掉时还有 fail-open 边界兜底(下一条)。
    """
    hook = _stage(tmp_path)
    (hook.parent / "json.py").write_text(
        "raise RuntimeError('shadowed stdlib module reached')\n", encoding="utf-8"
    )
    result = _run(hook, interpreter)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert "shadowed stdlib module reached" not in result.stderr
    assert "additionalContext" in result.stdout, "正常注入不该被这个投毒文件影响"


@pytest.mark.parametrize("interpreter", INTERPRETERS)
def test_a_failing_import_inside_the_guard_is_silent_and_zero(
    tmp_path: Path, interpreter: str
) -> None:
    """import 本身也在 fail-open 边界里。

    `PYTHONPATH` 排在标准库前面、又不是 hook 自己的目录,所以路径加固摘不掉
    它——正好用来证明边界(而不是加固)在托底:`sqlite3` import 直接炸,进程
    仍必须 rc=0 且不打印。
    """
    hook = _stage(tmp_path)
    poison = tmp_path / "poison"
    poison.mkdir()
    (poison / "sqlite3.py").write_text(
        "raise RuntimeError('poisoned sqlite3 reached')\n", encoding="utf-8"
    )
    import os

    env = dict(os.environ, PYTHONPATH=str(poison))
    result = subprocess.run(
        [interpreter, str(hook)], capture_output=True, text=True, env=env, timeout=60
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.parametrize("interpreter", INTERPRETERS)
def test_a_mem_module_raising_system_exit_is_silent_and_zero(
    tmp_path: Path, interpreter: str
) -> None:
    """`SystemExit` 继承 BaseException,旧的 `except Exception` 漏它。

    mem.py 是被 exec_module 真跑起来的仓库内文件,它抛 SystemExit(23) 会原样
    穿过旧 guard,让 hook 用攻击者选定的退出码结束。
    """
    hook = _stage(tmp_path)
    (hook.parent.parent / "mem.py").write_text("raise SystemExit(23)\n", encoding="utf-8")
    result = _run(hook, interpreter)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


@pytest.mark.parametrize("interpreter", INTERPRETERS)
def test_a_mem_module_raising_a_bare_base_exception_is_silent_and_zero(
    tmp_path: Path, interpreter: str
) -> None:
    """SystemExit 只是最干净的一例,任何 BaseException 子类都要被吞掉。"""
    hook = _stage(tmp_path)
    (hook.parent.parent / "mem.py").write_text(
        "class Boom(BaseException):\n    pass\n\n\nraise Boom('not an Exception')\n",
        encoding="utf-8",
    )
    result = _run(hook, interpreter)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_only_sys_is_imported_outside_the_fail_open_boundary() -> None:
    """顶层只留 `import sys`——它是唯一不可能被仓库内文件顶掉的模块。

    这条打在源码结构上:边界的正确性靠「guard 之外没有可失败的代码」,不是靠
    上面那几条恰好想到的触发式。
    """
    import ast

    tree = ast.parse(HOOK_PATH.read_text(encoding="utf-8"))
    top_level_imports = [
        node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    names = sorted(
        alias.name for node in top_level_imports if isinstance(node, ast.Import) for alias in node.names
    )
    assert names == ["sys"], names
    assert not [node for node in top_level_imports if isinstance(node, ast.ImportFrom)]
    assigned = [node for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign))]
    assert assigned == [], "顶层不许再算路径常量,它们要在 guard 里算"


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
