---
name: keep-review-process-light
description: 不要给每个 patch 都套外部审查流程；preflight gate + 自主审查已够用
type: feedback
originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---
终末地项目不要给每个小 patch 都套"strategy → external review → readiness → review tooling → execute → reviewer reply"这种 6 步循环，**preflight gate + Claude 自主语义审查已经覆盖大部分场景**，只有真正改证明等价性、动 frozen artifacts、新增对求解器架构的根本改动时才需要重型流程。

**Why:** Codex 时代每个 S 步骤（哪怕只改 1-2 行）都要走完整的外部审查流程：打包 review zip → 上传 ChatGPT 终末地 → DOM 验证 source 行 → 等 reviewer reply → 提取 → 本地 readiness → 再打包 review tooling → 又一次上传 ChatGPT → 等审查 → 最后才能改 1 行代码。这种流程是因为**当时没有可信的本地 gate**——只有人类外部 reviewer 能背书"代码改动安全"。Claude Code 已经有 `scripts/preflight_gate.py` 自动跑 5 项检查（frozen hash、禁止路径、AI 安全合同、边界隔离、核心测试），加上 Claude 自己能做语义审查，外部审查的频率应该大幅下降。Codex 那段流程开销 50% 时间花在 ChatGPT UI 自动化（DOM 点击、坐标校准如 `1905,780` vs `1905,850`）上，得不偿失。

**How to apply:**
- 默认走：写 patch → 跑 pytest 核心门禁 → preflight gate → commit
- 只有以下情况才考虑外部审查（/ultrareview）：
  - 修改 frozen artifacts（4 个 canonical 数据文件）
  - 改证明源头（master_model 核心 constraint 逻辑）
  - 引入新求解器或 swap 求解器架构（D/D' 方案）
  - 在 lock 名单里的状态变更（runtime_enablement_allowed 等）
  - 用户每天早上的 ultrareview 节奏（被授权的）
- 一般的 hint 调优、调度策略、AI sidecar 改动、tuning runner 改动**不需要**外部审查
- 如果发现自己在写 review 文档/上传 review 包，先停下问"这件事真的需要外部审查吗"

## 链 (补连 2026-06-01)
- [[autopilot-with-review-gate]] — autopilot 审查闸
