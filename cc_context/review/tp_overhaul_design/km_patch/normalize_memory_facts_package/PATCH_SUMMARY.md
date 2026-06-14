# normalize_memory_facts patch

目的：把 zmd 记忆树从「投影即原子」增量升级成「抽象事实 + 投影引用事实」。

主要改动：

1. 新增 7 个 `fact_*.md` 抽象事实节点，并同步到 `cc_context/memory/` 与 `_cc_live_memory/`。
2. 在 `MEMORY.md` 顶部新增「抽象事实层」直连覆盖块，避免只挂父索引导致 `MEMORY.md missing N nodes`。
3. 给首批高杠杆 projection 节点补 `> 事实依据: [[fact-*]]` 回指。
4. 修改 `scripts/check_memory_tree.py`：
   - fact 节点必须至少被一个 projection 回指；
   - 新增 feedback/projection 节点若不在 baseline exemption 中，必须引用至少一个 fact；
   - baseline 中已经补了 fact refs 的节点会报红，逼 baseline 只缩不涨；
   - 本机 harness 在场时，调用 repo→harness sync check，把第三投影漂移变成本地 gate。
5. 新增 `cc_context/memory_fact_projection_exemptions.txt`：首轮未迁移的 legacy feedback baseline。后续每迁一条，从这里删一条。
6. 修改 `cc_context/tools/sync_memory_to_harness.py`：
   - `fact_` 进入 repo→harness 投影；
   - 新增 `abstract-facts-index` harness 索引父节点；
   - 自动维护 harness `MEMORY.md` 的 fact 直连覆盖块，并检查 24KiB 上限。

验证：

```text
python3 scripts/check_memory_tree.py --memory-dir cc_context/memory --live-mirror _cc_live_memory --require-live-mirror
# memory graph: nodes=101, links=337, resolved=337, unresolved=0
# memory facts: facts=7, projection_edges=23, baseline_exemptions=40
# MEMORY.md size: 20494/24576 bytes
# live memory mirror: 102 files byte-identical
# memory tree check passed: 101 nodes, index within cap, graph/currency healthy
```

本地 harness 模拟：从材料包 harness 复制后运行 `sync_memory_to_harness.py --apply`，更新后 `MEMORY.md` 为 22735/24576 bytes，仍低于上限。

应用方式（在项目根目录）：

```powershell
# 先确认工作树干净
python scripts\check_memory_tree.py --require-live-mirror

# 应用补丁
patch -p1 < normalize_memory_facts.patch

# 同步第三投影（owner 机器 harness 在场时）
python cc_context\tools\sync_memory_to_harness.py --apply

# 验证
python scripts\check_memory_tree.py --require-live-mirror
python cc_context\tools\sync_memory_to_harness.py --check
```
