"""`devtools/memory_plate_tool.py` 的 CLI 级测试（批② 单门牌化 v2.0）。

全部走真 CLI（子进程），夹具在 tmp 造小卡集——**测试永不读写真记忆目录**。

被钉死的判据：
  1. 写出口硬判据：`--out` 指向 `.claude/projects/*/memory` 命名空间、或指向被读取的
     记忆目录本身/其内部/其祖先，一律 exit 2 且不创建任何目录。
  2. 排序：新卡头插（截断切尾保头 ⇒ 新卡必须活下来），旧卡保基线相对序。
  3. compile 行优先级：顶层 title > metadata.title > 无 title 卡的现存索引原行 > name 回退。
  4. 水位算术：JS 字符 = UTF-16 code unit（星平面字符算 2 个），200 行上限，>80% 报警。
  5. migrate-plan 四类对账分类。
  6. apply 只定点改卡片的 title/description/正文追加，默认 dry-run，commit 必须先外部备份。
  7. compile --write-index 只原子替换同目录 MEMORY.md，不能借此写卡。

变异自证：把工具源码复制一份并注入变异，用 `MEMORY_PLATE_TOOL` 环境变量指向变异体重跑
本文件即可（见 `_tool_path`）。受控写测试钉住目标守卫、外部备份、原子替换和 title 插入，
使这些约束的退化变异稳定变红。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

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


def write_proposals(path: Path, cards: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"cards": cards}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def file_snapshot(directory: Path) -> dict[str, tuple[str, bytes, int, int]]:
    snapshot: dict[str, tuple[str, bytes, int, int]] = {}
    for path in [directory, *sorted(directory.rglob("*"))]:
        relative = "." if path == directory else path.relative_to(directory).as_posix()
        kind = "dir" if path.is_dir() else "file"
        content = b"" if path.is_dir() else path.read_bytes()
        info = path.stat()
        snapshot[relative] = (kind, content, info.st_mtime_ns, info.st_ino)
    return snapshot


@pytest.fixture()
def memory_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cards"
    d.mkdir()
    return d


@pytest.fixture()
def cc_memory_dir(tmp_path: Path) -> Path:
    """不含 .claude 的假命名空间，钉住受控目标的通用尾部形状。"""
    d = tmp_path / "projects" / "-fake-project" / "memory"
    d.mkdir(parents=True)
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
    assert "1 张卡缺 title 且无现存索引行，已回退 name" in res.stdout


def test_missing_title_is_debt_not_hard_error(memory_dir: Path) -> None:
    write_card(memory_dir, "card-z", title=None)

    res = run_tool("validate", "--memory-dir", str(memory_dir))

    assert res.returncode == 0, res.stdout
    assert "硬错卡数: 0" in res.stdout
    assert "迁移欠账卡数: 1" in res.stdout
    assert "D1" in res.stdout


def test_metadata_title_validates_compiles_and_migrates_without_name_fallback(
    memory_dir: Path, tmp_path: Path
) -> None:
    title = "mtime不是内容到达信号(08-08迁移自咬)"
    raw = (
        "---\n"
        "name: mtime-is-not-an-arrival-signal\n"
        'description: "测试描述"\n'
        "metadata: \n"
        "  node_type: memory\n"
        f"  title: {title}\n"
        "  type: feedback\n"
        "  originSessionId: 4c4a1598-test\n"
        "---\n\n正文\n"
    )
    write_card(memory_dir, "mtime-is-not-an-arrival-signal", raw=raw)

    validated = run_tool("validate", "--memory-dir", str(memory_dir))

    assert validated.returncode == 0, validated.stdout
    assert "硬错卡数: 0" in validated.stdout
    assert "迁移欠账卡数: 0" in validated.stdout
    assert "提示：1 张卡的 title 在 metadata 内（不判错）" in validated.stdout
    assert "D1" not in validated.stdout

    compiled = run_tool("compile", "--memory-dir", str(memory_dir))
    expected_line = (
        f"- [{title}](mtime-is-not-an-arrival-signal.md) — 测试描述"
    )
    slug_fallback = (
        "- [mtime-is-not-an-arrival-signal]"
        "(mtime-is-not-an-arrival-signal.md) — 测试描述"
    )
    assert compiled.returncode == 0, compiled.stderr
    assert expected_line in compiled.stdout
    assert slug_fallback not in compiled.stdout
    assert "已回退 name" not in compiled.stdout

    out = tmp_path / "migrate-out"
    migrated = run_tool(
        "migrate-plan", "--memory-dir", str(memory_dir), "--out", str(out)
    )
    assert migrated.returncode == 0, migrated.stderr
    preview = (out / "MEMORY.compiled.preview.md").read_text(encoding="utf-8")
    assert expected_line in preview


def test_apply_dual_title_prefers_top_level_and_reports_one_conflict(
    cc_memory_dir: Path, tmp_path: Path
) -> None:
    raw = (
        "---\n"
        "name: dual\n"
        'title: "顶层旧标题"\n'
        'description: "描述保持"\n'
        "metadata:\n"
        "  node_type: memory\n"
        '  title: "metadata 标题"\n'
        "  type: project\n"
        "---\n\n正文\n"
    )
    card = write_card(cc_memory_dir, "dual", raw=raw)
    compiled = run_tool("compile", "--memory-dir", str(cc_memory_dir))

    assert compiled.returncode == 0, compiled.stderr
    assert "- [顶层旧标题](dual.md) — 描述保持" in compiled.stdout
    assert "- [metadata 标题](dual.md)" not in compiled.stdout

    proposals = write_proposals(
        tmp_path / "dual-proposals.json",
        [{"file": "dual.md", "title": "顶层新标题", "description": "描述保持"}],
    )
    backup_dir = tmp_path / "dual-backup"
    applied = run_tool(
        "apply",
        "--memory-dir",
        str(cc_memory_dir),
        "--proposals",
        str(proposals),
        "--commit",
        "--backup-dir",
        str(backup_dir),
    )

    expected = raw.replace('title: "顶层旧标题"\n', 'title: "顶层新标题"\n', 1).encode(
        "utf-8"
    )
    assert applied.returncode == 0, applied.stderr
    assert card.read_bytes() == expected
    assert '  title: "metadata 标题"' in card.read_text(encoding="utf-8")
    assert "[apply] title 位置冲突: dual.md" in applied.stdout
    assert "读取与写入以顶层为准" in applied.stdout
    assert "title 冲突=1" in applied.stdout
    assert "新增 title=0" in applied.stdout


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


# --------------------------------------------------------------------------------------
# 7. apply 受控写卡
# --------------------------------------------------------------------------------------


def test_apply_dry_run_emits_diff_and_preserves_bytes_and_mtime(
    cc_memory_dir: Path, tmp_path: Path
) -> None:
    card = write_card(cc_memory_dir, "dry")
    sentinel_ns = 1_700_000_000_123_456_789
    os.utime(card, ns=(sentinel_ns, sentinel_ns))
    proposals = write_proposals(
        tmp_path / "dry-proposals.json",
        [
            {
                "file": "dry.md",
                "title": "Dry 标题",
                "description": "新描述: 仍是预览",
                "body_addendum": "## 追加段\n\n只在 diff 中出现。\n",
            }
        ],
    )
    before = file_snapshot(cc_memory_dir)

    res = run_tool("apply", "--memory-dir", str(cc_memory_dir), "--proposals", str(proposals))

    assert res.returncode == 0, res.stderr
    assert "--- a/dry.md" in res.stdout
    assert "+++ b/dry.md" in res.stdout
    assert "@@" in res.stdout
    assert '+title: "Dry 标题"' in res.stdout
    assert "dry-run：未写入任何文件" in res.stdout
    assert file_snapshot(cc_memory_dir) == before
    assert card.stat().st_mtime_ns == sentinel_ns


def test_apply_commit_changes_only_allowed_bytes_and_makes_restorable_backup(
    cc_memory_dir: Path, tmp_path: Path
) -> None:
    raw = (
        "---\n"
        "name: precise\n"
        "description: '旧: 描述'   \n"
        "metadata:\n"
        "    node_type: memory\n"
        "    type: project\n"
        '    originSessionId: "session-1"\n'
        "    nested:\n"
        "      description: '嵌套字段不得改'\n"
        "---\n\n"
        "正文里的 description: 也不得改。\n"
    )
    card = write_card(cc_memory_dir, "precise", raw=raw)
    before = card.read_bytes()
    before_inode = card.stat().st_ino
    title = "精确标题"
    description = '新描述: 含 "引号"；中文标点'
    addendum = "## 新段\n\n追加内容。\n"
    proposals = write_proposals(
        tmp_path / "precise-proposals.json",
        [
            {
                "file": "precise.md",
                "title": title,
                "description": description,
                "body_addendum": addendum,
            }
        ],
    )
    backup_dir = tmp_path / "backups" / "apply-precise"
    expected = raw.replace(
        "name: precise\n",
        f"name: precise\ntitle: {json.dumps(title, ensure_ascii=False)}\n",
        1,
    ).replace(
        "description: '旧: 描述'   \n",
        f"description: {json.dumps(description, ensure_ascii=False)}\n",
        1,
    )
    expected = (expected + "\n" + addendum).encode("utf-8")

    with card.open("rb") as old_handle:
        res = run_tool(
            "apply",
            "--memory-dir",
            str(cc_memory_dir),
            "--proposals",
            str(proposals),
            "--commit",
            "--backup-dir",
            str(backup_dir),
        )
        assert res.returncode == 0, res.stderr
        assert old_handle.read() == before, "os.replace 后旧文件描述符必须仍看到改前 inode"

    assert card.read_bytes() == expected, "只允许 title/description/正文追加三处差异"
    assert card.stat().st_ino != before_inode, "受控写必须通过临时文件 + os.replace 更换 inode"
    assert (backup_dir / "precise.md").read_bytes() == before
    assert sorted(path.name for path in cc_memory_dir.iterdir()) == ["precise.md"]
    assert "改卡=1" in res.stdout
    assert "新增 title=1" in res.stdout
    assert "追加正文段=1" in res.stdout
    assert f"备份目录={backup_dir.resolve()}" in res.stdout

    card.write_bytes((backup_dir / "precise.md").read_bytes())
    assert card.read_bytes() == before, "外部备份必须能逐字节还原原卡"


def test_apply_existing_title_and_complex_description_round_trip(
    cc_memory_dir: Path, tmp_path: Path
) -> None:
    card = write_card(cc_memory_dir, "quoted", title="旧标题", description="旧描述")
    description = '路径 C:\\tmp: 他说 "你好"；中文标点：保留'
    title = '标题: "双引号"'
    proposals = write_proposals(
        tmp_path / "quoted-proposals.json",
        [{"file": str(card), "title": title, "description": description}],
    )
    backup_dir = tmp_path / "quoted-backup"

    res = run_tool(
        "apply",
        "--memory-dir",
        str(cc_memory_dir),
        "--proposals",
        str(proposals),
        "--commit",
        "--backup-dir",
        str(backup_dir),
    )

    assert res.returncode == 0, res.stderr
    text = card.read_text(encoding="utf-8")
    assert f"description: {json.dumps(description, ensure_ascii=False)}" in text
    fm_text = text.split("---\n", 2)[1]
    parsed = yaml.safe_load(fm_text)
    assert parsed["title"] == title
    assert parsed["description"] == description
    assert text.count("\ntitle:") == 1
    assert "新增 title=0" in res.stdout

    validated = run_tool("validate", "--memory-dir", str(cc_memory_dir))
    assert validated.returncode == 0, validated.stdout
    assert "迁移欠账卡数: 0" in validated.stdout


def test_apply_updates_existing_metadata_title_in_place_exact_bytes(
    cc_memory_dir: Path, tmp_path: Path
) -> None:
    raw = (
        "---\n"
        "name: metadata-only\n"
        'description: "描述保持"\n'
        "metadata: \n"
        "  node_type: memory\n"
        "  title: '旧 metadata 标题'   \n"
        "  type: feedback\n"
        "  originSessionId: session-metadata\n"
        "  nested:\n"
        '    title: "嵌套诱饵不得改"\n'
        "---\n\n"
        "正文里的 title: 也不得改。\n"
    )
    card = write_card(cc_memory_dir, "metadata-only", raw=raw)
    before = card.read_bytes()
    title = '新 metadata 标题: "保留"'
    proposals = write_proposals(
        tmp_path / "metadata-only-proposals.json",
        [{"file": "metadata-only.md", "title": title, "description": "描述保持"}],
    )
    backup_dir = tmp_path / "metadata-only-backup"
    expected = raw.replace(
        "  title: '旧 metadata 标题'   \n",
        f"  title: {json.dumps(title, ensure_ascii=False)}\n",
        1,
    ).encode("utf-8")

    res = run_tool(
        "apply",
        "--memory-dir",
        str(cc_memory_dir),
        "--proposals",
        str(proposals),
        "--commit",
        "--backup-dir",
        str(backup_dir),
    )

    assert res.returncode == 0, res.stderr
    assert card.read_bytes() == expected, "只允许 metadata.title 直属行变化"
    assert (backup_dir / card.name).read_bytes() == before
    assert b"\ntitle:" not in card.read_bytes(), "不得额外插入顶层 title"
    assert card.read_bytes().count(b"\n  title:") == 1
    assert '    title: "嵌套诱饵不得改"' in card.read_text(encoding="utf-8")
    assert "新增 title=0" in res.stdout
    assert "title 冲突=0" in res.stdout


def test_apply_without_title_still_inserts_top_level_after_name_exact_bytes(
    cc_memory_dir: Path, tmp_path: Path
) -> None:
    raw = (
        "---\n"
        "name: absent\n"
        'description: "描述保持"\n'
        "metadata:\n"
        "  node_type: memory\n"
        "  type: project\n"
        "---\n\n正文\n"
    )
    card = write_card(cc_memory_dir, "absent", raw=raw)
    before = card.read_bytes()
    title = "新增顶层标题"
    proposals = write_proposals(
        tmp_path / "absent-proposals.json",
        [{"file": "absent.md", "title": title, "description": "描述保持"}],
    )
    backup_dir = tmp_path / "absent-backup"
    expected = raw.replace(
        "name: absent\n",
        f"name: absent\ntitle: {json.dumps(title, ensure_ascii=False)}\n",
        1,
    ).encode("utf-8")

    res = run_tool(
        "apply",
        "--memory-dir",
        str(cc_memory_dir),
        "--proposals",
        str(proposals),
        "--commit",
        "--backup-dir",
        str(backup_dir),
    )

    assert res.returncode == 0, res.stderr
    assert card.read_bytes() == expected
    assert (backup_dir / card.name).read_bytes() == before
    assert f"name: absent\ntitle: {json.dumps(title, ensure_ascii=False)}\n" in card.read_text(
        encoding="utf-8"
    )
    assert "\n  title:" not in card.read_text(encoding="utf-8")
    assert "新增 title=1" in res.stdout
    assert "title 冲突=0" in res.stdout


def test_apply_missing_card_fails_full_preflight_without_writes(
    cc_memory_dir: Path, tmp_path: Path
) -> None:
    write_card(cc_memory_dir, "existing")
    proposals = write_proposals(
        tmp_path / "missing-proposals.json",
        [
            {"file": "existing.md", "title": "会改", "description": "会改"},
            {"file": "missing.md", "title": "不存在", "description": "不存在"},
        ],
    )
    backup_dir = tmp_path / "missing-backup"
    before = file_snapshot(cc_memory_dir)

    res = run_tool(
        "apply",
        "--memory-dir",
        str(cc_memory_dir),
        "--proposals",
        str(proposals),
        "--commit",
        "--backup-dir",
        str(backup_dir),
    )

    assert res.returncode == 2, res.stderr
    assert "REFUSED" in res.stderr
    assert file_snapshot(cc_memory_dir) == before
    assert not backup_dir.exists()


def test_apply_non_namespace_target_is_refused_without_writes(
    memory_dir: Path, tmp_path: Path
) -> None:
    write_card(memory_dir, "plain")
    proposals = write_proposals(
        tmp_path / "plain-proposals.json",
        [{"file": "plain.md", "title": "T", "description": "D"}],
    )
    backup_dir = tmp_path / "plain-backup"
    before = file_snapshot(memory_dir)

    res = run_tool(
        "apply",
        "--memory-dir",
        str(memory_dir),
        "--proposals",
        str(proposals),
        "--commit",
        "--backup-dir",
        str(backup_dir),
    )

    assert res.returncode == 2, res.stderr
    assert file_snapshot(memory_dir) == before
    assert not backup_dir.exists()


def test_apply_commit_requires_backup_dir_without_writes(
    cc_memory_dir: Path, tmp_path: Path
) -> None:
    write_card(cc_memory_dir, "no-backup")
    proposals = write_proposals(
        tmp_path / "no-backup-proposals.json",
        [{"file": "no-backup.md", "title": "T", "description": "D"}],
    )
    before = file_snapshot(cc_memory_dir)

    res = run_tool(
        "apply",
        "--memory-dir",
        str(cc_memory_dir),
        "--proposals",
        str(proposals),
        "--commit",
    )

    assert res.returncode == 2, res.stderr
    assert file_snapshot(cc_memory_dir) == before


def test_apply_backup_inside_namespace_is_refused_without_writes(
    cc_memory_dir: Path, tmp_path: Path
) -> None:
    write_card(cc_memory_dir, "inside")
    proposals = write_proposals(
        tmp_path / "inside-proposals.json",
        [{"file": "inside.md", "title": "T", "description": "D"}],
    )
    forbidden_backup = cc_memory_dir / "backups"
    before = file_snapshot(cc_memory_dir)

    res = run_tool(
        "apply",
        "--memory-dir",
        str(cc_memory_dir),
        "--proposals",
        str(proposals),
        "--commit",
        "--backup-dir",
        str(forbidden_backup),
    )

    assert res.returncode == 2, res.stderr
    assert file_snapshot(cc_memory_dir) == before
    assert not forbidden_backup.exists()


def test_apply_backup_in_another_memory_namespace_is_refused(
    cc_memory_dir: Path, tmp_path: Path
) -> None:
    write_card(cc_memory_dir, "source")
    proposals = write_proposals(
        tmp_path / "other-namespace-proposals.json",
        [{"file": "source.md", "title": "T", "description": "D"}],
    )
    other_memory = tmp_path / "projects" / "-other-project" / "memory"
    other_memory.mkdir(parents=True)
    source_before = file_snapshot(cc_memory_dir)

    res = run_tool(
        "apply",
        "--memory-dir",
        str(cc_memory_dir),
        "--proposals",
        str(proposals),
        "--commit",
        "--backup-dir",
        str(other_memory),
    )

    assert res.returncode == 2, res.stderr
    assert file_snapshot(cc_memory_dir) == source_before
    assert list(other_memory.iterdir()) == []


def test_apply_existing_file_outside_target_is_refused(
    cc_memory_dir: Path, tmp_path: Path
) -> None:
    write_card(cc_memory_dir, "inside")
    outside_dir = tmp_path / "outside"
    outside = write_card(outside_dir, "outside")
    proposals = write_proposals(
        tmp_path / "outside-proposals.json",
        [{"file": str(outside), "title": "T", "description": "D"}],
    )
    backup_dir = tmp_path / "outside-backup"
    inside_before = file_snapshot(cc_memory_dir)
    outside_before = outside.read_bytes()

    res = run_tool(
        "apply",
        "--memory-dir",
        str(cc_memory_dir),
        "--proposals",
        str(proposals),
        "--commit",
        "--backup-dir",
        str(backup_dir),
    )

    assert res.returncode == 2, res.stderr
    assert file_snapshot(cc_memory_dir) == inside_before
    assert outside.read_bytes() == outside_before
    assert not backup_dir.exists()


@pytest.mark.parametrize("field", ["title", "description"])
def test_apply_rejects_multiline_plate_values_without_writes(
    cc_memory_dir: Path, tmp_path: Path, field: str
) -> None:
    write_card(cc_memory_dir, "single-line")
    proposal = {"file": "single-line.md", "title": "T", "description": "D"}
    proposal[field] = "第一行\n第二行"
    proposals = write_proposals(tmp_path / f"multiline-{field}.json", [proposal])
    backup_dir = tmp_path / f"multiline-{field}-backup"
    before = file_snapshot(cc_memory_dir)

    res = run_tool(
        "apply",
        "--memory-dir",
        str(cc_memory_dir),
        "--proposals",
        str(proposals),
        "--commit",
        "--backup-dir",
        str(backup_dir),
    )

    assert res.returncode == 2, res.stderr
    assert "单行字符串" in res.stderr
    assert file_snapshot(cc_memory_dir) == before
    assert not backup_dir.exists()


def test_apply_refuses_existing_backup_without_overwriting_it(
    cc_memory_dir: Path, tmp_path: Path
) -> None:
    write_card(cc_memory_dir, "collision")
    proposals = write_proposals(
        tmp_path / "collision-proposals.json",
        [{"file": "collision.md", "title": "T", "description": "D"}],
    )
    backup_dir = tmp_path / "collision-backup"
    backup_dir.mkdir()
    existing_backup = backup_dir / "collision.md"
    existing_backup.write_bytes(b"older trusted backup\n")
    before = file_snapshot(cc_memory_dir)

    res = run_tool(
        "apply",
        "--memory-dir",
        str(cc_memory_dir),
        "--proposals",
        str(proposals),
        "--commit",
        "--backup-dir",
        str(backup_dir),
    )

    assert res.returncode == 2, res.stderr
    assert file_snapshot(cc_memory_dir) == before
    assert existing_backup.read_bytes() == b"older trusted backup\n"


def test_apply_rejects_memory_index_without_writes(cc_memory_dir: Path, tmp_path: Path) -> None:
    write_card(cc_memory_dir, "card")
    write_index(cc_memory_dir, [("Card", "card.md", "old")])
    proposals = write_proposals(
        tmp_path / "index-proposals.json",
        [{"file": "MEMORY.md", "title": "越权", "description": "越权"}],
    )
    backup_dir = tmp_path / "index-apply-backup"
    before = file_snapshot(cc_memory_dir)

    res = run_tool(
        "apply",
        "--memory-dir",
        str(cc_memory_dir),
        "--proposals",
        str(proposals),
        "--commit",
        "--backup-dir",
        str(backup_dir),
    )

    assert res.returncode == 2, res.stderr
    assert file_snapshot(cc_memory_dir) == before
    assert not backup_dir.exists()


# --------------------------------------------------------------------------------------
# 8. compile --write-index 受控写索引
# --------------------------------------------------------------------------------------


def test_compile_without_write_index_preserves_index_bytes_and_mtime(
    cc_memory_dir: Path
) -> None:
    write_card(cc_memory_dir, "preview", title="Preview", description="new")
    index_path = write_index(cc_memory_dir, [("Old", "preview.md", "old")])
    sentinel_ns = 1_700_000_001_123_456_789
    os.utime(index_path, ns=(sentinel_ns, sentinel_ns))
    before = file_snapshot(cc_memory_dir)

    res = run_tool("compile", "--memory-dir", str(cc_memory_dir))

    assert res.returncode == 0, res.stderr
    assert "- [Preview](preview.md) — new" in res.stdout
    assert file_snapshot(cc_memory_dir) == before
    assert index_path.stat().st_mtime_ns == sentinel_ns


def test_compile_preserves_raw_index_line_for_untitled_card_in_preview_and_write_index(
    cc_memory_dir: Path, tmp_path: Path
) -> None:
    titled = write_card(
        cc_memory_dir,
        "titled",
        title="字段中文标题",
        description="字段 description",
    )
    legacy = write_card(
        cc_memory_dir,
        "legacy",
        title=None,
        description="卡内 description 不得覆盖人工 hook",
    )
    fresh = write_card(
        cc_memory_dir,
        "fresh",
        title=None,
        description="全新卡 description",
    )
    preserved_line = '- [人工中文标题](legacy.md)    —   人工 hook：标点 "原样"  '
    old_index = (
        "# Memory Index\n"
        "- [应被 title 字段覆盖](titled.md) — 旧 hook\n"
        f"{preserved_line}\n"
    ).encode("utf-8")
    index_path = cc_memory_dir / "MEMORY.md"
    index_path.write_bytes(old_index)
    expected_index = (
        "# Memory Index\n"
        "- [fresh](fresh.md) — 全新卡 description\n"
        "- [字段中文标题](titled.md) — 字段 description\n"
        f"{preserved_line}\n"
    ).encode("utf-8")
    hint = "[compile] 提示：1 张卡缺 title 且无现存索引行，已回退 name\n"
    before_preview = file_snapshot(cc_memory_dir)

    preview = run_tool("compile", "--memory-dir", str(cc_memory_dir))

    assert preview.returncode == 0, preview.stderr
    preview_legacy_lines = [
        line for line in preview.stdout.encode("utf-8").splitlines(keepends=True) if b"(legacy.md)" in line
    ]
    assert preview_legacy_lines == [
        preserved_line.encode("utf-8") + b"\n"
    ], "无 title 的既有卡必须逐字节复用原索引行"
    assert preview.stdout.encode("utf-8") == expected_index + hint.encode("utf-8")
    assert file_snapshot(cc_memory_dir) == before_preview, "普通 compile 必须保持卡片与索引零写入"

    card_state = {
        path.name: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino)
        for path in (titled, legacy, fresh)
    }
    backup_dir = tmp_path / "priority-backup"
    written = run_tool(
        "compile",
        "--memory-dir",
        str(cc_memory_dir),
        "--write-index",
        "--backup-dir",
        str(backup_dir),
    )

    assert written.returncode == 0, written.stderr
    assert written.stdout.encode("utf-8") == expected_index + hint.encode("utf-8")
    assert index_path.read_bytes() == expected_index
    written_legacy_lines = [
        line for line in index_path.read_bytes().splitlines(keepends=True) if b"(legacy.md)" in line
    ]
    assert written_legacy_lines == [preserved_line.encode("utf-8") + b"\n"]
    assert (backup_dir / "MEMORY.md").read_bytes() == old_index
    for path in (titled, legacy, fresh):
        assert (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino) == card_state[path.name]

    js_chars, lines = _watermark_numbers(written.stderr)
    expected_text = expected_index.decode("utf-8")
    assert js_chars == len(expected_text.encode("utf-16-le")) // 2
    assert lines == len(expected_text.splitlines())


def test_compile_write_index_changes_only_index_and_backs_up_old_bytes(
    cc_memory_dir: Path, tmp_path: Path
) -> None:
    card_a = write_card(cc_memory_dir, "a", title="A", description="da")
    card_b = write_card(cc_memory_dir, "b", title="B", description="db")
    index_path = write_index(cc_memory_dir, [("Old B", "b.md", "old-b")])
    old_index = index_path.read_bytes()
    old_index_inode = index_path.stat().st_ino
    card_state = {
        path.name: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino)
        for path in (card_a, card_b)
    }
    original_members = sorted(path.name for path in cc_memory_dir.iterdir())
    backup_dir = tmp_path / "compile-backup"

    with index_path.open("rb") as old_handle:
        res = run_tool(
            "compile",
            "--memory-dir",
            str(cc_memory_dir),
            "--write-index",
            "--backup-dir",
            str(backup_dir),
        )
        assert res.returncode == 0, res.stderr
        assert old_handle.read() == old_index

    assert index_path.read_bytes() == res.stdout.encode("utf-8")
    assert index_path.stat().st_ino != old_index_inode
    assert (backup_dir / "MEMORY.md").read_bytes() == old_index
    assert sorted(path.name for path in cc_memory_dir.iterdir()) == original_members
    for path in (card_a, card_b):
        assert (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino) == card_state[path.name]

    js_chars, lines = _watermark_numbers(res.stderr)
    assert js_chars == len(res.stdout.encode("utf-16-le")) // 2
    assert lines == len(res.stdout.splitlines())
    assert "/ 25000" in res.stderr
    assert "/ 200" in res.stderr
    assert "已原子写入" in res.stderr


def test_compile_write_index_non_namespace_target_is_refused(
    memory_dir: Path, tmp_path: Path
) -> None:
    write_card(memory_dir, "plain", title="P")
    write_index(memory_dir, [("P", "plain.md", "old")])
    backup_dir = tmp_path / "compile-plain-backup"
    out_dir = tmp_path / "must-not-be-created"
    before = file_snapshot(memory_dir)

    res = run_tool(
        "compile",
        "--memory-dir",
        str(memory_dir),
        "--write-index",
        "--backup-dir",
        str(backup_dir),
        "--out",
        str(out_dir),
    )

    assert res.returncode == 2, res.stderr
    assert file_snapshot(memory_dir) == before
    assert not backup_dir.exists()
    assert not out_dir.exists(), "受控写安全预检必须早于普通 --out 的 mkdir"


def test_compile_write_index_requires_backup_dir_without_writes(
    cc_memory_dir: Path
) -> None:
    write_card(cc_memory_dir, "card", title="Card")
    write_index(cc_memory_dir, [("Old", "card.md", "old")])
    before = file_snapshot(cc_memory_dir)

    res = run_tool("compile", "--memory-dir", str(cc_memory_dir), "--write-index")

    assert res.returncode == 2, res.stderr
    assert file_snapshot(cc_memory_dir) == before


def test_compile_write_index_rejects_backup_inside_namespace(
    cc_memory_dir: Path
) -> None:
    write_card(cc_memory_dir, "card", title="Card")
    write_index(cc_memory_dir, [("Old", "card.md", "old")])
    forbidden_backup = cc_memory_dir / "compile-backup"
    before = file_snapshot(cc_memory_dir)

    res = run_tool(
        "compile",
        "--memory-dir",
        str(cc_memory_dir),
        "--write-index",
        "--backup-dir",
        str(forbidden_backup),
    )

    assert res.returncode == 2, res.stderr
    assert file_snapshot(cc_memory_dir) == before
    assert not forbidden_backup.exists()


def test_compile_write_index_cannot_use_out_to_target_card(
    cc_memory_dir: Path, tmp_path: Path
) -> None:
    card = write_card(cc_memory_dir, "card", title="Card")
    write_index(cc_memory_dir, [("Old", "card.md", "old")])
    backup_dir = tmp_path / "compile-card-backup"
    before = file_snapshot(cc_memory_dir)

    res = run_tool(
        "compile",
        "--memory-dir",
        str(cc_memory_dir),
        "--write-index",
        "--backup-dir",
        str(backup_dir),
        "--out",
        str(card),
    )

    assert res.returncode == 2, res.stderr
    assert "不得与普通产物通道 --out 同用" in res.stderr
    assert file_snapshot(cc_memory_dir) == before
    assert not backup_dir.exists()
