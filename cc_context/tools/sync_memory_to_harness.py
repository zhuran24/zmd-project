#!/usr/bin/env python3
"""把仓库 cc_context/memory 的工作规则/项目/参考节点投影到 harness 召回目录。

背景
----
Claude Code 的 auto-memory 召回只读 **harness 目录**
(``~/.claude/projects/<slug>/memory``):每次会话注入它的 ``MEMORY.md``,
并按各节点 frontmatter 的 ``description`` 做相关性召回。

owner 维护的 ``cc_context/memory``(+ ``_cc_live_memory`` 镜像)用 snake 文件名
+ ``feedback_/project_/reference_/user_`` 前缀,**不在** auto-memory 召回路径上。
两套树的 frontmatter ``name`` 与 wikilink 同为 kebab 命名空间,只有文件名风格不同。

历史问题(2026-06-14 体检发现):repo 有几十条 ``feedback_*`` 工作规则、
``project_*`` 状态、``reference_*`` 资源,harness 召回树里根本没有 —— owner 写的
规则 AI 自动召回读不到,且 ``CLAUDE.md`` 里 ``[[subagent-model-by-weight]]`` 等
wikilink 在召回树里跳空。本脚本把这些节点按其 ``name`` 投影成
``harness/<name>.md``,让规则进入召回,并重建 3 个索引父节点 + 校验。

为什么单向 repo -> harness
--------------------------
repo 那套是 owner 手工维护的权威源;harness 是召回投影。反向(harness 覆盖 repo)
会用少覆多删数据(见 ``zmd-env-memory-sync`` 记忆)。所以只做 repo -> harness。

``handoff_*`` 现状源**不投影全文**(每 commit 被 stamp 刷新、属高频易变值,复制即漂),
harness 侧保留手写的指针 stub(``windows-ninth-review-pending.md``)。

用法
----
    python cc_context/tools/sync_memory_to_harness.py --check   # 只报告 drift, exit 1 = 有漂移
    python cc_context/tools/sync_memory_to_harness.py --apply   # 投影缺失/漂移节点 + 重建索引
    python cc_context/tools/sync_memory_to_harness.py --apply --harness-dir <其它机器的 harness memory 目录>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 投影类前缀(snake 文件名);handoff_ 不投影全文,保留 harness stub
COPY_PREFIXES = ("feedback_", "project_", "reference_", "user_")
# 索引父节点分组:(父节点 name, 文件名前缀正则匹配的 tuple, type, description)
INDEX_GROUPS = [
    (
        "collaboration-rules-index",
        ("feedback_",),
        "feedback",
        "工作/协作偏好规则索引 — owner 立的几十条 how-to-work 铁律(用人话沟通、默认做不问、改记忆仪式、"
        "优化策略 stack、子代理按重量派、验证独立 backstop、调研 ROI 等);"
        '"该怎么干活/协作规矩/我又犯了什么毛病"类先看这, 细目见正文 wikilink',
    ),
    (
        "project-knowledge-index",
        ("project_", "handoff_"),
        "project",
        "项目知识索引 — 终末地 70x70 求解器身份根/Phase3C 路线图/死路总表 27 lever/硬件边界/"
        "权威数字源/记忆树架构/当前 phase 现状指针;接手项目或判断技术方向先看这",
    ),
    (
        "reference-resources-index",
        ("reference_",),
        "reference",
        "外部资源/配置/spec 参考索引 — Gemini 数学顾问、GitHub 备份、CP-SAT API 限制、host 调优、"
        "IP v2 蓝图建模、Windows/PowerShell 踩坑;需要外部工具/环境配置/已知 API 坑时看这",
    ),
]
MEMORY_MD_LIMIT = 24576  # harness MEMORY.md 尾部静默截断硬约束

DEFAULT_HARNESS = Path.home() / ".claude" / "projects" / "C--claude-pj-zmd-pj" / "memory"


def frontmatter_field(text: str, field: str) -> str | None:
    """从 markdown 节点文本里取 frontmatter 的某字段值(name/description)。"""
    in_fm = False
    for line in text.splitlines():
        s = line.strip()
        if s == "---":
            if not in_fm:
                in_fm = True
                continue
            break
        if in_fm and s.startswith(f"{field}:"):
            return s[len(field) + 1 :].strip().strip('"').strip("'")
    return None


def shorten(desc: str, limit: int = 48) -> str:
    desc = (desc or "").replace("\\", "").strip()
    if not desc:
        return "（description 待补）"
    desc = " ".join(desc.split())
    return desc[:limit].strip() + "…" if len(desc) > limit else desc


def repo_copy_nodes(repo_dir: Path) -> list[tuple[Path, str]]:
    """返回 [(repo 文件, 目标 name), ...],仅投影类(snake 前缀,排除 handoff_)。"""
    out = []
    for p in sorted(repo_dir.glob("*.md")):
        if p.name == "MEMORY.md":
            continue
        if not p.name.startswith(COPY_PREFIXES):
            continue
        name = frontmatter_field(p.read_text(encoding="utf-8"), "name")
        if not name:
            print(f"  ! {p.name} 无 frontmatter name, 跳过", file=sys.stderr)
            continue
        out.append((p, name))
    return out


def build_index_body(repo_dir: Path, prefixes: tuple, name: str, type_: str, desc: str) -> str:
    items = []
    for p in sorted(repo_dir.glob("*.md")):
        if not p.name.startswith(prefixes):
            continue
        txt = p.read_text(encoding="utf-8")
        nm = frontmatter_field(txt, "name")
        if not nm:
            continue
        items.append(f"- [[{nm}]] — {shorten(frontmatter_field(txt, 'description') or '')}")
    header = [
        "---",
        f"name: {name}",
        f"description: {desc}",
        "metadata: ",
        "  node_type: memory",
        f"  type: {type_}",
        "---",
        "",
        "这是**索引父节点**(导航用)。子节点各自 description 独立参与召回; 本节点把同族子节点聚在一处便于"
        "浏览/跳转, 并让 MEMORY.md 不必平铺几十行(harness MEMORY.md 有 ~24KB 尾部静默截断硬约束, 见 "
        "[[memory-tree-structural-health]])。原生维护副本在仓库 cc_context/memory/(snake 文件名), "
        "harness 这份是召回投影 (由 cc_context/tools/sync_memory_to_harness.py 维护)。",
        "",
    ]
    return "\n".join(header + items) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="实际写入(缺省=dry-run 仅报告)")
    ap.add_argument("--check", action="store_true", help="只检查, 有 drift 则 exit 1")
    ap.add_argument("--harness-dir", type=Path, default=DEFAULT_HARNESS, help="harness memory 目录")
    ap.add_argument("--repo-dir", type=Path, default=Path(__file__).resolve().parents[1] / "memory")
    args = ap.parse_args()

    repo_dir: Path = args.repo_dir
    harness_dir: Path = args.harness_dir
    if not repo_dir.is_dir():
        print(f"repo memory 目录不存在: {repo_dir}", file=sys.stderr)
        return 2
    if not harness_dir.is_dir():
        print(f"harness memory 目录不存在: {harness_dir} (用 --harness-dir 指定)", file=sys.stderr)
        return 2

    missing, drifted, ok = [], [], 0
    for src, name in repo_copy_nodes(repo_dir):
        dest = harness_dir / f"{name}.md"
        src_bytes = src.read_bytes()
        if not dest.exists():
            missing.append((src, dest))
        elif dest.read_bytes() != src_bytes:
            drifted.append((src, dest))
        else:
            ok += 1

    # 索引父节点是否需要重建(内容变了就算 drift)
    index_stale = []
    for iname, prefixes, type_, desc in INDEX_GROUPS:
        body = build_index_body(repo_dir, prefixes, iname, type_, desc)
        dpath = harness_dir / f"{iname}.md"
        if not dpath.exists() or dpath.read_text(encoding="utf-8") != body:
            index_stale.append((dpath, body))

    print(f"投影节点: {ok} 已同步 / {len(missing)} 缺失 / {len(drifted)} 漂移; "
          f"索引父节点需重建: {len(index_stale)}")
    for _, d in missing:
        print(f"  缺失 -> {d.name}")
    for _, d in drifted:
        print(f"  漂移 -> {d.name}")

    if args.apply:
        for src, dest in missing + drifted:
            dest.write_bytes(src.read_bytes())
        for dpath, body in index_stale:
            dpath.write_text(body, encoding="utf-8")
        print(f"已写入 {len(missing) + len(drifted)} 个节点 + {len(index_stale)} 个索引父节点")

    # MEMORY.md 体积守护
    mem_md = harness_dir / "MEMORY.md"
    if mem_md.exists():
        size = len(mem_md.read_bytes())
        flag = "  ⚠️ 超 24KB 截断线!" if size > MEMORY_MD_LIMIT else ""
        print(f"MEMORY.md: {size} 字节 / 上限 {MEMORY_MD_LIMIT}{flag}")

    has_drift = bool(missing or drifted or index_stale)
    if args.check and has_drift:
        print("DRIFT: repo 有节点未同步到 harness 召回树, 跑 --apply 修复", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
