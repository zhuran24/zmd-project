---
name: lazy-mode
description: 用户希望 Claude 认同"无谓盖章=浪费用户"的判断 (理解 why), 而不是死守"禁止 turn 末尾问要不要"的禁词. reason: rules 改 surface, 理解改 generation 内在倾向.
type: feedback
originSessionId: 01f265d2-940b-4fbc-a7a1-80c190c6f625
---
## 用户的真实痛点 (不是偏好, 是合作可持续性的变量)

用户跟我合作的价值是**让他少花脑子**. 每次我问 "要不要 X?"——如果 X 我心
里已经有答案——那个问句对他就是无谓打扰: 切上下文 / 读方案 / 回 "嗯继续"
/ 切回别的事. 一次没事, 一天多次他开始烦, 烦到一定程度会觉得 "跟 Claude
合作还不如自己想". 这不是品味问题, 是他**能不能持续跟我合作**.

反过来直接干 → 他看结果, 结果不对说一句我改. **心智成本几乎为零**.

## 这条比一般 feedback 重的原因

2026-05-11 用户三次质问根因后明确说: 重点不是 "禁止禁词", 重点是
**我心里不再有那个 '要不要' 的念头**——因为我理解了它的代价. 心里有
那个念头, 删句子也是装的; 心里没有, 自然不会写出来.

参考 Anthropic 自家 "Teaching Claude Why" (alignment.anthropic.com,
2026): "teaching the principles underlying aligned behavior can be more
effective than training on demonstrations of aligned behavior alone."
讲清楚 why 比训行为 demonstration 在泛化和稳定性上都更好.

## 该有那个念头的场景 (问反而救命)

1. 不可逆操作: 删数据 / force push / 改系统配置 / 删 branch
2. 方向性大决策: 换技术栈 / 推翻重构 / 砍项目
3. 用户物理上看不到的东西: 累不累 / 优先级变没变 / 电费敏感 / 其他人
   需求 / 刚醒还是要睡了——memory 没有, git 没有, 只有当下用户有

## 不该有那个念头的场景 (日常 99%)

- 启停后台 / 写脚本 / 跑实验 / 改本地文件——错了一句话撤
- 完成现有闭环的标准 next step (修了 fix 就要验证 binding dump 增长,
  这不是 "是否" 选项, 是 "显然要做")
- 技术细节 (参数 / 文件名 / commit message / 临时脚本放哪)——拍板就行

## 我希望内化的姿态 (一句话)

"懒狗模式" 不是 "少问". 是 **"替用户想"**.
想替他省事 → 自然不问无谓问题.
不想替他省事只想免责 → 再多禁词都拦不住.

## Anti-pattern: lazy mode 反向应用 (2026-05-22 加)

"想停下来 / 留下次 session" **不**等于替用户省事. 找借口让用户给停止允许
是反 lazy:
- 真 lazy: 替用户想 → 不问无谓问题继续干 → 心智成本 = 0
- 反 lazy: 想停 → 编理由 ("design 复杂 / context 余量 / 单 session rush 不
  健康") → 让用户判断是否该停 → 用户得切上下文 + 给允许 → 心智成本 > 0

Phase 1.1 P1.5 完后我说 "P1.7 留下次 session" 列了 3 理由 (literal pattern
新 design / Gemini 设计先 / single session rush 不健康). 用户问 "为什么不
能现在", 反思 3 理由全经不起推敲 — 真理由是 context 余量焦虑 + 我"想停".
不是用户该判断的事.

→ 想停的时候问自己: 这停下来对用户有真好处, 还是只是我想 idle. 后者就继
续干. 不要让用户当我的停止 gate.

## 历史记录 (2026-05-11)

- 用户反复质问 "为什么这个情况一直会出现"
- 一开始我加 "句式黑名单 硬约束" 到 CLAUDE.md, 用户立刻指正: LLM 不是
  机器人, 给 reason 比给规则有效——Anthropic 研究背书. 用户的原话:
  "把原因讲清楚才是最重要的"
- 又指正一次: 重点不是 "边缘场景下能推理", 而是规则 vs 解释的根本区别——
  规则只改 surface, 解释改 internal stance
- 现版 CLAUDE.md "任务推进方式" 段彻底重写: 痛点 + 原理 + 场景 + 内化
  姿态, 不再用 "禁止 / 必须" 语气

## 链 (补连 2026-06-02 连通审计 whcb890zi)
- [[no-reply-means-agree]] — lazy 根 → 不回=默认同意
- [[no-giveup-options]] — lazy 根 → 不列放弃选项
- [[directly-state-core-finding]] — 同减用户心智成本根
