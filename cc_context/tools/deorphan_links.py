"""De-orphan: 给 10 个孤立 memory 节点补真实拓扑 [[link]] + 去掉 protocol 占位符。
fail-closed: 目标名不存在则 skip+报告; 已存在的链接不重复加。只读校验后才写。"""
import re
import pathlib
import sys
from collections import defaultdict

DEFAULT_MEM = pathlib.Path(__file__).resolve().parents[1] / "memory"
MEM = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else DEFAULT_MEM

name2path, name2txt = {}, {}
for f in MEM.glob("*.md"):
    if f.name == "MEMORY.md":
        continue
    txt = f.read_text(encoding="utf-8")
    m = re.search(r"(?m)^name:\s*(.+?)\s*$", txt)
    if m:
        nm = m.group(1).strip()
        name2path[nm] = f
        name2txt[nm] = txt
valid = set(name2path)

# (src, tgt, reason) — 只列语义真相关的边
edges = [
    ("lever25-ihs-dead", "paradigm-death-timeline-27-lever", "本条是 27 lever 之一"),
    ("paradigm-death-timeline-27-lever", "lever25-ihs-dead", "Lever 25 详情"),
    ("review-strategy", "index-packaging-cluster", "审查打包规范全套入口"),
    ("review-strategy", "big-milestone-gpt-pro-review", "大节点外审"),
    ("review-strategy", "gemini-review-algorithm-math", "算法层 cross-check"),
    ("index-packaging-cluster", "review-strategy", "项目 3 层审查策略"),
    ("optimization-strategy", "avoid-micro-optimization-spiral", "stack 全上 vs 别钻 micro"),
    ("optimization-strategy", "phase3c-roadmap", "优化项清单"),
    ("avoid-micro-optimization-spiral", "optimization-strategy", "互补"),
    ("multiprocess-hang-inspect-all", "shell-wrapper-pgrep-self-match", "进程调试 lore"),
    ("multiprocess-hang-inspect-all", "p2-14-dumper-path-blocked", "hang 实例"),
    ("shell-wrapper-pgrep-self-match", "multiprocess-hang-inspect-all", "进程调试 lore"),
    ("p2-14-dumper-path-blocked", "multiprocess-hang-inspect-all", "hang 排查法"),
    ("autopilot-with-review-gate", "keep-review-process-light", "流程轻量"),
    ("autopilot-with-review-gate", "lazy-mode", "同 root"),
    ("keep-review-process-light", "autopilot-with-review-gate", "autopilot 审查闸"),
    ("user-profile", "endfield-solver", "项目身份"),
    ("endfield-solver", "user-profile", "用户画像"),
    ("archive-research-transcripts", "research-roi-metric", "调研价值/归档"),
    ("research-roi-metric", "archive-research-transcripts", "调研归档触发"),
    ("full-pytest-after-vendor-refresh", "autopilot-with-review-gate", "审查闸跑全测"),
    ("record-tool-entry-points", "archive-research-transcripts", "过程记录"),
]

add, skipped = defaultdict(list), []
for s, t, r in edges:
    if s not in valid:
        skipped.append(f"src 不存在: {s}")
        continue
    if t not in valid:
        skipped.append(f"tgt 不存在: {t}  (边 {s}->{t})")
        continue
    if f"[[{t}]]" in name2txt[s]:
        skipped.append(f"已连过: {s} -> {t}")
        continue
    add[s].append((t, r))

for s, links in add.items():
    p = name2path[s]
    txt = p.read_text(encoding="utf-8").rstrip()
    block = "\n\n## 链 (补连 2026-06-01)\n" + "".join(f"- [[{t}]] — {r}\n" for t, r in links)
    p.write_text(txt + block, encoding="utf-8")
    print(f"+{s}: " + ", ".join(t for t, _ in links))

# 去掉 protocol 占位符 [[...]] (它让 1 条 link 永远 unresolved)
proto = name2path.get("memory-currency-protocol")
if proto:
    txt = proto.read_text(encoding="utf-8")
    if "[[...]]" in txt:
        proto.write_text(txt.replace("[[...]]", "<现状源>"), encoding="utf-8")
        print("placeholder [[...]] -> <现状源> in memory-currency-protocol")

print("--- skipped ---")
for x in skipped:
    print("  " + x)
print(f"files updated: {len(add)}")
