#!/usr/bin/env python3
"""单门牌化 v2.0 工具（批② 工具席交付物，2026-08-08）。

四个子命令，**全部默认只读**：

  validate       逐卡校验 frontmatter schema（硬错 / 迁移欠账 / 提示 三栏）
  compile        由卡片 frontmatter 确定性编译 MEMORY.md 内容（保序 + 新卡头插）
  migrate-plan   干跑：索引行 [标题]/— hook 段 与 frontmatter 的逐卡对账方案
  apply          干跑：定点更新卡片 title/description，并可追加正文段

普通产物的写出口是显式 `--out <目录>`。**硬判据**：`--out` 指向（或落进）任何
`.../.claude/projects/<项目>/memory` 命名空间一律拒绝并 exit 2。参见
`_assert_safe_out_dir`；该守卫没有通用绕过开关。

真记忆目录只有两条窄写口：`apply --commit` 仅能原子替换已存在卡片，
`compile --write-index` 仅能原子替换同目录 `MEMORY.md`。两者都要求独立的目标形状判据、
命名空间外备份和全量写前预检；其余模式仍然只读真卡。

门牌格式（左线修正后的 v1.1 规则）::

    - [title](文件名.md) — description

`title` 缺失时，compile 优先逐字保留现存 MEMORY.md 行；仅无现存行时回退 `name`
并提示。迁移前缺 title 属「迁移欠账」而不是 validate 硬错。

排序（FINAL_VERDICT §1/§4，C7 反转）：注入截断是**切尾保头**，所以新卡必须在前——
以现有 MEMORY.md 行序为基线，已在索引的卡保持相对顺序，不在索引的新卡头插。

水位（FINAL_VERDICT §1，M-02 降级为监测项）：`eoe=25000` 的单位是 JS 字符
（UTF-16 code unit，`len(s.encode('utf-16-le')) // 2`），另有 200 行上限；>80% 报警。
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import stat
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml

# --------------------------------------------------------------------------------------
# 常量
# --------------------------------------------------------------------------------------

DEFAULT_MEMORY_DIR = Path.home() / ".claude" / "projects" / "-home-zhuran24-zmd-pj" / "memory"
INDEX_FILENAME = "MEMORY.md"
INDEX_HEADER = "# Memory Index"

ALLOWED_TYPES = ("user", "feedback", "project", "reference")

# 注入水位（JS 字符 = UTF-16 code unit；行数）
JS_CHAR_LIMIT = 25_000
LINE_LIMIT = 200
WATERMARK_WARN_RATIO = 0.80

# 对账覆盖率阈值：>= 该值视作「被对方完全覆盖」
DEFAULT_COVERAGE_THRESHOLD = 0.90

CLASS_SAME = "一致"
CLASS_INDEX_RICHER = "索引更富(建议回写)"
CLASS_DESC_RICHER = "description更富(建议反向)"
CLASS_HUMAN = "两边各有对方没有的(需人裁)"

INDEX_LINE_RE = re.compile(r"^- \[(?P<title>.*?)\]\((?P<file>[^)]+)\)(?:\s+—\s+(?P<hook>.*))?$")


# --------------------------------------------------------------------------------------
# 写出口硬判据
# --------------------------------------------------------------------------------------


class OutDirRefused(Exception):
    """`--out` 指向受保护路径。"""


def _is_memory_namespace_path(path: Path) -> bool:
    """路径自身或其任一祖先是否是 `.claude/projects/<项目>/memory`。

    只看路径成分，不碰文件系统——所以在 tmp 里造出的假命名空间同样会被拒（可测）。
    """
    parts = path.parts
    for i in range(len(parts) - 3):
        if parts[i] == ".claude" and parts[i + 1] == "projects" and parts[i + 3] == "memory":
            return True
    return False


def _assert_safe_out_dir(out_dir: Path, memory_dir: Path) -> Path:
    """写出口硬判据。违反即抛 OutDirRefused（调用方 exit 2）。

    三条：
      1. out 自身或其祖先落在任何 `.claude/projects/*/memory` 命名空间内 → 拒。
      2. out 与被读取的 memory 目录相同、或落在其内 → 拒。
      3. out 是被读取的 memory 目录的祖先（写它等于圈住真卡）→ 拒。
    """
    resolved = out_dir.expanduser().resolve()
    mem = memory_dir.expanduser().resolve()

    if _is_memory_namespace_path(resolved):
        raise OutDirRefused(
            f"--out {resolved} 落在 .claude/projects/*/memory 记忆命名空间内；"
            "本工具只读真卡，迁移本体由主线程执行。"
        )
    if resolved == mem or mem in resolved.parents:
        raise OutDirRefused(f"--out {resolved} 与被读取的记忆目录 {mem} 重合或落在其内。")
    if resolved in mem.parents:
        raise OutDirRefused(f"--out {resolved} 是被读取的记忆目录 {mem} 的祖先目录。")
    return resolved


def _prepare_out_dir(out_dir: Path | None, memory_dir: Path) -> Path | None:
    if out_dir is None:
        return None
    safe = _assert_safe_out_dir(out_dir, memory_dir)
    safe.mkdir(parents=True, exist_ok=True)
    return safe


class ControlledWriteRefused(Exception):
    """受控真记忆写入未通过独立安全判据。"""


def _is_cc_memory_namespace_path(path: Path) -> bool:
    """路径自身或祖先是否具有 ``projects/<ns>/memory`` 形状。"""
    parts = path.parts
    for i in range(len(parts) - 2):
        if parts[i] == "projects" and parts[i + 1] and parts[i + 2] == "memory":
            return True
    return False


def _assert_apply_target(memory_dir: Path) -> Path:
    """受控写目标必须是现存的 ``.../projects/<ns>/memory`` 目录。"""
    resolved = memory_dir.expanduser().resolve()
    parts = resolved.parts
    has_shape = len(parts) >= 3 and parts[-3] == "projects" and bool(parts[-2]) and parts[-1] == "memory"
    if not has_shape:
        raise ControlledWriteRefused(
            f"目标 {resolved} 不是 <...>/projects/<ns>/memory 形状的 CC memory 命名空间。"
        )
    if not resolved.is_dir():
        raise ControlledWriteRefused(f"目标 memory 目录不存在或不是目录: {resolved}")
    return resolved


def _assert_backup_dir(backup_dir: Path, memory_dir: Path, filenames: Sequence[str]) -> Path:
    """全量预检备份目录及目标文件；本函数不创建任何路径。"""
    resolved = backup_dir.expanduser().resolve()
    memory = memory_dir.expanduser().resolve()
    if _is_cc_memory_namespace_path(resolved):
        raise ControlledWriteRefused(f"--backup-dir {resolved} 不得落在任何 memory 命名空间内。")
    if resolved == memory or memory in resolved.parents:
        raise ControlledWriteRefused(f"--backup-dir {resolved} 与目标 memory 目录重合或落在其内。")
    if resolved in memory.parents:
        raise ControlledWriteRefused(f"--backup-dir {resolved} 是目标 memory 目录的祖先目录。")
    if resolved.exists() and not resolved.is_dir():
        raise ControlledWriteRefused(f"--backup-dir {resolved} 已存在但不是目录。")

    for filename in filenames:
        destination = resolved / filename
        if destination.exists() or destination.is_symlink():
            raise ControlledWriteRefused(f"备份目标已存在，拒绝覆盖: {destination}")
    return resolved


def _atomic_replace_bytes(
    path: Path,
    data: bytes,
    *,
    mode: int | None = None,
    no_clobber: bool = False,
) -> None:
    """先在目标同目录完整落盘，再原子替换或 no-clobber 发布。"""
    fd, raw_temp_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(raw_temp_path)
    fd_open = True
    try:
        if mode is not None:
            os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as handle:
            fd_open = False
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if no_clobber:
            try:
                os.link(temp_path, path)
            except FileExistsError as exc:
                raise ControlledWriteRefused(f"备份目标已被并发占用，拒绝覆盖: {path}") from exc
            temp_path.unlink()
        else:
            os.replace(temp_path, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if fd_open:
            os.close(fd)
        temp_path.unlink(missing_ok=True)


# --------------------------------------------------------------------------------------
# 卡片读取
# --------------------------------------------------------------------------------------


@dataclass
class Card:
    path: Path
    filename: str
    raw: str
    frontmatter: dict[str, Any] | None
    body: str
    parse_error: str | None = None

    @property
    def stem(self) -> str:
        return self.filename[:-3] if self.filename.endswith(".md") else self.filename

    def fm_get(self, key: str) -> Any:
        if not isinstance(self.frontmatter, dict):
            return None
        return self.frontmatter.get(key)

    @property
    def metadata(self) -> dict[str, Any]:
        md = self.fm_get("metadata")
        return md if isinstance(md, dict) else {}

    @property
    def name(self) -> str | None:
        v = self.fm_get("name")
        return v.strip() if isinstance(v, str) else None

    @property
    def title(self) -> str | None:
        v = self.fm_get("title")
        return v.strip() if isinstance(v, str) and v.strip() else None

    @property
    def description(self) -> str | None:
        v = self.fm_get("description")
        return v.strip() if isinstance(v, str) and v.strip() else None

    @property
    def type_(self) -> Any:
        return self.metadata.get("type")

    @property
    def modified(self) -> str:
        v = self.metadata.get("modified")
        return str(v) if v is not None else ""

    @property
    def plate_title(self) -> str:
        """默认门牌标题：title 缺失回退 name，name 也缺回退文件名 stem。"""
        return self.title or self.name or self.stem


def split_frontmatter(text: str) -> tuple[str | None, str]:
    """返回 (frontmatter 原文, 正文)。无 frontmatter 时返回 (None, 全文)。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return "\n".join(lines[1:idx]), "\n".join(lines[idx + 1 :])
    return None, text


