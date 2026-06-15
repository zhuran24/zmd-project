---
name: zmd-env-test-baseline
index_summary: "全量测试基线=全绿(2026-06-12 wireless 修复 fbb0466 起项目史上首次)0 failed/74 skipped;passed 数以台账 p1_2_closure_evidence.md+handoff stamp 为准;旧 20 个环境失败清单作废,今后任何 failed 都是真问题无豁免"
description: zmd 全量测试基线=全绿(2026-06-12 wireless 修复 fbb0466 起项目史上首次)0 failed/74 skipped;passed 数滚动上涨, 精确值以台账 p1_2_closure_evidence.md 头部与 handoff stamp 为准;旧20个环境失败清单作废, 今后任何 failed 都是真问题无豁免
metadata:
  node_type: memory
  type: project
  originSessionId: 01ce64d2-c550-4722-ba4f-1042a3935678
---

- **全量测试基线 = 全绿 (2026-06-12 wireless 修复 fbb0466 起, 项目史上首次; 当时 2900 passed)**: 0 failed / 74 skipped (xdist ~2min)。**passed 数随修复回归滚动上涨 (06-13 凌晨已 2967), 当前精确值以台账 `cc_context/review/p1_2_closure_evidence.md` 头部与 handoff 最新 stamp 为准, 别引用本条的历史数**。旧「约 20 个环境性失败」清单已作废——根因是工件外置, 现工件回树后全转绿。**今后任何 failed 都是真问题, 没有豁免名单。**

相关:[[zmd-checkout-env]] [[zmd-env-pytest-isolation]]
