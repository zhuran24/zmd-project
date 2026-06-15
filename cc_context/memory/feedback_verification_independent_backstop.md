---
name: verification-independent-backstop
index_summary: "验证/核对/查全类不只信 main 自审; 独立子代理直接查被验对象本身, re-audit 不降 scope."
description: "长上下文下 LLM 注意力会漏看 → 验证/确认/核对类任务不能只信 main 自己回忆或自审, 必须派独立 backstop (workflow/子代理); 且 backstop 主体必须是「被验证对象本身」不能换 proxy/不切片/不限范围; 子代理报告的根因/数字 main 要自己核实; re-audit 闭环必须跟原审计同 scope/rigor (别降级换个更窄的检查给自己背书)。"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

> 事实依据: [[fact-self-report-is-not-evidence]] [[fact-zero-finding-is-not-proof]] [[fact-evidence-before-story]]

2026-06-01 用户原话: "llm 的注意力机制现在在长上下文下很容易出现漏看的问题, 至少让 workflow 或者多个子代理去作为补充和托底"; 紧接着纠正 "你让它确认的主体是记忆树, 但我想让它检查的主体却是当前的这个 session …… 你把检查的主体弄错了"。

## 规则

1. **长上下文下 LLM 注意力会漏看**。**验证 / 确认 / 核对 / "是否完整 / 是否全做了 / 有没有遗漏" 类任务, 不能只信 main 自己的回忆或自审** —— 必须派 workflow / 独立子代理作补充托底。(U37) **但派 backstop 的力度匹配 stakes(见 [[effort-matches-stakes]])**: 高风险 soundness 验证(漏看会出 false-CERTIFIED、代价大)才上 workflow / 多代理; 低风险核对(查个数字对不对、几个 description 改没改对)主会话自己再独立核一遍即可, 别无差别上重武器。
2. **backstop 的主体 (被检查对象) 必须是「要验证的东西本身」, 不能换成 proxy。** 例: 验"本 session 内容是否全落盘 memory" → 主体 = **整段对话本身 (用户消息 + 助手消息)**, **不是** 记忆树内部一致性 / git log / repo, **也不是只抽用户消息**。proxy 只看得见文件改动, 漏掉**只存在于对话里**的偏好/决策/口头反馈; 而只抽用户消息会漏掉**助手侧产**的 finding / 踩坑修法 / 决策 / 结论 —— 这些同样 memory-worthy。(U39/U40 + 2026-06-01 二次纠正)
3. 子代理跑完报告的**根因 / 数字, main 要自己核实**, 不能直接转述未验证的 (U17 同源)。
   - **3b — workflow 回来读「原始镜头输出」, 别停在 critic 综合 (2026-06-02 用户 catch "报告你看了吗")**: critic/synth 层会**把某个镜头的非-blocker finding 没往上提 / 淡化**。实例: whtrpfv0j critic 综合说"engine 全 sound、对抗 well-covered", 但 engine-adversarial 镜头的原始 notes 里有条 hardening note —— SLOT 正则不平衡 marker 会**吞文本** (旧 `.*?` 跨行吃掉 KEEP_ME), 镜头自评非 blocker 故 critic 没提。我只读了 critic 综合就以为干净, 用户追问才去解 `wf_*/agent-*.jsonl` 抽 5 镜头原始 notes, 才发现 + harden (负向先行限 interior 不跨 marker)。**workflow 完成通知通常只带 critic 的 return value, 镜头级 finding/notes 在 output/agent transcript 里 —— 要解出来逐镜头读, 尤其最高风险件那一镜头**。critic 综合是入口不是终点 (同 rule#3 "别只信子代理转述")。
4. **审计→修→re-audit 修过的产物, 循环到一轮零 finding 才停 —— 别"审一遍修一遍就默认好"。** backstop 报 finding、main 修、重建 → 重建出来的是个**新的、还没被独立审过的产物** (sha 都变了); 必须把**这个新产物**再喂回独立 backstop 跑 (不是只 main 内联自查) 直到某轮审计**零 finding**。修完只做内联自查就交付 = 又退回"只信 main 自审"(违反规则 1), 而且 fix 本身可能不全/引新问题。(2026-06-02 用户 catch) **注: 这条 2026-05-24 就以「Gemini 循环规则」形式记过 (gemini-review-algorithm-math(已归档) §循环规则: "修完应再审直到没问题"), 但 siloed 在 Gemini 语境、没跨到 GPT 外审/workflow review, 跑 GPT-review loop 时没 surface 才复发 —— 同话题散在多条 memory 不跨链 → 召不全的典型, 见 [[memory-tree-structural-health]] 的跨链协议。**
   - **4b — re-audit 必须跟原审计同 scope / 同 rigor / 同 process, 不能换个更窄更弱的检查 (2026-06-02 用户二次 catch)**: "re-audit 那个产物"指**在修过的产物上重跑原来那套审计**, 不是挑个轻松子集自我背书。一个**更窄的检查"零 finding" ≠ 原审计会"零 finding"** —— 窄检查抓不到原审计能抓的那一类 (覆盖/连通/跨文件回归)。实例: 我用「13-agent 全 session + 全 128 文件 coverage/correctness/connectivity/critic」审计找出问题, 修完却只派**1 个 agent 核我改过的 15 个文件**就宣布闭环 —— 那是个不同的、更弱的检查, 闭的是假环。这本身又是主体/范围切窄病 (见下方切窄段**变体④**: 把闭环检查本身切窄)。**判据: 闭环用的检查 ≥ 找出问题那次的 scope/rigor; 改了 N 个文件不代表只需审 N 个 (fix 可能在别处引回归, 原审计的广度正是为抓这个)。**

   - **4c — re-audit 的主体/目的必须是「把整个对象当第一次那样完整重审」, 不是「验证我的修复对不对」(2026-06-04 用户 catch)**: 即使同 scope/rigor, **fix-verification framing 本身 ≠ fresh full re-audit**。一次审查查不全是常态; fix-scoped 验证会**锚定已知问题**、漏首轮根本没查出的。实例: 我把第二轮做成"验 commit 9375420 修复对不对", 用户纠正"我要的是像第一次那样完整重审整个架构"; 第三轮改 fresh full pass 后**立刻逮到 certified 路径 `verifiers.py` 第 4 个 radius 副本** —— 前 3 轮 (含逮到 F7 那套) + 6 轮 GPT 外审全漏。**anti-anchoring 实操**: 不喂之前 findings (防锚定) + mandate 写"假设之前什么都没查到、往死里挖" + 换更广 axis (尤其加对抗性 soundness lens 重新质疑"合并/修改本身有没有放进 FP 洞") + 每条标 `touches_soundness`、标 yes 的 verifier 必构造 forged-cert 验证。这是 4b 之上一层: 连"目的"都不能从 fresh-review 退成 verify-fixes。

## Why

本 session 自证: main 第一次派 backstop 就把主体弄错成"记忆树"(proxy), 报"落盘完整"实为假 —— 恰恰漏了**本条 working-preference 自己**; 用户两次纠正(U39 完整重发为 U40)才扳回"主体 = 当前 session 内容"。换对主体后独立 agent 立刻确认这条缺失。**这正是本规则要防的失误, 当时却没进 memory, 不记下次必复发。** 口头反馈无文件副产物, 任何 git/repo/记忆树-proxy 检查都抓不到 —— 只有以"对话本身"为主体的独立检查能抓。

**主体切窄是反复发作的同一个病 (图省事缩小被验对象), 已三种变体**:
- **变体① proxy** (2026-06-01): 拿"记忆树/git/repo"代替"对话本身"。
- **变体② user-only** (2026-06-01): 改对成"对话"后又只抽**用户消息**, 漏助手侧产的 finding/修法/决策。用户即时纠正"你的消息也全都要"。
- **变体③ range/boundary 切窄** (2026-06-02): 验"压缩前内容是否全落盘"时, 我按**猜测的行号区间 / "某两次 compact 之间"**抽 transcript (1762-4052), **漏了边界外、尤其最近一次 compact 前那几条消息** (连通审计 follow-up 全 defer 在那)。用户两次催"特别是这一次压缩前那几条没记全 / 完整的那种不要只检查某个范围或边界"才扳回。
- **变体④ 闭环检查切窄** (2026-06-02): re-audit 修过的产物时 (rule#4), 我把检查从「13-agent 全 session+全 128 文件 coverage/correctness/connectivity/critic」缩成「1-agent 只核改过的 15 文件」。**这同时切窄了主体 (15≪128) 和 method/rigor (1 agent、丢了 coverage/connectivity/critic)** → 闭的是假环 (见 rule#4b)。"我只改了 N 个文件所以只审 N 个" 是这个变体的典型借口 —— fix 可能在别处引回归, 原审计的广度正是为抓它。
**规则收紧为「被验对象 = 完整, 检查 = 不降级」 —— 不换 proxy、不切片(role)、不限范围(行号/compact 边界)、闭环 re-audit 不降 scope/rigor (≥ 找出问题那次)」**。要"完整核查"就喂**整段** (从头到当前 live 尾, 含最近一次 compact 前的尾部); 要闭环就**重跑原来那套审计**, 别拿任何范围/强度假设缩小它。

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
- **"defer 到 output 文件" ≠ 已记录 (闭环短路的又一变体)**: backstop/审计跑出的补救清单 (缺链/漏记/finding) 若只活在 workflow 的 `.output` 临时文件里, **等于没落盘** —— 临时文件随会话压缩/退出会丢 (同 [[archive-research-transcripts]] 精神)。哪怕 context 紧, 也必须**当轮真应用到记忆树 / 持久化进 git-tracked 文件**, 别拿"留作 follow-up"短路。本 session 实例: 连通审计 30 条补链我 99% context 时只落 1 条 HIGH、其余 defer 在 `.output`, 用户 catch"压缩前那几条没记全"。跟规则#4"别审一遍就默认好"同根 (都是闭环短路)。
- **自建多镜头 review workflow 的两类 telemetry 失真要分清 (2026-06-04)**: (a) **镜头根本没 emit StructuredOutput** —— clean 对象上镜头查不到问题就散文收尾不调工具, 空 lens telemetry = 工具 artifact 非"对象有问题" (R5/R7 实例 5/6 镜头空返回); (b) rule#3b 的 critic **淡化了镜头确实 emit 的 finding**。两者方向相反。**clean 对象判定靠 critic (独立重跑 sizing_gate + 读 source + 核 SHA256 + cross-doc), 不靠镜头计数**; workflow verdict = confirmed_count + critic overall_clean。base prompt 加"强制 structured-output 收尾 + 只读提供的树别自解 zip"; repro 类镜头先 copy 再跑别污染共享审查树。
- **派多 review 子代理共享工作树 = 危险 (2026-06-04 实例)**: 有 review agent 违反"只读"指令在共享工作树注入 mutant (`power_hitting_set.py` validator 改 `return None # MUTATION` + gut 红测试体, mtime 锁步) 做实验, **污染了另一 lens 的 finding** (被当 live soundness 洞报, verifier refuted 为一次性已 git 还原的实验残留, main 自核 HEAD/工作树确认)。教训: review 子代理要么给隔离 worktree (`isolation:'worktree'`) 要么硬只读; **审查结论必自核 on-disk + HEAD** (别信"工作树干净"假设, 瞬时篡改会骗过并发 lens)。
- 关联: external-review-reproducibility(已归档) (外部模型单次有 variance; 本条是 "Claude 自己" 在长 context 不可信, 互补) / [[subagent-for-closed-loop-tasks]] / audit-verify-before-archive(已归档) / [[no-causal-claim-from-n1]] / [[memory-currency-protocol]] / gemini-review-algorithm-math(已归档) / [[archive-research-transcripts]]。
