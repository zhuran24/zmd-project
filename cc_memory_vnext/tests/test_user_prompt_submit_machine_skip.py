# -*- coding: utf-8 -*-
"""UserPromptSubmit 跳过机器消息(2026-08-03 普查 §3.4 第 2 项)。

不接 CI(preflight 快 lane 只跑 src/tests);手跑:
    python -m pytest -p no:randomly --basetemp=.pytest_tmp/upsskip \
        cc_memory_vnext/tests/test_user_prompt_submit_machine_skip.py -q

普查实测:UPS 注入里 56% 的 prompt 是 harness 自己生成的机器消息
(子代理 task-notification / slash 命令回显 / 系统通知),没有读者。本文件钉三件事:
1. 三个机器前缀整体开头 -> 不跑 zmem、不打印任何东西(正例);
2. 真人 prompt(哪怕正文里【提到】这些标记)照常注入(反例);
3. fail-open 语义没变:zmem 失败/stdin 是坏 JSON 都 exit 0、不阻塞 prompt。
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HOOK_PATH = Path(__file__).resolve().parents[1] / "hooks" / "user_prompt_submit.py"


@pytest.fixture()
def hook(monkeypatch):
    spec = importlib.util.spec_from_file_location("user_prompt_submit_under_test", HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        return SimpleNamespace(returncode=0, stdout="# zmem context packet\n## L0\n- some-card", stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    mod._calls = calls
    yield mod
    sys.modules.pop(spec.name, None)


def _run(hook, monkeypatch, capsys, payload):
    raw = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
    rc = hook.main()
    return rc, capsys.readouterr()


MACHINE_PROMPTS = [
    "[SYSTEM NOTIFICATION] background task bcg38 finished",
    "<task-notification>\n<task-id>bcg38</task-id>\n</task-notification>",
    "<local-command-stdout>Set model to opus</local-command-stdout>",
    "<local-command-caveat>Caveat: The messages below were generated…</local-command-caveat>",
    "\n  <task-notification>\n<task-id>x</task-id>\n</task-notification>",
]


@pytest.mark.parametrize("prompt", MACHINE_PROMPTS)
def test_machine_prompts_skip_injection(hook, monkeypatch, capsys, prompt):
    rc, out = _run(hook, monkeypatch, capsys, {"prompt": prompt})
    assert rc == 0
    assert hook._calls == [], "机器消息不该起 zmem 子进程"
    assert out.out == ""


HUMAN_PROMPTS = [
    "继续",
    "帮我看看 <task-notification> 这个标记是哪来的",  # 正文提到标记,不是整体开头
    "把 [SYSTEM NOTIFICATION 的处理逻辑讲讲",
]


@pytest.mark.parametrize("prompt", HUMAN_PROMPTS)
def test_human_prompts_still_inject(hook, monkeypatch, capsys, prompt):
    rc, out = _run(hook, monkeypatch, capsys, {"prompt": prompt})
    assert rc == 0
    assert len(hook._calls) == 1
    assert "context" in hook._calls[0]
    assert "zmem context packet" in out.out


def test_empty_prompt_is_not_treated_as_machine(hook, monkeypatch, capsys):
    # 空 prompt 走原路径(zmem 自己决定给不给包),本批不改这条语义。
    rc, _ = _run(hook, monkeypatch, capsys, {"prompt": ""})
    assert rc == 0
    assert len(hook._calls) == 1


def test_zmem_failure_stays_fail_open(hook, monkeypatch, capsys):
    monkeypatch.setattr(
        hook.subprocess,
        "run",
        lambda cmd, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="index missing"),
    )
    rc, out = _run(hook, monkeypatch, capsys, {"prompt": "真人问题"})
    assert rc == 0
    assert out.out == ""
    assert "skipped" in out.err


def test_non_json_stdin_stays_fail_open(hook, monkeypatch, capsys):
    rc, out = _run(hook, monkeypatch, capsys, "not json at all")
    assert rc == 0
    assert len(hook._calls) == 1  # 退化成把整段当 prompt,仍然注入


def test_non_json_machine_stdin_also_skips(hook, monkeypatch, capsys):
    rc, out = _run(hook, monkeypatch, capsys, "<task-notification>\n<task-id>z</task-id>")
    assert rc == 0
    assert hook._calls == []
    assert out.out == ""


def test_prefix_list_is_the_documented_three():
    spec = importlib.util.spec_from_file_location("user_prompt_submit_prefixes", HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
        assert mod.MACHINE_PROMPT_PREFIXES == (
            "[SYSTEM NOTIFICATION",
            "<task-notification",
            "<local-command",
        )
    finally:
        sys.modules.pop(spec.name, None)
