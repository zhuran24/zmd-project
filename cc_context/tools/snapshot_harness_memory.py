"""单向 harness→repo 快照备份 (owner-decision #2: harness-only 节点无 git/无远程备份的数据安全口子).

harness 召回树 (C:\\Users\\22957\\.claude\\projects\\<slug>\\memory\\) 里有约 46 个 *harness-only* 节点
(chatgpt-* / cc-* / gpt-delivery-* / verification-* / 通用协议 等 AI 自动记的工作经验)——它们 repo 镜像
里没有对应文件, 不进 git / 无远程 / sync --check 也看不见 (单向 repo→harness 同步结构上不查反向). harness
目录一损坏 = 静默永久丢失, 而其中不可重建的踩坑因果经验丢了真丢.

本脚本把这些 harness-only 节点导出到 `cc_context/harness_memory_snapshot/`, 给它们 git 备份 (数据安全) +
干净 clone 可见 (可见性). 性质:
- **纯快照副本, 不是正式记忆树**: 不进 sync、不参与召回、check_memory_tree 不扫它 (DEFAULT_MEMORY_DIR=
  cc_context/memory) → 不引入 wikilink 死链, 不改变 by-design 的 harness-only 召回行为.
- **只增/刷新, 不反向覆盖**: 单向 harness→repo, 永不拿 snapshot 覆盖 harness (避免当初禁双向 sync 的删数据风险).
- **LF 行尾**: 规避 repo 的 LF 行尾政策 gate.
- **opsec 安全**: 只 copy 节点 .md 本身 (中性指针); 节点指向的仓库外隔离文件 (如 canary_calibration/) 绝不碰、绝不进仓库.

判据 = harness 节点的 frontmatter `name` 不在 cc_context/memory 任何节点的 `name` 集合里 = harness-only.

用法: python cc_context/tools/snapshot_harness_memory.py  (代码/记忆大改后重跑刷新快照; 全离线零 token).
"""
from __future__ import annotations

import pathlib
import re

HARNESS = pathlib.Path(
    r"C:\Users\22957\.claude\projects\C--claude-pj-zmd-pj\memory"
)
ROOT = pathlib.Path(__file__).resolve().parents[2]
REPO_MEM = ROOT / "cc_context" / "memory"
SNAPSHOT = ROOT / "cc_context" / "harness_memory_snapshot"

_NAME_RE = re.compile(r"^name:\s*(.+?)\s*$", re.MULTILINE)


def node_name(path: pathlib.Path) -> str | None:
    """从 frontmatter 取 name 字段 (跨树共同 kebab namespace)。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = _NAME_RE.search(text)
    return match.group(1).strip() if match else None


def repo_names() -> set[str]:
    names: set[str] = set()
    for node in REPO_MEM.glob("*.md"):
        if node.name == "MEMORY.md":
            continue
        name = node_name(node)
        if name:
            names.add(name)
    return names


def main() -> int:
    if not HARNESS.is_dir():
        print(f"harness 目录不存在: {HARNESS} (换机时改脚本顶部路径)")
        return 1
    known = repo_names()
    SNAPSHOT.mkdir(exist_ok=True)
    harness_only: list[str] = []
    for node in sorted(HARNESS.glob("*.md")):
        if node.name == "MEMORY.md":
            continue
        name = node_name(node)
        if not name or name in known:
            continue  # 投影类 / 共维护类 repo 已有备份, 跳过
        text = node.read_text(encoding="utf-8")
        (SNAPSHOT / f"{name}.md").write_text(text, encoding="utf-8", newline="\n")
        harness_only.append(name)
    print(f"harness-only 快照: {len(harness_only)} 个节点 → {SNAPSHOT}")
    for name in sorted(harness_only):
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