def load_card(path: Path) -> Card:
    raw = path.read_text(encoding="utf-8")
    fm_text, body = split_frontmatter(raw)
    if fm_text is None:
        return Card(path, path.name, raw, None, body, parse_error="缺 frontmatter 分隔块")
    try:
        obj = yaml.safe_load(fm_text)
    except Exception as exc:  # pragma: no cover - 真卡全部可解析
        return Card(path, path.name, raw, None, body, parse_error=f"YAML 解析失败: {exc!r}")
    if not isinstance(obj, dict):
        return Card(path, path.name, raw, None, body, parse_error="frontmatter 不是映射")
    return Card(path, path.name, raw, obj, body)


def load_cards(memory_dir: Path) -> list[Card]:
    if not memory_dir.is_dir():
        raise SystemExit(f"记忆目录不存在: {memory_dir}")
    paths = sorted(p for p in memory_dir.glob("*.md") if p.name != INDEX_FILENAME)
    return [load_card(p) for p in paths]


# --------------------------------------------------------------------------------------
# 索引解析
# --------------------------------------------------------------------------------------


@dataclass
class IndexEntry:
    lineno: int
    title: str
    filename: str
    hook: str
    raw: str


def parse_index(index_path: Path) -> tuple[list[IndexEntry], list[tuple[int, str]]]:
    """返回 (条目, 无法解析的行)。索引缺失视作空索引。"""
    if not index_path.is_file():
        return [], []
    lines = index_path.read_text(encoding="utf-8").splitlines()
    entries: list[IndexEntry] = []
    bad: list[tuple[int, str]] = []
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped == INDEX_HEADER or stripped.startswith("#"):
            continue
        m = INDEX_LINE_RE.match(line)
        if not m:
            bad.append((lineno, line))
            continue
        entries.append(
            IndexEntry(
                lineno=lineno,
                title=m.group("title").strip(),
                filename=m.group("file").strip(),
                hook=(m.group("hook") or "").strip(),
                raw=line,
            )
        )
    return entries, bad


# --------------------------------------------------------------------------------------
# 水位
# --------------------------------------------------------------------------------------


def js_char_length(text: str) -> int:
    """JS 字符数 = UTF-16 code unit 数（星平面字符算 2）。"""
    return len(text.encode("utf-16-le")) // 2


@dataclass
class Watermark:
    js_chars: int
    lines: int
    utf8_bytes: int

    @property
    def char_ratio(self) -> float:
        return self.js_chars / JS_CHAR_LIMIT

    @property
    def line_ratio(self) -> float:
        return self.lines / LINE_LIMIT

    @property
    def warn(self) -> bool:
        return self.char_ratio > WATERMARK_WARN_RATIO or self.line_ratio > WATERMARK_WARN_RATIO

    def report_lines(self, label: str) -> list[str]:
        out = [
            f"{label}:",
            f"  JS 字符 (UTF-16 code unit): {self.js_chars} / {JS_CHAR_LIMIT}  = {self.char_ratio * 100:.1f}%",
            f"  行数:                       {self.lines} / {LINE_LIMIT}  = {self.line_ratio * 100:.1f}%",
            f"  UTF-8 字节 (仅参考):        {self.utf8_bytes}",
        ]
        if self.warn:
            out.append(
                f"  !! WATERMARK WARNING: 已越 {WATERMARK_WARN_RATIO * 100:.0f}% 警戒线"
                "（注入截断切尾保头，超限先丢尾部旧卡）"
            )
        return out


