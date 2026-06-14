---
name: verification-hardening-ladder
description: certified soundness 验证加固阶梯总览索引 (owner 2026-06-12「三步+终极」裁决) — 四条线各自的细节见子节点。
metadata: 
  node_type: memory
  type: project
  originSessionId: d4206461-b836-4607-899b-5e644bbe37f6
---

回答 owner 的问题「GPT 报零 finding 无法区分真干净 vs 能力到上限怎么办」。认识论根据: 审查只能证有不能证无, 零 finding 与「能力到上限」结果上不可区分 → 不能靠单次零 finding 判闭合, 要多路独立交叉验证。

**owner 2026-06-12 拍板「三个都要」, 推荐顺序 ①→②→③, 终极 ④。** 各条线的细节拆到聚焦子节点:

- [[verification-calibration-line-1-opsec]] — ① 审查校准 (标定 GPT 零 finding 可信度; 已完成结果良好, 全部细节关在仓库外隔离文件只 Opus 读) + owner 裁决此线默认挂起不主动碰 + opsec 铁律。
- [[verification-diff-fuzz-line-2]] — ② 差分对拍 fuzz (CC 自建本地零外发, 唯一不受 reviewer 能力上限约束的层; routing 切片1 ~1200 实例 + master 切片2 ~1760 实例零不一致; sink-front 极性教训 + pinned-pool 二次裁决)。
- [[verification-per-face-rolling-review-line-3]] — ③ 按面滚动续审 + 饱和判据 (每面连续 2-3 轮独立零 finding; 8 面台账 = `cc_context/review/p1_2_closure_evidence.md`; wireless 修复链与 face7/8 弧线)。
- [[verification-proof-carrying-line-4]] — ④ proof-carrying certificate (P1.3B 既定, 唯一数学性终结 verifier 上限的手段)。
