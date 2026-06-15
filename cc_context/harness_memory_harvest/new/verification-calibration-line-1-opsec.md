---
name: verification-calibration-line-1-opsec
description: "certified 验证加固阶梯第①线「审查校准」(标定 GPT 零 finding 真干净 vs 能力到上限) — 已完成结果良好, 全部细节关在仓库外隔离文件只 Opus 读; owner 2026-06-12 裁决此线默认挂起不主动碰; opsec 铁律绝不进仓库/审查包/记忆树。"
metadata: 
  node_type: memory
  type: project
  originSessionId: d4206461-b836-4607-899b-5e644bbe37f6
---

第①线 = certified soundness 验证加固阶梯里的「审查校准」。背景认识论: 审查只能证有不能证无, GPT 报零 finding 与「reviewer 能力到上限」结果上不可区分 → 不能靠单次零 finding 判闭合。第①线就是标定「GPT 零 finding 可不可信」。

## ① 审查校准 (已完成, 结果良好)
标定「GPT 零 finding 可不可信」。**结果支持把此前那些零 finding 轮判为可信**(不是能力到上限产物); 附带把 2 条测试盲区回归补进真仓库 `test_p0_certified_soundness_fixes.py`。
- **⚠️ 时效 (2026-06-14 标, 非推进本线)**: 上面「零 finding 轮可信」是**截至 2026-06-12 的校准快照**, 不是「P1.2 已闭合」的现状断言。此后逐面续审仍持续抓到 HIGH soundness finding (face2 / preprocess / face8 系列) → 那些零 finding 轮并非真饱和; 本结论是否仍成立以 living 台账 `cc_context/review/p1_2_closure_evidence.md` 为准, owner 在 P1.2 闭合决策时重判。「挂起不主动推进这条线」与「标注这条判断的时效」是两回事, 后者不算推进。
- **⚠️ 这条线的方法/现状/细节刻意不在记忆树展开**——只在隔离文件。
- 全部细节在**隔离文件** `C:\Users\22957\canary_calibration\OPSEC_MODEL_ROUTING.md` (+ 同目录 `GROUND_TRUTH_20260612.md`): 仓库外、不入记忆树、**只 Opus 线程按需读**。
- 还需这类标定的面 = fuzz 写不出独立 oracle 的 (preprocess / binding)。

## 执行约束 (owner 裁决)
**⚠️ owner 2026-06-12 追加裁决: ① 这条线默认完全不碰——不是取消, 是挂起; 不主动排期/展开/派活/提建议, 等 owner 主动提及再恢复。** 任何会话别自作主张推进它。
真欠 ① 标定的面 (preprocess/binding) 留着等 owner 要做时再做; fuzz 能覆盖的面 (routing/master) 已被切片 1/2 兜底, 不需要 ①。

## opsec 铁律
① 那条线的细节**绝不进仓库、绝不入审查包、绝不在记忆树展开** (入包会暴露给 reviewer)。记忆树/仓库 handoff 只放中性短指针, 完整内容关在隔离文件。验收方法论见 [[gpt-delivery-acceptance-discipline]]。