def measure(text: str) -> Watermark:
    return Watermark(
        js_chars=js_char_length(text),
        lines=len(text.splitlines()),
        utf8_bytes=len(text.encode("utf-8")),
    )


# --------------------------------------------------------------------------------------
# validate
# --------------------------------------------------------------------------------------


@dataclass
class CardReport:
    filename: str
    hard: list[str] = field(default_factory=list)
    debt: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)


def validate_card(card: Card) -> CardReport:
    rep = CardReport(filename=card.filename)

    if card.parse_error is not None:
        rep.hard.append(f"H1 frontmatter 不可用: {card.parse_error}")
        return rep

    name = card.name
    if not name:
        rep.hard.append("H2 name 缺失或为空")
    elif name != card.stem:
        rep.hard.append(f"H3 name 与文件名不符: name={name!r} 文件名 stem={card.stem!r}")

    if not card.description:
        rep.hard.append("H4 description 缺失或为空")

    md_raw = card.fm_get("metadata")
    if md_raw is not None and not isinstance(md_raw, dict):
        rep.hard.append(f"H7 metadata 不是映射: {type(md_raw).__name__}")
    else:
        t = card.type_
        if t is None:
            rep.hard.append("H5 metadata.type 缺失（无法落在 user/feedback/project/reference 内）")
        elif t not in ALLOWED_TYPES:
            rep.hard.append(f"H5 metadata.type 非法: {t!r}（允许 {'/'.join(ALLOWED_TYPES)}）")

    if not card.body.strip():
        rep.hard.append("H6 正文为空")

    if card.title is None:
        rep.debt.append("D1 缺 title 字段（单门牌化迁移欠账：标题从 MEMORY.md 索引行回写）")

    if isinstance(md_raw, dict) and "node_type" not in md_raw:
        rep.info.append("I1 metadata 无 node_type（真卡存在此形态，不判错）")

    return rep


