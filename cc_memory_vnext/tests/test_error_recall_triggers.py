# -*- coding: utf-8 -*-
"""撞错召回:blob 形状 + 两张收窄卡的真假信号(2026-08-03 普查 §3.5 / 审查 ④)。

不接 CI(preflight 快 lane 只跑 src/tests);手跑:
    python -m pytest -p no:randomly --basetemp=.pytest_tmp/recall \
        cc_memory_vnext/tests/test_error_recall_triggers.py -q

三件事,全部用**仓库里真实的卡片文件**走真实 YAML 加载链,不手造 dict:
1. `build_error_blob()` 的形状(`# cwd:` / `$ 命令` / 输出)——两张卡的正则字面
   依赖它,改形状必须在这里先红;
2. 两张卡的正反例:审查列出的每一条假阳性/漏报都有对应用例
   (git pathspec 误命中 / worktree 内相对路径漏报 / 读旧红日志误命中 / 跑绿误命中);
3. **eval 数据自己不许自触发**:模拟 sed/cat/rg 读 `eval/regression.jsonl`,
   全窗口扫一遍,任何一张卡命中都算红——审查 ④ 指出这正是新增回归数据当时干的事,
   而且假命中还会把 seen-once 账本消费掉、把后面真该弹的一次压掉。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

VNEXT = Path(__file__).resolve().parents[1]
CARDS_DIR = VNEXT / "cards"
EVAL_FILE = VNEXT / "eval" / "regression.jsonl"
MEM_CARD = "memory-db-feature-branch-stale-do-ops-on-main"
PYTEST_CARD = "test-suite-speedup-landed-map"
RESPONSE_TAIL_CHARS = 6000


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return mod


@pytest.fixture(scope="module")
def zmem():
    mod = _load("zmem_under_test_recall", VNEXT / "zmem.py")
    yield mod
    sys.modules.pop("zmem_under_test_recall", None)


@pytest.fixture(scope="module")
def recall():
    if str(VNEXT) not in sys.path:
        sys.path.insert(0, str(VNEXT))
    mod = _load("post_tool_error_recall_under_test", VNEXT / "hooks" / "post_tool_error_recall.py")
    yield mod
    sys.modules.pop("post_tool_error_recall_under_test", None)


@pytest.fixture(scope="module")
def card_patterns(zmem):
    """真实卡文件 -> 真实 frontmatter 加载 -> 该卡实际生效的 error_regex 全集。"""
    patterns = {}
    for path in sorted(CARDS_DIR.glob("*.md")):
        card = zmem.load_frontmatter(path)
        triggers = zmem.as_dict(card.meta.get("triggers"))
        pats = zmem.normalize_list(triggers.get("error_regex")) + zmem.normalize_list(
            card.meta.get("error_regex")
        )
        if pats:
            patterns[card.id] = pats
    return patterns


def _fires(zmem, card_patterns, card_id, blob):
    assert card_id in card_patterns, f"{card_id} 没有 error_regex 了?"
    return zmem.error_regex_hit(card_patterns[card_id], [blob])


# --- 1. blob 形状 ------------------------------------------------------------


def test_blob_puts_cwd_then_command_then_output(recall):
    blob = recall.build_error_blob(
        {
            "cwd": "/home/zhuran24/zmd-pj/.claude/worktrees/wf-x",
            "tool_input": {"command": "python cc_memory/mem.py search pr2-5"},
            "tool_response": "no matches",
        }
    )
    assert blob.splitlines() == [
        "# cwd: /home/zhuran24/zmd-pj/.claude/worktrees/wf-x",
        "$ python cc_memory/mem.py search pr2-5",
        "no matches",
    ]


def test_blob_omits_missing_pieces(recall):
    assert recall.build_error_blob({"tool_response": "boom"}) == "boom"
    assert recall.build_error_blob({"cwd": "/repo", "tool_response": "boom"}) == "# cwd: /repo\nboom"
    assert recall.build_error_blob({"cwd": "/repo", "tool_input": {}}) == ""


# --- 2. 两张卡的正反例 -------------------------------------------------------

MEM_CASES = [
    pytest.param(
        "# cwd: /home/zhuran24/zmd-pj\n$ python /home/zhuran24/zmd-pj/.claude/worktrees/wf-x/cc_memory/mem.py search pr2-5\nno matches",
        True,
        id="absolute-worktree-path-fires",
    ),
    pytest.param(
        "# cwd: /home/zhuran24/zmd-pj/.claude/worktrees/wf-x\n$ python cc_memory/mem.py search pr2-5\nno matches",
        True,
        id="relative-path-with-worktree-cwd-fires",
    ),
    pytest.param(
        "# cwd: /home/zhuran24/zmd-pj\n$ python cc_memory/mem.py search pr2-5\nno matches",
        False,
        id="on-main-does-not-fire",
    ),
    pytest.param(
        # 审查 ④ 点名的假阳性:mem.py 只是 git pathspec,不是记忆操作。
        "# cwd: /home/zhuran24/zmd-pj\n$ git -C /home/zhuran24/zmd-pj/.claude/worktrees/wf-x stash push -- cc_memory/mem.py\nSaved working directory",
        False,
        id="git-pathspec-does-not-fire",
    ),
    pytest.param(
        "# cwd: /home/zhuran24/zmd-pj\n$ git checkout -- cc_memory/mem.py\n",
        False,
        id="git-checkout-pathspec-does-not-fire",
    ),
    pytest.param(
        # 只是读到一段引用了该命令的文本,没人真的跑过它。
        "# cwd: /home/zhuran24/zmd-pj\n$ cat notes.md\n$ python /repo/.claude/worktrees/wf-x/cc_memory/mem.py search pr2-5\nno matches",
        False,
        id="quoted-in-output-does-not-fire",
    ),
]


@pytest.mark.parametrize(("blob", "should_fire"), MEM_CASES)
def test_memory_db_stale_card_triggers(zmem, card_patterns, blob, should_fire):
    assert _fires(zmem, card_patterns, MEM_CARD, blob) is should_fire


PYTEST_CASES = [
    pytest.param(
        "# cwd: /home/zhuran24/zmd-pj\n$ python -m pytest -p no:randomly -q\n2 failed, 42 passed, 3525 deselected in 12.30s",
        True,
        id="red-run-fires",
    ),
    pytest.param(
        "# cwd: /home/zhuran24/zmd-pj\n$ cd /repo && /home/zhuran24/zmd-pj/.venv/bin/python -m pytest src/tests -q\n1 failed, 9 passed in 3.0s",
        True,
        id="red-run-with-cd-and-abs-interpreter-fires",
    ),
    pytest.param(
        "# cwd: /home/zhuran24/zmd-pj\n$ python -m pytest -p no:randomly -q\n44 passed, 3525 deselected in 12.30s",
        False,
        id="green-run-does-not-fire",
    ),
    pytest.param(
        "# cwd: /home/zhuran24/zmd-pj\n$ python -m pytest -q\n0 failed, 44 passed in 1.0s",
        False,
        id="zero-failed-does-not-fire",
    ),
    pytest.param(
        # 审查 ④ 点名的假阳性:只是 grep/rg 读一份历史红日志。
        "# cwd: /home/zhuran24/zmd-pj\n$ rg -n pytest .artifacts/full_rerun_20260725.log\n2 failed, 42 passed, 3525 deselected in 12.30s",
        False,
        id="reading-old-log-does-not-fire",
    ),
    pytest.param(
        "# cwd: /home/zhuran24/zmd-pj\n$ cat .artifacts/preflight_full.log\n$ python -m pytest -q\n2 failed, 42 passed in 9s",
        False,
        id="cat-of-log-quoting-the-command-does-not-fire",
    ),
    pytest.param(
        "# cwd: /home/zhuran24/zmd-pj\n$ python -m pytest -q\n3 xfailed, 44 passed in 1.0s",
        False,
        id="xfailed-does-not-fire",
    ),
]


@pytest.mark.parametrize(("blob", "should_fire"), PYTEST_CASES)
def test_test_suite_speedup_card_triggers(zmem, card_patterns, blob, should_fire):
    assert _fires(zmem, card_patterns, PYTEST_CARD, blob) is should_fire


# --- 3. eval 数据不许自触发 --------------------------------------------------


def _read_windows(text):
    """整篇 + 每个 6000 字滑窗 + 逐行/相邻两行,覆盖任意读法截出的片段。"""
    yield text
    for start in range(0, max(len(text) - RESPONSE_TAIL_CHARS, 0) + 1, 2000):
        yield text[start:start + RESPONSE_TAIL_CHARS]
    lines = text.splitlines()
    for i, line in enumerate(lines):
        yield line
        if i + 1 < len(lines):
            yield "\n".join(lines[i:i + 2])


READ_COMMANDS = (
    "sed -n '1,80p' cc_memory_vnext/eval/regression.jsonl",
    "cat cc_memory_vnext/eval/regression.jsonl",
    "rg -n error_regex cc_memory_vnext/eval/regression.jsonl",
    "grep -n pytest cc_memory_vnext/eval/regression.jsonl",
    "tail -20 cc_memory_vnext/eval/regression.jsonl",
)


def test_reading_the_eval_file_fires_no_card(zmem, recall, card_patterns):
    text = EVAL_FILE.read_text(encoding="utf-8")
    offenders = []
    for command in READ_COMMANDS:
        for chunk in _read_windows(text):
            blob = recall.build_error_blob(
                {
                    "cwd": "/home/zhuran24/zmd-pj",
                    "tool_input": {"command": command},
                    "tool_response": chunk,
                }
            )
            for card_id, patterns in card_patterns.items():
                if zmem.error_regex_hit(patterns, [blob]):
                    offenders.append((command.split()[0], card_id))
    assert not offenders, (
        "读 eval/regression.jsonl 就把卡打出来了(自触发,还会消费 seen-once 账本): "
        + ", ".join(sorted({f"{cmd} -> {cid}" for cmd, cid in offenders}))
    )


def test_eval_file_still_parses_and_keeps_its_cases(zmem):
    """打码只许改磁盘上的写法,不许改解析出来的值。"""
    import json

    ids = []
    for line in EVAL_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        ids.append(case["id"])
        for err in (case.get("frame") or {}).get("errors") or []:
            assert isinstance(err, str)
    assert "error-regex-mempy-relative-in-worktree-cwd-fires-20260803" in ids
    assert "error-regex-pytest-red-text-only-read-must-not-fire-20260803" in ids
    assert len(ids) == len(set(ids)), "eval case id 撞车"
