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
import tempfile
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


def _probe(rg, procs=None, recent="unused", raises=False, staged=(), dirty="mirror"):
    if raises:
        def _boom():
            raise RuntimeError("probe down")
        rg._count_cli_processes = _boom
    else:
        rg._count_cli_processes = lambda: procs
    rg._recent_other_session_transcript = lambda tp: recent
    # staged=() → 空购物车;staged=None → git 查询失败(无法判定)
    rg._staged_entries = lambda repo, cwd: (None if staged is None else list(staged))
    # dirty = commit -a 的打包面(staged+tracked 工作区改动);默认镜像 staged
    if dirty == "mirror":
        dirty = staged
    rg._dirty_entries_for_commit_all = lambda repo, cwd: (None if dirty is None else list(dirty))


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


# ---- 单会话残留 staged 关卡(owner 2026-07-06 追加)----

@pytest.mark.parametrize("cmd", ['git commit -m "x"', 'git commit -am "x"'])
def test_single_session_stale_staged_blocks_commit(rg, cmd):
    """单会话但购物车非空(可能是已退出会话的残留)→ 要求确认。"""
    _probe(rg, procs=1, recent=False, staged=["a.py", "b.py"])
    decision, got = _shell(rg, cmd)
    assert decision == "deny" and got.startswith("git-commit-stale-staged:await-resend")


def test_single_session_stale_staged_unknown_is_conservative(rg):
    """git 查不出 staged(None)→ 按有残留处理,仍要求确认。"""
    _probe(rg, procs=1, recent=False, staged=None)
    decision, got = _shell(rg, 'git commit -m "x"')
    assert decision == "deny" and got.startswith("git-commit-stale-staged:await-resend")


def test_single_session_pathspec_commit_skips_staged_check(rg):
    """带精确 pathspec 的提交不打包 index 里的其他内容,不查购物车。"""
    _probe(rg, procs=1, recent=False, staged=["leftover.py"])
    assert _shell(rg, 'git commit -m "x" -- file.py') == ("allow", "no-dangerous-shape")


def test_single_session_add_broad_skips_staged_check(rg):
    """add 不往外提交东西,关口设在 commit——单会话 add -A 不查购物车。"""
    _probe(rg, procs=1, recent=False, staged=["leftover.py"])
    assert _shell(rg, "git add -A") == ("allow", "no-dangerous-shape")


def test_single_session_worktree_commit_all_skips_staged_check(rg):
    """worktree 有私有 index,无残留对象,豁免。"""
    _probe(rg, procs=1, recent=False, staged=["leftover.py"])
    rg._MULTI_SESSION_CACHE = None
    rg._captured.clear()
    try:
        rg.check_shell('git commit -am "x"', "t-wt", r"C:\Users\u\.claude\worktrees\w1", "X:\\f.jsonl")
    except _Exit:
        pass
    assert rg._captured["out"] == ("allow", "no-dangerous-shape")


def test_stale_staged_resend_confirms(rg):
    _probe(rg, procs=1, recent=False, staged=["leftover.py"])
    decision, got = _shell(rg, 'git commit -m "z"', session="t-stale-resend")
    assert decision == "deny" and got.startswith("git-commit-stale-staged")
    assert _shell(rg, 'git commit -m "z"', session="t-stale-resend")[0] == "allow"


def test_multi_session_plain_commit_shape_takes_precedence(rg):
    """多会话下仍走原 git-commit-no-pathspec 形状,不落到 stale-staged。"""
    _probe(rg, procs=3, staged=["leftover.py"])
    decision, got = _shell(rg, 'git commit -m "x"')
    assert decision == "deny" and got.startswith("git-commit-no-pathspec:await-resend")


# ---- 2026-07-06 codex 对抗审查绕过回归 ----

