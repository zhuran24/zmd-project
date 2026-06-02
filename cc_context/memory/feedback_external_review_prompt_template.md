---
name: external-review-prompt-template
description: GPT pro / Gemini / 别窗口 external review chat prompt 撰写 7-section 模板 (input-side). 真瓶颈 / 死路 inventory 邀请挑战 / 审查重点 axis 化 / 关键决策点 explicit 列选项 / 优先方向 (不限于此) / 不可达论证 prompt armor / deliverable 压缩包. **两个允许的输出规定例外: §6 不可达论证 armor + 给补丁+打包(非1:1) (2026-06-02 新增, reviewer 补丁仍 verify-before-apply 不盲打); 其余 (schema/字数/verdict label) 不规定**.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8ce2a10d-50a6-4d5c-82bf-3c4414cb623f
---

External review prompt (GPT pro 大节点 / Gemini cross-check / 别 chat 窗口
独立审查) 走 7-section 结构. 不是命令格式 mandate, 是经多次 audit 迭代
稳定下来的 prompt 模板.

**Why**: external reviewer 是 0 history 新窗口, 必须 self-contained 给 context.
轻量 200-500 字 brief 缺前提 → reviewer 错估问题陈述 (per
[[gemini-math-consultant]] 反例); 重 axis 化 + 关键决策 explicit 选项化
→ reviewer 不 default 接受 obvious 路径 (跟 [[main-merger-scope-creep-bias]]
同 spirit: external reviewer 同样有 "做全=安全 / 现状=合理" default bias,
explicit 选项 force evaluate). 7-section 是 audit/decision/falsification
覆盖最小集.

**How to apply**: 写 prompt 时按下面 section 顺序填. 不必每 section 等
篇幅, 但**全部 7 段必须出现**. 漏 section 是 reviewer 角度漏的 leading
indicator.

## 8-Section 结构

### 1. 顶部 1-2 句标题段
项目名 + 当前 phase + audit 类型 (一审 / 二审 / 三审 / N审).

### 2. 真瓶颈现状
- 项目背景 (1-2 句, 给数学问题陈述 + paradigm)
- 本次包是什么 (包覆盖哪个 commit / 包内 sha / 包内含 + **不含**什么 +
  不含的 rationale)
- 上次 review 的 verdict + finding count (如果是 N 审, N>=2)
- 详 README 在 zip 内哪个路径

### 3. 已 verdict NOT_GO 的 lever 历史 (含死因 + reproducer, 欢迎挑战)
List dead lever 跟 verdict 分类. 配一段邀请 push back:

> 这些不是"禁止讨论", 是"当时数据 / 当时方法 verdict NOT_GO". 如果看到
> 我们 verdict 时漏的角度 / 新算法跨过当时门槛 / prior reproducer 数据
> 本身有问题, **直接 push back**, 不要因 prior verdict 自我审查.

**措辞硬度** = "已 verdict NOT_GO" + "欢迎挑战" + "不是禁止讨论".
**不写** "死路黑名单 / 禁止 / 不准 / 不可" 等强硬词 — 反 falsification
mode, reviewer 会回避真有价值的挑战.

### 4. 本次审查重点 (axis 化)
按 axis 分 (e.g. A patch verify / B verdict sound 性 / C phase boundary
决策 / D scope creep 轨迹). 每 axis 列 sub-question.

**关键决策点必 explicit 列 (a)/(b)/(c) 选项**, 不让 reviewer default 接受
"我们走的现状路径". 例:

> 走 doc-only 路径 / 真补缺失数据 / 提前实施下一 phase. 不要 default
> 接受现状 — 如果其他选项数学上 / 工程上更 sound, 直接 push back.

为啥 explicit 列选项: 跟 [[main-merger-scope-creep-bias]] 同 root —
reviewer 同种 RLHF bias 在"现状已 ship 看起来合理"时 default 接受, 不
主动 evaluate alternative. 写 prompt 时强制 evaluate.

### 5. 优先关注方向 (不限于此)
Bullet list 给 reviewer 自由 angle, 但**结尾必带"不限于此"** — 防 axis
化漏的维度.

### 6. 不可达性论证要求 (prompt armor 例外)

