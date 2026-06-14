---
name: zmd-env-candidate-placements
description: zmd candidate_placements.json(certified exact 必需输入)已就位且随时可再生——本地 45,773,799B sha adcc2a6e…, 被 .gitignore 防误推 45MB;丢了用 placement_generator.py 现场再生 ~3s;旧 53.6MB/d5e3911f 已 superseded, zmd.7z 老归档带病不可作恢复源
metadata:
  node_type: memory
  type: project
  originSessionId: 01ce64d2-c550-4722-ba4f-1042a3935678
---

- `data/preprocessed/candidate_placements.json`(certified exact 必需输入)**已就位且随时可再生 (2026-06-12 wireless 修复后)**: 本地树有 (45,773,799B, sha `adcc2a6e…`), 被 .gitignore (外置策略持久化, 防 add -A 误推 45MB); 丢了用 `python3.13 src/placement/placement_generator.py` 现场再生 (~3s, 双机验证 bit 级确定性)。**旧 53.6MB/`d5e3911f…` 版本已 superseded**——zmd.7z 老归档里的是带病旧版, 不可作恢复源; campaign resume 撞旧 hash 会 fail-closed (by design)。

相关:[[zmd-checkout-env]]