def cmd_validate(args: argparse.Namespace) -> int:
    memory_dir = args.memory_dir.expanduser()
    out_dir = _prepare_out_dir(args.out, memory_dir)
    cards = load_cards(memory_dir)
    reports = [validate_card(c) for c in cards]

    hard_reports = [r for r in reports if r.hard]
    debt_reports = [r for r in reports if r.debt]

    lines: list[str] = []
    lines.append(f"# memory_plate_tool validate — {memory_dir}")
    lines.append("")
    lines.append(f"卡片数: {len(cards)}")
    lines.append(f"硬错卡数: {len(hard_reports)}")
    lines.append(f"迁移欠账卡数: {len(debt_reports)}")
    lines.append("")

    lines.append("## 硬错（fail）")
    if not hard_reports:
        lines.append("（无）")
    for r in hard_reports:
        lines.append(f"- {r.filename}")
        for msg in r.hard:
            lines.append(f"    - {msg}")
    lines.append("")

    lines.append("## 迁移欠账（不算 fail）")
    debt_counter: dict[str, int] = {}
    for r in debt_reports:
        for msg in r.debt:
            key = msg.split("（")[0]
            debt_counter[key] = debt_counter.get(key, 0) + 1
    if not debt_reports:
        lines.append("（无）")
    else:
        for key, n in sorted(debt_counter.items()):
            lines.append(f"- {key}: {n} 张")
        lines.append("")
        lines.append("<details><summary>逐卡</summary>")
        for r in debt_reports:
            lines.append(f"- {r.filename}: " + "; ".join(r.debt))
        lines.append("</details>")
    lines.append("")

    info_reports = [r for r in reports if r.info]
    lines.append("## 提示（不判错）")
    if not info_reports:
        lines.append("（无）")
    for r in info_reports:
        lines.append(f"- {r.filename}: " + "; ".join(r.info))
    lines.append("")

    text = "\n".join(lines) + "\n"
    sys.stdout.write(text)

    if out_dir is not None:
        (out_dir / "validate_report.md").write_text(text, encoding="utf-8")
        payload = [
            {"filename": r.filename, "hard": r.hard, "debt": r.debt, "info": r.info}
            for r in reports
        ]
        (out_dir / "validate_report.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        sys.stderr.write(f"[validate] 报告已写入 {out_dir}\n")

    return 1 if hard_reports else 0


# --------------------------------------------------------------------------------------
# apply：受控定点改卡
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ApplyChange:
    path: Path
    original: bytes
    updated: bytes
    title_added: bool
    body_added: bool
    source_device: int
    source_inode: int
    source_mode: int

    @property
    def changed(self) -> bool:
        return self.original != self.updated


def _yaml_double_quoted(value: str) -> str:
    """JSON 字符串是 YAML 双引号标量的安全子集。"""
    return json.dumps(value, ensure_ascii=False)


def _load_apply_proposals(path: Path) -> list[dict[str, str]]:
    try:
        payload = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ControlledWriteRefused(f"无法读取 --proposals {path}: {exc}") from exc

    if not isinstance(payload, dict) or set(payload) != {"cards"}:
        raise ControlledWriteRefused("--proposals 顶层必须且只能包含 cards 数组。")
    raw_cards = payload["cards"]
    if not isinstance(raw_cards, list) or not raw_cards:
        raise ControlledWriteRefused("--proposals.cards 必须是非空数组。")

    required = {"file", "title", "description"}
    allowed = required | {"body_addendum"}
    proposals: list[dict[str, str]] = []
    for index, item in enumerate(raw_cards, start=1):
        if not isinstance(item, dict):
            raise ControlledWriteRefused(f"proposals.cards[{index}] 必须是对象。")
        keys = set(item)
        if not required <= keys or not keys <= allowed:
            raise ControlledWriteRefused(
                f"proposals.cards[{index}] 字段必须为 file/title/description，"
                "可选 body_addendum，且不得有其他字段。"
            )
        for key in required:
            if not isinstance(item[key], str):
                raise ControlledWriteRefused(f"proposals.cards[{index}].{key} 必须是字符串。")
        if not item["file"]:
            raise ControlledWriteRefused(f"proposals.cards[{index}].file 不得为空。")
        if "body_addendum" in item and not isinstance(item["body_addendum"], str):
            raise ControlledWriteRefused(f"proposals.cards[{index}].body_addendum 必须是字符串。")
        for key in ("title", "description"):
            if "\r" in item[key] or "\n" in item[key]:
                raise ControlledWriteRefused(
                    f"proposals.cards[{index}].{key} 必须是单行字符串，不得含 CR/LF。"
                )
        body_addendum = item.get("body_addendum", "")
        if "\r" in body_addendum:
            raise ControlledWriteRefused(
                f"proposals.cards[{index}].body_addendum 含 CR；受控写只接受 LF 行尾。"
            )
        proposals.append(
            {
                "file": item["file"],
                "title": item["title"],
                "description": item["description"],
                "body_addendum": body_addendum,
            }
        )
    return proposals


def _resolve_apply_card(memory_dir: Path, file_value: str) -> Path:
    requested = Path(file_value).expanduser()
    if requested.is_absolute():
        candidate = requested
    else:
        if requested.name != file_value or file_value in {".", ".."}:
            raise ControlledWriteRefused(f"相对 file 只允许直属文件名，不允许路径或穿越: {file_value!r}")
        candidate = memory_dir / requested

    if candidate.name == INDEX_FILENAME:
        raise ControlledWriteRefused("apply 通道拒绝写 MEMORY.md；索引只能由 compile --write-index 写入。")
    if candidate.suffix != ".md":
        raise ControlledWriteRefused(f"apply 只接受现存 .md 卡文件: {candidate}")
    if candidate.is_symlink():
        raise ControlledWriteRefused(f"apply 拒绝符号链接卡文件: {candidate}")
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ControlledWriteRefused(f"卡文件不存在，apply 不会新建: {candidate}") from exc
    if resolved.parent != memory_dir:
        raise ControlledWriteRefused(f"卡文件必须直属于目标 memory 目录，拒绝目录外或子目录路径: {candidate}")
    if not resolved.is_file():
        raise ControlledWriteRefused(f"目标不是普通卡文件: {resolved}")
    return resolved


def _frontmatter_field_matches(text: str, key: str, fm_end: int) -> list[re.Match[str]]:
    pattern = re.compile(rf"(?m)^{re.escape(key)}:[^\n]*$")
    return list(pattern.finditer(text, 4, fm_end))


def _rewrite_card_bytes(path: Path, original: bytes, title: str, description: str, body_addendum: str) -> tuple[bytes, bool, bool]:
    if b"\r" in original:
        raise ControlledWriteRefused(f"卡文件含 CR 行尾，拒绝隐式归一化: {path}")
    try:
        text = original.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ControlledWriteRefused(f"卡文件不是有效 UTF-8: {path}") from exc
    if not text.startswith("---\n"):
        raise ControlledWriteRefused(f"卡文件缺少行首 frontmatter 分隔符: {path}")
    closing = re.compile(r"(?m)^---[ \t]*(?=\n|\Z)").search(text, 4)
    if closing is None:
        raise ControlledWriteRefused(f"卡文件缺少 frontmatter 结束分隔符: {path}")
    fm_end = closing.start()

    names = _frontmatter_field_matches(text, "name", fm_end)
    titles = _frontmatter_field_matches(text, "title", fm_end)
    descriptions = _frontmatter_field_matches(text, "description", fm_end)
    if len(names) != 1 or len(descriptions) != 1 or len(titles) > 1:
        raise ControlledWriteRefused(
            f"卡片必须有且仅有一个顶层 name/description，且至多一个 title: {path}"
        )
    name_match = names[0]
    description_match = descriptions[0]
    if name_match.start() >= description_match.start():
        raise ControlledWriteRefused(f"卡片顶层 name 必须位于 description 之前: {path}")

    for key, match in (("name", name_match), ("description", description_match)):
        raw_value = match.group(0).split(":", 1)[1].lstrip()
        if raw_value.startswith(("|", ">")):
            raise ControlledWriteRefused(f"{path} 的 {key} 使用块标量，无法安全做单行定点替换。")

    title_line = f"title: {_yaml_double_quoted(title)}"
    description_line = f"description: {_yaml_double_quoted(description)}"
    edits: list[tuple[int, int, str]] = [
        (description_match.start(), description_match.end(), description_line)
    ]
    title_added = not titles
    if titles:
        title_match = titles[0]
        raw_title = title_match.group(0).split(":", 1)[1].lstrip()
        if raw_title.startswith(("|", ">")):
            raise ControlledWriteRefused(f"{path} 的 title 使用块标量，无法安全做单行定点替换。")
        if not (name_match.start() < title_match.start() < description_match.start()):
            raise ControlledWriteRefused(f"现有 title 必须位于 name 之后、description 之前: {path}")
        edits.append((title_match.start(), title_match.end(), title_line))
    else:
        edits.append((name_match.end(), name_match.end(), "\n" + title_line))

    rewritten = text
    for start, end, replacement in sorted(edits, reverse=True):
        rewritten = rewritten[:start] + replacement + rewritten[end:]

    body_added = bool(body_addendum)
    if body_added:
        if rewritten.endswith("\n\n"):
            separator = ""
        elif rewritten.endswith("\n"):
            separator = "\n"
        else:
            separator = "\n\n"
        rewritten += separator + body_addendum

    fm_text, _ = split_frontmatter(rewritten)
    try:
        parsed = yaml.safe_load(fm_text) if fm_text is not None else None
    except yaml.YAMLError as exc:
        raise ControlledWriteRefused(f"定点改写后的 frontmatter 无法解析: {path}: {exc}") from exc
    if not isinstance(parsed, dict) or parsed.get("title") != title or parsed.get("description") != description:
        raise ControlledWriteRefused(f"定点改写后的 title/description 无法精确回读: {path}")
    return rewritten.encode("utf-8"), title_added, body_added


def _prepare_apply_changes(memory_dir: Path, proposals: Sequence[dict[str, str]]) -> list[ApplyChange]:
    changes: list[ApplyChange] = []
    seen: set[Path] = set()
    for proposal in proposals:
        path = _resolve_apply_card(memory_dir, proposal["file"])
        if path in seen:
            raise ControlledWriteRefused(f"同一卡片在 proposals 中重复出现: {path}")
        seen.add(path)
        original = path.read_bytes()
        updated, title_added, body_added = _rewrite_card_bytes(
            path,
            original,
            proposal["title"],
            proposal["description"],
            proposal["body_addendum"],
        )
        source_stat = path.stat()
        changes.append(
            ApplyChange(
                path=path,
                original=original,
                updated=updated,
                title_added=title_added,
                body_added=body_added,
                source_device=source_stat.st_dev,
                source_inode=source_stat.st_ino,
                source_mode=stat.S_IMODE(source_stat.st_mode),
            )
        )
    return changes


def _assert_apply_sources_unchanged(changes: Sequence[ApplyChange]) -> None:
    for change in changes:
        current_stat = change.path.stat()
        if (
            current_stat.st_dev != change.source_device
            or current_stat.st_ino != change.source_inode
            or change.path.read_bytes() != change.original
        ):
            raise ControlledWriteRefused(f"预检后卡片发生变化，拒绝覆盖: {change.path}")


def _print_apply_diffs(changes: Sequence[ApplyChange]) -> None:
    for change in changes:
        before = change.original.decode("utf-8").splitlines(keepends=True)
        after = change.updated.decode("utf-8").splitlines(keepends=True)
        diff = "".join(
            difflib.unified_diff(
                before,
                after,
                fromfile=f"a/{change.path.name}",
                tofile=f"b/{change.path.name}",
            )
        )
        if diff:
            sys.stdout.write(diff)
            if not diff.endswith("\n"):
                sys.stdout.write("\n")
        else:
            sys.stdout.write(f"[apply] {change.path.name}: 无变化\n")


def cmd_apply(args: argparse.Namespace) -> int:
    if args.commit:
        memory_dir = _assert_apply_target(args.memory_dir)
        if args.backup_dir is None:
            raise ControlledWriteRefused("apply --commit 必须提供 --backup-dir。")
    else:
        memory_dir = args.memory_dir.expanduser().resolve()
        if not memory_dir.is_dir():
            raise ControlledWriteRefused(f"目标 memory 目录不存在或不是目录: {memory_dir}")

    proposals = _load_apply_proposals(args.proposals)
    changes = _prepare_apply_changes(memory_dir, proposals)
    changed = [change for change in changes if change.changed]
    backup_dir: Path | None = None

    if args.commit:
        backup_dir = _assert_backup_dir(
            args.backup_dir,
            memory_dir,
            [change.path.name for change in changed],
        )
        _assert_apply_sources_unchanged(changes)
        if changed:
            backup_dir.mkdir(parents=True, exist_ok=True)
            for change in changed:
                backup_path = backup_dir / change.path.name
                _atomic_replace_bytes(
                    backup_path,
                    change.original,
                    mode=change.source_mode,
                    no_clobber=True,
                )
                if backup_path.read_bytes() != change.original:
                    raise RuntimeError(f"备份写后校验失败: {backup_path}")
            _assert_apply_sources_unchanged(changes)
            for change in changed:
                _atomic_replace_bytes(change.path, change.updated, mode=change.source_mode)

    _print_apply_diffs(changes)
    backup_label = str(backup_dir) if backup_dir is not None else "(dry-run，未使用)"
    sys.stdout.write(
        "[apply] 摘要: "
        f"改卡={len(changed)}，新增 title={sum(change.title_added for change in changed)}，"
        f"追加正文段={sum(change.body_added for change in changed)}，备份目录={backup_label}\n"
    )
    if not args.commit:
        sys.stdout.write("[apply] dry-run：未写入任何文件；加 --commit 才会落盘。\n")
    return 0


# --------------------------------------------------------------------------------------
# compile
# --------------------------------------------------------------------------------------


def order_cards(cards: Sequence[Card], baseline: Sequence[IndexEntry]) -> list[Card]:
    """保序 + 头插。

    - 已在基线索引里的卡：保持基线相对顺序；
    - 不在基线里的新卡：插到最前，新卡之间按 metadata.modified 降序（缺失视作最旧），
      同序按文件名升序 —— 保证确定性。
    """
    by_name = {c.filename: c for c in cards}
    baseline_order = [e.filename for e in baseline if e.filename in by_name]
    seen = set(baseline_order)
    fresh = [c for c in cards if c.filename not in seen]
    fresh.sort(key=lambda c: (c.modified == "", _neg_key(c.modified), c.filename))
    return fresh + [by_name[n] for n in baseline_order]


class _neg_key:
    """字符串降序排序键（避免 reverse= 与次级升序键打架）。"""

    __slots__ = ("value",)

    def __init__(self, value: str) -> None:
        self.value = value

    def __lt__(self, other: "_neg_key") -> bool:
        return self.value > other.value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _neg_key) and self.value == other.value


