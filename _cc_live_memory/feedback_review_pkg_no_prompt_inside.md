---
name: review-pkg-no-prompt-inside
description: "External review 打包 (GPT pro / 别窗口) 包内只放纯事实素材 — **不放 prompt 也不放主动性内容** (审查指引 / verdict claim / Close 列表). 用户说过多次."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-22 用户原话: "promet不要放在包里, 这个说过好多次了".

## 规则

External review 打包给 GPT pro / 别 chat 窗口审查时:

**包内只放**:
- 全 src (self-contained 可跑)
- 真数据 (canonical_rules / preprocessed / candidate_placements)
- spec docs (cut_family_specs / state_machine / lifecycle 等)
- git diff (format-patch)
- cross_check archives (历史 finding context)
- testing infra (requirements.txt / pytest.ini)
- README (使用说明 + smoke test 命令)

**包内不放**:
- PROMPT.md / audit prompt — 由 chat 一并给用户, 用户自己 paste 给 GPT pro
- 任何 "此次 review 的 task 说明 / 指引"
- **任何主动性内容 (2026-05-22 加)** — 引导 reviewer 朝特定结论的 framing:
  - "请审查 X / 期望反馈" 这种 instruct → 是 prompt 该说, 不放包
  - "Step X 已 close / 数学 sound / Phase 1.1 修复闭环" 这种 verdict claim →
    引导 reviewer 信"已 close", 反 falsification mode
  - "Close: 4 P0 + 5 必修" 这种分类 → reviewer 看完 priming "这些不用查"
  - "verify reproducibility (key claims)" 段 cite file:line → 主动给"信"的
    锚点, reviewer 该自己 dig
  - 包目的写 "请整 phase audit ..." 这种 → reviewer 不该被告诉看什么

## 例外 (唯一): code_context/ review-only mirror 的"非 master"定向标注 (v17 四审坑 → 反转)

no-priming 禁"引导/规范 reviewer 行为"的内容. **唯一例外** = 给入包的 throw-away
代码一句**中性定向标注**: `code_context/<phase>/` 的 README 写明
"**review-only source snapshot, NOT a master merge target**" (+ SHA256SUMS,
刻意不放 scripts/ 下).

