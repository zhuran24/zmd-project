---
name: gpt-delivery-no-blind-trust
description: "外发 GPT Pro 拿回的补丁/审查交付绝不能按 GPT 自验摘要直接采信——GPT 只跑 targeted 看不到端到端、补丁自身常带 bug、probe 可能不判别、probe 常硬编码 Linux 路径;附标准验收链(reviewer probe 复现→git apply→patched probe 转拒→独占全量 xdist→preflight_gate 必全绿→修连带→推锚仪式→commit)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 20690dc4-0860-4f42-a5a5-e1cccbd7b8d7
---

外发 GPT Pro 拿回的补丁/审查交付**绝不能按 GPT 的自验摘要直接采信**。zmd 过夜审查循环(2026-06-11,V81→V98 共 18 轮)实测教训:

**Why(每条都真实踩过):**
- **GPT 自验只跑 targeted 测试,永远看不到端到端**。多轮 GPT 补丁通过它自己的 probe/targeted pytest,却**直接弄崩真实 solver 路径**(V88:ghost_pick 注入 solution 后 5 个下游消费点把它当设施查池 KeyError;V97/V98:wrapper 预 resolve 洗掉 symlink alias)。GPT 不跑全量(它那边 candidate_placements 外置)。
- **GPT 补丁自身常带 bug**:函数错位赋值(V92 frontdoor)、死变量 ruff F841、mypy None 类型、重复 JSON 键、ghost_pick 误计占用会拒所有真实 terminal(V83/V84)、最优性扫描没 gate mandatory 非空(V84)。
- **probe 可能不判别**:V97 我的本地 toy 用 INFEASIBLE 场景,根本不走 CERTIFIED 的权威路径,patched/unpatched 返回同样结果——**probe 不判别就换手段**:`git stash push <补丁动的 src 文件>` 跑 reviewer 回归确认 unpatched FAIL、pop 后 patched PASS,才坐实 finding 真实+补丁有效。
- **GPT probe 常硬编码 Linux 路径**(`/mnt/data`),在 Windows 崩在 print/relative_to 行——但核心逻辑在崩之前已执行,看崩之前的输出或改用本地路径重写。

**How to apply(标准验收链,缺一不可):**
1. 先跑 reviewer 的 probe(original)本地复现 finding——不判别就 stash 对比;
2. `git apply`(注意 -p1/-p2 层级,补丁前缀可能带 `project/`;各级 `--check` 都报 "does not apply" 且上下文逐行肉眼核对一致时 = 纯空白差异,先核对再 `--ignore-whitespace` 贴 [06-13 gm_r8 实测],贴完靠测试+ruff 兜底);
3. patched probe 转拒;
4. **独占全量 xdist** 对照环境性基线(candidate_placements 外置那 10F+10E,多一个都要查连带);
5. **`python scripts/preflight_gate.py --ci --base-ref HEAD~1` 必全绿**(当前 17 项 [1/17]..[17/17], 随门禁增减以脚本实时编号为准——别记死旧的 20/20; pytest 盖不到 frozen hash/LF 行尾/记忆树死链/ruff/mypy);
6. 逐个修连带(协议变更类如 anchor 必填会牵 ~20-30 个 mock);
7. 推锚仪式齐(见 [[zmd-project-entry]] 指向的 handoff 易漏点清单)→ commit。

**关键心态**:GPT 找洞能力强、写补丁会埋雷;CC 的价值在"复现判别 + 端到端验收 + 连带收尾",不是橡皮图章。验收基线注意: 2026-06-12 fbb0466 起全量 = **全绿** (旧 10F+10E 环境性豁免作废, 见 [[zmd-checkout-env]])。关联 [[no-workflow-use-chrome-gpt-review]]。

细分主题见: [[gpt-delivery-probe-discrimination]]、[[gpt-delivery-completeness-semantic-consumers]]、[[gpt-delivery-archive-ruff]]、[[gpt-delivery-owner-patch-and-severity]]、[[gpt-delivery-dont-track-model-downgrade]]、[[gpt-delivery-adversarial-agent-review]]。