def _render_index_line(title: str, filename: str, description: str) -> str:
    if description:
        return f"- [{title}]({filename}) — {description}"
    return f"- [{title}]({filename})"


def render_index(entries: Iterable[tuple[str, str, str]]) -> str:
    """entries = (title, filename, description) → MEMORY.md 内容。"""
    lines = [INDEX_HEADER]
    lines.extend(_render_index_line(title, filename, description) for title, filename, description in entries)
    return "\n".join(lines) + "\n"


def compile_index(cards: Sequence[Card], baseline: Sequence[IndexEntry]) -> tuple[str, int]:
    """编译索引，并返回 ``(MEMORY.md 内容, name 回退卡数)``。

    行内容优先级：卡片 title > 无 title 卡的现存索引原行 > name 回退。
    ``order_cards`` 单独决定顺序，所以保序与新卡头插规则不受本函数影响。
    """
    ordered = order_cards(cards, baseline)
    baseline_by_file: dict[str, IndexEntry] = {}
    for entry in baseline:
        baseline_by_file.setdefault(entry.filename, entry)

    lines = [INDEX_HEADER]
    name_fallback_count = 0
    for card in ordered:
        if card.title is not None:
            lines.append(_render_index_line(card.title, card.filename, card.description or ""))
            continue
        existing = baseline_by_file.get(card.filename)
        if existing is not None:
            lines.append(existing.raw)
            continue
        name_fallback_count += 1
        lines.append(_render_index_line(card.name or card.stem, card.filename, card.description or ""))
    return "\n".join(lines) + "\n", name_fallback_count


