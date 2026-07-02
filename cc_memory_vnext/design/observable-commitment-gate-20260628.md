# 可观测提交点记忆闸(Observable-Commitment Memory Gate)— ③ 的真地基

> 日期:2026-06-28。
> 来源:owner 把本会话的 `recall-trigger-discussion-20260628.md`(③ 六代理讨论)喂给 ChatGPT,得到一份更准的 reframe;原文已搬进仓库 `design/chatgpt-observable-commitment-gate-source-20260628.md`。
> 地位:**这份【取代/修正】③ 讨论的 framing。** ③ 那场六代理大会摸到的是侧面(第四档"看守");本份是 ③ 真正的地基。本会话(memory-update 回合)把它钉成 canonical 记录,防它又被压缩丢掉。

---

## 0. 一句话

③ 的真问题不是"系统自动把卡推给我"(我 ③ 收敛到的"看守"=push),而是"**怎么逼模型在该查的时候真去查**"(带门的 pull)。解法不是再加 hook,是把系统从"希望模型记得去图书馆"改成"**出门前必须过借阅闸机**"——**没有记忆查找证明(ZMEM_PROOF),就不准把想法变成动作/结论。**

## 1. owner 的纠正(我 ③ 跑偏的根本点)

- 我 ③ 整场做成了"系统替我看、把卡 push 给我"。
- owner 要的是"**让模型【该查的时候真去查】**"——域图(覆盖域图)告诉模型"哪里有记忆",但"模型知道了也不会主动去查"。真缺的不是 Domain Atlas,是 **Memory Lookup Reflex(查记忆反射层)**:不是"记忆覆盖哪些域",而是"**哪些认知动作必须查记忆**"。

## 2. 物理边界(owner turn-7 钉死,ChatGPT turn-8 认了)

hook 只有 3 个触发面:① 用户提示词 ② 模型输出 ③ 工具调用(分"发命令"和"返结果"两条)。**隐藏思考(thought)钩不到**;`additionalContext` 在下一次模型请求才读到,塞不进正在跑的那段 thought。→ "念头那一刻弹卡"在现有 hook 下**物理无解**。

## 3. 三个目标,三个解(别混,一混就继续在雾地基上砌砖)

| 目标 | 解 |
|---|---|
| **(a) 念头那一刻记忆立刻出现** | **无解**(钩不到隐藏思考)。只能:高频高杀伤卡进 L0 常驻;稀有具体卡降 manual/offline、**不准算进自动召回保证** |
| **(b) 没查过的想法不准变成动作/结论** | **可解 = 提交点闸门**(当前 hook 就能建)。← 近期键石 |
| **(c) 推理中途多次及时查** | 要**改 agent loop**(Intent-First Active Memory Loop:把隐藏长推理切成"先外露 next-intent → 系统查 → 再走一小段"的可观测短步)。大改、未来 |

## 4. 可落地的硬货:Observable-Commitment Gate + ZMEM_PROOF

- `zmem search` 成功就吐一枚短证明 token:`ZMEM_PROOF session=.. turn=.. domains=.. hash=..`,自然留在 transcript。
- **闸不猜"模型查没查",而是查 transcript 里有没有对应 proof**:
  - **PreToolUse 闸**:高危动作(`git add -A`/无 pathspec commit/push、frozen/certified 写、spawn 子代理、`rm -rf`、发布封印)若本轮无 proof → `deny`/`ask`:"先查再来"。
  - **Stop 闸**:输出含项目记忆依赖断言("当前方案是X/owner 意思是/之前已经/这文件现在/已确认已验证")但无 proof → `block` 续写:"你在下依赖项目记忆的结论却没查,先查再改"。
  - **UserPromptSubmit**:只做早期预测注入(prompt 里已有的路径/域/风险动词)。
- **`skip` 必须显式留痕**(`memory.skip(reason=...)`)——否则永远分不清"正确地没查" vs "忘了查"。
- 为什么比 ③ 的看守强:**确定性**(闸本身不需 LLM,就查 proof 在不在)、**当前 hook 可建**、且**逼出真 search → 结果进【当下】上下文**。

## 5. 更深的地基:可观测性契约(schema 层)

