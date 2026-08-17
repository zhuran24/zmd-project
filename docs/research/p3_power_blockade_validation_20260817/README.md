# P3 区域供电封锁 family 验证（2026-08-17）

> **状态：** `P3_VALIDATION_COMPLETE_CANDIDATE_STRENGTHENED_NOT_PROMOTED`
> **作用域：** research-only / evidence-only
> **前代候选：** `P1B-BOTTOM-EDGE-5X5-3X2-TILE-BLOCKADE-V1`
> **编译与消费：** 未申请、未实施
> **claim / cut / certified / lower-ledger 效力：** 均无。

## 1. 本批回答的问题

P1b 从一份 33×35 top-right body incumbent 中，把 266 实例 whole-layout 供电 nogood 收缩为 6 个精确姿态，并提出“底边 5×5 六块 3×2 拼块封死下排中间目标全部电杆落点”的 P3/P4 candidate。

P3 不把一次局部核直接送进消费面，而是验证五件事：

1. 可复算 incumbent 中的实际命中频率；
2. 差一块、差一格时，pattern 的真边界；
3. 整体纵向平移与 target tile 换位；
4. 六 literal 在 pose-bool 与 coordinate master 中的忠实表示义务；
5. 5×5 以外，6×4/4×6 是否存在同型局部封锁。

完整本地证据包位于：

```text
.artifacts/p3_power_blockade_validation_20260817/
```

主要入口：

- `REPORT.md`：完整方法、数据和裁断；
- `P3_TERMINAL_RECEIPT.json`：typed 终局；
- `RUN_PROTOCOL.json`：发射前冻结的五线协议；
- `layout_sample_catalog.json`：样本准入、拒绝与去重 provenance；
- `master_literal_translation_audit.json`：双表示只读审计；
- `MANIFEST.json` 与 `SHA256SUMS.txt`：本机证据身份。

## 2. 开工对账

按 `LEDGER_RECONCILIATION_PROTOCOL_V1` 对账：

```text
relation                NO_CURRENT_MATCH
canonical before state  NO_CANONICAL_POWER_BLOCKADE_PATTERN_FAMILY_CLAIM
local before state      ONE_P1B_CANDIDATE_WITH_56_HORIZONTAL_TRANSLATIONS_ONLY
```

current claim 中有九杆下界、conditional halo、restricted pole-domain 负结果等相关上下文，但没有等价或更强的局部六块封锁、近失配边界、target 换位、混合模板或 master-literal 翻译结论。

## 3. Incumbent 小样本频率

冻结路径共发现 42 个文件：P1b 当前 incumbent、AB16、Batch 4 postmem、front-clear lift、W0 fix 和带 body cells 的 band22 strict witness。

准入要求是：至少 266 个 facility bodies；pose 能按当前 pool 复算，或旧 index 可由唯一稳定 pose ID 恢复；custom witness 必须直接携带 body cells；body 不重叠。完全相同的 body layout 只计一次。

结果：

```text
声明文件             42
准入文件             29
拒绝文件             13
唯一准入布局          9
当前唯一布局          1
历史唯一布局          8
命中布局              1
当前命中            1 / 1
历史命中            0 / 8
```

唯一命中的是 P1b incumbent，且同一布局内出现两次：`x=19` 与 `x=24`。这说明当前构造偏好会重复生成该结构，但当前样本只有 1，历史样本也不是随机总体，不能据此宣称 pattern 常见或稀有。

正式判词：

```text
SMALL_CORPUS_CURRENT_1_OF_1_HISTORICAL_0_OF_8
```

## 4. 近失配边界

复算 37 个声明变体：

```text
BLOCKED                 17
EXPOSED                  9
INVALID_BODY_OVERLAP    11
```

删除五个 blocker 中任意一个都会暴露 20 或 25 个合法 coverer，重现 P1b inclusion-minimal 结论。

真正的新边界是：

```text
统一水平缝 0 或 1 格  → 仍 BLOCKED
统一水平缝 2 或 3 格  → EXPOSED
上下排缝 0 或 1 格    → 仍 BLOCKED
上下排缝 2 或 3 格    → EXPOSED
```

左、右、上侧单独增加一格 seam 也仍被封死。因此“无缝 3×2”是充分但不紧的描述，未来 family 语句应允许至多一格局部 seam。

## 5. 纵向平移与 target 换位

复算：

```text
horizontal x      {0,19,55}
lower_y           0..60
target roles      6
cases             1,098
blocked cases        20
```

水平内部 `x=19`：

- 下排中间 target 只在 `lower_y=0,1` 被封；
- 上排中间 target 只在 `lower_y=59,60` 被封；
- 其余四个 target role 全部存在合法 coverer。