def cmd_compile(args: argparse.Namespace) -> int:
    index_backup_dir: Path | None = None
    old_index: bytes | None = None
    index_device: int | None = None
    index_inode: int | None = None
    index_mode: int | None = None
    if args.write_index:
        if args.out is not None:
            raise ControlledWriteRefused("compile --write-index 不得与普通产物通道 --out 同用。")
        memory_dir = _assert_apply_target(args.memory_dir)
        if args.backup_dir is None:
            raise ControlledWriteRefused("compile --write-index 必须提供 --backup-dir。")
        index_path = memory_dir / INDEX_FILENAME
        if index_path.is_symlink() or not index_path.is_file():
            raise ControlledWriteRefused(
                f"compile --write-index 只替换现存的非符号链接 {INDEX_FILENAME}: {index_path}"
            )
        old_index = index_path.read_bytes()
        index_stat = index_path.stat()
        index_device = index_stat.st_dev
        index_inode = index_stat.st_ino
        index_mode = stat.S_IMODE(index_stat.st_mode)
        index_backup_dir = _assert_backup_dir(args.backup_dir, memory_dir, [INDEX_FILENAME])
    else:
        memory_dir = args.memory_dir.expanduser()

    # 受控写的全部纯判据必须先于这个可能 mkdir 的普通 --out 出口。
    out_dir = _prepare_out_dir(args.out, memory_dir)
    baseline_path = (args.baseline_index or (memory_dir / INDEX_FILENAME)).expanduser()

    cards = load_cards(memory_dir)
    baseline, bad = parse_index(baseline_path)
    for lineno, line in bad:
        sys.stderr.write(f"[compile] 基线索引第 {lineno} 行无法解析，已忽略: {line!r}\n")

    disk = {c.filename for c in cards}
    for e in baseline:
        if e.filename not in disk:
            sys.stderr.write(f"[compile] 基线索引指向不存在的卡，已丢弃: {e.filename}\n")

    text, name_fallback_count = compile_index(cards, baseline)
    wm = measure(text)

    sys.stdout.write(text)
    if name_fallback_count:
        sys.stdout.write(
            f"[compile] 提示：{name_fallback_count} 张卡缺 title 且无现存索引行，已回退 name\n"
        )

    if args.write_index:
        assert old_index is not None
        assert index_backup_dir is not None
        assert index_device is not None
        assert index_inode is not None
        assert index_mode is not None
        current_stat = index_path.stat()
        if (
            current_stat.st_dev != index_device
            or current_stat.st_ino != index_inode
            or index_path.read_bytes() != old_index
        ):
            raise ControlledWriteRefused(f"编译期间 {index_path} 发生变化，拒绝覆盖。")
        index_backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = index_backup_dir / INDEX_FILENAME
        _atomic_replace_bytes(backup_path, old_index, mode=index_mode, no_clobber=True)
        if backup_path.read_bytes() != old_index:
            raise RuntimeError(f"备份写后校验失败: {backup_path}")
        current_stat = index_path.stat()
        if (
            current_stat.st_dev != index_device
            or current_stat.st_ino != index_inode
            or index_path.read_bytes() != old_index
        ):
            raise ControlledWriteRefused(f"备份后 {index_path} 发生变化，拒绝覆盖。")
        _atomic_replace_bytes(index_path, text.encode("utf-8"), mode=index_mode)
        sys.stderr.write(f"[compile] {index_path} 已原子写入；旧索引备份: {backup_path}\n")

    if out_dir is not None:
        (out_dir / "MEMORY.compiled.md").write_text(text, encoding="utf-8")
        # 刻意与 migrate-plan 的 watermark.txt 分名，两个子命令可以写进同一个 --out 目录
        (out_dir / "compile_watermark.txt").write_text(
            "\n".join(wm.report_lines("compiled MEMORY.md")) + "\n", encoding="utf-8"
        )
        sys.stderr.write(f"[compile] 产物已写入 {out_dir}\n")

    for line in wm.report_lines("[compile] 水位"):
        sys.stderr.write(line + "\n")

    return 0


# --------------------------------------------------------------------------------------
# migrate-plan：门牌对账
# --------------------------------------------------------------------------------------

_PUNCT_MAP = {
    "，": ",", "、": ",", "；": ";", "：": ":", "（": "(", "）": ")",
    "【": "[", "】": "]", "「": "\"", "」": "\"", "『": "\"", "』": "\"",
    "《": "<", "》": ">", "？": "?", "！": "!", "。": ".", "／": "/",
    "＋": "+", "－": "-", "＝": "=", "～": "~", "·": ".", "…": ".",
    "—": "-", "–": "-",
}

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")
_WORD_RE = re.compile(r"[a-z][a-z0-9_.\-]*")
_NUM_RE = re.compile(r"\d+")


def normalize_plate(text: str) -> str:
    out = []
    for ch in text:
        ch = _PUNCT_MAP.get(ch, ch)
        if ch.isspace():
            continue
        out.append(ch.lower())
    return "".join(out)


def plate_tokens(text: str) -> set[str]:
    """CJK 二元组 + ASCII 词 + 数字。用于「谁覆盖谁」的机械判据。"""
    norm = normalize_plate(text)
    tokens: set[str] = set()
    for m in _WORD_RE.finditer(norm):
        w = m.group(0).strip(".-")
        if len(w) >= 2:
            tokens.add("w:" + w)
    for m in _NUM_RE.finditer(norm):
        tokens.add("n:" + m.group(0))
    for m in _CJK_RE.finditer(norm):
        run = m.group(0)
        if len(run) == 1:
            tokens.add("c:" + run)
        else:
            for i in range(len(run) - 1):
                tokens.add("c:" + run[i : i + 2])
    return tokens


def coverage(subset: set[str], superset: set[str]) -> float:
    """subset 有多大比例被 superset 覆盖。subset 为空视作全覆盖。"""
    if not subset:
        return 1.0
    return len(subset & superset) / len(subset)


LEAN_INDEX = "偏索引"
LEAN_DESC = "偏description"
LEAN_BOTH = "双富"
LEAN_DOMINANCE = 0.25  # 一侧独有 token 数 ≤ 另一侧的该比例 → 判为「偏另一侧」


@dataclass
class Reconciliation:
    filename: str
    index_title: str
    index_hook: str
    description: str
    klass: str
    cov_desc_in_index: float
    cov_index_in_desc: float
    only_index: list[str]
    only_desc: list[str]
    chosen_description: str
    chosen_title: str
    lean: str = ""
    merge_upper_bound: str = ""


def classify_plate(
    index_hook: str, description: str, threshold: float
) -> tuple[str, float, float, set[str], set[str]]:
    t_idx = plate_tokens(index_hook)
    t_desc = plate_tokens(description)
    cov_desc = coverage(t_desc, t_idx)   # description 被索引覆盖的比例
    cov_idx = coverage(t_idx, t_desc)    # 索引被 description 覆盖的比例
    only_index = t_idx - t_desc
    only_desc = t_desc - t_idx

    if normalize_plate(index_hook) == normalize_plate(description):
        klass = CLASS_SAME
    elif cov_desc >= threshold and cov_idx >= threshold:
        klass = CLASS_SAME
    elif cov_desc >= threshold:
        klass = CLASS_INDEX_RICHER
    elif cov_idx >= threshold:
        klass = CLASS_DESC_RICHER
    else:
        klass = CLASS_HUMAN
    return klass, cov_desc, cov_idx, only_index, only_desc