@pytest.mark.parametrize("cmd", [
    'git commit --message "x"',        # blocker: 长选项参数曾被误当 pathspec
    'git commit --cleanup strip -m "x"',
    'git commit --unknown-flag value', # 未知长选项吞参:宁多查不漏查
])
def test_long_option_args_are_not_pathspec(rg, cmd):
    _probe(rg, procs=1, recent=False, staged=["leftover.py"])
    decision, got = _shell(rg, cmd)
    assert decision == "deny" and got.startswith("git-commit-stale-staged")


@pytest.mark.parametrize("cmd", [
    'git commit --only own.py -m x',   # --only 语义安全(不打包既有 staged),不该错拦
    'git commit --amend own.py -m x',  # --amend 已知无参,own.py 是精确 pathspec
    'git commit -m x -- -i_file.py',   # -- 后的 -i* 是文件名不是 --include
    'git commit -m x -- -a_file.py',   # -- 后的 -a* 是文件名不是 --all
])
def test_known_safe_shapes_not_over_blocked(rg, cmd):
    _probe(rg, procs=1, recent=False, staged=["leftover.py"], dirty=["leftover.py"])
    assert _shell(rg, cmd) == ("allow", "no-dangerous-shape")


def test_directory_pathspec_is_broad(rg):
    """git commit -- <目录> 会打包目录下别人的 staged 残留 → 按宽 pathspec 查。

    cwd 必须落在 `.claude/worktrees/` 之外:gate 对 worktree 内的提交整体放行
    (`in_worktree`,hooks/pre_tool_risk_gate.py),而 pytest 的 tmp_path 跟着
    `--basetemp` 走——从一个 worktree 里跑、basetemp 又设在该 worktree 下时,
    tmp_path 自己就带上了 `/.claude/worktrees/`,这条用例会假红。用系统临时目录
    把 cwd 与 basetemp 解耦。
    """
    with tempfile.TemporaryDirectory() as neutral:
        cwd = Path(neutral)
        (cwd / "src").mkdir()
        _probe(rg, procs=1, recent=False, staged=["src/leftover.py"])
        rg._MULTI_SESSION_CACHE = None
        rg._captured.clear()
        try:
            rg.check_shell("git commit -m x -- src", "t-dir", str(cwd), "X:\\f.jsonl")
        except _Exit:
            pass
    decision, got = rg._captured["out"]
    assert decision == "deny" and got.startswith("git-commit-stale-staged")


@pytest.mark.parametrize("cmd", [
    'git commit -m x -- .',            # 宽 pathspec 等效打包全部
    'git commit -m x -- "src/*.py"',   # 引号内通配符
    'git commit --include own.py -m x',  # --include 会连带打包既有 staged
    'git commit -i own.py -m x',
])
def test_broad_pathspec_and_include_still_checked(rg, cmd):
    _probe(rg, procs=1, recent=False, staged=["leftover.py"])
    decision, got = _shell(rg, cmd)
    assert decision == "deny" and got.startswith("git-commit-stale-staged")


def test_commit_all_checks_full_payload_not_just_staged(rg):
    """commit -a 的打包面含 tracked 工作区改动/intent-to-add,staged 空也要查。"""
    _probe(rg, procs=1, recent=False, staged=(), dirty=["tracked.py"])
    decision, got = _shell(rg, 'git commit -am "x"')
    assert decision == "deny" and got.startswith("git-commit-stale-staged")


def test_commit_all_fully_clean_allows(rg):
    _probe(rg, procs=1, recent=False, staged=(), dirty=())
    assert _shell(rg, 'git commit -am "x"') == ("allow", "no-dangerous-shape")


def test_multi_session_long_option_takes_plain_shape(rg):
    _probe(rg, procs=3, staged=["leftover.py"])
    decision, got = _shell(rg, 'git commit --message "x"')
    assert decision == "deny" and got.startswith("git-commit-no-pathspec:await-resend")


