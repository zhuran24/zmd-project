---
name: verification-independent-backstop
description: "长上下文下 LLM 注意力会漏看 → 验证/确认/核对类任务不能只信 main 自己回忆或自审, 必须派独立 backstop (workflow/子代理); 且 backstop 主体必须是「被验证对象本身」不能换 proxy; 子代理报告的根因/数字 main 要自己核实。"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

2026-06-01 用户原话: "llm 的注意力机制现在在长上下文下很容易出现漏看的问题, 至少让 workflow 或者多个子代理去作为补充和托底"; 紧接着纠正 "你让它确认的主体是记忆树, 但我想让它检查的主体却是当前的这个 session …… 你把检查的主体弄错了"。

## 规则

1. **长上下文下 LLM 注意力会漏看**。**验证 / 确认 / 核对 / "是否完整 / 是否全做了 / 有没有遗漏" 类任务, 不能只信 main 自己的回忆或自审** —— 必须派 workflow / 独立子代理作补充托底。(U37)
2. **backstop 的主体 (被检查对象) 必须是「要验证的东西本身」, 不能换成 proxy。** 例: 验"本 session 内容是否全落盘 memory" → 主体 = **整段对话本身 (用户消息 + 助手消息)**, **不是** 记忆树内部一致性 / git log / repo, **也不是只抽用户消息**。proxy 只看得见文件改动, 漏掉**只存在于对话里**的偏好/决策/口头反馈; 而只抽用户消息会漏掉**助手侧产**的 finding / 踩坑修法 / 决策 / 结论 —— 这些同样 memory-worthy。(U39/U40 + 2026-06-01 二次纠正)
3. 子代理跑完报告的**根因 / 数字, main 要自己核实**, 不能直接转述未验证的 (U17 同源)。
4. **审计→修→re-audit 修过的产物, 循环到一轮零 finding 才停 —— 别"审一遍修一遍就默认好"。** backstop 报 finding、main 修、重建 → 重建出来的是个**新的、还没被独立审过的产物** (sha 都变了); 必须把**这个新产物**再喂回独立 backstop 跑 (不是只 main 内联自查) 直到某轮审计**零 finding**。修完只做内联自查就交付 = 又退回"只信 main 自审"(违反规则 1), 而且 fix 本身可能不全/引新问题。(2026-06-02 用户 catch) **注: 这条 2026-05-24 就以「Gemini 循环规则」形式记过 ([[gemini-review-algorithm-math]] §循环规则: "修完应再审直到没问题"), 但 siloed 在 Gemini 语境、没跨到 GPT 外审/workflow review, 跑 GPT-review loop 时没 surface 才复发 —— 同话题散在多条 memory 不跨链 → 召不全的典型, 见 [[memory-tree-structural-health]] 的跨链协议。**

## Why

本 session 自证: main 第一次派 backstop 就把主体弄错成"记忆树"(proxy), 报"落盘完整"实为假 —— 恰恰漏了**本条 working-preference 自己**; 用户两次纠正(U39 完整重发为 U40)才扳回"主体 = 当前 session 内容"。换对主体后独立 agent 立刻确认这条缺失。**这正是本规则要防的失误, 当时却没进 memory, 不记下次必复发。** 口头反馈无文件副产物, 任何 git/repo/记忆树-proxy 检查都抓不到 —— 只有以"对话本身"为主体的独立检查能抓。

**主体二次切窄 (同 session 2026-06-01 再踩)**: 我把主体从 proxy 改对成"对话"后, 又只抽了**用户消息**当主体; 用户即时纠正"你的消息也全都要"。memory-worthy 内容助手侧也大量产 (踩坑修法/判断/结论), 只抽 user 仍漏。**proxy → user-only 是同一个病的两次发作: 图省事把主体切窄。规则收紧为「主体 = 完整被验对象, 不切片」。**

