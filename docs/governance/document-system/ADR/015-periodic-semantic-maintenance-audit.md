# DOC-ADR-015：只读周期审计与统一修复回路

状态：Accepted
日期：2026-08-13

## 背景

事件驱动 intake 能在变化发生时阻止漏分类、漏登记和稳定身份原地改写，但它不能可靠发现渐进式陈旧、跨批次术语碰撞、历史审阅未决项积压，或已经存在却长期无人重新触发的开放问题。项目因此仍需要周期盘库。

若周期盘库再建立一份可手工关闭的 review ledger、状态 dashboard 或 authority 列表，日常写入与定期维护就会拥有两套真源。审计日期、Git 最近触达时间和 finding 也不能被误写成数学复核、owner 裁决或 claim 状态。

## 决定

1. `.docsystem/manifest.json` 只登记 maintenance audit 的配置、schema 与生成投影坐标。
2. `maintenance_audit.json` 声明 profile、check、严重度阈值和后续 action，但不复制 claim、review、triage、dossier、policy 或 owner authority 正文。
3. `devtools/document_maintenance_audit.py` 只读现有真源和 Git-visible 历史，产生可重建 finding；它没有写入命令。
4. `weekly` profile 只让机械 `error` 阻断。语义待办保持可见，但不能仅因开放问题存在就让每次提交失败。
5. `deep` 与 `phase_close` 同时阻断逾期 `warning` 和机械 `error`；`phase_close` 额外列出 active dossier、triage、未决 review、open claim 与 ephemeral 文档表面，但清单本身不授予 close。
6. `docs/MAINTENANCE_QUEUE.md` 是 `phase_close` 的确定性生成投影，禁止手工编辑。
7. Git 最近触达日期只作为复核触发器，不证明文档语义已重新审核。
8. 接受 finding 后，修复必须回到原有 `docctl intake`、knowledge ledger、policy 或 owner decision 事务；审计层不提供“关闭 finding”的平行写入口。
9. 周期审计作为统一非变异治理门的只读 lane 运行；其回归测试进入所有治理 profile。

## 后果

日常 agent 仍只加载当前路径的操作卡和事件 intake。只有周期维护、phase close 或明确查询维护欠账时才加载审计队列。仓库获得了第二种触发方式，但没有第二条写入路径：事件触发负责及时入账，周期触发负责发现遗漏，两者最终回到同一真源事务。
