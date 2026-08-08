"""`devtools/memory_plate_tool.py` 的 CLI 级测试（批② 单门牌化 v2.0）。

全部走真 CLI（子进程），夹具在 tmp 造小卡集——**测试永不读写真记忆目录**。

被钉死的判据：
  1. 写出口硬判据：`--out` 指向 `.claude/projects/*/memory` 命名空间、或指向被读取的
     记忆目录本身/其内部/其祖先，一律 exit 2 且不创建任何目录。
  2. 排序：新卡头插（截断切尾保头 ⇒ 新卡必须活下来），旧卡保基线相对序。
  3. title 回退：缺 title 时用 name。
  4. 水位算术：JS 字符 = UTF-16 code unit（星平面字符算 2 个），200 行上限，>80% 报警。
  5. migrate-plan 四类对账分类。

变异自证：把工具源码复制一份并注入变异，用 `MEMORY_PLATE_TOOL` 环境变量指向变异体重跑
本文件即可（见 `_tool_path`）——工具席已用它跑过 3 个变异（守卫拆除 / 头插改尾插 /
UTF-16 计数改 len），每个都被对应测试逮住。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TOOL = REPO_ROOT / "devtools" / "memory_plate_tool.py"


def _tool_path() -> Path:
    """允许变异自证：MEMORY_PLATE_TOOL 指向变异副本时测本应变红。"""
    override = os.environ.get("MEMORY_PLATE_TOOL")
    return Path(override) if override else DEFAULT_TOOL


def run_tool(*args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, str(_tool_path()), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )


def write_card(
    memory_dir: Path,
    stem: str,
    *,
    description: str = "描述",
    title: str | None = None,
    type_: str | None = "project",
    modified: str | None = None,
    body: str = "正文内容。",
    name: str | None = None,
    raw: str | None = None,
) -> Path:
    memory_dir.mkdir(parents=True, exist_ok=True)
    path = memory_dir / f"{stem}.md"
    if raw is not None:
        path.write_text(raw, encoding="utf-8")
        return path
    fm = ["---", f"name: {name if name is not None else stem}"]
    if title is not None:
        fm.append(f'title: "{title}"')
    fm.append(f'description: "{description}"')
    fm.append("metadata:")
    fm.append("  node_type: memory")
    if type_ is not None:
        fm.append(f"  type: {type_}")
    if modified is not None:
        fm.append(f"  modified: {modified}")
    fm.append("---")
    path.write_text("\n".join(fm) + "\n\n" + body + "\n", encoding="utf-8")
    return path


def write_index(memory_dir: Path, rows: list[tuple[str, str, str]]) -> Path:
    memory_dir.mkdir(parents=True, exist_ok=True)
    lines = ["# Memory Index"]
    for title, filename, hook in rows:
        lines.append(f"- [{title}]({filename}) — {hook}")
    path = memory_dir / "MEMORY.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.fixture()
def memory_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cards"
    d.mkdir()
    return d


# --------------------------------------------------------------------------------------
# 1. 写出口硬判据
# --------------------------------------------------------------------------------------


def test_refuses_out_dir_inside_memory_namespace(tmp_path: Path, memory_dir: Path) -> None:
    write_card(memory_dir, "a")
    write_index(memory_dir, [("A", "a.md", "hook")])
    forbidden = tmp_path / "home" / ".claude" / "projects" / "-fake-proj" / "memory"

    res = run_tool("compile", "--memory-dir", str(memory_dir), "--out", str(forbidden))

    assert res.returncode == 2, res.stderr
    assert "REFUSED" in res.stderr
    assert not forbidden.exists(), "被拒的 --out 绝不能被创建"


def test_refuses_out_dir_below_memory_namespace(tmp_path: Path, memory_dir: Path) -> None:
    write_card(memory_dir, "a")
    forbidden = tmp_path / ".claude" / "projects" / "-p" / "memory" / "nested" / "deep"

    res = run_tool("validate", "--memory-dir", str(memory_dir), "--out", str(forbidden))

    assert res.returncode == 2, res.stderr
    assert not forbidden.exists()


def test_refuses_out_dir_equal_to_source_memory_dir(memory_dir: Path) -> None:
    write_card(memory_dir, "a")
    before = sorted(p.name for p in memory_dir.iterdir())

    res = run_tool("compile", "--memory-dir", str(memory_dir), "--out", str(memory_dir))

    assert res.returncode == 2, res.stderr
    assert sorted(p.name for p in memory_dir.iterdir()) == before, "源目录必须零写入"


def test_refuses_out_dir_that_is_ancestor_of_source(tmp_path: Path, memory_dir: Path) -> None:
    write_card(memory_dir, "a")

    res = run_tool("compile", "--memory-dir", str(memory_dir), "--out", str(memory_dir.parent))

    assert res.returncode == 2, res.stderr


def test_normal_out_dir_is_accepted(tmp_path: Path, memory_dir: Path) -> None:
    """正对照：普通 tmp 目录必须能写——证明上面的红不是「全都拒」。"""
    write_card(memory_dir, "a")
    write_index(memory_dir, [("A", "a.md", "hook")])
    out = tmp_path / "out"

    res = run_tool("compile", "--memory-dir", str(memory_dir), "--out", str(out))

    assert res.returncode == 0, res.stderr
    assert (out / "MEMORY.compiled.md").is_file()


def test_no_out_dir_writes_nothing(tmp_path: Path, memory_dir: Path) -> None:
    write_card(memory_dir, "a")
    write_index(memory_dir, [("A", "a.md", "hook")])
    snapshot = {p: p.read_bytes() for p in memory_dir.iterdir()}

    res = run_tool("migrate-plan", "--memory-dir", str(memory_dir))

    assert res.returncode == 0, res.stderr
    assert {p: p.read_bytes() for p in memory_dir.iterdir()} == snapshot
    assert list(tmp_path.iterdir()) == [memory_dir]


# --------------------------------------------------------------------------------------
# 2. 排序：新卡头插 + 旧卡保序
# --------------------------------------------------------------------------------------


def _index_files(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        if line.startswith("- ["):
            out.append(line.split("](", 1)[1].split(")", 1)[0])
    return out


def test_new_cards_are_head_inserted_and_baseline_order_preserved(memory_dir: Path) -> None:
    # 基线索引里是 b, a（**故意不是字母序**，用来证明保的是基线序不是排序）
    write_card(memory_dir, "a", modified="2026-01-01T00:00:00.000Z")
    write_card(memory_dir, "b", modified="2026-01-02T00:00:00.000Z")
    write_card(memory_dir, "new_old", modified="2026-05-01T00:00:00.000Z")
    write_card(memory_dir, "new_fresh", modified="2026-08-08T00:00:00.000Z")
    write_index(memory_dir, [("B", "b.md", "hb"), ("A", "a.md", "ha")])

    res = run_tool("compile", "--memory-dir", str(memory_dir))

    assert res.returncode == 0, res.stderr
    # 新卡在前（新卡之间 modified 降序），老卡按基线相对序在后
    assert _index_files(res.stdout) == ["new_fresh.md", "new_old.md", "b.md", "a.md"]


def test_new_card_without_modified_sorts_after_dated_new_cards(memory_dir: Path) -> None:
    write_card(memory_dir, "dated", modified="2026-08-01T00:00:00.000Z")
    write_card(memory_dir, "undated", modified=None)
    write_index(memory_dir, [])

    res = run_tool("compile", "--memory-dir", str(memory_dir))

    assert res.returncode == 0, res.stderr
    assert _index_files(res.stdout) == ["dated.md", "undated.md"]


def test_baseline_entry_without_card_on_disk_is_dropped(memory_dir: Path) -> None:
    write_card(memory_dir, "a")
    write_index(memory_dir, [("Ghost", "ghost.md", "h"), ("A", "a.md", "ha")])

    res = run_tool("compile", "--memory-dir", str(memory_dir))

    assert res.returncode == 0, res.stderr
    assert _index_files(res.stdout) == ["a.md"]
    assert "ghost.md" in res.stderr


# --------------------------------------------------------------------------------------
# 3. title 回退
# --------------------------------------------------------------------------------------


def test_title_field_used_when_present(memory_dir: Path) -> None:
    write_card(memory_dir, "card-x", title="中文门牌标题", description="钩子")
    write_index(memory_dir, [])

    res = run_tool("compile", "--memory-dir", str(memory_dir))

    assert "- [中文门牌标题](card-x.md) — 钩子" in res.stdout


def test_title_falls_back_to_name_when_missing(memory_dir: Path) -> None:
    write_card(memory_dir, "card-y", title=None, description="钩子")
    write_index(memory_dir, [])

    res = run_tool("compile", "--memory-dir", str(memory_dir))

    assert "- [card-y](card-y.md) — 钩子" in res.stdout


def test_missing_title_is_debt_not_hard_error(memory_dir: Path) -> None:
    write_card(memory_dir, "card-z", title=None)

    res = run_tool("validate", "--memory-dir", str(memory_dir))

    assert res.returncode == 0, res.stdout
    assert "硬错卡数: 0" in res.stdout
    assert "迁移欠账卡数: 1" in res.stdout
    assert "D1" in res.stdout


# --------------------------------------------------------------------------------------
# 4. 水位算术
# --------------------------------------------------------------------------------------


def _watermark_numbers(text: str) -> tuple[int, int]:
    js = lines = -1
    for line in text.splitlines():
        if "JS 字符" in line and js < 0:
            js = int(line.split(":", 1)[1].split("/")[0].strip())
        if line.strip().startswith("行数") and lines < 0:
            lines = int(line.split(":", 1)[1].split("/")[0].strip())
    return js, lines


def test_js_char_count_uses_utf16_code_units(memory_dir: Path) -> None:
    """星平面字符（emoji）算 2 个 JS 字符——这是 M-02 证伪实验钉死的单位。"""
    write_card(memory_dir, "e", title="T", description="🍎")  # 1 个 emoji = 2 code unit
    write_index(memory_dir, [])

    res = run_tool("compile", "--memory-dir", str(memory_dir))
    js, lines = _watermark_numbers(res.stderr)

    expected = len(res.stdout.encode("utf-16-le")) // 2
    assert js == expected
    assert js == len(res.stdout) + 1, "emoji 必须比 Python 字符数多算 1"
    assert lines == 2


def test_watermark_warns_just_above_eighty_percent(memory_dir: Path) -> None:
    """造一张恰好把水位顶过 80% 的卡，并与它的「差一点」孪生做对照。"""
    header_and_scaffold = len("# Memory Index\n") + len("- [T](big.md) — \n")
    target = int(JS_LIMIT * 0.8) + 1 - header_and_scaffold + 1  # 越线
    write_card(memory_dir, "big", title="T", description="漢" * target)
    write_index(memory_dir, [])

    res = run_tool("compile", "--memory-dir", str(memory_dir))
    js, _ = _watermark_numbers(res.stderr)

    assert js > JS_LIMIT * 0.8
    assert "WATERMARK WARNING" in res.stderr

    # 对照臂：少 3 个字符就不该报警
    write_card(memory_dir, "big", title="T", description="漢" * (target - 3))
    res2 = run_tool("compile", "--memory-dir", str(memory_dir))
    js2, _ = _watermark_numbers(res2.stderr)
    assert js2 <= JS_LIMIT * 0.8
    assert "WATERMARK WARNING" not in res2.stderr


def test_watermark_warns_on_line_count(memory_dir: Path) -> None:
    for i in range(161):  # 161 卡 + 标题行 = 162 行 > 200*0.8 = 160
        write_card(memory_dir, f"c{i:03d}", description="d")
    write_index(memory_dir, [])

    res = run_tool("compile", "--memory-dir", str(memory_dir))
    js, lines = _watermark_numbers(res.stderr)

    assert lines == 162
    assert js < JS_LIMIT * 0.8, "本臂只许行数越线，字符不许越——否则测不出行判据"
    assert "WATERMARK WARNING" in res.stderr


JS_LIMIT = 25_000


# --------------------------------------------------------------------------------------
# 5. migrate-plan 四类对账
# --------------------------------------------------------------------------------------


def _plan_class(plan_text: str, filename: str) -> str:
    for line in plan_text.splitlines():
        if line.startswith(f"| `{filename}` |"):
            return line.split("|")[2].strip()
    raise AssertionError(f"逐卡表里没有 {filename}\n{plan_text}")


@pytest.fixture()
def four_class_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cards"
    common = "语义路由断裂时门牌接不住新问法"
    extra_a = "另外还有编译触发闭环这一条要同批做"
    extra_b = "反向还有一条注入截断切尾保头的结论"
    write_card(d, "same", description=common)
    write_card(d, "index-richer", description=common)
    write_card(d, "desc-richer", description=common + extra_a)
    write_card(d, "human", description=common[:6] + extra_a)
    write_index(
        d,
        [
            ("同", "same.md", common),
            ("索引富", "index-richer.md", common + extra_a),
            ("desc富", "desc-richer.md", common),
            ("人裁", "human.md", common[6:] + extra_b),
        ],
    )
    return d


def test_migrate_plan_four_classes(four_class_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    res = run_tool("migrate-plan", "--memory-dir", str(four_class_dir), "--out", str(out))
    assert res.returncode == 0, res.stderr

    plan = (out / "migrate_plan.md").read_text(encoding="utf-8")
    assert _plan_class(plan, "same.md") == "一致"
    assert _plan_class(plan, "index-richer.md") == "索引更富(建议回写)"
    assert _plan_class(plan, "desc-richer.md") == "description更富(建议反向)"
    assert _plan_class(plan, "human.md") == "两边各有对方没有的(需人裁)"

    # 需人裁的卡必须逐字列出两边原文，供人裁
    assert "## 需人裁清单（1 张" in plan
    assert "### `human.md`" in plan


def test_migrate_plan_preview_writes_back_index_title_and_hook(
    four_class_dir: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    res = run_tool("migrate-plan", "--memory-dir", str(four_class_dir), "--out", str(out))
    assert res.returncode == 0, res.stderr

    preview = (out / "MEMORY.compiled.preview.md").read_text(encoding="utf-8")
    # 标题段来自索引行；索引更富的卡 hook 段被回写
    assert "- [索引富](index-richer.md) — 语义路由断裂时门牌接不住新问法另外还有编译触发闭环这一条要同批做" in preview
    # description 更富的卡保留 description
    assert "- [desc富](desc-richer.md) — 语义路由断裂时门牌接不住新问法另外还有编译触发闭环这一条要同批做" in preview
    assert (out / "watermark.txt").is_file()
    assert "人裁上界" in (out / "watermark.txt").read_text(encoding="utf-8")


def test_migrate_plan_leaves_source_untouched(four_class_dir: Path, tmp_path: Path) -> None:
    snapshot = {p.name: p.read_bytes() for p in four_class_dir.iterdir()}
    res = run_tool("migrate-plan", "--memory-dir", str(four_class_dir), "--out", str(tmp_path / "o"))
    assert res.returncode == 0, res.stderr
    assert {p.name: p.read_bytes() for p in four_class_dir.iterdir()} == snapshot


# --------------------------------------------------------------------------------------
# 6. validate 硬错判据
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs,marker",
    [
        ({"name": "wrong-name"}, "H3"),
        ({"description": ""}, "H4"),
        ({"type_": "bogus"}, "H5"),
        ({"type_": None}, "H5"),
        ({"body": "   "}, "H6"),
    ],
)
def test_validate_hard_errors(memory_dir: Path, kwargs: dict, marker: str) -> None:
    write_card(memory_dir, "card", **kwargs)

    res = run_tool("validate", "--memory-dir", str(memory_dir))

    assert res.returncode == 1, res.stdout
    assert marker in res.stdout


def test_validate_flags_missing_frontmatter(memory_dir: Path) -> None:
    write_card(memory_dir, "bare", raw="没有 frontmatter 的裸文件\n")

    res = run_tool("validate", "--memory-dir", str(memory_dir))

    assert res.returncode == 1
    assert "H1" in res.stdout


def test_validate_tolerates_extra_metadata_keys_and_missing_node_type(memory_dir: Path) -> None:
    """真卡形态：metadata 子结构不一（originSessionId 等），不得因此判错。"""
    raw = (
        "---\n"
        "name: tolerant\n"
        'description: "钩子"\n'
        "metadata: \n"
        "  type: feedback\n"
        "  originSessionId: 2d1bde6a-0d74-4480-a300-cbb98732c0b6\n"
        "  modified: 2026-08-08T09:49:33.556Z\n"
        "  weird_extra: 1\n"
        "---\n\n正文\n"
    )
    write_card(memory_dir, "tolerant", raw=raw)

    res = run_tool("validate", "--memory-dir", str(memory_dir))

    assert res.returncode == 0, res.stdout
    assert "硬错卡数: 0" in res.stdout
    assert "I1" in res.stdout  # node_type 缺失只进提示栏


def test_validate_json_report(memory_dir: Path, tmp_path: Path) -> None:
    write_card(memory_dir, "ok")
    out = tmp_path / "out"

    res = run_tool("validate", "--memory-dir", str(memory_dir), "--out", str(out))

    assert res.returncode == 0, res.stdout
    payload = json.loads((out / "validate_report.json").read_text(encoding="utf-8"))
    assert payload[0]["filename"] == "ok.md"
    assert payload[0]["hard"] == []
