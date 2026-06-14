---
name: zmd-env-pytest-isolation
description: zmd 全量 pytest 必须独占跑——pytest.ini 的 --basetemp=.pytest_tmp 在仓库根, 多 pytest 进程并发会互删临时目录→Windows 随机 FileExistsError/setup ERROR;加速跑法 xdist 8 worker -n8 + 独立 basetemp ~85s
metadata:
  node_type: memory
  type: project
  originSessionId: 01ce64d2-c550-4722-ba4f-1042a3935678
---

- **全量 pytest 必须独占跑**:pytest.ini 配 `--basetemp=.pytest_tmp` 在仓库根,多个 pytest 进程并发(如审查 agent 同时跑测试)会互删对方临时目录 → Windows 上随机出现 FileExistsError / setup ERROR / "顺序依赖失败"假象。跑全量前确认没有并发 agent 在跑测试,必要时先删 `.pytest_tmp`。
- **全量加速跑法(已验证失败集与串行一致)**:`python -m pytest src/tests/ -q -p no:randomly -n 8 --dist loadfile --basetemp="$env:TEMP\zmd_pytest"` —— xdist 8 worker 并行 ~85s(串行 ~7min),独立 basetemp 顺便防并发污染。已写进项目 CLAUDE.md Commands 段。

相关:[[zmd-checkout-env]] [[zmd-env-test-baseline]]
