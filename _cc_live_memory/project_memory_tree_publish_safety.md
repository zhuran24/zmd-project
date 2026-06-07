---
name: memory-tree-publish-safety
metadata:
  node_type: memory
  type: project
  originSessionId: gpt-5.5-pro-handoff-20260606
---

2026-06-06 GPT-5.5 Pro 接手后补强记忆树的 publish-safety / currentness gate。

## 当前判定

记忆树的 wikilink 图本身是健康的：所有节点被 `MEMORY.md` 覆盖、无 unresolved link、无孤点。但它原本有三条不适合 GitHub 发布和长期交接的尾巴：

1. Gemini API key 曾以明文进入 tracked scripts 与 memory。
2. `stamp_living_status.py` 默认写外部 CC live path，不是 repo-native；干净 clone / 沙盒 / Codex 不能可靠检查 INSTANCE 槽。
3. preflight 没有检查 memory graph、INSTANCE drift、`MEMORY.md` 尾部容量、repo secret、live mirror byte drift。

## 已落的结构补强

- `scripts/check_repo_secrets.py`：扫描当前 tracked/untracked 工作树中的 Gemini/OpenAI/GitHub/private-key pattern。它只保证当前树不再带 secret；Git 历史和已外发 review 包里的旧 key 仍需 owner 侧轮换/吊销。
- `scripts/check_memory_tree.py`：检查 frontmatter name 唯一、wikilink 全解析、无孤点、`MEMORY.md` 覆盖全节点、INSTANCE 槽同步、索引大小低于 24 KiB 级阈值；若外层 `_cc_live_memory/` 存在，则要求它与 repo mirror 字节一致。
- `cc_context/tools/stamp_living_status.py`：默认 memory dir 改为 `cc_context/memory`，支持 `--check/--sync/--memory-dir`。现在 INSTANCE/projection 模型能在 repo clone 中被机器验证。
- `scripts/preflight_gate.py`：接入 secret scan 与 memory tree health，文档树和记忆树都进入同一提交门禁。

## 当前操作规则

- 运行 Gemini cross-check scripts 前只设置本机环境变量 `GEMINI_API_KEY`；不要把 key 写进 repo、memory、review package 或 GitHub issue/PR。
- 结构性 memory 改动后运行：

```bash
python cc_context/tools/stamp_living_status.py --sync
python scripts/check_memory_tree.py
python scripts/check_repo_secrets.py
python scripts/preflight_gate.py
```

- 如果从带外层 live mirror 的观察点包工作，改完 repo memory 后同步 `_cc_live_memory/`，否则 `check_memory_tree.py` 会报告 byte drift。
- `MEMORY.md` 仍要控制体积；新增条目前先压缩旧描述，不要让索引尾部重新掉出上下文。

## 边界

这次补强不重写 Git 历史，也不声称已经推 GitHub。GitHub 上传走 `zmd-gh-upload-bundle/v1`，由本地 Codex 校验、应用 patch、测试、commit、push/PR。用户已确认旧 Gemini key 已经过期；代码侧仍必须保持 current tree / review package secret=0, 不把任何新 key 写回 repo 或 memory。

关联：[[memory-currency-protocol]]、[[memory-tree-structural-health]]、[[github-backup]]、[[gemini-math-consultant]]。
