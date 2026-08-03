# -*- coding: utf-8 -*-
"""撞错召回:策略转向后的形状、退役卡与蛇吞尾排除(2026-08-03 普查 §3.5)。

不接 CI(preflight 快 lane 只跑 src/tests);手跑:
    python -m pytest -p no:randomly --basetemp=/tmp/recall \
        cc_memory_vnext/tests/test_error_recall_triggers.py -q

本文件钉的是**退出正则军备竞赛**这个决定,不是又一版更聪明的正则:

1. `build_error_blob()` 的形状回到「$ 命令 + 输出」,不含 cwd —— 那一行是为一张
   已经退役的卡加的,代价是 12 张活卡里 10 张能被一行普通 cwd 文本假触发;
2. 两张卡(memory-db-feature-branch-stale / test-suite-speedup-landed-map)的
   error_regex 全空,历史上那些「真信号」形状现在一条都不许弹 —— 它们历史真阳
   是 0,其余触发面(keywords/intents/paths)照常保留;
3. **蛇吞尾排除**:读写本系统自己的治理件(卡片 / 回归数据 / 两套记忆测试 /
   剪枝普查产物)时整条召回跳过。这条不再靠给数据打码来防(打码只挡 raw
   reader,`jq` 按 JSON 语义读就还原了),而是 hook 自己认路径。end-to-end 用
   真 hook 子进程 + 真卡片编出来的索引跑,不是对着正则自说自话。
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

VNEXT = Path(__file__).resolve().parents[1]
REPO = VNEXT.parent
CARDS_DIR = VNEXT / "cards"
EVAL_FILE = VNEXT / "eval" / "regression.jsonl"
HOOK_PATH = VNEXT / "hooks" / "post_tool_error_recall.py"
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
    mod = _load("post_tool_error_recall_under_test", HOOK_PATH)
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


def _fires_any(zmem, card_patterns, blob) -> list[str]:
    return sorted(
        card_id
        for card_id, patterns in card_patterns.items()
        if zmem.error_regex_hit(patterns, [blob])
    )


# --- 1. blob 形状:cwd 拼接已撤销 --------------------------------------------


def test_blob_is_command_then_output_with_no_cwd_line(recall):
    blob = recall.build_error_blob(
        {
            "cwd": "/home/zhuran24/zmd-pj/.claude/worktrees/wf-x",
            "tool_input": {"command": "python cc_memory/mem.py search pr2-5"},
            "tool_response": "no matches",
        }
    )
    assert blob.splitlines() == [
        "$ python cc_memory/mem.py search pr2-5",
        "no matches",
    ]
    assert "cwd" not in blob


def test_blob_omits_missing_pieces(recall):
    assert recall.build_error_blob({"tool_response": "boom"}) == "boom"
    assert recall.build_error_blob({"cwd": "/repo", "tool_response": "boom"}) == "boom"
    assert recall.build_error_blob({"cwd": "/repo", "tool_input": {}}) == ""


def test_hook_never_reads_the_payload_cwd(recall):
    """撤销要撤干净:整个 hook 不许再碰 payload 的 cwd(不然下次又被拼回去)。"""
    source = HOOK_PATH.read_text(encoding="utf-8")
    code_lines = [
        line for line in source.splitlines() if 'payload.get("cwd")' in line or "payload['cwd']" in line
    ]
    assert code_lines == [], f"hook 又读了 payload.cwd: {code_lines}"


# --- 2. 两张卡退出 error_regex 通道 -------------------------------------------


@pytest.mark.parametrize("card_id", [MEM_CARD, PYTEST_CARD])
def test_retired_cards_have_no_error_regex_at_all(zmem, card_id):
    card = zmem.load_frontmatter(CARDS_DIR / f"{card_id}.md")
    triggers = zmem.as_dict(card.meta.get("triggers"))
    assert zmem.normalize_list(triggers.get("error_regex")) == []
    assert zmem.normalize_list(card.meta.get("error_regex")) == []


@pytest.mark.parametrize("card_id", [MEM_CARD, PYTEST_CARD])
def test_retired_cards_keep_every_other_trigger_surface(zmem, card_id):
    """退的是错误文本定向召回这一条通道,卡本身有价值,别把它一起废了。"""
    card = zmem.load_frontmatter(CARDS_DIR / f"{card_id}.md")
    triggers = zmem.as_dict(card.meta.get("triggers"))
    assert zmem.normalize_list(triggers.get("keywords"))
    assert zmem.normalize_list(triggers.get("intents"))
    assert zmem.normalize_list(triggers.get("examples"))
    assert str(card.meta.get("status")) == "active"


# 三轮收窄里被当成「真信号」的每一种形状,现在一条都不许弹任何卡。
RETIRED_POSITIVES = [
    pytest.param(
        "$ python /home/zhuran24/zmd-pj/.claude/worktrees/wf-x/cc_memory/mem.py search pr2-5\nno matches",
        id="mem-absolute-worktree-path",
    ),
    pytest.param(
        "# cwd: /home/zhuran24/zmd-pj/.claude/worktrees/wf-x\n$ python cc_memory/mem.py search pr2-5\nno matches",
        id="mem-relative-path-with-cwd-header",
    ),
    pytest.param(
        "$ python cc_memory/mem.py search pr2-5\nno matches",
        id="mem-bare-no-matches",
    ),
    pytest.param(
        "$ python -m pytest -p no:randomly -q\n2 failed, 42 passed, 3525 deselected in 12.30s",
        id="pytest-red-summary",
    ),
    pytest.param(
        "# cwd: /home/zhuran24/zmd-pj\n$ python -m pytest -q\n1 failed, 9 passed in 3.0s",
        id="pytest-red-summary-with-cwd-header",
    ),
    pytest.param(
        "$ python -m pytest -p no:randomly -q\n44 passed, 3525 deselected in 12.30s",
        id="pytest-green-summary",
    ),
]


@pytest.mark.parametrize("blob", RETIRED_POSITIVES)
def test_retired_shapes_fire_nothing(zmem, card_patterns, blob):
    assert _fires_any(zmem, card_patterns, blob) == []


# --- 3. 蛇吞尾排除 ------------------------------------------------------------

GOVERNANCE_HITS = [
    pytest.param({"command": "sed -n '1,80p' cc_memory_vnext/eval/regression.jsonl"}, id="bash-eval"),
    pytest.param({"command": "cat cc_memory_vnext/cards/vnext-self-history.md"}, id="bash-card"),
    pytest.param({"command": "python -m pytest cc_memory/tests -q"}, id="bash-mem-tests"),
    pytest.param({"command": "python -m pytest cc_memory_vnext/tests -q"}, id="bash-vnext-tests"),
    pytest.param({"command": "rg drift .artifacts/prune_v2_20260803/usage_census/report.md"}, id="bash-census"),
    pytest.param({"file_path": str(EVAL_FILE)}, id="read-eval-abs"),
    pytest.param({"file_path": r"C:\repo\cc_memory_vnext\cards\x.md"}, id="windows-separators"),
    pytest.param({"path": "cc_memory_vnext/tests", "pattern": "error_regex"}, id="grep-in-tests"),
]


@pytest.mark.parametrize("tool_input", GOVERNANCE_HITS)
def test_governance_targets_are_excluded(recall, tool_input):
    assert recall.governance_target({"tool_input": tool_input}) is not None


GOVERNANCE_MISSES = [
    pytest.param({"command": "python -m pytest src/tests -q"}, id="ordinary-tests"),
    pytest.param({"command": "python cc_memory/mem.py search pr2-5"}, id="mem-cli-is-not-governance"),
    pytest.param({"file_path": "src/search/outer_search.py"}, id="ordinary-source"),
    pytest.param({"command": "git push"}, id="git"),
    pytest.param({}, id="empty-tool-input"),
]


@pytest.mark.parametrize("tool_input", GOVERNANCE_MISSES)
def test_ordinary_work_is_not_excluded(recall, tool_input):
    assert recall.governance_target({"tool_input": tool_input}) is None


def test_exclusion_ignores_the_tool_response(recall):
    """真报错的输出里【提到】治理件路径不算 —— 那是真信号,误排除会静默吃掉它。"""
    payload = {
        "tool_input": {"command": "python -m pytest src/tests -q"},
        "tool_response": "FileNotFoundError: cc_memory_vnext/eval/regression.jsonl",
    }
    assert recall.governance_target(payload) is None


def _eval_windows(text):
    """整篇 + 每个 6000 字滑窗 + 逐行/相邻两行,覆盖任意读法截出的片段。"""
    yield text
    for start in range(0, max(len(text) - RESPONSE_TAIL_CHARS, 0) + 1, 2000):
        yield text[start:start + RESPONSE_TAIL_CHARS]
    lines = text.splitlines()
    for i, line in enumerate(lines):
        yield line
        if i + 1 < len(lines):
            yield "\n".join(lines[i:i + 2])


RAW_READ = "sed -n '1,80p' cc_memory_vnext/eval/regression.jsonl"
JQ_READ = "jq -r '.frame.errors[]?' cc_memory_vnext/eval/regression.jsonl"


def _jq_decoded(text: str) -> str:
    """`jq -r '.frame.errors[]?'` 会做的事:按 JSON 语义读出来,转义全还原。"""
    out = []
    for line in text.splitlines():
        if not line.strip():
            continue
        frame = json.loads(line).get("frame") or {}
        out.extend(str(err) for err in (frame.get("errors") or []))
    return "\n".join(out)


@pytest.mark.parametrize("command", [RAW_READ, JQ_READ], ids=["raw", "jq"])
def test_reading_the_eval_file_never_recalls(recall, zmem, card_patterns, command):
    """读回归数据(raw 或 jq)在任何窗口下都不许召回 —— 排除闸挡在建 blob 之前。"""
    text = EVAL_FILE.read_text(encoding="utf-8")
    body = _jq_decoded(text) if command is JQ_READ else text
    for chunk in _eval_windows(body):
        payload = {
            "cwd": str(REPO),
            "tool_input": {"command": command},
            "tool_response": chunk,
        }
        assert recall.governance_target(payload) is not None


def test_the_exclusion_is_load_bearing_not_decorative(recall, zmem, card_patterns):
    """反证:没有排除闸,读这份数据确实会自弹 —— 所以打码撤掉是安全的。"""
    body = _jq_decoded(EVAL_FILE.read_text(encoding="utf-8"))
    offenders = set()
    for chunk in _eval_windows(body):
        blob = recall.build_error_blob(
            {"tool_input": {"command": JQ_READ}, "tool_response": chunk}
        )
        offenders.update(_fires_any(zmem, card_patterns, blob))
    assert offenders, "回归数据不再含任何可自触发的字面?那这条排除闸的必要性就没被证明"


# --- 3b. end-to-end:真 hook 子进程 + 真卡片编的索引 --------------------------


@pytest.fixture(scope="module")
def hook_tree(tmp_path_factory):
    """真实 hook + 真实 zmem + 真实卡片,在 tmp 里编一份索引跑起来。

    不用仓库里那份 `.index/cards_index.json`:它是 git-ignored 的生成物,可能
    stale、也可能根本不存在,拿它当被测对象等于测了个不确定的东西。
    """
    root = tmp_path_factory.mktemp("recall_tree") / "vnext"
    (root / "hooks").mkdir(parents=True)
    shutil.copy2(VNEXT / "zmem.py", root / "zmem.py")
    shutil.copy2(HOOK_PATH, root / "hooks" / HOOK_PATH.name)
    shutil.copytree(CARDS_DIR, root / "cards")
    built = subprocess.run(
        [sys.executable, str(root / "zmem.py"), "build-index"],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    return root / "hooks" / HOOK_PATH.name


def _run_hook(hook: Path, payload: dict, session: str):
    body = dict(payload)
    body["session_id"] = session
    return subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        capture_output=True,
        timeout=120,
    )


def test_end_to_end_real_error_on_ordinary_file_still_recalls(hook_tree):
    """先证明这条通道是通的:普通源码上的真报错照常弹卡。"""
    proc = _run_hook(
        hook_tree,
        {
            "cwd": str(REPO),
            "tool_input": {"command": "python -m pytest src/tests/test_binding.py -q"},
            "tool_response": "MODEL_INVALID: does not refer to a supported interval",
        },
        "sess-ordinary",
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert b"ortools-915-proto-wrapper-pitfalls" in proc.stdout


@pytest.mark.parametrize("command", [RAW_READ, JQ_READ], ids=["raw", "jq"])
def test_end_to_end_reading_the_eval_file_prints_nothing(hook_tree, command):
    text = EVAL_FILE.read_text(encoding="utf-8")
    body = _jq_decoded(text) if command is JQ_READ else text
    proc = _run_hook(
        hook_tree,
        {
            "cwd": str(REPO),
            "tool_input": {"command": command},
            "tool_response": body,
        },
        "sess-" + ("raw" if command is RAW_READ else "jq"),
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert proc.stdout == b"", proc.stdout.decode("utf-8", "replace")


def test_end_to_end_reading_a_card_prints_nothing(hook_tree):
    card = CARDS_DIR / f"{MEM_CARD}.md"
    proc = _run_hook(
        hook_tree,
        {
            "cwd": str(REPO),
            "tool_input": {"command": f"cat cc_memory_vnext/cards/{card.name}"},
            "tool_response": card.read_text(encoding="utf-8"),
        },
        "sess-card",
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert proc.stdout == b""


# --- 4. 回归数据本身 ----------------------------------------------------------


def test_eval_file_parses_and_keeps_its_cases():
    ids = []
    for line in EVAL_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        ids.append(case["id"])
        for err in (case.get("frame") or {}).get("errors") or []:
            assert isinstance(err, str)
    # 08-03 那三条「正例」随卡片退役翻成负例,数据形状留着当反例。
    assert "error-regex-retired-mempy-relative-in-worktree-must-not-fire-20260803" in ids
    assert "error-regex-retired-pytest-red-summary-must-not-fire-20260803" in ids
    assert "error-regex-pytest-red-text-only-read-must-not-fire-20260803" in ids
    assert len(ids) == len(set(ids)), "eval case id 撞车"


def test_eval_file_is_readable_plaintext_again():
    """打码撤销:磁盘上就是明文。防自触发的是 hook 的排除闸,不是这份数据的写法。"""
    raw = EVAL_FILE.read_text(encoding="utf-8")
    assert "\\u00" not in raw and "\\u002" not in raw
    assert "$ git push" in raw, "反证:明文字面确实回来了"