def reconcile(
    cards: Sequence[Card], entries: Sequence[IndexEntry], threshold: float
) -> list[Reconciliation]:
    by_file = {e.filename: e for e in entries}
    out: list[Reconciliation] = []
    for c in cards:
        e = by_file.get(c.filename)
        idx_title = e.title if e else ""
        idx_hook = e.hook if e else ""
        desc = c.description or ""
        only_index: set[str]
        only_desc: set[str]
        if e is None:
            klass = "无索引行(新卡,直接用 frontmatter)"
            cov_desc = cov_idx = 1.0
            only_index, only_desc = set(), set()
        else:
            klass, cov_desc, cov_idx, only_index, only_desc = classify_plate(
                idx_hook, desc, threshold
            )

        # 预览用回写策略（见 migrate_plan.md 说明）：
        #   索引更富 / 一致 → 用索引 hook；description 更富 → 保留 description；
        #   需人裁 → 取较长者（水位取保守上界），并进人裁清单。
        if klass == CLASS_INDEX_RICHER or klass == CLASS_SAME:
            chosen = idx_hook or desc
        elif klass == CLASS_DESC_RICHER:
            chosen = desc or idx_hook
        elif klass == CLASS_HUMAN:
            chosen = idx_hook if js_char_length(idx_hook) >= js_char_length(desc) else desc
        else:
            chosen = desc

        n_i, n_d = len(only_index), len(only_desc)
        if n_i == 0 and n_d == 0:
            lean = ""
        elif n_d <= LEAN_DOMINANCE * n_i:
            lean = LEAN_INDEX
        elif n_i <= LEAN_DOMINANCE * n_d:
            lean = LEAN_DESC
        else:
            lean = LEAN_BOTH

        if klass == CLASS_HUMAN and idx_hook and desc:
            merged = f"{idx_hook};{desc}"
        else:
            merged = chosen

        out.append(
            Reconciliation(
                filename=c.filename,
                index_title=idx_title,
                index_hook=idx_hook,
                description=desc,
                klass=klass,
                cov_desc_in_index=cov_desc,
                cov_index_in_desc=cov_idx,
                only_index=sorted(only_index),
                only_desc=sorted(only_desc),
                chosen_description=chosen,
                chosen_title=idx_title or c.plate_title,
                lean=lean,
                merge_upper_bound=merged,
            )
        )
    return out


def _md_cell(text: str, limit: int = 60) -> str:
    t = text.replace("|", "\\|").replace("\n", " ")
    return t if len(t) <= limit else t[: limit - 1] + "…"


