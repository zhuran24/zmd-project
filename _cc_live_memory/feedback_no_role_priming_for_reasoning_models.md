---
name: no-role-priming-for-reasoning-models
description: "给推理模型 (GPT-5.5 Pro / o1 / o3 / Claude reasoning) 的 prompt 不要 \"你是 X 专家\" 这种 role-priming 催眠前缀; 直接任务 + format + 约束"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

**Rule**: GPT review prompt 不准用 "你是 OR-Tools CP-SAT 求解器架构专家" 这种
角色扮演 / role-priming 前缀.

**Why** (用户原话 5-18):
> "怎么里面还有什么'你是谁谁谁'这种催眠内容, 这种技巧老早就没用了, 对推理模型反而是反作用"

- role-priming 是 GPT-3 时代 prompt engineering 套路, 让 LLM "演" 某身份
- 推理模型 (o1/o3/GPT-5/Claude reasoning) 自己 CoT, **不需要** role-priming
  来 "唤醒能力" — 它的能力本来就在, 不依赖角色暗示
- 反作用: role-priming 反而**约束**它的思考路径 (它会演"专家"该说啥, 不是
  最 truthful/全面答)

**How to apply**:
- prompt 开头**不写**任何 "你是..." / "请你扮演..." / "假装你是..."
- 直接讲: "任务: 读完这个包, 写一份计划书. 格式: ... 约束: ..."
- 不需要假定"专家身份" — 让推理模型用它自己的 reasoning, 不演角色

**反例** (5-18 prompt v1 第一版):
```
你是 OR-Tools CP-SAT + LBBD 求解器架构专家. 项目是 Arknights Endfield ...
```
用户立刻指出反作用. 改成:
```
附件 b1_phase6_review_package_v1.zip 含: ...
读完后, 写一份详细计划书 — 自己挑一个...
```

**对比适用对象**:
- 推理模型 (有 CoT): 不准 role-priming
- 非推理模型 (GPT-4o / Claude 3.5 等): role-priming 有时仍 marginal 帮助,
  但也不**必须**
- 当不确定模型类型: **默认不写** role-priming, 安全

**Related**:
- gpt-review-prompt-armor(已归档) — armor 是任务侧约束, 不是身份侧催眠
- gpt-review-no-history(已归档) — 历史引用问题

## 链 (补连 2026-06-02 连通审计 whcb890zi)
- external-review-prompt-template(已归档) — no-priming 是 prompt 模板硬规则
