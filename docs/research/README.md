# `docs/research/` 历史研究与外审档案

本目录保存按日期或版本冻结的实验、证明草稿、外审输入输出、原始响应和阶段性结论。文内的“当前”“已闭”“LIVE”“GO”“最终”等词只对记录时间点成立，不能覆盖今天的机器状态或 owner 决定。

- 当前状态：[`../CURRENT.md`](../CURRENT.md)
- claim、decision 与全部一级研究包目录：[`../CATALOG.md`](../CATALOG.md)
- semantic review、availability-only review 与未审 triage：[`../BACKFILL_LEDGER.md`](../BACKFILL_LEDGER.md)
- 跨目录主题与术语：[`../TOPIC_INDEX.md`](../TOPIC_INDEX.md)、[`../TERMINOLOGY.md`](../TERMINOLOGY.md)
- 按问题进入项目：[`../START_HERE.md`](../START_HERE.md)
- 文档分区与局部前门：[`../SECTION_INDEX.md`](../SECTION_INDEX.md)
- 本机 artifact 根的边界说明：[`../../.artifacts/README.md`](../../.artifacts/README.md)

研究档案的职责是保留证据，不是追随现态改写。dossier 被登记或放入 triage 只说明它可发现且已分流，不表示内容已经做过语义审阅。要把历史观察升级为当前结论，必须给它稳定 claim ID，写明作用域、前提、直接后果、明确不推出的内容和证据，再由知识脊柱投影。

旧路径 `INDEX.md` 现为机器生成的兼容跳转；它原先只索引 2026-05-07/08 Phase 3C agent transcript。字节载荷已按真实范围重命名为 [`research_phase3c_agent_transcript_index_20260507_08.md`](../history/navigation/research_phase3c_agent_transcript_index_20260507_08.md)，不是本目录总索引。总目录由 `data/knowledge/dossiers.json` 生成到 [`../CATALOG.md`](../CATALOG.md)。

## 新 research workflow

新的 tracked research 包使用类型化入口创建，不要先裸建目录、以后再等盘点补账：

```bash
.venv/bin/python devtools/docctl.py new research-dossier \
  docs/research/<package> --title "<title>" --date YYYY-MM-DD --topic <topic>
```

任务关闭前先写 current semantic review 与必要 claim/decision，再运行 `devtools/docctl.py close-dossier` 登记 typed outcome。关闭后的正文由 dossier lifecycle 自动收紧为 immutable；更正使用 erratum、successor 或 superseding knowledge record。