def cmd_migrate_plan(args: argparse.Namespace) -> int:
    memory_dir = args.memory_dir.expanduser()
    out_dir = _prepare_out_dir(args.out, memory_dir)
    threshold = args.coverage_threshold

    cards = load_cards(memory_dir)
    index_path = memory_dir / INDEX_FILENAME
    entries, bad = parse_index(index_path)
    for lineno, line in bad:
        sys.stderr.write(f"[migrate-plan] 索引第 {lineno} 行无法解析: {line!r}\n")

    recs = reconcile(cards, entries, threshold)
    by_file = {r.filename: r for r in recs}

    ordered = order_cards(cards, entries)
    preview = render_index(
        (
            by_file[c.filename].chosen_title,
            c.filename,
            by_file[c.filename].chosen_description,
        )
        for c in ordered
    )
    preview_wm = measure(preview)
    merged_preview = render_index(
        (
            by_file[c.filename].chosen_title,
            c.filename,
            by_file[c.filename].merge_upper_bound,
        )
        for c in ordered
    )
    merged_wm = measure(merged_preview)
    current_wm = measure(index_path.read_text(encoding="utf-8")) if index_path.is_file() else measure("")

    counts: dict[str, int] = {}
    for r in recs:
        counts[r.klass] = counts.get(r.klass, 0) + 1

    lines: list[str] = []
    lines.append("# 单门牌化 v2.0 迁移干跑方案（migrate-plan）")
    lines.append("")
    lines.append(f"- 记忆目录: `{memory_dir}`（**只读**）")
    lines.append(f"- 卡片数: {len(cards)}；索引行数: {len(entries)}")
    lines.append(f"- 覆盖率阈值: {threshold}")
    lines.append("")
    lines.append("## 迁移规则")
    lines.append("")
    lines.append("每卡两段回写：`[标题]` 段 → frontmatter `title`；`— hook` 段 → frontmatter `description`。")
    lines.append("对账分类的机械判据 = 门牌 token 集（CJK 二元组 + ASCII 词 + 数字）的双向覆盖率：")
    lines.append("")
    lines.append(f"- **{CLASS_SAME}**：归一化后相等，或双向覆盖率均 ≥ 阈值。")
    lines.append(f"- **{CLASS_INDEX_RICHER}**：description 被索引覆盖（≥阈值），索引另有内容。")
    lines.append(f"- **{CLASS_DESC_RICHER}**：索引被 description 覆盖（≥阈值），description 另有内容。")
    lines.append(f"- **{CLASS_HUMAN}**：两边互不覆盖 —— **本工具不合并，留给人裁**。")
    lines.append("")
    lines.append("预览编译产物的回写策略（仅为算水位与看形状，不是裁决）：一致/索引更富取索引 hook；")
    lines.append("description 更富保留 description；需人裁取较长者（水位保守上界）。")
    lines.append("")
    lines.append("## 分类分布")
    lines.append("")
    lines.append("| 分类 | 卡数 |")
    lines.append("| --- | ---: |")
    for k in (CLASS_SAME, CLASS_INDEX_RICHER, CLASS_DESC_RICHER, CLASS_HUMAN):
        lines.append(f"| {k} | {counts.get(k, 0)} |")
    for k, v in sorted(counts.items()):
        if k not in (CLASS_SAME, CLASS_INDEX_RICHER, CLASS_DESC_RICHER, CLASS_HUMAN):
            lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("### 阈值敏感度（同一份数据换阈值的分类分布）")
    lines.append("")
    lines.append("| 阈值 | " + " | ".join((CLASS_SAME, CLASS_INDEX_RICHER, CLASS_DESC_RICHER, CLASS_HUMAN)) + " |")
    lines.append("| ---: | ---: | ---: | ---: | ---: |")
    for tau in (0.50, 0.60, 0.70, 0.80, 0.90):
        c2: dict[str, int] = {}
        for r in recs:
            if not r.index_hook and not r.description:
                continue
            k = classify_plate(r.index_hook, r.description, tau)[0]
            c2[k] = c2.get(k, 0) + 1
        lines.append(
            f"| {tau:.2f} | "
            + " | ".join(
                str(c2.get(k, 0))
                for k in (CLASS_SAME, CLASS_INDEX_RICHER, CLASS_DESC_RICHER, CLASS_HUMAN)
            )
            + " |"
        )
    lines.append("")
    lines.append(
        "读法：阈值一路放宽到 0.50 也不能把「需人裁」压下去 ⇒ 两块门牌的分叉是**普遍的、"
        "不是少数离群卡**（严格判据下 78/80 互不覆盖）。所以下面给「倾向」子档做人裁排序，"
        "不靠调阈值制造好看的分布。"
    )
    lines.append("")

    lines.append("## 逐卡表")
    lines.append("")
    lines.append("倾向（仅排序用，不是裁决）：一侧独有 token 数 ≤ 另一侧的 "
                 f"{LEAN_DOMINANCE:.0%} 即判「偏另一侧」，否则「{LEAN_BOTH}」。")
    lines.append("")
    lines.append("| 卡 | 分类 | 倾向 | cov(desc⊆idx) | cov(idx⊆desc) | 仅索引 tok | 仅desc tok | 回写 title |")
    lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | --- |")
    for r in sorted(recs, key=lambda r: (r.klass, r.lean, r.filename)):
        lines.append(
            f"| `{r.filename}` | {r.klass} | {r.lean} | {r.cov_desc_in_index:.2f} | "
            f"{r.cov_index_in_desc:.2f} | {len(r.only_index)} | {len(r.only_desc)} | "
            f"{_md_cell(r.chosen_title, 40)} |"
        )
    lines.append("")
    lean_counts: dict[str, int] = {}
    for r in recs:
        if r.klass == CLASS_HUMAN:
            lean_counts[r.lean] = lean_counts.get(r.lean, 0) + 1
    lines.append("需人裁卡的倾向分布：" + ", ".join(f"{k}={v}" for k, v in sorted(lean_counts.items())))
    lines.append("")

    human = [r for r in recs if r.klass == CLASS_HUMAN]
    human.sort(key=lambda r: -(len(r.only_index) + len(r.only_desc)))
    lines.append(f"## 需人裁清单（{len(human)} 张，按分叉规模降序）")
    lines.append("")
    if not human:
        lines.append("（无）")
    for r in human:
        lines.append(f"### `{r.filename}`")
        lines.append("")
        lines.append(
            f"- 覆盖率: desc⊆idx = {r.cov_desc_in_index:.2f} / idx⊆desc = {r.cov_index_in_desc:.2f}"
            f"；倾向 {r.lean}"
        )
        lines.append(f"- 索引标题: {r.index_title}")
        lines.append("")
        lines.append("索引行 hook（逐字）:")
        lines.append("")
        lines.append("```")
        lines.append(r.index_hook)
        lines.append("```")
        lines.append("")
        lines.append("frontmatter description（逐字）:")
        lines.append("")
        lines.append("```")
        lines.append(r.description)
        lines.append("```")
        lines.append("")
        lines.append(f"- 仅索引有的 token（{len(r.only_index)}）: " + " ".join(t[2:] for t in r.only_index[:40]))
        lines.append(f"- 仅 description 有的 token（{len(r.only_desc)}）: " + " ".join(t[2:] for t in r.only_desc[:40]))
        lines.append("")

    lines.append("## 水位")
    lines.append("")
    lines.append("三个口径：现状 / 迁移后编译预览（按上面的回写策略）/ 人裁上界"
                 "（需人裁的卡假定两边合并保留，是最坏情况）。")
    lines.append("")
    lines.append("```")
    lines.extend(current_wm.report_lines("当前 MEMORY.md"))
    lines.extend(preview_wm.report_lines("迁移后编译预览"))
    lines.extend(merged_wm.report_lines("人裁上界（需人裁卡两边合并）"))
    lines.append("```")
    lines.append("")

    plan_text = "\n".join(lines) + "\n"
    watermark_text = (
        "\n".join(
            current_wm.report_lines("当前 MEMORY.md")
            + preview_wm.report_lines("迁移后编译预览")
            + merged_wm.report_lines("人裁上界（需人裁卡两边合并）")
        )
        + "\n"
    )

    if out_dir is not None:
        (out_dir / "migrate_plan.md").write_text(plan_text, encoding="utf-8")
        (out_dir / "MEMORY.compiled.preview.md").write_text(preview, encoding="utf-8")
        (out_dir / "watermark.txt").write_text(watermark_text, encoding="utf-8")
        sys.stderr.write(f"[migrate-plan] 产物已写入 {out_dir}\n")
    else:
        sys.stdout.write(plan_text)

    summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    sys.stderr.write(f"[migrate-plan] {len(cards)} 卡；{summary}\n")
    for line in preview_wm.report_lines("[migrate-plan] 预览水位"):
        sys.stderr.write(line + "\n")
    return 0


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="memory_plate_tool",
        description="单门牌化 v2.0：文件记忆层门牌校验 / 编译 / 迁移干跑 / 受控应用（默认只读）",
    )
    sub = p.add_subparsers(dest="command", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument(
            "--memory-dir",
            type=Path,
            default=DEFAULT_MEMORY_DIR,
            help=f"记忆卡目录，默认 {DEFAULT_MEMORY_DIR}",
        )
        sp.add_argument(
            "--out",
            type=Path,
            default=None,
            help="普通报告写出口；指向真记忆命名空间一律拒绝并 exit 2",
        )

    sp_v = sub.add_parser("validate", help="逐卡校验 frontmatter schema")
    add_common(sp_v)
    sp_v.set_defaults(func=cmd_validate)

    sp_c = sub.add_parser("compile", help="由 frontmatter 编译 MEMORY.md 内容（保序+头插）")
    add_common(sp_c)
    sp_c.add_argument(
        "--baseline-index",
        type=Path,
        default=None,
        help="排序基线索引，默认 <memory-dir>/MEMORY.md",
    )
    sp_c.add_argument(
        "--write-index",
        action="store_true",
        help="受控写入：仅原子替换 <memory-dir>/MEMORY.md",
    )
    sp_c.add_argument(
        "--backup-dir",
        type=Path,
        default=None,
        help="--write-index 必填；必须位于任何 memory 命名空间之外",
    )
    sp_c.set_defaults(func=cmd_compile)

    sp_m = sub.add_parser("migrate-plan", help="索引行 × frontmatter 逐卡对账干跑")
    add_common(sp_m)
    sp_m.add_argument(
        "--coverage-threshold",
        type=float,
        default=DEFAULT_COVERAGE_THRESHOLD,
        help=f"覆盖率阈值，默认 {DEFAULT_COVERAGE_THRESHOLD}",
    )
    sp_m.set_defaults(func=cmd_migrate_plan)

    sp_a = sub.add_parser("apply", help="定点应用卡片 title/description/正文追加（默认 dry-run）")
    sp_a.add_argument(
        "--memory-dir",
        type=Path,
        default=DEFAULT_MEMORY_DIR,
        help=f"目标记忆卡目录，默认 {DEFAULT_MEMORY_DIR}",
    )
    sp_a.add_argument("--proposals", type=Path, required=True, help="受控改卡 JSON proposals 文件")
    sp_a.add_argument("--commit", action="store_true", help="通过全部安全判据后备份并原子写卡")
    sp_a.add_argument(
        "--backup-dir",
        type=Path,
        default=None,
        help="--commit 必填；必须位于任何 memory 命名空间之外",
    )
    sp_a.set_defaults(func=cmd_apply)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except (OutDirRefused, ControlledWriteRefused) as exc:
        sys.stderr.write(f"REFUSED: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
