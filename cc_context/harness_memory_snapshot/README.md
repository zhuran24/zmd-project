# harness_memory_snapshot — harness 召回树的快照备份

**这是什么**：harness 召回树（`~/.claude/projects/<slug>/memory/`，AI auto-memory 真正自动召回读的那棵树）里 **harness-only 节点**（repo 镜像 `cc_context/memory/` 没有对应文件的，约 47 个：`chatgpt-*` / `cc-*` / `gpt-delivery-*` / `verification-*` / 通用协议 等 AI 自动记的工作经验）的**只读快照备份**。

**为什么存在**（2026-06-14 四路记忆树审查 owner-decision #2/#3，议会 F-A = MEDIUM-HIGH 数据安全）：这些 harness-only 节点此前**不进 git、无远程备份**，`sync --check` 单向也查不到它们，harness 目录一损坏 = **静默永久丢失**，而其中不可重建的踩坑因果经验丢了真丢。本目录给它们：① **数据安全**（git 备份，丢了能恢复）；② **可见性**（干净 clone 也能看到这条项目级 soundness 弧线 + 工作经验）。

**性质（重要）**：
- **纯快照副本，不是正式记忆树**：不进 `sync_memory_to_harness.py`、不参与 auto-memory 召回、`check_memory_tree.py` 不扫它（`DEFAULT_MEMORY_DIR=cc_context/memory`）→ 不引入 wikilink 死链、不改变 by-design 的 harness-only 召回行为。**改记忆请改 harness 正本，不是改这里。**
- **单向 harness→repo，只刷新不反向覆盖**：永不拿快照覆盖 harness（避免当初禁双向 sync 的删数据风险）。
- **刷新**：`python cc_context/tools/snapshot_harness_memory.py`（harness/代码大改后重跑，全离线零 token）。
- **opsec**：只备份节点 `.md` 本身（中性指针）；节点指向的仓库外隔离文件（如 `C:\Users\22957\canary_calibration\`）**绝不进这里**。
