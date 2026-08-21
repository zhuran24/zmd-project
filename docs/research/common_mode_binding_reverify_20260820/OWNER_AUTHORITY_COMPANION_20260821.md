# I1 owner authority companion（2026-08-21）

> **性质：** 本文件是 2026-08-21 会话 widget 中 owner 显式信号的窄 tracked authority companion。
> **适用范围：** 仅覆盖 I1 范围 A、clean-review 连胜裁量、P1.2 re-close 与 strong-status allowlist 历史 id 处置；不扩张到其他 proof obligation、production promotion、release closure 或 `CERTIFIED` 发布。

## Owner 信号

1. **范围 A：批准。** I1 re-close 前补齐指定 checker 守卫的 mutation 测试，并把全部既定 test anchor 补入强制 `required_tests`；当前范围 A 的守卫与锚点闭合获准作为本次 re-close 输入。
2. **clean-review 连胜：不清零。** 本次 reopen 是 `source_sha256_drift_reopens_p1_2_close_claim` sink mutation policy 的机械后果，不是既有 close claim 的 soundness 缺陷；六轮外部审计没有发现 soundness 破口。因此 owner 以裁量保留 clean-review 连胜，计数继续由 owner 在仓库外维护，仓库不从报告或 receipt 推导计数。
3. **P1.2 re-close：批准。** 六轮外部审计已收敛，第六轮 B 段终判为 `CLEAN_FOR_REOPEN`；owner 批准在最终字节、Stage-B 语义复核与 sealed-authority floor 收口后重新关闭 P1.2。
4. **allowlist 历史 id：永久接受。** `data/proof_obligations/strong_status_write_allowlist.json` 中 id 尾号 `_295` 是历史命名，不是坐标承诺；对应守卫当前实际位于 `src/search/heuristic_feasible_finder.py:309`。checker 对 allowlist 的 SHA-256 与 size 双 pin 以及语义元组/坐标核验不受该命名失真影响。owner 永久接受该 id 形态，不要求重命名。

## Stage-B coordinate-delegate alias 语义复核

复核对象是 `src/tests/cuts/test_stage_b_contracts.py::_coordinate_delegate_alias_use_digest()` 的完整 normalized record 集：

| 项 | HEAD 封印态 | 当前实现态 |
|---|---|---|
| digest | `74297d2e9c7679ffcfb7b8f1ee56d74f19dd5c92ae2bbdca9571056283ad6bbc` | `c0e07e47a43311c4facc7e967ea39b86e66851cc2fec5ab157ba6b7fa31498a4` |
| record 数 | 152 | 152 |
| 删除 / 新增 | 1 / 1 | 同一语句的旧 AST / 新 AST |

唯一变化位于 `src/models/master_model.py::MasterPlacementModel.build_exact_core` 的 `return ExactMasterCore(...)` 语句：

- `coordinate_binding=coordinate_binding` 绑定与消费保持不变；其 `_coordinate_delegate` acquisition、export、alias 名与后续使用均未变化。
- 语句只增加 `generic_output_slots_by_operation=dict(model.generic_output_slots_by_operation)` 与 `utility_operation_by_template=dict(model.utility_operation_by_template)` 两个快照字段。
- 两个字段属于 I1 批内既定的 plan-derived generic-output / utility-operation map 接线；`src/models/master_model.py` 是 ACLOSE 73 sink 重封中已披露的五个变化 sink 之一，相关实现、测试、proof checker 与封印字节已经过六轮外部审计。
- 没有新增 delegate acquisition、one-hop alias、alias-use statement、private backend 调用或 facade 绕行；digest 漂移来自保守封印把整条 constructor statement 纳入 AST，而不是 coordinate-delegate alias dataflow 语义变化。

**复核结论：** 未发现未经审计的语义变化；Stage-B alias-use pin 可重封为 `c0e07e47a43311c4facc7e967ea39b86e66851cc2fec5ab157ba6b7fa31498a4`。

## 审计与收据坐标

六轮外部审计正文位于 `/home/zhuran24/zmd-pj/.artifacts/gpt_harvest_20260818/EXTERNAL_AUDIT_I1_ROUND1_20260820.md` 至 `EXTERNAL_AUDIT_I1_ROUND6_20260820.md`；第六轮定向复核终判位于同目录 `EXTERNAL_AUDIT_I1_ROUND6B_20260820.md`。ACLOSE 初始收据、R6FIX 收据与 re-close 终收据分别位于 `.artifacts/i1_round4_self_check_20260820/ACLOSE_SELF_CHECK_20260820.json`、`ACLOSE_R6FIX_SELF_CHECK_20260820.json` 与 `ACLOSE_CLOSE_RECEIPT_20260821.json`。
