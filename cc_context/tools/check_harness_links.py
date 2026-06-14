"""本地 harness 召回树链接健康检查 (meta 盲区根治).

四路记忆树审查的 meta 发现: `scripts/check_memory_tree.py` 是 CI gate, 但它 `DEFAULT_MEMORY_DIR=
cc_context/memory` —— **只扫 repo 树, 根本不扫 harness 召回树**。而 harness 才是 AI auto-memory 真正
召回读的那棵树, 它那 ~47 个 harness-only 节点的 wikilink / 死链**此前从没被任何工具检查过**
(codex-cli-as-subagent 的 `[[self-protection]]` 悬空链就是这盲区里冒出来的第一个实例)。

为什么不直接让 check_memory_tree 扫 harness: 它是 CI gate, 而 **CI 环境没有本地 harness 目录**
(harness 在 `~/.claude/projects/<slug>/`), 强制扫会让 CI 必然失败。故 harness 链接检查只能是
**本地工具, 不进自动 gate**; 本脚本复用 check_memory_tree 的解析/检查逻辑, 对 harness 树跑一遍,
harness 不在场 (CI) 时优雅 skip。手动 / 记忆大改后跑。
"""
from __future__ import annotations

import pathlib
import sys

_SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import check_memory_tree as cmt  # noqa: E402  (路径注入后才能 import)

HARNESS = pathlib.Path(
    r"C:\Users\22957\.claude\projects\C--claude-pj-zmd-pj\memory"
)


def main() -> int:
    if not HARNESS.is_dir():
        print(f"harness 目录不在场 (如 CI): {HARNESS} — skip (by design, 见脚本 docstring)")
        return 0
    name_to_path, _path_to_name, errors = cmt._load_memory(HARNESS)
    errors += cmt._check_links(HARNESS, name_to_path, _path_to_name)
    # harness 树的 isolated / MEMORY.md-missing 多为 by-design (索引父结构与 repo 树不同),
    # 这里只硬报「悬空 wikilink」和「重名」这两类真问题。
    hard = [e for e in errors if "unresolved wikilinks" in e or "duplicate memory name" in e]
    if hard:
        print("harness 链接问题 (需修):")
        for line in hard:
            print(f"  {line}")
        return 1
    print(f"harness 链接健康: {len(name_to_path)} 节点, 无悬空 wikilink / 无重名")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
