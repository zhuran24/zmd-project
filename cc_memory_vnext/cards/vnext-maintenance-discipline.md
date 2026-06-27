---
id: vnext-maintenance-discipline
kind: constraint
title: v-next 自喂养纪律:被纠正/踩新坑→补金标准+卡片
summary: 当 owner 纠正我、或我踩了反复犯的新坑时,必须把它补成 cc_memory_vnext 的一条金标准 frame(取自真实信号、禁照 scope 反填)+ 一张新卡或更新已有卡,保持 zmem eval 绿。这是记忆系统自我进化的闭环,断了它就退回被动库。每个会话都要做。
scope:
  domains: [memory-vnext, memory-maintenance]
  paths: [cc_memory_vnext/eval/regression.jsonl, cc_memory_vnext/cards]
  symbols: [regression.jsonl]
status: active
priority: P0
severity: high
triggers:
  intents: [owner-correction, new-pitfall, memory-maintenance, memory-write]
  keywords: [纠正, 又犯, 又错, 应该是, 记一下, 踩坑, 别再犯, 反复犯, 金标准, regression, 维护记忆, 补一条]
  negative_keywords: []
  paths: [cc_memory_vnext/eval/regression.jsonl, cc_memory_vnext/cards]
  symbols: [regression.jsonl]
  error_regex: []
  examples:
    - owner 又纠正了一个我反复犯的错,怎么让以后的会话别再犯
    - 我踩了个新坑,要不要补进记忆系统的金标准
    - 这条得记下来,不然下个会话又不知道
activation:
  layer_hint: L0
  must_know: true
  session_start_l0: true
  claim_guards: [纠正我, 反复纠正, 又犯了, 又错了, 又踩了, 别再犯, 反复犯, 补进记忆, 以后的会话, 别的会话, 下个会话又]
  reason: 自喂养闭环一断,记忆系统就停止进化、退回"等查询的被动库"。
provenance:
  op: record
  reason: owner 2026-06-27 指出"未来会话不知道这个补金标准机制"的 institutionalization 缺口,补成常驻自喂养纪律卡(每会话 L0 + 纠正时 claim_guard 弹)。
  evidence:
    - "本会话 owner 提问:被纠正时补金标准的机制,当前项目每个新会话都知道要这么做吗"
    - "CLAUDE.md / Active card memory (cc_memory_vnext) 节"
updated_at: "2026-06-27"
---
当 owner 纠正我、或我发现自己踩了一个**会反复犯**的新坑时,不要只在当前会话改正就完事——那样下一个会话又不知道、又会犯。必须把它**喂回记忆系统**,让以后所有会话自动避开:

1. **补一条金标准 frame** 到 `cc_memory_vnext/eval/regression.jsonl`:从这次**真实发生**的信号(owner 的原话、踩坑的场景)构造一个 `{prompt, intents, domains, expected_cards}`,声明"遇到这种话,该出现哪张卡"。**禁止照卡片的 scope.paths/symbols 反填**(否则是规则考自己=自欺)。
2. **补/改一张卡** `cc_memory_vnext/cards/*.md`:把这条知识写成卡(或更新已有卡的触发器),让它在那种场景下能被 force-inject。
3. **跑 `python cc_memory_vnext/zmem.py build-index && zmem eval`** 确认新 frame 通过、且没把别的搞坏(25/25 这类全绿)。

这是整个主动记忆系统**自我进化的唯一闭环**:召回覆盖面靠"真实踩的坑不断补进金标准"来变宽。owner 不会去人工翻几百万字会话,所以**测量与补全要么靠这条会话内纪律、要么靠小模型评测器**——但纪律这条是每个会话当场就能做、且必须做的。断了它,记忆系统就停在今天的 15 卡不动、慢慢退化成又一个没人查的被动库。
