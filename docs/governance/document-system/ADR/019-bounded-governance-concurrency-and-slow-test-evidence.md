# DOC-ADR-019｜有界治理并发与慢测实测证据

状态：Accepted
日期：2026-08-15

## 问题

文档治理门包含多个 pytest、静态检查与投影校验 lane。若默认并发过高，多个 Python 测试进程会争用 CPU、内存与文件系统缓存，导致单项耗时被并发噪声放大；反过来，只看整个测试文件的总耗时，又会把许多快速单测误登记为 slow。真实仓库评审要求新增文档测试要么进入集中 slow registry，要么留下可机械检查的实测依据。

## 决定

1. 治理门默认最多并行 4 条 lane；lane 仍使用独立进程和仓外临时目录。
2. landing 对抗回归的 lane timeout 为 300 秒，预算覆盖低速机器上的完整事务，不把测试本身改成写入门。
3. `.docsystem/manifest.json` 保存结构化 `test_timing_receipt`，记录 8 秒 call-phase 阈值、串行命令、被测输入摘要、收集数量、最大 call 耗时和 slow registry 处置。
4. `docctl doctor` 校验 receipt 与当前测试文件字节一致；测试变化后必须重新串行测量，不能沿用旧收据。
5. slow 判定只使用 pytest call phase。文件总耗时、setup 聚合或并发争用不能单独触发 slow 登记。
6. 达到或超过阈值的节点必须出现在 `src/tests/conftest.py::_SLOW_TEST_NODEIDS`；无节点达到阈值时，receipt 必须显式声明 `no_new_entries_required`。

## 后果

- 日常治理门的资源占用有明确上界，测试超时更接近真实缺陷而不是并发风暴。
- 新增文档测试是否需要进入 slow lane 由可复核收据决定，不再依赖“整个文件跑了多久”的直觉。
- 测试文件、慢测 registry 或 receipt 任一方漂移都会由 doctor 或回归测试阻断。