若 finding 暗示某方向 "做不到 / 必须 X / 不能 defer", **必须给形式化
证明**:
- complexity reduction (problem X ≤_p problem Y)
- proof system lower bound (resolution / cutting plane)
- resource inequality (memory / variable count / time)
- 引文献 (paper / theorem 名 + 年份)

**不接受** "I believe" / "intuitively" / "experience suggests" / "通常
这样" / "在我看来" 等 vague claim.

来源 [[gpt-review-prompt-armor]] — L14 实测 reviewer 首次诚实列 caveat
+ 应验. 此 section 是 **下面 "不规定 reviewer 回答方式" 原则的明确例外**
— 因为不可达性论证 vague claim 在 LP/CP-SAT 数学语境下经常实测错估
paradigm (L14 反例), 必须用 prompt armor force reviewer 严谨化.

### 7. 最后将文档和补丁以压缩包的形式给出

prompt 末尾就一句话标题 + 1 行 sha. **不展开 rationale** (不写"散在 chat
里 patch 不能 apply" / "多 round 易丢" 等解释 — reviewer 自然懂).

## Prompt 末尾固定排版 (重要)

§6 不可达论证 + §7 deliverable + sha256 三块**顺序固定**, sha256 **必单独
最末 1 行**, 不夹中间:

```markdown
... (前面 §1-§5 略) ...

## §6 不可达性论证要求

若 finding 暗示某方向 "做不到 / 必须 X / 不能 defer", **必须给形式化证明**:
- complexity reduction
- proof system lower bound
- resource inequality
- 引文献

**不接受** "I believe" / "intuitively" / "experience suggests" / "通常
这样" 等 vague claim.

## §7 最后将文档和补丁以压缩包的形式给出

包 sha256: `<full sha256 hash>`
```

**不要**:
- §7 展开 rationale ("散布 patch 不能 apply" / "多 round 易丢" 都不写)
- sha 放 §2 真瓶颈段中间 (容易被淹)
- sha 放 §7 标题行 inline ("...压缩包的形式给出, sha=xxx" 这种)
- 加 "## 解包步骤 (参考)" 段 (这是已删 section, 易复发)
- §6 跟 §7 颠倒 (deliverable 是 prompt-most-action, 放最末才对)

## 不规定 reviewer 回答方式 (除 §6 armor 外)

§6 不可达论证 armor + 「给补丁+打包(非1:1)」(2026-06-02 新增) 是**两个允许**的 "规定回答形式" 例外, 其余一律不
规定 reviewer 怎么答 / 怎么 verdict / 输出 schema / 字数长度. 不写:

- "按 severity / file:line / 问题陈述 / reproduce / defer 字段输出 —— 但 **fix/补丁 现在反而要要** (2026-06-02, 见下方「给补丁+打包(非1:1)」专节, 修正早先 "不要 fix 字段")"
- "末尾必给 GO / GO_WITH_MINOR / NOT_GO verdict"
- "回答控制在 X 字以内"
- "每个 finding 不超过 3 段"
- 其他 schema 锁

Why: reviewer 是独立审查者不是模板填表机, 自然有自己的论证习惯跟输出
风格. 规定 schema 反 reviewer 独立性 (跟 [[review-pkg-no-prompt-inside]]
包内不放 priming 同 spirit), 且 schema 锁可能 force reviewer 牺牲该有的
细节去 fit 模板. §6 是例外因为 vague claim 在数学层会埋 paradigm 错估,
代价高于 schema 锁副作用; 输出格式 / 字数 / verdict label 没有同等
mathematical-soundness 风险, 不应该锁.

## 让 reviewer 给补丁 + 打包 (2026-06-02 用户决定; §6 之外第二个输出例外; 补丁与 finding 非 1:1)

prompt 的输出约束段要求 reviewer **不只指出问题就给出能直接落地的补丁** (哪个文件、改成
什么, 最好可直接 apply 的 diff 或替换用代码/文案片段, 可标把握度), **并把说明文档 + 补丁以
压缩包(zip)形式给出** (= §7「将文档和补丁以压缩包的形式给出」, 让 main 直接下载落地)。
**补丁跟 finding 不必一一对应** —— 一个补丁可覆盖多条, 怎么组织 reviewer 定; **别锁死"每条
finding 一个补丁"** (用户 2026-06-02 明确: 关系非 1:1, 只要让他"给补丁 + 打包"即可)。措辞例
(放原 §6 armor 同一个 "硬性输出约束" 段, header 改「硬性输出约束（两条）」, 不叫"唯一"):

> 2. **给出补丁并打包**: 不只指出问题就给能直接落地的补丁 (file + diff/替换片段; 补丁与
>    finding **不必 1:1**, 一个补丁可覆盖多条, 可标把握度); 最后把说明文档和补丁以压缩包形式给出。

**Why**: 省 main 从 finding 反推 fix; reviewer 往往比 main 更懂自己 finding 的精确修法。

**护栏 (必守)**: reviewer 给的补丁是**起点不是终点 —— 仍 verify-before-apply, 不能盲打**。
reviewer 可能提个错的/肤浅的补丁 (跟 finding 本身可能错同理); main 必须像核 finding 一样
先对真代码/数据核实补丁正确再应用 (per [[no-causal-claim-from-n1]] [[audit-verify-before-archive]])。
这跟 "要补丁" 不矛盾: 要补丁是为了 actionable, verify 是为了别盲信。

**与独立性的小张力 (接受)**: 让 reviewer 提补丁, 理论上下一轮可能 review 到自己提的修法,
独立性略降; 但每轮是新窗口零历史 (per [[gpt-review-no-history]]), 看不到自己上轮的补丁,
所以张力很小, 用户已权衡接受。

## Anti-patterns (避免)

- 罗列 fact 不分 axis — reviewer 不知哪些维度该看
- 关键决策点写 "我们选了 X" priming, 不写 (a)/(b)/(c) 选项 force evaluate
- 死路 inventory 强硬措辞 "禁止 / 黑名单" — 反 falsification mode
- 角色催眠前缀 "你是 X 专家 / 数学家 / CP-SAT 专家" — per
  [[no-role-priming-for-reasoning-models]] 推理模型反作用
- 引用上次 GPT 输出 ("参考上次 v11 计划书 / 你之前说的方向") — 新窗口
  零历史 per [[gpt-review-no-history]]
- 缺 sha256 / commit / 包路径 — reviewer 不知拿哪个版本
- 规定 reviewer 输出 schema / verdict label / 字数 (见上段; §6 不可达
  论证 armor 是唯一例外, 其余 schema 锁都不写)
- prompt 放进 zip — per [[review-pkg-no-prompt-inside]] 职责分清
- **prompt 文件里放使用说明 / meta header** (如 `> 用法: 把 X 发给 GPT pro` / `这段是 prompt, 不在 zip 里`) — 废话(用户自己知道) + 逼用户先删才能粘。**prompt 文件必须纯净: 全选复制即可直接粘给 reviewer**, 只含给 reviewer 看的内容(标题 + 正文); 操作说明(发哪个包 / 不进 zip / 怎么用)放 chat message 里跟用户讲, **不进 prompt 文件本身**。(2026-06-01 用户明确)

## Refs

- [[gpt-review-prompt-armor]] — 真瓶颈讲清 + 死路 inventory + 不可达论证
  (本 memory 是 armor 的 7-section 模板化, 不冲突)
- [[gpt-review-no-history]] — 新窗口零历史, 不引用上次 GPT 输出
- [[no-role-priming-for-reasoning-models]] — 不写"你是 X 专家"
- [[review-pkg-no-prompt-inside]] — prompt 不入包 + 包内不放 priming
- [[external-review-reproducibility]] — 同 prompt 跑两次结果不一致, fixed
  schema 缓解
- [[main-merger-scope-creep-bias]] — explicit 选项 force evaluate, 同
  spirit
- [[adversarial-soundness-audit]] — reviewer 5 验
- [[gemini-prompt-audit-mode]] — Gemini 用 audit 模式找问题 (不夸傻),
  同种 prompt-armor 方向
- [[gpt-error-types-taxonomy]] — 3 类 GPT 错估 (算法 / 前提 / 能力上限)
- [[gemini-math-consultant]] — Gemini 1500 字最低 prompt 同理
- [[gemini-better-at-natural-tone]] — 长 narrative 默认 Gemini 写更自然
