# -*- coding: utf-8 -*-
"""UserPromptSubmit: 机器消息跳注 + 严格 fail-open(2026-08-03 普查 §3.4 第 2 项)。

不接 CI(preflight 快 lane 只跑 src/tests);手跑:
    python -m pytest -p no:randomly --basetemp=.pytest_tmp/upsskip \
        cc_memory_vnext/tests/test_user_prompt_submit_machine_skip.py -q

**本文件全部走真实 CLI 子进程**:把 hook 原样复制到 tmp 树、在旁边放一个替身
`zmem.py`,再用真实 stdin 字节 / 真实环境变量把它跑起来。上一版用
`monkeypatch.setattr(subprocess, "run")` 直接调 `main()`,结果是 08-03 审查列出的
五条真实异常路径(顶层非 object 的 JSON / 子进程起不来 / 子进程挂死 / 子进程输出
非法 UTF-8 / ASCII-only 终端)一条都没被咬住,而 docstring 已经写着"any error
means exit 0"。替身进程是唯一能让这些路径真的发生的办法。

钉三件事:
1. 三个机器前缀 + 结构终止符 -> 不起 zmem 子进程、不打印任何东西;
2. 前缀边界:`<task-notifications>` / `<local-commandment>` /
   `[SYSTEM NOTIFICATIONAL]` 这些真人能打出来的词照常注入(旧 startswith 全吞);
3. fail-open 是实测真话:上述五条路径逐条 exit 0。
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parents[1] / "hooks" / "user_prompt_submit.py"

SENTINEL_NAME = "zmem_was_started"

# 替身 zmem:证明"子进程确实被起过"(写哨兵文件)并回一个可断言的包。
FAKE_ZMEM_OK = """
import pathlib, sys
pathlib.Path(__file__).with_name({sentinel!r}).write_text("1", encoding="utf-8")
sys.stdout.write("# zmem context packet\\n## L0\\n- some-card\\n")
""".format(sentinel=SENTINEL_NAME)

FAKE_ZMEM_FAILS = """
import sys
sys.stderr.write("index missing\\n")
raise SystemExit(1)
"""

# 非法 UTF-8:裸 0xff / 截断的多字节序列。text=True + errors="replace" 之前
# 这里是 UnicodeDecodeError -> exit 1。
FAKE_ZMEM_BAD_UTF8 = r"""
import sys
sys.stdout.buffer.write(b"# packet \xff\xfe \xc3(\n")
sys.stdout.buffer.flush()
"""

FAKE_ZMEM_HANGS = """
import time
time.sleep(60)
"""

# ASCII-only 终端下打印中文:_encodable 之前这里是 UnicodeEncodeError -> exit 1。
# 替身自己走 buffer 写死 UTF-8 字节,免得它先被 PYTHONIOENCODING=ascii 干掉 ——
# 要测的是 hook 打印中文包这一步,不是替身自己的编码。
FAKE_ZMEM_CHINESE = """
import sys
sys.stdout.buffer.write("# zmem 上下文包\\n## L0\\n- 并发会话共享 index 坑\\n".encode("utf-8"))
sys.stdout.buffer.flush()
"""


def _tree(tmp_path: Path, zmem_source: str | None) -> Path:
    """真实 hook 副本 + 可控替身 zmem,组成一棵和生产同构的小树。"""
    root = tmp_path / "vnext"
    (root / "hooks").mkdir(parents=True)
    hook = root / "hooks" / "user_prompt_submit.py"
    shutil.copy2(HOOK_PATH, hook)
    if zmem_source is not None:
        (root / "zmem.py").write_text(zmem_source, encoding="utf-8")
    return hook


def _run(hook: Path, stdin: bytes | str, env_extra: dict[str, str] | None = None, timeout: float = 60.0):
    data = stdin.encode("utf-8") if isinstance(stdin, str) else stdin
    import os

    env = dict(os.environ)
    env.pop("ZMEM_UPS_TIMEOUT_SECONDS", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(hook)],
        input=data,
        capture_output=True,
        timeout=timeout,
        env=env,
    )


def _started(hook: Path) -> bool:
    return (hook.parent.parent / SENTINEL_NAME).exists()


def _payload(prompt: str) -> str:
    import json

    return json.dumps({"prompt": prompt}, ensure_ascii=False)


# --- 1. 机器消息:不起子进程、不打印 ---------------------------------------

MACHINE_PROMPTS = [
    "[SYSTEM NOTIFICATION] background task bcg38 finished",
    "[SYSTEM NOTIFICATION - background task bcg38 finished]",
    "[SYSTEM NOTIFICATION background task finished]",
    "<task-notification>\n<task-id>bcg38</task-id>\n</task-notification>",
    "<task-notification agent=\"Q3\">\n<task-id>x</task-id>\n</task-notification>",
    "<local-command-stdout>Set model to opus</local-command-stdout>",
    "<local-command-caveat>Caveat: The messages below were generated…</local-command-caveat>",
    "\n  <task-notification>\n<task-id>x</task-id>\n</task-notification>",
]


@pytest.mark.parametrize("prompt", MACHINE_PROMPTS)
def test_machine_prompts_skip_injection(tmp_path, prompt):
    hook = _tree(tmp_path, FAKE_ZMEM_OK)
    proc = _run(hook, _payload(prompt))
    assert proc.returncode == 0
    assert proc.stdout == b""
    assert not _started(hook), "机器消息不该起 zmem 子进程"


# --- 2. 前缀边界:真人 prompt 照常注入 --------------------------------------

HUMAN_PROMPTS = [
    "继续",
    # 08-03 审查点名的三个反例:旧 startswith 全部误吞、且吞得悄无声息。
    "<task-notifications> schema question",
    "<local-commandment> wording question",
    "[SYSTEM NOTIFICATIONAL] wording question",
    # 正文里【提到】标记,不是整体开头。
    "帮我看看 <task-notification> 这个标记是哪来的",
    "把 [SYSTEM NOTIFICATION 的处理逻辑讲讲",
]


@pytest.mark.parametrize("prompt", HUMAN_PROMPTS)
def test_human_prompts_still_inject(tmp_path, prompt):
    hook = _tree(tmp_path, FAKE_ZMEM_OK)
    proc = _run(hook, _payload(prompt))
    assert proc.returncode == 0
    assert _started(hook), f"真人 prompt 被误当机器消息吞掉: {prompt!r}"
    assert b"zmem context packet" in proc.stdout


def test_empty_prompt_is_not_treated_as_machine(tmp_path):
    # 空 prompt 走原路径(zmem 自己决定给不给包),本批不改这条语义。
    hook = _tree(tmp_path, FAKE_ZMEM_OK)
    proc = _run(hook, _payload(""))
    assert proc.returncode == 0
    assert _started(hook)


# --- 3. fail-open:hostile stdin --------------------------------------------

HOSTILE_STDIN = [
    pytest.param(b"[]", id="toplevel-array"),
    pytest.param(b'"human"', id="toplevel-string"),
    pytest.param(b"0", id="toplevel-number"),
    pytest.param(b"false", id="toplevel-false"),
    pytest.param(b"null", id="toplevel-null"),
    pytest.param(b"", id="empty"),
    pytest.param(b"not json at all", id="not-json"),
    pytest.param(b"{unclosed", id="broken-json"),
    # 非法 UTF-8 字节流(stdin 侧)。
    pytest.param(b'{"prompt": "\xff\xfe broken"}', id="non-utf8-bytes"),
]


@pytest.mark.parametrize("raw", HOSTILE_STDIN)
def test_hostile_stdin_stays_fail_open(tmp_path, raw):
    hook = _tree(tmp_path, FAKE_ZMEM_OK)
    proc = _run(hook, raw)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert b"Traceback" not in proc.stderr


# --- 4. fail-open:子进程侧的四种真实事故 ------------------------------------


def test_missing_zmem_stays_fail_open(tmp_path):
    hook = _tree(tmp_path, None)  # 没有 zmem.py
    proc = _run(hook, _payload("真人问题"))
    assert proc.returncode == 0
    assert proc.stdout == b""
    assert b"skipped" in proc.stderr


def test_zmem_nonzero_exit_stays_fail_open(tmp_path):
    hook = _tree(tmp_path, FAKE_ZMEM_FAILS)
    proc = _run(hook, _payload("真人问题"))
    assert proc.returncode == 0
    assert proc.stdout == b""
    assert b"skipped" in proc.stderr


def test_zmem_invalid_utf8_output_stays_fail_open(tmp_path):
    hook = _tree(tmp_path, FAKE_ZMEM_BAD_UTF8)
    proc = _run(hook, _payload("真人问题"))
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert b"Traceback" not in proc.stderr
    assert b"packet" in proc.stdout


def test_hanging_zmem_is_bounded_and_fail_open(tmp_path):
    hook = _tree(tmp_path, FAKE_ZMEM_HANGS)
    started = time.monotonic()
    proc = _run(hook, _payload("真人问题"), env_extra={"ZMEM_UPS_TIMEOUT_SECONDS": "0.5"}, timeout=30.0)
    elapsed = time.monotonic() - started
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert elapsed < 20.0, f"超时保护没生效,等了 {elapsed:.1f}s"
    assert b"skipped" in proc.stderr


def test_ascii_only_stdout_stays_fail_open(tmp_path):
    """LC_ALL=C 之类 ASCII-only 环境:中文包不得炸成 exit 1。"""
    hook = _tree(tmp_path, FAKE_ZMEM_CHINESE)
    proc = _run(
        hook,
        _payload("human question"),
        env_extra={
            "LC_ALL": "C",
            "LANG": "C",
            "PYTHONIOENCODING": "ascii",
            "PYTHONUTF8": "0",
            "PYTHONCOERCECLOCALE": "0",
        },
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert b"UnicodeEncodeError" not in proc.stderr
    assert b"Traceback" not in proc.stderr
    assert b"zmem" in proc.stdout


# --- 5. run_zmem 的 OSError / 超时家族(直调真实函数,不打桩) ---------------


def _module():
    spec = importlib.util.spec_from_file_location("user_prompt_submit_under_test", HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return mod


def test_run_zmem_returns_none_when_binary_missing():
    mod = _module()
    try:
        assert mod.run_zmem(["/nonexistent/zmem-binary-xyz"]) is None
    finally:
        sys.modules.pop("user_prompt_submit_under_test", None)


def test_run_zmem_returns_none_on_timeout():
    mod = _module()
    try:
        assert mod.run_zmem([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.5) is None
    finally:
        sys.modules.pop("user_prompt_submit_under_test", None)


# --- 6. 前缀表与其残余歧义的自白 --------------------------------------------


def test_prefix_table_is_the_documented_three_with_terminators():
    mod = _module()
    try:
        assert mod.MACHINE_PROMPT_PREFIXES == (
            ("[SYSTEM NOTIFICATION", r"[ \-\]]"),
            ("<task-notification", r"[>\s]"),
            ("<local-command", r"[->]"),
        )
    finally:
        sys.modules.pop("user_prompt_submit_under_test", None)


def test_residual_ambiguity_is_declared_in_docstring():
    """结构边界之外不再加聪明判断——但这条残余歧义必须留在 docstring 里。"""
    mod = _module()
    try:
        doc = mod.is_machine_prompt.__doc__ or ""
        assert "<task-notification> what does this tag mean?" in doc
        # 这句真人 prompt 确实会被吞:声明的就是它,不许悄悄改语义又不改自白。
        assert mod.is_machine_prompt("<task-notification> what does this tag mean?") is True
    finally:
        sys.modules.pop("user_prompt_submit_under_test", None)