贴左边缘时，底边会额外封下左，顶边会额外封上左；贴右边缘时出现对称结果。

因此该机制的承重条件不是“六块包围目标”，而是：

```text
局部 body 壳 + 水平网格边界
```

离开上下边界后，原六块 pattern 不再成立。

## 6. 双 master literal 翻译审计

审计只做 representability 查询，没有调用 cut attach。

P1b 六个精确姿态在 pose-bool 中各对应一个：

```text
x_vars[(mandatory_group, pose_idx)]
```

在 coordinate master 中各对应：

```text
OR(该 mandatory group 的任一 symmetric slot 实现 pose_tuple)
```

规范化后，两边都是同一组六个：

```text
(group_id, pose_idx)
```

查询前后，两种 model proto 的 SHA、大小、变量数和约束数完全不变；错误 instance 与错误 pose 都 fail closed；六项没有 alias。

最重要的语义纪律是：mandatory instance name 只用于找到 symmetric group，不是稳定 literal 身份。未来谓词必须陈述为“六个 group-pose presence 事件不能同时成立”，不能把 P1b 的具名 owner 当成执行语义。

13 条义务中：

```text
已关闭  8
开放    5
```

开放项包括：正式 instance-name nonidentity 合同、编译 reject-set 对 trigger-set 的包含／等价、独立 proto replay、实际 invalidation 接线和 owner attach 权限。

当前判词：

```text
READ_ONLY_AUDIT_PASS_WITH_OPEN_COMPILATION_OBLIGATIONS
```

不是“已可编译”。

## 7. 6×4 / 4×6 混合模板

有限探针使用冻结 candidate pool 中真实存在的 solid pose。目标与 blocker 形状包括：

```text
5×5, 6×4, 4×6
```

目标位于底边 `y=1`，分别测试左边缘、内部和右边缘；blocker 必须互不重叠，封住全部 target coverers，并至少含一个非 5×5 姿态。

结果：

```text
probe cases                          9
MIXED_EXTENSION_CANDIDATE            7
TARGET_GEOMETRY_ABSENT_FROM_POOL      2
```

两项 `N/A` 是 4×6 target 在左右极边缘没有冻结 pose，不是无解。

七个候选均为有限探针中的最优解：边缘目标通常需要 3 个 blocker，内部目标通常需要 5 个；全部包含 6×4/4×6 body，留下 0 个未封 coverer。

这足以说明 5×5 不是该几何机制的唯一模板，但不证明这些局部 body 可以在完整 266 实例布局中同时出现，也不验证 ports、binding、routing 或 full verifier。

## 8. 总结与候选重构

P3 结果支持把未来 family 分成三类，而不是直接编译 P1b 原句：

1. `HORIZONTAL-BOUNDARY-MIDDLE-TARGET-SHELL`：上下边界、中间 target、允许一格 seam；
2. `CORNER-TARGET-SHELL`：同时贴水平与左右边界时的角 target；
3. `MIXED-RECTANGULAR-BODY-SHELL`：5×5、6×4、4×6 的局部 coverer-blocking set。

当前 typed 终局：

```text
status                    P3_VALIDATION_COMPLETE_CANDIDATE_STRENGTHENED_NOT_PROMOTED
current claim created     false
production cut created    false
lowering implemented      false
certified effect          false
canonical ledger write    false
owner gate                CLOSED
```

下一步若继续，应从三类中选择一条最窄、最有 production incidence 的语句，补独立 checker 和 holdout corpus，再另行请求 owner-gated lowering canary。本 dossier 不申请、不实现该步骤。

## 9. 明确不推出

本批不推出：

- P1b pattern 在 production 中常见或罕见；
- 任一完整锚点、尺寸或 score band 不可行；
- mixed local candidates 能嵌入完整布局；
- pose-bool/coordinate representability 等于 cut soundness；
- candidate 已成为 claim、cut、theorem 或 certified evidence；
- canonical lower bound、exact-status 或 stable claim ledger 有任何变化。

## 10. 本地证据身份

```text
.artifacts/p3_power_blockade_validation_20260817/MANIFEST.json
SHA-256 e535433d738ae75c5053906ea10cbc4a1a8dd361dc73c615c55de6d731b48c67

.artifacts/p3_power_blockade_validation_20260817/SHA256SUMS.txt
SHA-256 df7935bec42cd9e4996c2b23c2f6c11a3508b5b1cc66cf057728236796053665
```

本地 payload 可在轻量 checkout 缺失；恢复后必须按 manifest 与 SHA 清单复核。文件存在与 checker PASS 均不授予 claim、cut、production 或 certified authority。
