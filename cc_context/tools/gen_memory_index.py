"""记忆树索引生成器 (memtree 重构 P3, 2026-06-15) — 非破坏性。

保留 MEMORY.md 现有人工结构 (section 标题 / 引言 / 节点分组), 只把每条索引行
`- [title](file.md) — 摘要` 的**摘要**用该节点 frontmatter 的 **index_summary** 重生成
(index_summary = 单一来源), 修掉「MEMORY.md 摘要 vs index_summary」漂移。

边界 (GPT 外审 2026-06-16 指出, 必读): 本生成器**只重写摘要文本, 不重建标题/分组/结构**
(那些仍取自现有 MEMORY.md 模板), 故改标题不会被 --check 抓到 —— 它是「摘要一致性刷新器」,
**不是完整 lockfile**。而 index_summary 本身 vs 节点正文是否新鲜, 由 check_description_freshness
的 body-sha gate 管 (本工具不负责; 回种 stale 摘要不会被本工具发现, 见 R2 已修案例)。

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
LIVE_MEM_MD = ROOT / "_cc_live_memory" / "MEMORY.md"
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


_IDXSUM_RE = re.compile(r'^index_summary:\s*"((?:[^"\\]|\\.)*)"\s*$', re.MULTILINE)


def node_index_summary(mem_dir: Path, filename: str) -> str | None:
    """读节点 frontmatter 的 index_summary (方案A 单一来源, 双引号 YAML 标量)。"""
    try:
        text = (mem_dir / filename).read_text(encoding="utf-8")
    except OSError:
        return None
    fm = _FM_RE.match(text)
    front = fm.group(1) if fm else text
    m = _IDXSUM_RE.search(front)
    if not m:
        return None
    return m.group(1).replace('\\"', '"').replace("\\\\", "\\")


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
        # 方案A: 优先用节点 index_summary (单一来源, 保质量); 缺失才回退截断 description
        summary = node_index_summary(mem_dir, filename)
        if summary is None:
            summary = truncate_lead(desc)
        out_lines.append(f"{prefix}{filename}{sep}{summary}")
        if summary.strip() != old_summary.strip():
            refreshed.append({
                "file": filename, "status": "refreshed",
                "old": old_summary.strip()[:80], "new": summary[:80],
            })
    return "\n".join(out_lines) + "\n", refreshed


def validate_index_nodes(mem_dir: Path) -> list[str]:
    """硬校验每条索引行: 目标节点文件存在 + 有 index_summary (缺 = 静默回退源, GPT 外审点的)。"""
    errs: list[str] = []
    for line in (mem_dir / "MEMORY.md").read_text(encoding="utf-8").splitlines():
        m = _LINE_RE.match(line)
        if not m:
            continue
        fn = m.group(2)
        if not (mem_dir / fn).exists():
            errs.append(f"索引引用的节点文件缺失: {fn}")
        elif node_index_summary(mem_dir, fn) is None:
            errs.append(f"节点缺 index_summary (会静默回退截断 description): {fn}")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--mem-dir", type=Path, default=DEFAULT_MEM_DIR)
    ap.add_argument("--check", action="store_true", help="只报告会刷新几行, 不写文件")
    ap.add_argument("--apply", action="store_true",
                    help="把生成结果写进正本 cc_context/memory/MEMORY.md + _cc_live 镜像")
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
    errs = validate_index_nodes(args.mem_dir)
    for e in errs:
        print(f"  !! {e}")
    if args.check:
        print("\n(--check: 未写文件)")
        if changed:
            print(f"!! lockfile gate: MEMORY.md 与 index_summary 不一致 ({len(changed)} 行) "
                  "— 改 index_summary 后须重跑生成器同步 MEMORY.md 正本")
        if changed or errs:
            return 1
    elif args.apply:
        if over or errs:
            print("!! 超 cap 或有节点缺 index_summary/文件 — 拒绝写正本。")
            return 1
        (args.mem_dir / "MEMORY.md").write_text(generated, encoding="utf-8", newline="\n")
        LIVE_MEM_MD.write_text(generated, encoding="utf-8", newline="\n")
        print(f"\n写正本 -> {args.mem_dir / 'MEMORY.md'} + {LIVE_MEM_MD} ({len(changed)} 行刷新)")
        return 0
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
