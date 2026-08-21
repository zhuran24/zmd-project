# e73add1 baseline attribution and masked-real replay

日期：2026-08-20

## 结论先行

第一版把同 HEAD 轻量 worktree 中的 `38 failures / 34 errors` 写成“零遗漏归因”，这是错误的。该矩阵只证明 baseline/current 在相同的早期失败点同时终止，不能证明被缺失工件遮住的后续行为相同。

第二轮外部异源审计读取原始机器收据
[`MASKED_REAL_DIFF_20260820.json`](MASKED_REAL_DIFF_20260820.json) 后确认：

```text
outcome_changes             14
baseline_pass_current_fail  14
```

14 条全部位于 `src/tests/test_binding.py`，属于本批新增 plan snapshot 要求未同步到 stale test doubles 的同一缺陷类。原收据如实保留，不覆盖、不改写，也不再被叙述成零分叉。

修复 14 条 stale doubles 后，使用同一真实 54 MiB candidate artifact 对原 47 个被遮 nodeid 重新进行 baseline/current 差分。修后机器收据为：

```text
docs/research/common_mode_binding_reverify_20260820/
MASKED_REAL_DIFF_POSTFIX_20260820.json
```

该收据必须由最终冻结字节重新生成。它的通过条件是：

```text
requested_nodeids           47
baseline                    47 passed
current                     47 passed
outcome_changes              0
baseline_pass_current_fail   0
temporary_artifacts_removed true
```

因此，正确结论不是“早期同红所以没有回归”，而是“在真实工件接入后，原 47 个被遮 nodeid 逐条执行到终点，修后 baseline/current outcome 相同”。

## 轻量 checkout 初始矩阵

对照树：

```text
baseline /home/zhuran24/.devspace/worktrees/zmd-pj-18f7c8f3
current  /home/zhuran24/.devspace/worktrees/zmd-pj-4dfe6504
HEAD     e73add14a286ddce16b217f8d2df3a1fcf0fea21
```

两边以相同 Python、相同 nodeid、独立 basetemp 和 pycache 运行 non-slow `src/tests`。收集面：

| 集合 | nodeids |
|---|---:|
| baseline | 7,522 |
| current | 7,551 |
| 共同 | 7,521 |
| baseline-only | 1 |
| current-only | 30 |

干净 baseline 在轻量 checkout 上得到：

```text
38 failures / 34 errors
```

它们的**最先暴露失败点**如下：

| 早期失败点 | failures | errors | 说明 |
|---|---:|---:|---|
| 缺 `candidate_placements.json` | 31 | 16 | 47 个 nodeid 在工件读取处提前终止；此桶在接入工件前是差分盲区 |
| R4 handoff Python identity 不合 | 0 | 18 | worktree-local Python identity 与共享主仓解释器不合 |
| R4 缺 worktree `.venv` | 1 | 0 | 本地固定解释器路径不存在 |
| 缺 `ghost_strict_fix_20260805` 本机历史 evidence | 4 | 0 | local-optional history 不在轻量树中 |
| 缺 `.venv-uvbolt-backup` | 1 | 0 | 固定 Python 备份路径不存在 |
| baseline `docs/CATALOG.md` 陈旧 | 1 | 0 | baseline 自身生成投影漂移 |
| **合计** | **38** | **34** | 仅表示最先失败点，不表示后续行为已归因 |

后五桶可直接由报错本身归因；第一个 47-node 桶必须接入真实工件后重放，不能从“baseline/current 同样 FileNotFoundError”推断后续一致。

## 原始 14 条分叉

第二轮外审使用真实 candidate artifact 让 47 个 nodeid 穿过读取边界。原始修复前收据记录：

```text
outcome_changes             14
baseline_pass_current_fail  14
```

共同根因是 production binding snapshot 合同增长后，`test_binding.py` 的多个 controller/model doubles 没有同步完整的：

```text
generic_input_slots_by_operation
generic_output_slots_by_operation
utility_operation_by_template
```

这不是环境失败，而是本批回归。它们已逐条补齐，并由修后 47-node 真差分验证。

## 修后真实工件差分方法

真实工件只从主仓读取：

```text
path   /home/zhuran24/zmd-pj/data/preprocessed/candidate_placements.json
size   54,467,709 bytes
sha256 f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3
```

重放程序从原始收据提取精确 47 个 nodeid，将该工件作为只读普通文件临时复制到 baseline/current 两棵 worktree，分别运行相同 nodeid，然后比较逐 testcase outcome。无论成功或异常，`finally` 都会删除两个临时副本；收据记录 `temporary_artifacts_removed`。

这里不用 symlink，因为部分仓内 contract 会把 symlink 视为不同的 authority surface；也不修改主仓工件。

## 测试口径

仓库默认 `pytest.ini` 的 `testpaths` 是 `src/tests`。因此“non-slow suite”只指 `src/tests`，不自动覆盖：

```text
devtools/tests
certside 的 Windows→WSL 全链 harness
历史 local-optional .artifacts replay
```

本批对修改过的 `devtools/tests`、sidecar emitter/checker/parity 和文档治理另行执行定向测试与 gate；不能把它们折叠进“全量 pytest”四个字。

## 治理边界

本页只修正测试归因方法和结果。它不改变以下事实：

- 两条 sealed-authority parity 测试必须保持红；
- draft `p1_2_proof_obligations.json` 自洽不等于 P1.2 已 re-close；
- 外部第三轮审计与 owner re-close 尚未完成；
- 本批未 commit，未修改主仓或 `data/review_gates/**`。
