---
id: vnext-card-lifecycle
kind: reference
title: 卡片生命周期:何时新建/就地更新/supersede/archive
summary: v-next 卡片的增改删规则。新建=出现未覆盖且写得出 trigger example 的 route-time 知识;就地更新=同知识更精确的小订正;supersede=belief 真变了(旧内容错);archive/删=不再成立。belief 变了禁静默覆盖必须声明 supersede;同 scope 两张 active 必须声明关系否则 verify fail;改完 build-index+eval 绿、新教训补金标准。
scope:
  domains: [card-lifecycle, memory-vnext-ops]
  paths: [cc_memory_vnext/cards]
  symbols: []
status: active
priority: P1
triggers:
  intents: [card-create, card-update, card-delete, card-maintenance, memory-write]
  keywords:
    - 新建卡片
    - 创建卡片
    - 加一张卡
    - 更新卡片
    - 改卡
    - 删卡
    - 删除卡片
    - supersede
    - archive
    - 卡片生命周期
    - 卡片维护
    - 什么时候建卡
    - 这条该不该建卡
  negative_keywords: []
  paths: [cc_memory_vnext/cards]
  symbols: []
  error_regex: []
  examples:
    - 这条知识该新建一张卡,还是改已有的卡?
    - 这张卡的内容现在不对了,该 supersede 还是直接改?
    - 一条记忆不再成立了,卡片怎么删/归档
    - 什么时候该建卡、什么时候更新、什么时候删
activation:
  layer_hint: L1
  must_know: false
  reason: 增改删卡片选错操作(尤其 belief 变了却静默覆盖)会让记忆悄悄漂移。
provenance:
  op: record
  reason: owner 2026-06-27 指出卡片增改删的生命周期规则没有被做成卡(只有自喂养纪律覆盖了"新建触发"),补此运维卡。
  evidence:
    - "cc_memory_vnext/zmem.py verify_cards (同 scope 冲突/域内唯一 active/pending 不入 cards 的强制)"
    - "cc_memory_vnext/cards/vnext-maintenance-discipline.md (新建触发=自喂养)"
    - "cc_memory/mem.py read cc-memory-update-vs-supersede-rule --body (旧系统同款 --force vs supersede 判据)"
updated_at: "2026-06-27"
---
v-next 卡片的增改删,按"知识到底发生了什么"选操作,别一律覆盖:

- **新建**:出现一条还没被覆盖的 route-time 可注入知识(owner 纠正 / 新坑 / 新红线 / 新当前态 / 新参考),**且写得出 ≥1 个具体 trigger example**(写不出的不进 active recall)。选对 `kind`(constraint/decision/status/pitfall/open_obligation/file_local/reference)。
- **就地更新(订正)**:同一条知识没变错、只是更精确 / 补全 / 小修(如放宽 claim_guards、改个数值)。卡片就是真相,直接编辑那个 `.md`。**订正正文时 title/summary 必须同步改**——摘要是注入层、正文不一定被读;实例:排期卡正文记了 owner 当晚修正(先深化后收口)而 title/summary 还是原拍(先收口后深化),只读摘要会得出与 owner 最终裁决**相反**的结论(2026-07-05 盘点抓到并修正)。
- **supersede(取代)**:这条知识**真的变了**——旧内容现在是错的,不是不精确。旧卡 `status: superseded`,新卡 `provenance.op: supersede` + `supersedes:[旧id]` + `reason` + `evidence`。**禁止 belief 变了却静默覆盖正文**(那是旧系统漂移的根因)。
- **archive / 删**:知识不再成立/不再相关。软删 = `status: archived`(不 active → 不注入、不进索引,git 留史);硬删 = 删掉 `.md`(git log 仍保留)。别留一张内容已死却还 `active` 的卡。

**两条 verify 硬约束**(违反就 fail,等于强制你按上面来):① 同 scope(domains+paths+symbols)两张 active 卡必须声明 `supersedes`/`contradicts`,否则冲突报错;② 同一 domain 不得有第二张 active `status` 卡。

**改完务必**:`python cc_memory_vnext/zmem.py build-index && zmem eval` 跑绿;若这是一条新坑 / 被 owner 纠正的教训,顺手补一条金标准 frame(承 `vnext-maintenance-discipline` 的自喂养闭环)。
