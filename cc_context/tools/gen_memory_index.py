"""记忆树索引生成器 (memtree 重构 P3, 2026-06-15) — 非破坏性。

保留 MEMORY.md 现有人工结构 (section 标题 / 引言 / 节点分组), 只把每条索引行
`- [title](file.md) — 摘要` 的**摘要**用该节点 frontmatter 的 description **刷新**
(description = 单一来源), 修掉手抄摘要漂移。

GPT 外审钦点回归样本: repo MEMORY.md 第 128 行 `zmd-round2-dispatch-fix-state` 摘要
说「Round5=重启第1轮进行中」, 而节点正文已是 Round5 RESET / R6 —— 索引 stale, 现有 gate
全绿没抓到。本生成器刷新该行即止血。

硬 24KB cap: 生成结果超 24576 B 则**报红、不静默裁剪** (GPT rule)。
输出 MEMORY.generated.md (不动正本, 供 owner diff 后再决定是否替换)。**不碰 harness。**

用法:
    python cc_context/tools/gen_memory_index.py            # 生成 + 报告 (默认)
    python cc_context/tools/gen_memory_index.py --check    # 只报告"有几行会被刷新", 不写文件
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MEM_DIR = ROOT / "cc_context" / "memory"
# 旁路输出放 knowledge/ (控制层), 不能放 cc_context/memory/ (那里 .md 会被 check_memory_tree
# 当节点扫 -> 无 frontmatter name 直接 BLOCK)。S2 替换时再 copy 它到 memory/MEMORY.md。
GEN_OUT = ROOT / "cc_context" / "knowledge" / "MEMORY.generated.md"
MAX_BYTES = 24_576

# 索引行: `- [title](file.md) — summary`  (em dash 分隔)
_LINE_RE = re.compile(r"^(\s*-\s*\[[^\]]*\]\()([^)]+\.md)(\)\s*—\s*)(.*)$")
_DESC_RE = re.compile(r"^description:\s*(.+?)\s*$", re.MULTILINE)
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# 通道① (MEMORY.md 无条件注入) 索引行摘要 = description 的前导短句;
# 完整 description 仍在节点 frontmatter, 供通道② (按 query 语义召回) 用。
LEAD_CAP = 52
_SENT_END = ("。", "；", "！")
_CLAUSE = ("、", "，", ",", ";", "：", ":", " ")


def truncate_lead(desc: str) -> str:
    """取 description 前导短句作索引行摘要: 优先在首个句末标点截 (cap 内);
    否则在 cap 处子句边界截 + …。"""
    for end in _SENT_END:
        idx = desc.find(end)
        if 0 < idx <= LEAD_CAP:
            return desc[:idx]
    if len(desc) <= LEAD_CAP:
        return desc
    cut = desc[:LEAD_CAP]
    for b in _CLAUSE:
        j = cut.rfind(b)
        if j > LEAD_CAP // 2:
            return cut[:j] + "…"
    return cut + "…"


def node_description(mem_dir: Path, filename: str) -> str | None:
    path = mem_dir / filename
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    fm = _FM_RE.match(text)
    front = fm.group(1) if fm else text
    m = _DESC_RE.search(front)
    if not m:
        return None
    return m.group(1).strip().strip('"').strip()


def regenerate(mem_dir: Path) -> tuple[str, list[dict]]:
    """返回 (生成后的全文, 刷新明细列表)。结构行原样保留, 只刷新索引行摘要。"""
    src = (mem_dir / "MEMORY.md").read_text(encoding="utf-8")
    out_lines: list[str] = []
    refreshed: list[dict] = []
    for line in src.splitlines():
        m = _LINE_RE.match(line)
        if not m:
            out_lines.append(line)
            continue
        prefix, filename, sep, old_summary = m.groups()
        desc = node_description(mem_dir, filename)
        if desc is None:
            out_lines.append(line)  # 找不到节点/description: 原样保留, 记一笔
            refreshed.append({"file": filename, "status": "no_description_kept_old"})
            continue
        summary = truncate_lead(desc)
        out_lines.append(f"{prefix}{filename}{sep}{summary}")
        if summary.strip() != old_summary.strip():
            refreshed.append({
                "file": filename, "status": "refreshed",
                "old": old_summary.strip()[:80], "new": summary[:80],
            })
    return "\n".join(out_lines) + "\n", refreshed


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--mem-dir", type=Path, default=DEFAULT_MEM_DIR)
    ap.add_argument("--check", action="store_true", help="只报告会刷新几行, 不写文件")
    args = ap.parse_args()

    if not (args.mem_dir / "MEMORY.md").exists():
        print(f"找不到 {args.mem_dir / 'MEMORY.md'}")
        return 1

    generated, refreshed = regenerate(args.mem_dir)
    size = len(generated.encode("utf-8"))
    changed = [r for r in refreshed if r["status"] == "refreshed"]
    missing = [r for r in refreshed if r["status"] != "refreshed"]

    print(f"生成大小: {size}/{MAX_BYTES} B  ({'超出!' if size > MAX_BYTES else 'OK'})")
    print(f"摘要刷新 (索引 stale 被修): {len(changed)} 行")
    for r in changed:
        print(f"  REFRESH {r['file']}")
        print(f"     旧: {r['old']}")
        print(f"     新: {r['new']}")
    if missing:
        print(f"找不到 description, 原样保留: {len(missing)} 行  "
              f"{[r['file'] for r in missing]}")

    over = size > MAX_BYTES
    if args.check:
        print("\n(--check: 未写文件)")
    else:
        GEN_OUT.parent.mkdir(parents=True, exist_ok=True)
        GEN_OUT.write_text(generated, encoding="utf-8", newline="\n")
        print(f"\n生成 -> {GEN_OUT} (正本未动; owner diff 后再决定替换)")
    if over:
        print("!! 超 24576 B 硬 cap — 需削减 (不静默裁剪); 替换正本前必须先解决。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
