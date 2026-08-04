# -*- coding: utf-8 -*-
"""mem.py 的冻结口径:boot 横幅 + 写命令提醒(2026-08-03 owner 拍板)。

手跑:
    python -m pytest -p no:randomly --basetemp=.pytest_tmp/freeze \\
        cc_memory/tests/test_archive_freeze_notices.py -q

冻结是个纯文本机制——没有任何东西被拦住,拦住就等于放弃档案订正能力。所以它
能不能起作用,全看那两句话在不在、说得对不对。本文件钉的就是这个:

1. `boot` 顶部有冻结横幅(日期 + 新记忆去文件记忆层 + 读侧照常),且旧推销文案
   (「Semantic + rerank retrieval」整节、「main win」、suggest-before-adding)
   已经不再打印;
2. 每条写命令执行前打一行醒目提醒到 stderr,**且不阻断**(退出码照常、写入照常),
   `init --reset`(清空整个档案)也在内;
3. `finalize` 不打提醒——它是收口动作,重复提醒只会训练读者跳过这行。

全部跑在 tmp 库副本上:真实 `cc_memory/memory.db` 一个字节都不碰(用例自证)。
"""
from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

CC_MEMORY = Path(__file__).resolve().parents[1]
MEM_PATH = CC_MEMORY / "mem.py"
REAL_DB = CC_MEMORY / "memory.db"

# C 部分口径:这五条是任务书点名的写命令,mem.py 实际覆盖面更宽(见
# ARCHIVE_WRITE_COMMANDS),这里钉住点名的那五条一条不少。
# 每条都给足最小合法参数:argparse 报错会在 main() 之前退出,那样测的就不是
# 提醒有没有打、而是 argparse 有没有拦。
NAMED_WRITE_COMMANDS = {
    "add-entry": ("add-entry", "--title", "freeze probe"),
    "set-fact": ("set-fact", "--subject", "probe", "--predicate", "is", "--value", "a probe"),
    "add-event": ("add-event", "--text", "freeze probe"),
    "propose": ("propose", "--operation", "update_fact", "--touches", "probe-id", "--reason", "freeze probe"),
    "supersede": ("supersede", "probe-new", "probe-old"),
}


@pytest.fixture
def sandbox(tmp_path: Path) -> tuple[Path, Path]:
    database = tmp_path / "memory.db"
    shutil.copy2(REAL_DB, database)
    return database, tmp_path / "export.md"