**坑 (来历, v17 四审 ~2026-05-26)**: 早先 PR #1 "verdict-only style" 故意不放
spike toy code (怕 reviewer anchor 在 throw-away 设计选择) → **v17 四审 Reviewer B
catch 这是 evidence gap**: reviewer 没法 source-check 产数据 artifact 的 call site.
反转 = spike code 要入包 (见 [[review-pkg-data-completeness]] How-to #1). 但**新
问题**: 直接把 toy code 丢进 project/ 树, reviewer 会误当 production master 代码
flag (false-positive finding). 所以**必须加**那句"review-only / 非 master"说明 —
它技术上是"规范 reviewer 怎么对待这段代码"的引导内容, no-priming 本该禁, 但
**破例允许**.

**为啥能破例 (定向 vs 结论 priming 的界)**: 它是**定向/消歧** (这文件是什么 /
怎么定位它), 防 reviewer 误判"toy code = 待审 production 代码"这种 false-positive;
**不是** verdict-priming (该得出什么结论 / 哪些已 close). 判别: "这是 review-only
mirror, 非 master" = 定向标注 ✓ 可放; "这些 finding 已 close / 数学 sound" = 结论
引导 ✗ 不放. (注: 下方反例 #3 记的是 v14 pre-reversal 决定, 已被本 v17 反转覆盖,
别照旧理解成"spike code 不入包".)

## 为啥

1. **prompt 是当下 chat 的临时 directive**, 不该跟 long-term audit package
   绑定 — 包多次 review 复用, prompt 每次不一样.
2. **用户 workflow**: 用户给 GPT pro 时通常直接 paste 我给的 prompt 到 chat,
   GPT pro 看到 + 包. 把 prompt 藏在 zip 让用户 还得先 unzip 找出来 paste —
   多余步骤.
3. **职责清晰**: 包是 "供 GPT pro 看的内容资料库", prompt 是 "我给用户的
   audit 指引". 两层独立.
4. **跟 [[review-package-for-new-window]] 一致**: 包不带 history carry-forward.
   prompt 是 history 形式 (本次 task 说明), 不该入包.

### 为啥主动性内容也不能放 (2026-05-22 加)

包内的 README / CHANGELOG 容易写成 "audit 指引 + 现状声称" 这种主动性内容 —
看起来 helpful 但实际反 reviewer 独立性:

5. **reviewer 该独立判断**, 不该被包内 verdict claim priming.  "Step A-H
   全 close" / "数学 sound" 这类话让 reviewer 默认信而不主动 falsify — 跟
   [[gpt-review-prompt-armor]] "GO 必先 falsify 3 死法" 精神冲突.
6. **跟 prompt 重复**: prompt 已说 "请整 phase audit / 期望反馈 X". 包内
   README 再写一次就是重复, 且会被 reviewer 当 cross-confirm "包 + prompt
   都让我看 X" → 更强 priming.
7. **包内只该是事实素材**: 数据 / src / spec / 历史 audit archive (factual
   record) / commit log (factual git history) / 怎么跑 (factual command).
   "我认为这些 P0 已 close" 是结论不是事实.

## Apply when

任何 review 打包给 external (GPT pro / claude window / Gemini / 别 chat)
之前:

- ✅ zip 含 src/data/spec/diff/cross_check/testing infra/README
- ❌ zip **不**含 PROMPT.md / audit指引 / task 描述

prompt 通过 chat message 给用户, 用户自己 take 给 GPT pro.

## 反例

### 1. PROMPT.md 漏放 (2026-05-22)

第一次 zip `phase1_1_gpt_pro_review_v1.zip` 时把 PROMPT.md 放包内 — 用户提醒
"prompt 不要放包里, 这个说过好多次了". 立刻 fix: rm PROMPT.md + re-zip.

### 3. v14 spike close gate pkg "PR #1 verdict-only style" (2026-05-26)

Spike GO_WITH_MINOR 后 build v14 review pkg 时:
- **含**: spike verdict.md + phase_a_report.md + 实测 jsonl 数据 (让 GPT
  验数字 sound)
- **不含**: spike-only py code (toy_translator / scale_ramp / filter_mock /
  feasible_smoke / oracle_emit_fixture / spike_prod_scale_runner /
  off_limits_check / failfast_probe / telemetry 等)

Rationale: per MERGER §5.1 rollback-safety "GO → 2 PR (PR #1 verdict doc
only / PR #2 重写 P1.3A 实施, **不 cherry-pick spike code**)" — PR #1
verdict-only style 防 GPT review anchor 在 throw-away spike toy translator
的 design choice. Spike code 是验证用 throw-away, P1.3A 主体应走 N=8
parallel design 不是 cherry-pick spike code.

实操: build script 用 `git archive master` 当 base + spike branch 选定 file
overlay (`git show spike/...:path > staging/path`) 加 verdict/report/jsonl
+ 加 `SPIKE_COMMIT_LOG.md` (commit log dump). 不 walk spike branch py code.

### 2. README/CHANGELOG 主动性内容 (2026-05-22)

打 v2 包时 README 写 "请整 phase audit ... / 期望反馈 (两层)" + CHANGELOG
写 "Close: 4 P0 + 5 必修 / verify reproducibility key claims cite". 用户提醒
"包内不能放主动性内容, 记一下然后把包改掉". 立刻 fix: 删 README "期望反馈" /
"包目的" 引导句, 删 CHANGELOG "Phase 1.1 状态 / Close / Defer 分类 / verify
reproducibility" 段; 只留 factual commit timeline + 怎么跑 + 文件清单.

## Refs

- [[review-pkg-data-completeness]] — **互补**: 本条禁主动性 priming, 那条
  要 factual evidence 完整入包 (spike code mirror / Gemini archive / raw
  telemetry 等). 一起读.
- [[review-package-for-new-window]] — 包不带 carry-forward / history ref
- [[gpt-review-prompt-armor]] — prompt 内容 armor 规则 (跟"prompt 放哪"独立)
- [[external-review-reproducibility]] — GPT 两次跑结果不同, prompt 单独 audit
