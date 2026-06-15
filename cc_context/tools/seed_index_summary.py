"""把现有 MEMORY.md 的好摘要回种进各节点 frontmatter 的 index_summary 字段 (memtree P3 方案A)。

动机 (实测 diff 证伪"截断 description"): description 为通道② 召回写、带分类前缀又长,
截断成索引行会丢信息+加冗余前缀, 质量不如 owner 手 condense 的 MEMORY.md 摘要。方案A =
保住这批好摘要, 把它从 MEMORY.md 挪进节点 frontmatter `index_summary` (单一来源、与节点同住),
之后生成器从 index_summary 出索引, body-sha gate 抓"正文变了 index_summary 没跟上"。

本脚本: 解析 cc_context/memory/MEMORY.md 的每条 `- [title](file.md) — summary`,
把 summary 原样写进 file.md frontmatter 的 `index_summary` (插在 name 行后)。
**同时写 cc_context/memory + _cc_live_memory 两镜像** (保字节一致过 live-mirror gate)。
幂等: 已有 index_summary 的节点跳过。**不碰 harness。**

用法:
    python cc_context/tools/seed_index_summary.py --check   # dry-run: 报将改哪些 + 抽样
    python cc_context/tools/seed_index_summary.py --apply   # 实际写两镜像 + 写后自校验
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO_MEM = ROOT / "cc_context" / "memory"
LIVE_MEM = ROOT / "_cc_live_memory"

_LINE_RE = re.compile(r"^\s*-\s*\[[^\]]*\]\(([^)]+\.md)\)\s*—\s*(.*)$")
_FM_RE = re.compile(r"^(---\s*\n)(.*?)(\n---\s*\n)", re.DOTALL)
_NAME_LINE_RE = re.compile(r"^name:\s", re.MULTILINE)
_IDX_LINE_RE = re.compile(r"^index_summary:\s", re.MULTILINE)


def yaml_dq(s: str) -> str:
    """双引号 YAML 标量: 转义反斜杠和双引号; 中文标点/markdown/括号在双引号内合法。"""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def parse_memory_index(mem_dir: Path) -> dict[str, str]:
    """MEMORY.md -> {filename: summary}。"""
    out: dict[str, str] = {}
    for line in (mem_dir / "MEMORY.md").read_text(encoding="utf-8").splitlines():
        m = _LINE_RE.match(line)
        if m:
            out[m.group(1).strip()] = m.group(2).strip()
    return out


def add_index_summary(text: str, summary: str) -> str | None:
    """在 frontmatter 的 name 行后插入 index_summary。已存在则返回 None (跳过)。"""
    fm = _FM_RE.match(text)
    if not fm:
        return None
    front = fm.group(2)
    if _IDX_LINE_RE.search(front):
        return None  # 已有
    name_m = _NAME_LINE_RE.search(front)
    if not name_m:
        return None
    # name 行末尾插入新行
    name_line_end = front.find("\n", name_m.start())
    if name_line_end == -1:
        name_line_end = len(front)
    new_front = (
        front[:name_line_end] + "\n" + f"index_summary: {yaml_dq(summary)}"
        + front[name_line_end:]
    )
    return text[:fm.start(2)] + new_front + text[fm.end(2):]


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--check", action="store_true", help="dry-run: 报将改哪些, 不写")
    ap.add_argument("--apply", action="store_true", help="实际写 repo + _cc_live 两镜像")
    args = ap.parse_args()
    if not (args.check or args.apply):
        ap.error("需 --check 或 --apply")

    index = parse_memory_index(REPO_MEM)
    to_seed, skipped, missing, special = [], [], [], []
    for filename, summary in index.items():
        node = REPO_MEM / filename
        if not node.exists():
            missing.append(filename)
            continue
        text = node.read_text(encoding="utf-8")
        new_text = add_index_summary(text, summary)
        if new_text is None:
            skipped.append(filename)
            continue
        if '"' in summary or "\\" in summary:
            special.append(filename)
        to_seed.append((filename, summary, new_text))

    print(f"MEMORY.md 索引行: {len(index)}; 待回种 {len(to_seed)}; "
          f"已有跳过 {len(skipped)}; 文件缺失 {len(missing)}; 含转义字符 {len(special)}")
    for filename, summary, _ in to_seed[:5]:
        print(f"  + {filename}\n      index_summary: {summary[:70]}")
    if missing:
        print(f"  缺失文件: {missing}")
    if special:
        print(f"  含 \" 或 \\ (已转义): {special}")

    if args.check:
        print("\n(--check: 未写文件)")
        return 0

    # --apply: 写两镜像
    written = 0
    for filename, summary, new_text in to_seed:
        (REPO_MEM / filename).write_text(new_text, encoding="utf-8", newline="\n")
        live = LIVE_MEM / filename
        if live.exists():
            live_text = live.read_text(encoding="utf-8")
            live_new = add_index_summary(live_text, summary)
            if live_new is not None:
                live.write_text(live_new, encoding="utf-8", newline="\n")
        written += 1

    # 写后自校验: 每个改过的节点重新解析, 确认 index_summary 能读回原值
    bad = []
    for filename, summary, _ in to_seed:
        text = (REPO_MEM / filename).read_text(encoding="utf-8")
        fm = _FM_RE.match(text)
        got = re.search(r'^index_summary:\s*"((?:[^"\\]|\\.)*)"\s*$',
                        fm.group(2) if fm else "", re.MULTILINE)
        recovered = got.group(1).replace('\\"', '"').replace("\\\\", "\\") if got else None
        if recovered != summary:
            bad.append(filename)
    print(f"\n已写 {written} 节点 × 2 镜像。写后自校验: {len(bad)} 个 index_summary 读回不一致 "
          f"{bad if bad else '(全部一致)'}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