def _mem(sandbox: tuple[Path, Path], *args: str) -> subprocess.CompletedProcess[str]:
    database, export = sandbox
    return subprocess.run(
        [sys.executable, str(MEM_PATH), "--db", str(database), "--export", str(export), *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_boot_leads_with_the_freeze_banner(sandbox: tuple[Path, Path]) -> None:
    result = _mem(sandbox, "boot")
    assert result.returncode == 0, result.stderr
    head = result.stdout.split("## Session")[0]
    assert "只读档案" in head
    assert "2026-08-03" in head
    assert "文件记忆层" in head


def test_boot_still_offers_the_read_side(sandbox: tuple[Path, Path]) -> None:
    stdout = _mem(sandbox, "boot").stdout
    for command in ("search", "read <id> --body", "find <id>", "impact <id>"):
        assert command in stdout, command


def test_boot_no_longer_pitches_the_retrieval_layer(sandbox: tuple[Path, Path]) -> None:
    stdout = _mem(sandbox, "boot").stdout
    for retired in (
        "Semantic + rerank retrieval",
        "this is the main win",
        "before adding memory",
    ):
        assert retired not in stdout, retired


@pytest.mark.parametrize("command", sorted(NAMED_WRITE_COMMANDS))
def test_every_named_write_command_warns_before_running(
    sandbox: tuple[Path, Path], command: str
) -> None:
    """提醒在命令跑之前打出来,命令本身成不成功都一样(supersede 会失败,照样提醒)。"""
    result = _mem(sandbox, *NAMED_WRITE_COMMANDS[command])
    assert "冻结为只读档案" in result.stderr, (command, result.stderr)
    assert "2026-08-03" in result.stderr


def test_the_warning_does_not_block_the_write(sandbox: tuple[Path, Path]) -> None:
    database, _ = sandbox
    before = database.read_bytes()
    result = _mem(sandbox, "add-event", "--text", "archive revision probe")
    assert result.returncode == 0, result.stderr
    assert "冻结为只读档案" in result.stderr
    assert database.read_bytes() != before, "写命令必须仍然真的写进去"


def test_the_warning_goes_to_stderr_not_into_the_parsed_output(
    sandbox: tuple[Path, Path],
) -> None:
    result = _mem(sandbox, "add-event", "--text", "probe")
    assert "冻结为只读档案" not in result.stdout


def test_init_reset_warns_before_dropping_the_archive(sandbox: tuple[Path, Path]) -> None:
    """`init --reset` 是这个 CLI 能对档案做的最狠的一件事,它必须先提醒。

    它 drop 掉并重建全部受管表——4 facts / 11 entries / 14 edges 归零——而第一版
    ARCHIVE_WRITE_COMMANDS 恰恰漏了它,于是唯一最具破坏性的写路径成了全 CLI 里
    唯一不提醒的那条(2026-08-03 对抗审查 archive-init-warning-bypass)。
    """
    database, _ = sandbox

    def _counts() -> dict[str, int]:
        connection = sqlite3.connect(database)
        try:
            return {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("facts", "entries", "edges")
            }
        finally:
            connection.close()

    before = _counts()
    assert sum(before.values()) > 0, "样本库本来就是空的话这条测不出东西"
    result = _mem(sandbox, "init", "--reset")
    assert result.returncode == 0, result.stderr
    assert "冻结为只读档案" in result.stderr, result.stderr
    assert "2026-08-03" in result.stderr
    # 提醒是 advisory,不阻断:reset 照样发生。
    assert sum(_counts().values()) == 0


def test_plain_init_also_warns_because_it_is_the_same_write_command(
    sandbox: tuple[Path, Path],
) -> None:
    """登记按函数对象走,所以 `init`(不带 --reset)也提醒——宁可多说一句。"""
    result = _mem(sandbox, "init")
    assert result.returncode == 0, result.stderr
    assert "冻结为只读档案" in result.stderr


def test_boot_read_first_lines_render_titles_not_archive_prose(
    sandbox: tuple[Path, Path],
) -> None:
    """boot 的 Read first 段也停止透传 index_summary(与 SessionStart hook 同批)。

    `memory-runtime-protocol` 的摘要是冻结前写的旧写协议(boot / --semantic /
    set-fact / add-entry),打在冻结横幅底下就是当前指令。整段改成 `id — title`。
    """
    stdout = _mem(sandbox, "boot").stdout
    read_first = stdout.split("## Read first", 1)[1].split("## Commands", 1)[0]
    assert "- `memory-runtime-protocol` — Slim memory runtime protocol" in read_first
    for stale in ("新会话 boot", "--semantic", "set-fact", "add-entry", "supersede"):
        assert stale not in read_first, stale


def test_finalize_is_the_closing_action_and_does_not_warn(sandbox: tuple[Path, Path]) -> None:
    result = _mem(sandbox, "finalize", "--no-gpu")
    assert result.returncode == 0, result.stderr
    assert "冻结为只读档案" not in result.stderr


@pytest.mark.parametrize("command", ("boot", "search", "read", "find", "impact"))
def test_the_read_side_never_warns(sandbox: tuple[Path, Path], command: str) -> None:
    result = _mem(sandbox, command, "probe") if command != "boot" else _mem(sandbox, command)
    assert "冻结为只读档案" not in result.stderr


def test_the_named_write_commands_are_all_in_the_registered_set() -> None:
    """按函数对象登记,改子命令名字掉不出去;这里核对点名的五条 + `init` 都在。

    `init` 是 2026-08-03 对抗审查补进来的:它带 `--reset` 会清空整个档案,却是
    第一版登记里唯一漏掉的写命令。
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("mem_under_test_freeze", MEM_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["mem_under_test_freeze"] = module
    try:
        spec.loader.exec_module(module)
        registered = module.ARCHIVE_WRITE_COMMANDS
        for name in (
            "cmd_init",
            "cmd_add_entry",
            "cmd_set_fact",
            "cmd_add_event",
            "cmd_propose",
            "cmd_supersede",
        ):
            assert getattr(module, name) in registered, name
        assert module.cmd_finalize not in registered
        assert module.cmd_boot not in registered
    finally:
        sys.modules.pop("mem_under_test_freeze", None)


def test_the_real_database_is_never_touched_by_this_file(sandbox: tuple[Path, Path]) -> None:
    before = REAL_DB.read_bytes()
    _mem(sandbox, "add-event", "--text", "probe")
    assert REAL_DB.read_bytes() == before
