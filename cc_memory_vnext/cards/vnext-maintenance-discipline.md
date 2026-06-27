---
id: vnext-maintenance-discipline
kind: constraint
title: v-next 自喂养纪律:模型主动建/改/删卡(被纠正·踩新坑·发现旧卡过时)
summary: 卡片维护是【模型主动发起】的、不等 owner 开口说"改卡"(所以是 T0 常驻反射、不靠 prompt 关键词)。两类主动触发都要做:① owner 纠正我/我踩了反复犯的新坑→建卡+补金标准 frame(禁照 scope 反填);② 我干活时发现某张已有卡过时/被刚学到的推翻/与现状矛盾→主动就地改 or supersede or archive,别留 stale 卡继续误导(HOW 选操作见 vnext-card-lifecycle)。改完 zmem eval 绿。系统化巡检 stale=判官层(V2);判官上线前靠这条会话内反射兜底。断了就退回被动库。
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
  claim_guards: [纠正我, 反复纠正, 又犯了, 又错了, 又踩了, 别再犯, 反复犯, 补进记忆, 以后的会话, 别的会话, 下个会话又, 卡过时, 卡片过时, 这卡过时, 已经变了, 和现在矛盾, 之前那条不对, 旧卡, 这条记忆不对, 这卡得改]
  reason: 自喂养闭环一断,记忆系统就停止进化、退回"等查询的被动库"。
provenance:
  op: record
  reason: owner 2026-06-27 指出"未来会话不知道这个补金标准机制"的 institutionalization 缺口,补成常驻自喂养纪律卡(每会话 L0 + 纠正时 claim_guard 弹)。
  evidence:
    - "本会话 owner 提问:被纠正时补金标准的机制,当前项目每个新会话都知道要这么做吗"
    - "CLAUDE.md / Active card memory (cc_memory_vnext) 节"
updated_at: "2026-06-27"
---
**卡片维护是我(模型)要主动发起的——不会等 owner 在 prompt 里说"该改卡了"。所以这是 T0 常驻反射(每会话启动注入),不靠你提关键词触发。两类主动触发都得做:**

### 触发一:出现新知识 → 主动建卡
当 owner 纠正我、或我发现自己踩了一个**会反复犯**的新坑时,不要只在当前会话改正就完事——那样下一个会话又不知道、又会犯。必须把它**喂回记忆系统**,让以后所有会话自动避开:

1. **补一条金标准 frame** 到 `cc_memory_vnext/eval/regression.jsonl`:从这次**真实发生**的信号(owner 的原话、踩坑的场景)构造一个 `{prompt, intents, domains, expected_cards}`,声明"遇到这种话,该出现哪张卡"。**禁止照卡片的 scope.paths/symbols 反填**(否则是规则考自己=自欺)。
2. **补/改一张卡** `cc_memory_vnext/cards/*.md`:把这条知识写成卡(或更新已有卡的触发器),让它在那种场景下能被 force-inject。
3. **跑 `python cc_memory_vnext/zmem.py build-index && zmem eval`** 确认新 frame 通过、且没把别的搞坏(25/25 这类全绿)。

### 触发二:发现【已有卡】过时 → 主动改/取代/删(最容易漏的一半)
干活中只要撞见某张**已有卡/记忆**内容过时、被我刚学到的东西推翻、或与现状矛盾(就像本会话我发现 codex-team 那张卡的旧结论被实测推翻)——**不要绕过去、不要等 owner catch**。当场按 [[vnext-card-lifecycle]] 选操作:小订正→就地改;belief 真变了→supersede 并声明;不再成立→archive/删。**留一张 stale 的 active 卡比没有更糟**——它还在每回合被注入、继续误导以后的会话。这一半是模型主动审,系统化巡检版=判官层(V2),判官上线前全靠这条反射。

这是整个主动记忆系统**自我进化的唯一闭环**:召回覆盖面靠"真实踩的坑不断补进金标准"来变宽。owner 不会去人工翻几百万字会话,所以**测量与补全要么靠这条会话内纪律、要么靠小模型评测器**——但纪律这条是每个会话当场就能做、且必须做的。断了它,记忆系统就停在今天的 15 卡不动、慢慢退化成又一个没人查的被动库。