每张 active 卡必须声明自己有**系统可观测的触发面**:
```yaml
activation:
  observable_from: [user_prompt, tool_input, tool_result, assistant_visible, session_start]
  delivery: [pre_reasoning, pre_action_gate, post_action_context, end_turn_watch, resident_l0]
  max_latency: before_action | before_next_model_call | next_turn | offline
  guarantee: hard | advisory | shadow | manual_only
```
`zmem verify --coverage`:**P0/P1 active 卡没有 `observable_from` → verify fail**;只有 `manual_only` 且非 `resident_l0` → fail;每个 `observable_from` 必须有投影函数 + ≥1 source-tagged eval。
→ 地基从"我希望对的卡会出现"改成"**每张卡都有被系统看见的理由**"。没这条,卡再多、reranker 再强、LLM 判官再贵,都只是"一个没人会敲门的图书馆"。

## 6. 它和 ③ 的关系 + 治本会话那个事故

- **不是推翻 ③,是接住并修正**:③ 的"看守"降级为**第四档**(专管"我外露了计划但还没变成动作/结论");真正近期键石是**提交点闸门**(b 档)。
- ③ 的"四层方案"(UPS 富化/L0 常驻/PreToolUse 窄门/影子)全保留,但**重新挂到"可观测性契约 + 提交点 proof"这个地基上**。
- **治"读了没连上"**:本会话 owner 逼出的最深一刀——我压缩后第一句就"读记忆"、也真读了 HISTORY §5(判官就在那),但做成出综述(summary 深度)丢了"§5=③答案"的连接、还重推了一遍。提交点闸的"做设计判断前必须有 memory proof"会**逼我在判断那一刻重新 search → 记忆落在当下上下文**,这是比"turn-1 读一次"或"push 个指针"都强的解。

## 7. 我的评估(採纳 + 挑刺)

- **採纳**:三目标分离、提交点闸门、ZMEM_PROOF、可观测性契约。(b)档当前可落地。
- **挑刺/边界**(ChatGPT 自己也认):① 闸只在提交点兜,治不了 (a)、也治不了"查了但查错词";② "是不是记忆依赖断言/动作"的识别靠关键词模式,会误判(像看守的风险词预筛);③ 强制 search 有摩擦,靠 `skip-with-reason` 放掉纯改写/翻译。**这些是规格边界、不是硬伤——它老实标了"无解的别装能解"。**
- **诚实**:这份(owner 拿我 ③ 文档喂 ChatGPT 后)在核心问题上**比我那场六代理会强**。我该认。

## 8. 落地顺序(ChatGPT 给的 6 步,凝练)

1. **卡 schema 加 `observable_from` + `zmem verify --coverage`**(地基,先立)。
2. **`zmem search` 吐 `ZMEM_PROOF`** + eval 加 `source` 字段(frame 拆 user_prompt/tool_input/tool_result/assistant_visible/session_start)。
3. **PreToolUse 闸**:高危动作无 proof → deny/ask(=README 的 MVP-1a 收窄成 proof 检查)。
4. **Stop 闸**:记忆依赖断言无 proof → block 续写。
5. **PostToolUse/Failure/Batch**:`error_regex` 驱动"遇到什么"召回(撞错/拿结果就弹)。
6. **新 eval**:`SearchDecisionHitRate`(该查时真发起 search/skip 没)、`SkipFalseNegativeRate`、`UnnecessaryLookupRate`——测"模型有没有真进查记忆动作",不只"系统有没有碰巧塞对卡"。
- 真正的 (c) "中途及时查" = `active_memory_loop`(next-intent 颗粒度),需接管 Claude Code 之外一层 runner,**未来**。

## 9. 外部佐证(ChatGPT 引)

Toolformer(工具调用是可训练的 policy 不是性格)、OpenAI `tool_choice:"required"`(强制先调一个工具)、FLARE/Active RAG(用"即将生成的内容"形成查询、生成中途多次检索)、Self-RAG(检索触发训成模型输出流里的显式 reflection token)。结论一致:**靠提示词说"记得查"不够,必须把"查"变成结构化/门控的动作。**

---

*本份是 memory-update 回合(2026-06-28)对 owner 提供的 ChatGPT 分析的 canonical 记录 + 我的评估。下一步:把这套接进 ③ 的落地(observable_from schema + ZMEM_PROOF 闸),它是 ③ 真正的地基。*
