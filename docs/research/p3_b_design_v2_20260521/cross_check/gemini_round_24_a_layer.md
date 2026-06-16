这是一份针对 B Design v2 Phase 0 收尾与 A 集成层 (Day 18-21) 的 Round 24 Cross-Check 报告。

总体评价：**理论大厦已经完美竣工，但在将数学 Spec 转化为工程 Plan 和 Exit Criteria 时，存在几个“工程与理论的摩擦点”（特别是 RAM 计算、过期策略矛盾和目录结构脱节）。**

以下是详细的 A/B/C/D 审查报告：

### 任务 A: 验 A1 8 exit criteria 设计 sound

8 条 Criteria 的大方向非常精准，但存在 **2 个漏测项** 和 **1 个危险的数学计算错误**：

1. **[漏测项] 缺失 F8/F9 的硬性 Synthetic Test 门禁**：
   - 脚本中 `#2` 和 `#3` 只 hardcode 检查了 F3 (port_exposure) 和 F7 (power_hitting_set)。
   - **风险**：F8 的 Liang-Barsky 严格 AABB 裁剪和 F9 的 Area-based 面积积分，是整个框架中最复杂、最容易写出 False Positive/Negative 的几何算法。
   - **修正**：必须增加 `#2b` 和 `#3b`，强制要求 `test_family_8_power_grid_reach.py` 和 `test_family_9_density_envelope.py` 必须存在且 PASS。
2. **[数学错误] 12GB/worker 的 RAM 阈值会导致 168h 跑崩**：
   - 脚本 `#6` 规定 `cut_store_peak_mb < 12288 (12 GB)`，而 A3 Plan R2 写的是 `12 GB/worker`。
   - **风险**：单机总 RAM 是 48 GB。CP-SAT Master 进程和 OS 至少需要占用 16 GB。如果开启 4 个 Worker 进程，`12 GB * 4 = 48 GB`，加上 Master 的内存，**绝对会引发 OOM (Out of Memory) 导致 168h Campaign 崩溃**。
   - **修正**：`pass_condition` 必须改为全局视角（例如 `Total Cut Store < 20 GB`），或者将单 Worker 阈值压低到 `< 5 GB/worker`。
3. **[漏测项] 缺失对 Disk Rotation / GC 的机制测试**：
   - 既然 168h 必然面临磁盘/内存压力，Cut Store 的 Rotation (轮转/清理) 是保命机制。Exit Criteria 应该加一条验证 Rotation 逻辑本身没有 Bug 的测试（例如 `test_cut_store_rotation.py` PASS）。

### 任务 B: 验 A2 PROJECT_LOCK update 完备性

PROJECT_LOCK 的更新非常严密，但我发现了一个 **A2 (Lock) 与 A3 (Plan) 之间的严重规则冲突**，以及一个关键的防退化遗漏：

1. **[严重冲突] Step 10 Expiry 豁免权矛盾**：
   - **A2 §4 规定**："Step 10 dominance/expiry/demotion defer to Phase 2"（严禁在 Phase 1 实施 Cut 过期或降级）。
   - **A3 R2 规划**："P1.21 加 disk quota + rotation"。
   - **冲突**：如果 Rotation 机制为了保内存而删除了 Active Cut，这在定义上就是 **Expiry (过期)**！这会直接违反 Lock。
   - **修正**：必须在 A2 §4 中明确写出豁免条款："允许基于系统容量上限的 LRU/FIFO 驱逐 (Capacity-based Eviction) 以防止 OOM，这属于工程兜底，不属于语义上的 Step 10 Expiry"。
2. **[防退化遗漏] F9 的 Area-based 计数必须入 Lock**：
   - A2 §3A 提到了 "F9 paradigm 降级 lock" (只允许面积溢出触发)，但这不够。
   - **修正**：必须在 §3A 中补充："F9 必须使用 Area-based counting (sum of cells) 而非 instance counting"。这是我们在 Round 20 极其艰难才发现的 False Negative 漏洞，必须焊死在 Lock 里，防止未来代码重构时退化。

### 任务 C: 验 A3 Phase 1 plan 工程可行性

工程排期整体合理，但依赖图和风险评估有微调空间：

1. **[依赖图微调] Liang-Barsky 算法的排期**：
   - P1.14 (F8) 强依赖 `ghost_geometry.py` 中的 Liang-Barsky 算法。但在 P1.4 的 Framework helpers 规划中，没有明确标出这个文件的开发。建议在 P1.4 明确加入 `ghost_geometry.py`，以彻底解除 P1.14 的前置阻塞。
2. **[漏估风险] F9 QuickXplain 的耗时爆炸**：
   - P1.15 (F9) 提到要对 Window 进行 minimize。QuickXplain 需要反复调用 Sub-problem Oracle。如果 Oracle 是 Routing，耗时极大。
   - **修正**：在 §5 风险中加入 "R6: F9 QuickXplain 耗时爆炸"。缓解措施："Phase 1 允许直接使用 Bounding Rect 作为 Window (Fallback)，不强制要求 Minimize"。
3. **[实施顺序优化] 解耦算法 Bug 与 IO Bug**：
   - 当前计划在 P1.21 就上 Disk Persist (持久化)，然后 P1.22 才做 5-inst Smoke Test。
   - **建议**：将 5-inst Smoke Test 提前到 P1.20。先在**纯内存**环境下跑通 9 大 Family 的数学逻辑，证明算法没 Bug，然后再上 Disk IO 和 Rotation。这样排查 Bug 时能明确区分是“数学写错了”还是“文件读写错了”。

### 任务 D: 跨 A1+A2+A3 一致性 + 找 sound bug

在交叉对比三份文件时，发现了一个**目录结构脱节**的 Bug：

1. **[目录结构不一致] 导致 Criterion #8 误判**：
   - **A3 P1.21 和 R2** 明确说明了 Cut Store 会采用 "active vs quarantine 分目录" 的结构。
   - **A1 脚本** 在 `check_8_persisted_cuts_replay` 函数中，依然使用的是 `cuts_dir.glob("*.json")` 进行平铺目录的查找。
   - **后果**：如果 Phase 1 严格按 A3 实现了子目录，A1 的脚本会找不到任何 Cut 文件，导致 Criterion #8 永远卡在 PENDING 或 FAIL。
   - **修正**：A1 脚本需要更新，显式遍历 `data/cuts/active/*.json` 和 `data/cuts/quarantine/*.json`。
2. **[Fail-closed 语义对齐]**：
   - A2 §4 规定了 "未知 assumption -> fail-closed (HOLD)"。A1 脚本目前的 JSON Schema 检查是占位符，建议在脚本注释中明确：未来补全 6 步 Verify 测试时，必须验证 "未知 Assumption 导致 HOLD，且该 Cut 不会被错误地转入 QUARANTINE 目录"。

---
**总结**：
A 集成层的设计在宏观上是**无懈可击**的，完美承接了 Phase 0 的所有数学共识。只要在正式写代码前，修复上述的 **RAM 乘法计算、Expiry 豁免权冲突以及目录 glob 路径** 这几个工程细节，就可以毫无后顾之忧地启动 Phase 1 编码了！