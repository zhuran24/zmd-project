# Phase 1.1 最终检查与修复报告

**结论：Phase 1.1 可以正式通过，进入 Phase 1.2。**

这次检查没有只看“测试绿不绿”，而是重点看了 1.1 里容易漏的小洞：cut 证书是否可被篡改、source_digest 是否会被旧值骗过、store 状态机是否能被误激活、watcher 索引是否会被外部改坏、F1/F2 的 payload 解析是否太宽松、可选 solver 缺依赖时会不会拖垮全仓 collection，以及文档和门禁脚本是否还写着旧状态。

## 已修复的问题

1. **source_digest 不再信外部手写值。**  
   之前 `BState.source_digest` 如果被写成旧值，可能遮住真实 source 变化。现在 replay 会按当前注入的 source 重新计算，旧缓存不能绕过检查。

2. **cut 证书加了完整性检查。**  
   新增 `validate_cut_integrity()`，反序列化和 replay 前都会检查 `cert_payload` hash、`oracle_cert_hash`、以及 geometric payload 和 cert payload 是否一致。坏 cut 会直接拒绝或 quarantine。

3. **Cut 运行时 schema 加严。**  
   空 `cut_id`、非 tuple literals、非 bytes payload、坏 cert、literal 里 bool/float/string slot、非字符串 pose_id、坏 `minimization_audit` 都会 fail-closed。

4. **CutStore 状态机补洞。**  
   不存在的 cut 不能 reactivate；已经 quarantined 的 cut 也不能重新激活。

5. **watcher 查询不再暴露内部集合。**  
   `cuts_affected_by_*()` 返回副本，外部 `.clear()` 不会破坏内部 watcher index。

6. **F2 cutset 的 free cells 修正。**  
   现在会排除 `exterior_blocks`，不再允许路线穿过静态外部阻挡。

7. **F1/F2 payload 解析加严。**  
   bitset 现在要求合法 base64、长度正确、额外高位不能置位；route/cut_edges cell 不再用宽松 `int(...)` 转换，bool、float、越界值都会失败。

8. **可选 solver 测试不再卡全仓。**  
   HiGHS / SCIP 缺依赖时正常 skip，不会 collection error，也不会因为“没有测试可跑”导致失败。

9. **退出门禁脚本修正旧文件名。**  
   `test_family_3_port_exposure.py` 改为 `test_family_port_exposure.py`；`test_replay_suite.py` 改为 `test_replay.py`。Criterion 1/2/4 已通过。

10. **文档状态对齐。**  
    README 和 `docs/项目说明` 已更新：cuts 测试数从 178 对齐到 181；source_digest 不再写成 placeholder / Phase 1.2 待办；strict gate 当前默认已 ON。

## 验证结果

| 检查项 | 结果 |
|---|---|
| `pytest src/tests/cuts/ -q` | 181 passed |
| `python -O -m pytest src/tests/cuts/ -q` | 181 passed，1 个 pytest warning，来自 `python -O` 下 pytest 对 assert 的正常提醒 |
| optional HiGHS/SCIP tests | 14 skipped，退出码 0 |
| `ruff check ...` | All checks passed |
| `mypy --strict --explicit-package-bases src/cuts/` | Success，22 个 source files 无错误 |
| `vulture ...` | 无输出，未发现当前阈值下的死代码 |
| `bandit -q -r src/cuts/` | 无输出，未发现安全扫描问题 |
| `radon cc src/cuts/ -s -a` | Average complexity A |
| `scripts/b_design_v2_exit_criteria.py --criterion 1 2 4 --json` | 1/2/4 全 PASS |
| `patch -p1 --dry-run` | 在原始项目副本上 clean，无冲突 |

说明：我没有把“全仓 2492 个 pytest 全量执行完成”写成结论；全仓 full run 量比较大，不适合在这次交付里强行宣称。当前结论基于 1.1 相关门禁、静态检查、安全扫描、复杂度扫描、可选依赖边界和补丁 dry-run。

## 应用方式

在原始项目根目录执行：

```bash
patch -p1 < phase1_1_final_gate_fixes.patch
```

也可以直接使用交付包里的 `overlay/` 目录，把文件覆盖到项目根目录。

## 本次变更文件

共 25 个文件。完整列表见 `changed_files.txt`。