def test_commit_pathspec_kind_classification(rg, tmp_path):
    k = rg.commit_pathspec_kind
    assert k(["-m", "x"]) == "none"
    assert k(["--message", "x"]) == "none"
    assert k(["-m", "x", "--", "file.py"]) == "precise"
    assert k(["-m", "x", "file.py"]) == "precise"
    assert k(["-m", "x", "--", "."]) == "broad"
    assert k(["-m", "x", "src/*.py"]) == "broad"
    assert k(["-m", "x", ":(top)f.py"]) == "broad"
    assert k(["--unknown-opt", "file.py"]) == "none"  # 未知长选项吞参(保守)
    assert k(["--amend", "file.py"]) == "precise"  # 已知无参长选项不吞参
    assert k(["--only", "file.py"]) == "precise"
    assert k(["--amend", "-m", "x", "file.py"]) == "precise"
    # 目录 pathspec 判 broad,不存在的路径当文件(precise)
    (tmp_path / "adir").mkdir()
    assert k(["-m", "x", "--", "adir"], str(tmp_path)) == "broad"
    assert k(["-m", "x", "--", "afile.py"], str(tmp_path)) == "precise"


# ---- 真实 _staged_entries / git_dash_c_dir(不 monkeypatch)----

def _git(repo, *args):
    import subprocess
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        capture_output=True, text=True, timeout=15,
    )


def test_staged_entries_real_repo(rg, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    assert _git(repo, "init", "-q").returncode == 0
    assert _git(repo, "commit", "--allow-empty", "-q", "-m", "init").returncode == 0
    assert rg._staged_entries(str(repo), str(repo)) == []
    (repo / "f.txt").write_text("x", encoding="utf-8")
    assert _git(repo, "add", "f.txt").returncode == 0
    assert rg._staged_entries(str(repo), str(repo)) == ["f.txt"]


def test_dirty_entries_real_repo(rg, tmp_path):
    """commit -a 打包面:tracked 改动与 intent-to-add 都要抓到,untracked 排除。"""
    repo = tmp_path / "repo2"
    repo.mkdir()
    assert _git(repo, "init", "-q").returncode == 0
    (repo / "t.txt").write_text("v1", encoding="utf-8")
    assert _git(repo, "add", "t.txt").returncode == 0
    assert _git(repo, "commit", "-q", "-m", "init").returncode == 0
    assert rg._dirty_entries_for_commit_all(str(repo), str(repo)) == []
    (repo / "untracked.txt").write_text("x", encoding="utf-8")  # ?? 不被 -a 打包
    assert rg._dirty_entries_for_commit_all(str(repo), str(repo)) == []
    (repo / "t.txt").write_text("v2", encoding="utf-8")  # tracked 工作区改动
    assert rg._dirty_entries_for_commit_all(str(repo), str(repo)) == ["t.txt"]
    (repo / "ita.txt").write_text("x", encoding="utf-8")
    assert _git(repo, "add", "-N", "ita.txt").returncode == 0  # intent-to-add
    entries = rg._dirty_entries_for_commit_all(str(repo), str(repo))
    assert "ita.txt" in entries and "t.txt" in entries
    # 同一状态下旧探针(diff --cached)看不到 t.txt 的工作区改动——这正是 -a 需要
    # 独立打包面检查的原因
    assert "t.txt" not in (rg._staged_entries(str(repo), str(repo)) or [])


def test_staged_entries_bad_dir_is_none(rg, tmp_path):
    # 注:目录存在但非仓库时,git 会向上冒泡找 .git(pytest tmp 在本仓库树内,
    # 测不出「非仓库」),所以这里用确定性的「目录不存在 → returncode!=0 → None」。
    missing = tmp_path / "definitely" / "missing"
    assert rg._staged_entries(str(missing), str(tmp_path)) is None


def test_git_dash_c_dir_extraction(rg):
    tokens = rg.tokenize_segments('git -C "C:/some repo" commit -m x')[0]
    assert rg.git_dash_c_dir(tokens, 0) == "C:/some repo"
    tokens2 = rg.tokenize_segments("git commit -m x")[0]
    assert rg.git_dash_c_dir(tokens2, 0) == ""


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
