---
name: zmd-history-archaeology
description: 追溯 ZMD 旧结论、owner 原话或证据谱系时使用：先查 CATALOG/VALIDITY，再下钻 Git、档案与转录。
---

# ZMD 历史考据路由

本 skill 从历史树前门之后开始；进入 `/home/zhuran24/zmd-pj` 仍先读 `HISTORY_START.md`。历史树只提供材料与登记点，不产生今日 current、研究 authority 或认证效力。

## 检索次序

1. 先查 `docs/CATALOG.md`，再按问题读取 `docs/VALIDITY_LEDGER.md` 与 `docs/BACKFILL_LEDGER.md`。先确定稳定 ID、结论身份、有效性、successor、回填深度和证据入口。
2. 账本不能回答首次出现、措辞演变或提交边界时，再查 Git 历史。以文件历史、提交对象和 blame 坐标区分当时字节与后生转述。
3. Git 只给出索引或轻量材料时，再下钻 `.artifacts/` 的具名 dossier、manifest 与原始 payload。工件存在只证明材料存在，不自动提升其结论身份。
4. 仍需还原会话原话、操作过程或压缩前上下文时，最后进入转录档案；按 `/cc-transcript` 的 latest/history/live 规则读取，不凭摘要补写原话。

## 全称否定

“没有出现”“从未提出”“只有这一处”等承重全称否定，必须按 `docs/AGENT_OPERATIONS.md#search-negatives` 执行搜索假阴性规程：先声明搜索域与同义措辞、正式名或代码键、数值特征和可能生成路径，再用 `git grep` 穷尽全部 tracked 路径；需要覆盖未跟踪史料时另行声明范围并显式检索。关键词零命中只能作为弱证据。能写成有界正面陈述时，不写全称否定。

## 来源层判读

- 历史材料中的 `current` 只表示其记录时点的 current，不等于今日 current。
- owner 原话、同期操作化修补、后生解释和当前实现映射分层引用；解释不能倒签为早期原话，后来的实现也不能反证出生动机。
- 结论按材料当时的证据身份引用。后续复用、替代或失效以有效性账本和 successor 链为准，不因被多次转述而升级身份。
