# -*- coding: utf-8 -*-
"""pre_tool_risk_gate.py 多会话总开关测试(2026-07-06 落地 + 对抗审查修复回归)。

不接 CI(preflight 快 lane 只跑 src/tests);手跑:
    python -m pytest -p no:randomly --basetemp=.pytest_tmp/riskgate cc_memory_vnext/tests/test_pre_tool_risk_gate.py -q

覆盖三层:
1. gate 层(monkeypatch 探针):单/多会话、fail-safe、frozen 不受开关影响、lazy、重发确认。
2. 真实 _recent_other_session_transcript:三态语义(True/False/None),对抗审查
   major finding 回归——「无法判定」不得折叠成「确认无其他会话」。
3. 真实 _count_cli_processes(monkeypatch subprocess.run):反向排除 Claude Desktop,
   .local/bin 与 AppData claude-code 两条真实 CLI 路径都计入。
"""
from __future__ import annotations

import importlib.util
import json
import os
import time
import types
import uuid
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parents[1] / "hooks" / "pre_tool_risk_gate.py"


class _Exit(Exception):
    pass


@pytest.fixture()
def rg(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("pre_tool_risk_gate_under_test", HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # 日志/pending 重定向到 tmp,不污染真实 logs/
    monkeypatch.setattr(mod, "DECISION_LOG", tmp_path / "decisions.jsonl")
    monkeypatch.setattr(mod, "PENDING_DIR", tmp_path / "pending")
    mod._MULTI_SESSION_CACHE = None

    captured = {}

    def fake_allow(reason="allow"):
        captured["out"] = ("allow", reason)
        raise _Exit

    def fake_decision(decision, msg, shape, session):
        captured["out"] = (decision, shape)
        raise _Exit

    monkeypatch.setattr(mod, "emit_allow", fake_allow)
    monkeypatch.setattr(mod, "emit_decision", fake_decision)
    mod._captured = captured
    return mod


def _shell(rg, cmd, session=None, transcript="X:\\fake\\transcript.jsonl"):
    rg._MULTI_SESSION_CACHE = None
    rg._captured.clear()
    try:
        rg.check_shell(cmd, session or ("t-" + uuid.uuid4().hex[:8]), r"C:\claude pj\zmd-pj", transcript)
    except _Exit:
        pass
    return rg._captured["out"]


def _probe(rg, procs=None, recent="unused", raises=False):
    if raises:
        def _boom():
            raise RuntimeError("probe down")
        rg._count_cli_processes = _boom
    else:
        rg._count_cli_processes = lambda: procs
    rg._recent_other_session_transcript = lambda tp: recent


DANGEROUS = [
    ("git add -A", "git-add-broad"),
    ('git commit -am "x"', "git-commit-all"),
    ('git commit -m "x"', "git-commit-no-pathspec:await-resend"),
    ("git push --force origin main", "git-push-force:await-resend"),
    ("rm -rf build", "rm-rf:await-resend"),
    ("Remove-Item -Recurse -Force build", "remove-item-recurse-force:await-resend"),
]


@pytest.mark.parametrize("cmd,shape", DANGEROUS)
def test_multi_session_denies(rg, cmd, shape):
    _probe(rg, procs=3)
    decision, got = _shell(rg, cmd)
    assert decision == "deny" and got.startswith(shape)


@pytest.mark.parametrize("cmd,shape", DANGEROUS)
def test_single_session_allows(rg, cmd, shape):
    _probe(rg, procs=1, recent=False)
    assert _shell(rg, cmd) == ("allow", "no-dangerous-shape")


def test_recent_transcript_keeps_protection(rg):
    _probe(rg, procs=1, recent=True)
    assert _shell(rg, "git add -A") == ("deny", "git-add-broad")


def test_transcript_probe_unavailable_is_failsafe(rg):
    """major finding 回归:探针②返回 None(无法判定)必须按多会话拦。"""
    _probe(rg, procs=1, recent=None)
    assert _shell(rg, "git add -A") == ("deny", "git-add-broad")


def test_zero_procs_is_failsafe(rg):
    _probe(rg, procs=0, recent=False)
    assert _shell(rg, "git add -A") == ("deny", "git-add-broad")


def test_probe_error_is_failsafe(rg):
    _probe(rg, raises=True)
    assert _shell(rg, "git add -A") == ("deny", "git-add-broad")


def test_frozen_artifact_ignores_switch(rg):
    _probe(rg, procs=1, recent=False)
    rg._MULTI_SESSION_CACHE = None
    rg._captured.clear()
    try:
        rg.check_file_write(r"C:\claude pj\zmd-pj\rules\canonical_rules.json", "t-frozen")
    except _Exit:
        pass
    decision, got = rg._captured["out"]
    assert decision == "deny" and got.startswith("frozen-artifact-write:await-resend")


@pytest.mark.parametrize("cmd", ["git status --short", 'echo "git add -A"'])
def test_lazy_no_probe_on_safe_commands(rg, cmd):
    _probe(rg, raises=True)  # 探针置为炸弹:被碰到就会 fail-safe 成 deny
    assert _shell(rg, cmd) == ("allow", "no-dangerous-shape")


def test_resend_confirm_still_works(rg):
    _probe(rg, procs=3)
    decision, got = _shell(rg, 'git commit -m "y"', session="t-resend")
    assert decision == "deny" and got.startswith("git-commit-no-pathspec")
    assert _shell(rg, 'git commit -m "y"', session="t-resend")[0] == "allow"


def test_single_session_skip_logged(rg):
    _probe(rg, procs=1, recent=False)
    _shell(rg, "git add -A", session="t-log")
    lines = (rg.DECISION_LOG).read_text(encoding="utf-8").splitlines()
    assert any('"single_session_skip"' in ln and '"git-add-broad"' in ln for ln in lines)


# ---- 真实 _recent_other_session_transcript(不 monkeypatch)----

def _touch(path: Path, age_seconds: float) -> None:
    path.write_text("{}", encoding="utf-8")
    ts = time.time() - age_seconds
    os.utime(path, (ts, ts))


def test_transcript_probe_empty_path_is_none(rg, tmp_path):
    assert rg._recent_other_session_transcript("") is None


def test_transcript_probe_missing_file_is_none(rg, tmp_path):
    assert rg._recent_other_session_transcript(str(tmp_path / "nope.jsonl")) is None


def test_transcript_probe_recent_sibling_true(rg, tmp_path):
    me = tmp_path / "me.jsonl"
    _touch(me, 0)
    _touch(tmp_path / "other.jsonl", 60)
    assert rg._recent_other_session_transcript(str(me)) is True


def test_transcript_probe_only_old_sibling_false(rg, tmp_path):
    me = tmp_path / "me.jsonl"
    _touch(me, 0)
    _touch(tmp_path / "other.jsonl", rg.SESSION_RECENT_WINDOW_SECONDS + 300)
    assert rg._recent_other_session_transcript(str(me)) is False


def test_transcript_probe_subdir_jsonl_not_counted(rg, tmp_path):
    me = tmp_path / "me.jsonl"
    _touch(me, 0)
    sub = tmp_path / "me"
    sub.mkdir()
    _touch(sub / "agent-x.jsonl", 60)  # 子代理 transcript,不算其他会话
    assert rg._recent_other_session_transcript(str(me)) is False


# ---- 真实 _count_cli_processes(monkeypatch subprocess.run)----

def _fake_ps(monkeypatch, rg, payload):
    def fake_run(*args, **kwargs):
        return types.SimpleNamespace(stdout=payload, stderr="", returncode=0)
    monkeypatch.setattr(rg.subprocess, "run", fake_run)


def test_count_excludes_desktop_includes_both_cli_paths(rg, monkeypatch):
    procs = [
        {"ProcessId": 1, "ExecutablePath": r"C:\Users\u\.local\bin\claude.exe"},
        {"ProcessId": 2, "ExecutablePath": r"C:\Users\u\.local\bin\claude.exe"},
        {"ProcessId": 3, "ExecutablePath": r"C:\Users\u\AppData\Roaming\Claude\claude-code\current\claude.exe"},
        {"ProcessId": 4, "ExecutablePath": r"C:\Users\u\AppData\Local\AnthropicClaude\app-1.0\claude.exe"},
        {"ProcessId": 5, "ExecutablePath": None},  # 拿不到路径 → 照计(过度保护方向)
    ]
    _fake_ps(monkeypatch, rg, json.dumps(procs))
    assert rg._count_cli_processes() == 4


def test_count_single_dict_result(rg, monkeypatch):
    _fake_ps(monkeypatch, rg, json.dumps({"ProcessId": 1, "ExecutablePath": r"C:\u\.local\bin\claude.exe"}))
    assert rg._count_cli_processes() == 1


def test_count_empty_output_is_zero(rg, monkeypatch):
    _fake_ps(monkeypatch, rg, "")
    assert rg._count_cli_processes() == 0
