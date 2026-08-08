# -*- coding: utf-8 -*-
"""注入通道死掉必须留下两个记号:一行 OFF + 一条 recall_failure(M-05 / M-30)。

病灶:两个活 hook(SessionStart / UserPromptSubmit)对 zmem 的任何失败都 fail-open
——注入零字节、退出 0、只往 stderr 写一句 `skipped`。而 hook 的 stderr 不进转录,
所以「召回死了」和「这一回合本来就没卡可注」在我这边**长得一模一样**;生产零注入
率本底 32-37%,任何故障都能在里面躲着不被发现。附带死掉的还有随包走的
`!! STALE INDEX` 警告——注入一断,那条守卫也跟着哑了。

修法不动 fail-open 底线(退出码永远 0、绝不抛异常炸 hook),只加两个出口:
* stdout 一行 `!! MEMORY RECALL OFF: <原因>`,顶替消失的那个包;
* activation log 追一条 `{"event":"recall_failure", ...}`,让事后能算故障率。

手跑:
    python -m pytest -p no:randomly --basetemp=.pytest_tmp/recalloff \
        cc_memory_vnext/tests/test_recall_failure_visibility.py -q
进门:preflight 记忆 lane 整目录收集 `cc_memory_vnext/tests`。

**全部走真链**:把真 hook 复制进 tmp 树、旁边放可控替身 `zmem.py`、用真 stdin 字节
起真子进程,读它真打出来的 stdout 和真写出来的日志文件。不打桩 `subprocess.run`
——08-03 审查的教训就是打桩把五条真实异常路径全放过了。仓库里那份真
`logs/activation_decisions.jsonl` 一个字节都不碰。

三条承重断言,对应三个性质:正常路径必须一字不变(假阳性会被无视)、失败路径必须
出声(否则守卫是摆设)、日志写不进去也不能把出声那半带走(日志是次要出口)。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1] / "hooks"

OFF_MARK = b"MEMORY RECALL OFF"
LOG_RELPATH = Path("logs") / "activation_decisions.jsonl"

# 两个 hook 的差别只有 stdin 形状和超时 env 名;承重语义完全对称,所以整份文件
# 按 hook 参数化跑两遍。漏掉任何一个 = 那一半的注入通道仍然是静默的。
HOOKS = ("session_start.py", "user_prompt_submit.py")
TIMEOUT_ENV = {
    "session_start.py": "ZMEM_SESSION_START_TIMEOUT_SECONDS",
    "user_prompt_submit.py": "ZMEM_UPS_TIMEOUT_SECONDS",
}

FAKE_ZMEM_OK = """
import sys
sys.stdout.write("# zmem context packet\\nversion: v1\\n## L0\\n- some-card\\n")
"""

FAKE_ZMEM_FAILS = """
import sys
sys.stderr.write("CONTEXT FAIL: index missing: /nope/cards_index.json\\n")
raise SystemExit(1)
"""

FAKE_ZMEM_FAILS_MULTILINE = """
import sys
sys.stderr.write("Traceback (most recent call last):\\n  File x\\nZmemError: boom\\n")
raise SystemExit(3)
"""

FAKE_ZMEM_HANGS = """
import time
time.sleep(60)
"""


def _tree(tmp_path: Path, hook_name: str, zmem_source: str | None) -> Path:
    """真 hook 副本 + 可控替身 zmem,和生产同构的一棵小树。"""
    root = tmp_path / "vnext"
    (root / "hooks").mkdir(parents=True)
    hook = root / "hooks" / hook_name
    shutil.copy2(HOOKS_DIR / hook_name, hook)
    if zmem_source is not None:
        (root / "zmem.py").write_text(zmem_source, encoding="utf-8")
    return hook


def _vnext_root(hook: Path) -> Path:
    return hook.parent.parent


def _log_path(hook: Path) -> Path:
    return _vnext_root(hook) / LOG_RELPATH


def _run(hook: Path, env_extra: dict[str, str] | None = None, timeout: float = 60.0):
    """起真子进程。stdin 给两个 hook 都喂 payload:SessionStart 不读,无害。"""
    env = dict(os.environ)
    for name in TIMEOUT_ENV.values():
        env.pop(name, None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps({"prompt": "真人问题"}, ensure_ascii=False).encode("utf-8"),
        capture_output=True,
        timeout=timeout,
        env=env,
    )


def _records(hook: Path) -> list[dict]:
    path = _log_path(hook)
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def _failures(hook: Path) -> list[dict]:
    return [record for record in _records(hook) if record.get("event") == "recall_failure"]


# --- 1. 正常路径:一字不变 ---------------------------------------------------


@pytest.mark.parametrize("hook_name", HOOKS)
def test_healthy_recall_prints_no_off_line(tmp_path, hook_name):
    """包正常送达时不许有 OFF 行:假阳性一周内就会让人把这行当噪音无视掉。"""
    hook = _tree(tmp_path, hook_name, FAKE_ZMEM_OK)
    proc = _run(hook)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert OFF_MARK not in proc.stdout, proc.stdout
    assert b"zmem context packet" in proc.stdout


@pytest.mark.parametrize("hook_name", HOOKS)
def test_healthy_recall_writes_no_failure_record(tmp_path, hook_name):
    hook = _tree(tmp_path, hook_name, FAKE_ZMEM_OK)
    assert _run(hook).returncode == 0
    # 替身 zmem 不写日志,所以正常路径下这个文件根本不该被 hook 建出来。
    assert _failures(hook) == []


@pytest.mark.parametrize("hook_name", HOOKS)
def test_healthy_packet_is_byte_identical_to_the_child_output(tmp_path, hook_name):
    """成功路径的 stdout = 子进程 stdout 去尾空白,加守卫前后逐字节相同。"""
    hook = _tree(tmp_path, hook_name, FAKE_ZMEM_OK)
    proc = _run(hook)
    expected = "# zmem context packet\nversion: v1\n## L0\n- some-card\n".strip() + "\n"
    assert proc.stdout.decode("utf-8") == expected


# --- 2. 失败路径:必须出声 ---------------------------------------------------


@pytest.mark.parametrize("hook_name", HOOKS)
def test_zmem_nonzero_exit_prints_off_line(tmp_path, hook_name):
    hook = _tree(tmp_path, hook_name, FAKE_ZMEM_FAILS)
    proc = _run(hook)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert OFF_MARK in proc.stdout, proc.stdout
    # 原因要能指向真因,不能只说「失败了」。
    assert b"index missing" in proc.stdout


@pytest.mark.parametrize("hook_name", HOOKS)
def test_zmem_nonzero_exit_logs_recall_failure(tmp_path, hook_name):
    hook = _tree(tmp_path, hook_name, FAKE_ZMEM_FAILS)
    assert _run(hook).returncode == 0
    failures = _failures(hook)
    assert len(failures) == 1, failures
    record = failures[0]
    assert record["ts"]
    assert "index missing" in record["reason"]
    assert record["hook"] in ("SessionStart", "UserPromptSubmit")


@pytest.mark.parametrize("hook_name", HOOKS)
def test_missing_zmem_prints_off_line(tmp_path, hook_name):
    """zmem 整个不在 = 最坏情形;子进程根本起不来也得出声。"""
    hook = _tree(tmp_path, hook_name, None)
    proc = _run(hook)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert OFF_MARK in proc.stdout, proc.stdout
    assert len(_failures(hook)) == 1


@pytest.mark.parametrize("hook_name", HOOKS)
def test_hanging_zmem_prints_off_line_within_budget(tmp_path, hook_name):
    """挂死的子进程被超时掐掉之后,同样要留下两个记号。"""
    hook = _tree(tmp_path, hook_name, FAKE_ZMEM_HANGS)
    proc = _run(hook, env_extra={TIMEOUT_ENV[hook_name]: "0.5"}, timeout=30.0)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert OFF_MARK in proc.stdout, proc.stdout
    assert len(_failures(hook)) == 1


@pytest.mark.parametrize("hook_name", HOOKS)
def test_off_reason_is_one_line(tmp_path, hook_name):
    """多行 traceback 必须压成一行:OFF 行是一行,刷屏的守卫等于没有守卫。"""
    hook = _tree(tmp_path, hook_name, FAKE_ZMEM_FAILS_MULTILINE)
    proc = _run(hook)
    assert proc.returncode == 0
    lines = [line for line in proc.stdout.decode("utf-8").splitlines() if line.strip()]
    assert len(lines) == 1, lines
    assert lines[0].startswith("!! MEMORY RECALL OFF: ")
    assert "ZmemError: boom" in lines[0]


@pytest.mark.parametrize("hook_name", HOOKS)
def test_off_line_survives_ascii_only_locale(tmp_path, hook_name):
    """LC_ALL=C 下 OFF 行仍要打得出来:它是纯 ASCII,就是为这一条。"""
    hook = _tree(tmp_path, hook_name, FAKE_ZMEM_FAILS)
    proc = _run(
        hook,
        env_extra={
            "LC_ALL": "C",
            "LANG": "C",
            "PYTHONIOENCODING": "ascii",
            "PYTHONUTF8": "0",
            "PYTHONCOERCECLOCALE": "0",
        },
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert OFF_MARK in proc.stdout, proc.stdout
    assert b"UnicodeEncodeError" not in proc.stderr


@pytest.mark.parametrize("hook_name", HOOKS)
def test_off_line_mentions_the_stale_index_check_is_off_too(tmp_path, hook_name):
    """连带损失要写在脸上:注入一死,随包的 STALE INDEX 守卫也跟着哑了。"""
    hook = _tree(tmp_path, hook_name, FAKE_ZMEM_FAILS)
    assert b"STALE INDEX" in _run(hook).stdout


# --- 3. 日志写不进去 ≠ 出声那半也没了 ---------------------------------------


def _off_lines(proc) -> list[str]:
    return [line for line in proc.stdout.decode("utf-8").splitlines() if OFF_MARK.decode() in line]


@pytest.mark.parametrize("hook_name", HOOKS)
def test_unwritable_log_still_prints_exactly_one_off_line(tmp_path, hook_name):
    """`logs` 被一个普通文件占住 = 日志出口彻底不可用(mkdir 直接抛)。

    钉的是**恰好一行**,不是"至少一行":日志追加不吞异常的那一版里,异常会从
    `recall_off` 一路冒到顶层兜底网,兜底网又调一次 `recall_off` —— stdout 变成两行
    OFF、真因被"hook 自己炸了"盖掉,而"至少一行"的断言对此一无所知(实测:该变异
    体在加这条之前全绿存活)。日志是次要出口,不许把主要出口搅浑,也不许把退出码
    带成非零。
    """
    hook = _tree(tmp_path, hook_name, FAKE_ZMEM_FAILS)
    blocker = _vnext_root(hook) / "logs"
    blocker.write_text("not a directory", encoding="utf-8")

    proc = _run(hook)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert len(_off_lines(proc)) == 1, proc.stdout
    # 真因仍要指向 zmem,不能被"hook 自己炸了"顶掉。
    assert "index missing" in _off_lines(proc)[0]
    assert b"Traceback" not in proc.stderr
    assert blocker.read_text(encoding="utf-8") == "not a directory"


@pytest.mark.parametrize("hook_name", HOOKS)
def test_readonly_log_dir_still_prints_exactly_one_off_line(tmp_path, hook_name):
    """目录在但不可写(0o500)是另一种真实形态,同样只掉日志、不掉 OFF 行。"""
    hook = _tree(tmp_path, hook_name, FAKE_ZMEM_FAILS)
    logs = _vnext_root(hook) / "logs"
    logs.mkdir(parents=True)
    logs.chmod(0o500)
    try:
        proc = _run(hook)
        assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
        assert len(_off_lines(proc)) == 1, proc.stdout
        assert "index missing" in _off_lines(proc)[0]
    finally:
        logs.chmod(0o700)


# --- 4. hook 自己炸了 -------------------------------------------------------


@pytest.mark.parametrize("hook_name", HOOKS)
def test_hook_internal_crash_still_prints_off_line(tmp_path, hook_name):
    """最坏情形:hook 自身在起子进程之前就抛。

    删掉 `sys.executable` —— 两个 hook 都用它拼 argv,`_run` 里读它当场抛
    AttributeError,失败点落在顶层 `except BaseException` 那一层而不是子进程分支。
    这条钉的是「兜底网也要出声」:兜底网只 `return 0` 的那一版,正是本批要消灭的
    静默。
    """
    hook = _tree(tmp_path, hook_name, FAKE_ZMEM_OK)
    driver = hook.parent / "crash_driver.py"
    driver.write_text(
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('hook_under_test', {str(hook)!r})\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "sys.modules['hook_under_test'] = mod\n"
        "spec.loader.exec_module(mod)\n"
        "del sys.executable\n"
        "raise SystemExit(mod.main())\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(driver)],
        input=b'{"prompt": "x"}',
        capture_output=True,
        timeout=60.0,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert OFF_MARK in proc.stdout, proc.stdout
    assert len(_failures(hook)) == 1
    assert "raised" in _failures(hook)[0]["reason"]


# --- 5. 记录形状不砸既有消费方 ----------------------------------------------


@pytest.mark.parametrize("hook_name", HOOKS)
def test_failure_record_is_readable_by_the_injection_ledger_reader(tmp_path, hook_name):
    """`devtools/memory_reference_scan.py` 逐行读这个日志算 never_read_card。

    它对每条记录取 `record.get("injected") or ()`,所以新记录没有 `injected` 字段
    也不会炸;这里正面钉住这个形状,免得后来有人给失败记录塞个空 `injected`
    列表——那会让「这张卡从没被注入过」的判据平白多出一堆空样本。
    """
    hook = _tree(tmp_path, hook_name, FAKE_ZMEM_FAILS)
    assert _run(hook).returncode == 0
    record = _failures(hook)[0]
    assert "injected" not in record
    assert set(record) == {"event", "ts", "hook", "reason"}