**proxy 第三变种 (核 shipped 包内容)**: 验证 workflow/子代理核对包内容时, 读到的常是 build 脚本里的**源 README 模板**(proxy), 不是 **shipped 成品**顶层文件 → 假阳性。本 session 实例: 打包 workflow 报 v22 README "解包步骤还写 7za" 是误报, 实地核 shipped 顶层 README + project/README.md 才确认 7za/project.7z/tools token 全 0、已是单层 unzip。**包合规类 finding 必回 shipped 文件本身复核。**

## How to apply

- 遇 "确认 / 核实 / 查全 / 是否遗漏 / 是否都做了" 类任务 → **先问"主体是什么"**, 把**那个东西本身**喂给独立 agent, 别用代理信号代替。
- 验 "session 内容全落盘 memory" → 抽 transcript **整段对话** (`cc_context/tools/extract_session_turns.py` 抽 role=user **+ role=assistant** 文本) 当主体, 独立 agent 逐条查 memory 覆盖。**别只抽 user** —— 值得记的事助手侧也大量产 (finding/修法/决策/结论)。
- 别因"内容在我 context 里 / 我刚做的我知道"就自审了事 —— 长 context 下我会漏。
- 子代理报告的 verdict/数字, 落 memory/commit 前 main 自己 grep/跑一遍核 —— **派生数字 (count/算术) 独立重算不照抄: 即使底层工作对了, 抄错一个数也误导** (本 session 实例: 子代理报 "119→121(+3)" 实为 122 的算术笔误, 工作没错; 拿 backup 对账 = 旧全在 + 列新增 = delta 抓出)。
- **grep/过滤验证时 pattern 易过宽误中同名文件** → 先窄化精确目标集再重跑 (本 session 核 v22 README 合规时 grep "README" 命中几十个, 必须收窄到包顶层 + project/README.md)。
- **自己脚本算出的关键数字 (尤其支撑 verdict 的) 也要 verify-the-method, 不只 re-run**: 重跑同一个有 bug 的方法只复现错值。不是只核别人报的数, 自产数也要核**产它的算法对不对**。本 session 实例: 我写的 `sizing_gate.py` bitset 解码 MSB/LSB 反了 → 整条 "F1/F9 大池子 100K → 1.9GB blow-up" 数字链是假的, 还写进了 RESULTS/verdict/README/memory 4 处, 直到外审独立按 LSB 重算才逮到 (见 [[no-causal-claim-from-n1]] / [[windows-ninth-review-pending]])。
- **跨文档重复内容 (同一张表/同一个数字出现在 README + verdict + RESULTS) 编辑时必一起改; 跨文档一致性是独立 backstop 的高频捕获项**: 本 session v23/v24/v25 三轮验证 workflow **各逮一次**我手工漏的镜像漂移 (改了 verdict 没改 README 的同张 Finding 表 / 改了 runner 没重生成 verdict 的 G10 行 / 改了 RESULTS 没改 verdict 的 F9 数字), 每次内联自查都没发现、都是独立 workflow 抓的。改前 grep 全部副本一起改 —— 这是 [[memory-tree-structural-health]] "改一条 memory 前 grep 全树找全实例" 的**项目文档版** (同一个 "改一处漏多处" 根因, 跨 memory 和 docs 两域)。
- **修复后必 re-audit 那个修过的产物 (闭环, 别短路)**: 每次 fix+rebuild 产生**新工件**, 独立 backstop 要在**新工件**上重跑, 循环到零 finding 才算 ship-ready。本 session 实例: v25 验证 workflow 报 3 瑕疵 → 我修+重建成新 sha f245bc9 → **只内联自查就交付, 没在重建包上再跑 workflow** (用户 catch: "修了一遍之后就默认好了, 没再审到没问题为止")。
- 关联: [[external-review-reproducibility]] (外部模型单次有 variance; 本条是 "Claude 自己" 在长 context 不可信, 互补) / [[subagent-for-closed-loop-tasks]] / [[audit-verify-before-archive]] / [[no-causal-claim-from-n1]] / [[memory-currency-protocol]]。
