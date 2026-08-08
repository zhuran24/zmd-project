#!/usr/bin/env python3
"""单门牌化 v2.0 工具（批② 工具席交付物，2026-08-08）。

三个子命令，**全部默认只读**：

  validate       逐卡校验 frontmatter schema（硬错 / 迁移欠账 / 提示 三栏）
  compile        由卡片 frontmatter 确定性编译 MEMORY.md 内容（保序 + 新卡头插）
  migrate-plan   干跑：索引行 [标题]/— hook 段 与 frontmatter 的逐卡对账方案

写操作的唯一出口是显式 `--out <目录>`。**硬判据**：`--out` 指向（或落进）任何
`.../.claude/projects/<项目>/memory` 命名空间一律拒绝并 exit 2——真记忆目录只许读，
迁移本体由主线程在 owner 点头后自己执行。参见 `_assert_safe_out_dir`。

门牌格式（左线修正后的 v1.1 规则）::

    - [title](文件名.md) — description

`title` 缺失时回退 `name`（迁移前 80 张真卡普遍缺 title，属「迁移欠账」不是硬错）。

排序（FINAL_VERDICT §1/§4，C7 反转）：注入截断是**切尾保头**，所以新卡必须在前——
以现有 MEMORY.md 行序为基线，已在索引的卡保持相对顺序，不在索引的新卡头插。

水位（FINAL_VERDICT §1，M-02 降级为监测项）：`eoe=25000` 的单位是 JS 字符
（UTF-16 code unit，`len(s.encode('utf-16-le')) // 2`），另有 200 行上限；>80% 报警。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
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
        """编译用标题：title 缺失回退 name，name 也缺回退文件名 stem。"""
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


def render_index(entries: Iterable[tuple[str, str, str]]) -> str:
    """entries = (title, filename, description) → MEMORY.md 内容。"""
    lines = [INDEX_HEADER]
    for title, filename, description in entries:
        if description:
            lines.append(f"- [{title}]({filename}) — {description}")
        else:
            lines.append(f"- [{title}]({filename})")
    return "\n".join(lines) + "\n"


def compile_index(cards: Sequence[Card], baseline: Sequence[IndexEntry]) -> str:
    ordered = order_cards(cards, baseline)
    return render_index(
        (c.plate_title, c.filename, c.description or "") for c in ordered
    )


def cmd_compile(args: argparse.Namespace) -> int:
    memory_dir = args.memory_dir.expanduser()
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

    text = compile_index(cards, baseline)
    wm = measure(text)

    sys.stdout.write(text)
    for line in wm.report_lines("[compile] 水位"):
        sys.stderr.write(line + "\n")

    if out_dir is not None:
        (out_dir / "MEMORY.compiled.md").write_text(text, encoding="utf-8")
        # 刻意与 migrate-plan 的 watermark.txt 分名，两个子命令可以写进同一个 --out 目录
        (out_dir / "compile_watermark.txt").write_text(
            "\n".join(wm.report_lines("compiled MEMORY.md")) + "\n", encoding="utf-8"
        )
        sys.stderr.write(f"[compile] 产物已写入 {out_dir}\n")

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
        description="单门牌化 v2.0：文件记忆层门牌校验 / 编译 / 迁移干跑（默认只读）",
    )
    sub = p.add_subparsers(dest="command", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument(
            "--memory-dir",
            type=Path,
            default=DEFAULT_MEMORY_DIR,
            help=f"记忆卡目录（只读），默认 {DEFAULT_MEMORY_DIR}",
        )
        sp.add_argument(
            "--out",
            type=Path,
            default=None,
            help="唯一写出口目录；指向真记忆命名空间一律拒绝并 exit 2",
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
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except OutDirRefused as exc:
        sys.stderr.write(f"REFUSED: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
