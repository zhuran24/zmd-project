# `specs/ecosystem_notes/` 历史生态注记入口

本目录保存外部工具、数据源和产品表面的 inventory、词汇借用与兼容映射研究。各注记按记录时点冻结为 historical evidence；它们帮助设计 adapter 和 exporter，但不定义 ZMD 的 certified semantics，也不把外部仓库状态提升为 owner authority。

## 冻结注记

- [IndustrialPlanner frontend inventory](industrial_planner_frontend_inventory.md)
- [IndustrialPlanner blueprint contract notes](industrial_planner_blueprint_contract_notes.md)
- [endfield-calc catalog inventory](endfield_calc_catalog_inventory.md)
- [endfield-calc snapshot ingest mapping](endfield_calc_snapshot_ingest_mapping.md)
- [endfield-calc current semantic alignment](endfield_calc_current_repository_semantic_alignment.md)
- [endfield-base report notes](endfield_base_report_notes.md)
- [D.I.G.E. product-surface patterns](dige_product_surface_patterns.md)
- [Aslappyslashy modeling vocabulary](aslappyslashy_modeling_vocabulary_notes.md)
- [Exploratory layout inspirations](exploratory_layout_inspirations.md)

## 使用边界

- 外部字段或 UI 形状只能通过 adapter/export contract 进入项目。
- 任何借用都要回到 [`BORROWED_COMPONENTS.md`](../../BORROWED_COMPONENTS.md) 和 [`docs/compatibility_matrix.md`](../../docs/compatibility_matrix.md) 核对许可、方向与损失边界。
- 注记中的“current”只表示记录时点；需要今天的项目状态时读取 [`docs/CURRENT.md`](../../docs/CURRENT.md)。
- 注记正文不追随外部仓库或项目现态重写；更正通过 successor、erratum、稳定 claim 或现行规范表达。
- 发现可复用结论时写入稳定 claim 或现行规范，不把 research note 本身当作当前 authority。

返回 [规范入口](../README.md) 或 [兼容与适配分区](../../docs/SECTION_INDEX.md)。
