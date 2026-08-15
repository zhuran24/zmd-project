# DOC-ADR-002：自治理 framework core 与最小自举

状态：Accepted
日期：2026-08-11

## 背景

如果文档机制只管理普通文档，却不管理自己的 manifest、policy、schema、resolver 和维护指南，那么框架仍依赖某个 agent 记得手工同步。这样只能维持文档内容，无法维持文档框架。

任何自描述系统又都需要一个终止递归的起点。为“维护规则的规则”无限增加上一层，只会把入口埋得更深。

## 决定

保留一个极小自举内核：

1. 固定查找 `.docsystem/manifest.json`；
2. 文档操作前调用 `docctl context`；
3. 修改 framework core 时自动进入 L2/L3；
4. manifest 或 resolver 失效时读取 `.docsystem/RECOVERY.md`。

manifest 以最终收紧层登记 framework core。局部 policy 无法解除该保护。framework core 变化必须同步说明、ADR、迁移、投影和测试。

Accepted ADR 本身由 manifest 的 `adrs` 映射完整登记。编号、稳定 ID 与路径必须一致；未登记的新 ADR 和一个路径对应多个 ID 都视为框架分叉并 fail closed。

## 结果

优点：

- agent 永远能找到完整指南；
- 框架路径不会被局部规则降级；
- 正常操作保持轻量，框架操作自动升级；
- resolver 损坏时仍有不依赖 resolver 的固定恢复路径。

代价：

- manifest 和 recovery 路径成为少量硬编码公理；
- L3 变化比普通文档变化更重；
- doctor 和定点测试必须覆盖框架自身。

## 未采用方案

- 让 `DOC_POLICY.json` 完全管理自身：待修改文件可以先给自己放宽权限。
- 只把完整指南写进 `CLAUDE.md`：长期提示词过重，而且绑定单一 agent 产品。
- 为 bootstrap 再建一套上级 bootstrap：递归不终止。
