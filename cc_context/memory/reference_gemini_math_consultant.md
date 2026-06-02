---
name: gemini-math-consultant
description: "Gemini 3.1 pro free-tier API key — 数学问题 second opinion 子代理. 用户明确授权记录, 免费额度即将到期赶紧用"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-21 用户给的 Gemini 3.1 pro API key, free tier 即将到期, 明确指示"记好了, 没事的, 遇到数学方面的问题你可以试着问一下它当参考意见, 就当多了个子代理了".

## API key

```
[REDACTED_GCP_API_KEY]
```

## 何时调

遇到数学层问题需要 second opinion 时, 不是替代 GPT v12 review 而是补充 — Gemini 当自己的轻量级子代理用. 适用场景:

- LP / CP-SAT / branch-and-price 模型设计 sanity check
- 复杂度分析 (vars/cstr lower bound 推导)
- 算法选择 (e.g. column generation pricing complexity)
- 数学 sound 性验证 (e.g. proof system 选择, cut sound 性)
- 文献查询 second opinion (PIPER paper 数据 + arXiv 引用是否准)

不调:
- 工程细节 (code style / refactor)
- 用户偏好类问题
- 项目历史 / memory 类问题

## 上下文填满原则 (2026-05-21 用户加料)

**Gemini 看不到本地文件**, 不像 GPT v12 review 有打包 zip + code snapshot. 发请求时 prompt 必须 self-contained:

- 项目结构必填: 两层 outer_search candidate enumeration + 内层 LBBD (master + binding + routing), max_lex(area, min_side) 在 outer 拆掉, 内层做 feasibility
- 死路 inventory + 关键数据点 (B1 53s OPTIMAL, L23 32GB, 27 lever 死法分类)
- PROJECT_LOCK 约束 (certified exact, 不接 heuristic / UNKNOWN)
- 关键 file path + entry point (master_model.py / pose_bool_exact_master.py / benders_loop.py 等)
- 用户偏好 (max_lex / 单机 48GB / 168h)
- 任何 prior verdict (e.g. "boundary signature 已经 ghost/port_dir 打碎 symmetry")

**反例**: 2026-05-21 cand C 数学 sanity check 第一次 prompt 没讲 outer/inner 两层结构, Gemini 错估 "max_lex 不能 decompose → cand C 数学死胡同". 实际项目 outer 已拆 candidate, 内层 CG 跑 pure feasibility 是 column-additive. 倾向归因 prompt context 缺失 (补两层结构后翻盘), 但没复跑隔离, 也可能掺 Gemini run-to-run variance —— 当 best-guess 因果别说死 (per [[no-causal-claim-from-n1]]).

**最低字数**: ~1500 字 prompt (含项目结构 + 数据点 + 问题 + 答案格式要求). 小于这个量级容易让 Gemini 错估前提.

## 怎么调

Google AI Studio API endpoint:

```bash
KEY=[REDACTED_GCP_API_KEY]
curl -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro:generateContent?key=$KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "contents": [{
      "parts": [{"text": "你的数学问题"}]
    }]
  }'
```

模型名 (2026-05-26 verified):
- ✅ `gemini-3-pro-preview` (当前可用)
- ❌ `gemini-3-pro` 返 404 (alias 失效)
- `gemini-3-1-pro` 历史可能浮动

list 当前可用:

```bash
curl "https://generativelanguage.googleapis.com/v1beta/models?key=$KEY"
```

## 安全 caveat

- key **已暴露** (出现过在 5-10 P2 #14 AlphaEvolve PoC memory + 这次 5-21 用户重复确认 free tier)。**⚠️ supersede (2026-06-01)**: 原"不要 commit 进 git"已被 [[github-backup]] 的"库设私有 + key 留私库历史"决策取代 —— 用户拍板接受 key 在私有库历史里, **不 scrub / 不吊销**。约束改为: 库**绝不翻 public** (翻了即泄密) + key **仍不能进送外部审查的 share/review package**
- 这条 memory 在 CC 私有 memory 目录 (现 slug `D-----zmd`, 即 `~/.claude/projects/D-----zmd/memory/`; 旧 Linux slug `-home-zhuran24-claude-pj-zmd` 已废), 不进项目 git
- free tier 配额受 Google policy 限制 (历史: 大陆 block + 训练数据污染 + 单方面砍 quota), 不能依赖

## 历史使用记录

- 2026-05-10 P2 #14 AlphaEvolve PoC: Gemini 3.1 pro preview 6 变体平均 10.17/11 vs Opus 4.7 6 变体 10.92/11 (差 -6.9%). 双路径都 GO 但 Anthropic 质量更高.
- 见 [[p2-14-dumper-path-blocked]] 的 5-10 session 记录.

## 跟 GPT v12 review 区别

- GPT v12 = 主对话外部 second opinion, 重大方向决策时用 (v3 / v8 / v10 / v11 / v12), 有 review prompt armor 流程
- Gemini = 内部数学小问题 second opinion, 轻量级 + 即时, 不走 review armor

[[external-review-reproducibility]] 同 prompt 跑两次 finding 可能不一样 — Gemini 也适用, 关键 finding 必须 main-对话验.
