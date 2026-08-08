# -*- coding: utf-8 -*-
"""hook 接线的 tracked 模板 + `check-wiring` 自检(M-03)。

病灶:整套记忆系统靠 `.claude/settings.local.json` 里的 hook 条目才会跑,而
`.gitignore:94` 把 `.claude/` 整目录忽略。于是脚本随仓库走、**发动脚本的那份声明
不走**:新 clone / 交付副本拿到手,记忆系统默认是死的,而且一声不吭——没有模板可
比对,也没有任何机器会说"你这儿没接线"。

修法两件:`hooks/WIRING.template.json`(tracked 的脱敏接线拷贝)+
`zmem.py check-wiring`(只读比对)。**check-wiring 是灯不是闸**:退出码永远 0,
异常吞成一行降级说明,不改任何文件。

手跑:
    python -m pytest -p no:randomly --basetemp=.pytest_tmp/wiring \
        cc_memory_vnext/tests/test_hook_wiring_template.py -q
进门:preflight 记忆 lane 整目录收集 `cc_memory_vnext/tests`。

夹具全部在 tmp 里自建**假 settings**(`--settings` 注入),绝不读写本机那份真
`.claude/settings.local.json`。三态各有承重断言:缺接线要报(不然新 clone 照样静
默死)、漂移要指名道姓(只说"不一致"等于没说)、一致必须安静(假阳性会被无视)。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

VNEXT = Path(__file__).resolve().parents[1]
REPO = VNEXT.parent
ZMEM_PATH = VNEXT / "zmem.py"
TEMPLATE_PATH = VNEXT / "hooks" / "WIRING.template.json"
_MODULE_NAME = "zmem_under_test_wiring"


def _zmem():
    cached = sys.modules.get(_MODULE_NAME)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, ZMEM_PATH)
    mod = importlib.util.module_from_spec(spec)
    # zmem 用 `from __future__ import annotations` + frozen dataclass,
    # dataclasses 解析注解时会回查 sys.modules[cls.__module__];先登记再 exec。
    sys.modules[_MODULE_NAME] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(_MODULE_NAME, None)
        raise
    return mod


@pytest.fixture(scope="module")
def zmem():
    return _zmem()


FAKE_ROOT = "/fake/repo"

# 模板不认识的别的 hook:必须原样无视,不能被算成缺失或漂移。
FOREIGN_HOOK = {
    "hooks": [
        {"type": "command", "command": 'python3 "/somewhere/else/codegraph_index_guard.py"', "timeout": 10}
    ]
}


def _template() -> dict:
    return json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))


def _wired_settings() -> dict:
    """由模板本身展开出的"接线完好"的 settings,不依赖本机实际配置。"""
    text = json.dumps({"hooks": _template()["hooks"]}, ensure_ascii=False)
    return json.loads(text.replace("{REPO_ROOT}", FAKE_ROOT))


def _write(tmp_path: Path, settings: dict) -> Path:
    path = tmp_path / "settings.local.json"
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _check(zmem, settings_path: Path, template: Path = TEMPLATE_PATH) -> int:
    return zmem.main(
        [
            "check-wiring",
            "--template",
            str(template),
            "--settings",
            str(settings_path),
            "--repo-root",
            FAKE_ROOT,
        ]
    )


def _entry_count() -> int:
    return sum(
        len(group.get("hooks") or ())
        for groups in _template()["hooks"].values()
        for group in groups
    )


# --- 态 1:接线缺失 ----------------------------------------------------------


def test_missing_settings_file_reports_wiring_missing(zmem, tmp_path, capsys):
    """新 clone 的真实形态:settings 根本不存在。"""
    assert _check(zmem, tmp_path / "nope.json") == 0
    out = capsys.readouterr().out
    assert "WIRING MISSING" in out, out
    # 光说"缺"没用,得说清后果和去哪抄。
    assert "recall is off" in out
    assert str(TEMPLATE_PATH) in out
    assert "{REPO_ROOT}" in out and FAKE_ROOT in out


def test_settings_without_any_memory_hooks_reports_wiring_missing(zmem, tmp_path, capsys):
    """settings 在、但一条记忆 hook 都没接:和没有文件是同一个后果。"""
    path = _write(tmp_path, {"hooks": {"SessionStart": [FOREIGN_HOOK]}})

    assert _check(zmem, path) == 0
    out = capsys.readouterr().out
    assert "WIRING MISSING" in out, out
    assert "recall is off" in out


def test_dropping_one_entry_is_reported_as_missing_not_ok(zmem, tmp_path, capsys):
    settings = _wired_settings()
    settings["hooks"].pop("UserPromptSubmit")
    path = _write(tmp_path, settings)

    assert _check(zmem, path) == 0
    out = capsys.readouterr().out
    assert "WIRING DRIFT" in out, out
    assert "MISSING UserPromptSubmit" in out
    assert "user_prompt_submit.py" in out


# --- 态 2:接线漂移 ----------------------------------------------------------


def test_stale_command_path_is_reported_as_drift_with_both_sides(zmem, tmp_path, capsys):
    """同一个脚本挂在别的路径上 = 漂移;报告必须同时给出期望和实际。

    这是交付副本最可能的形态:settings 是从别的机器抄来的,路径还指着原机器。
    只说"不一致"的报告没人能照着修,所以两侧都要打出来。
    """
    settings = _wired_settings()
    settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"] = (
        'python3 "/old/machine/cc_memory_vnext/hooks/user_prompt_submit.py"'
    )
    path = _write(tmp_path, settings)

    assert _check(zmem, path) == 0
    out = capsys.readouterr().out
    assert "WIRING DRIFT" in out, out
    assert "DRIFT   UserPromptSubmit" in out
    assert "/old/machine/" in out
    assert f"{FAKE_ROOT}/cc_memory_vnext/hooks/user_prompt_submit.py" in out


def test_wrong_matcher_is_reported(zmem, tmp_path, capsys):
    """风控闸挂错 matcher(Edit -> Read)= 那类工具其实没被守住。"""
    settings = _wired_settings()
    for group in settings["hooks"]["PreToolUse"]:
        if group.get("matcher") == "Edit":
            group["matcher"] = "Read"
    path = _write(tmp_path, settings)

    assert _check(zmem, path) == 0
    out = capsys.readouterr().out
    assert "WIRING DRIFT" in out, out
    assert "PreToolUse [Edit]" in out
    assert "[Read]" in out


def test_changed_subcommand_args_do_not_cross_match(zmem, tmp_path, capsys):
    """`cc_mem_hook.py stop` 和 `... post-tool` 同名不同活。

    只按 basename 配对的话,Stop 里挂成 `post-tool` 会被读成"同一条只是漂移了",
    实际是 stop 那条根本没接。args 是身份的一部分,这条钉的就是它。
    """
    settings = _wired_settings()
    settings["hooks"]["Stop"][0]["hooks"][0]["command"] = (
        f'python3 "{FAKE_ROOT}/cc_memory/hooks/cc_mem_hook.py" post-tool'
    )
    path = _write(tmp_path, settings)

    assert _check(zmem, path) == 0
    out = capsys.readouterr().out
    assert "MISSING Stop" in out, out
    assert "DRIFT   Stop" not in out


# --- 态 3:一致 --------------------------------------------------------------


def test_fully_wired_settings_reports_ok(zmem, tmp_path, capsys):
    path = _write(tmp_path, _wired_settings())

    assert _check(zmem, path) == 0
    out = capsys.readouterr().out
    assert out.startswith("WIRING OK: "), out
    assert f"{_entry_count()}/{_entry_count()}" in out
    assert "MISSING" not in out and "DRIFT" not in out


def test_foreign_hooks_do_not_disturb_the_verdict(zmem, tmp_path, capsys):
    """settings 里的别家 hook(codegraph / latest.md / auto-continue)一律无视。

    比对口径是"记忆系统接上了没",不是"你这份 settings 和我的一样吗"。多出来的
    条目当成噪音报出来,一周内就会让人把这条命令当噪音关掉。
    """
    settings = _wired_settings()
    settings["hooks"]["SessionStart"].append(FOREIGN_HOOK)
    settings["hooks"]["Notification"] = [FOREIGN_HOOK]
    path = _write(tmp_path, settings)

    assert _check(zmem, path) == 0
    assert capsys.readouterr().out.startswith("WIRING OK: ")


def test_quoting_and_whitespace_differences_are_not_drift(zmem, tmp_path, capsys):
    """引号风格 / 多余空格不是接线差异,报出来就是假阳性。"""
    settings = _wired_settings()
    settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"] = (
        f"python3   {FAKE_ROOT}/cc_memory_vnext/hooks/user_prompt_submit.py"
    )
    path = _write(tmp_path, settings)

    assert _check(zmem, path) == 0
    assert capsys.readouterr().out.startswith("WIRING OK: ")


def test_timeout_and_async_flags_are_out_of_scope(zmem, tmp_path, capsys):
    """只比 (event, matcher, command)。timeout/async 是调参,不是"接没接上"。"""
    settings = _wired_settings()
    settings["hooks"]["PostToolUse"][0]["hooks"][0]["timeout"] = 60
    settings["hooks"]["PostToolUse"][0]["hooks"][0]["async"] = False
    path = _write(tmp_path, settings)

    assert _check(zmem, path) == 0
    assert capsys.readouterr().out.startswith("WIRING OK: ")


# --- advisory 底线:炸了也只是一行字 -----------------------------------------


def test_broken_settings_json_degrades_to_one_line(zmem, tmp_path, capsys):
    path = tmp_path / "settings.local.json"
    path.write_text("{not json at all", encoding="utf-8")

    assert _check(zmem, path) == 0
    out = capsys.readouterr().out
    assert out.startswith("WIRING CHECK UNAVAILABLE: "), out
    assert len([line for line in out.splitlines() if line.strip()]) == 1


def test_missing_template_degrades_to_one_line(zmem, tmp_path, capsys):
    path = _write(tmp_path, _wired_settings())

    assert _check(zmem, path, template=tmp_path / "gone.json") == 0
    assert capsys.readouterr().out.startswith("WIRING CHECK UNAVAILABLE: ")


def test_settings_with_unexpected_shapes_does_not_raise(zmem, tmp_path, capsys):
    """hooks 是字符串、group 是数字、command 缺失——脏 settings 不能把灯打炸。"""
    path = _write(
        tmp_path,
        {
            "hooks": {
                "SessionStart": "not a list",
                "UserPromptSubmit": [3, {"hooks": [{"type": "command"}]}, {"hooks": None}],
            }
        },
    )

    assert _check(zmem, path) == 0
    assert "Traceback" not in capsys.readouterr().out


# --- 模板本身不许烂掉 -------------------------------------------------------


def test_every_script_named_by_the_template_exists_in_the_repo(zmem):
    """模板会随脚本改名而烂掉,而烂掉的模板比没有模板更坏(照抄出死接线)。"""
    entries = zmem.flatten_hook_wiring(_template()["hooks"])
    assert entries, "模板一条 hook 都没有"
    for entry in entries:
        script = entry.command.split('"')[1]
        assert script.startswith("{REPO_ROOT}/"), entry.command
        relative = script[len("{REPO_ROOT}/") :]
        assert (REPO / relative).is_file(), f"模板指向不存在的脚本: {relative}"


def test_template_only_declares_memory_system_hooks(zmem):
    """脱敏 + 收窄:只抄记忆系统那几条,别把别人的 hook 也带进来。"""
    entries = zmem.flatten_hook_wiring(_template()["hooks"])
    for entry in entries:
        script = entry.command.split('"')[1]
        assert "/cc_memory/" in script or "/cc_memory_vnext/" in script, script
    # 脱敏:模板里不许残留任何一台具体机器的绝对路径。
    assert "/home/" not in TEMPLATE_PATH.read_text(encoding="utf-8")


def test_template_covers_the_two_injection_hooks_this_batch_hardened(zmem):
    """M-05 的两个出声出口挂在这两个 hook 上;模板漏了它们等于漏了整条注入链。"""
    scripts = {
        Path(zmem.hook_command_signature(entry.command)[0]).name
        for entry in zmem.flatten_hook_wiring(_template()["hooks"])
    }
    assert {"session_start.py", "user_prompt_submit.py"} <= scripts
