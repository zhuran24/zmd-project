# DOC-ADR-003：legacy doc_classes 作为生成兼容投影

状态：Accepted
日期：2026-08-11

## 背景

`devtools/docs_reference_scan.py` 固定读取 `data/repository_governance/doc_classes.json`，并依赖其 `locked / historical / living` 三类语义。新的自描述文档系统需要更细的 class、mutation、authority、context 和联动规则。

继续手工维护两套分类会再次制造平行真源。直接移除旧文件又会不必要地破坏已经稳定的引用完整性扫描器。

## 决定

保留旧路径和旧 schema，但把文件改为生成投影：

- 不随目录变化的 scanner 配置放在 `legacy_doc_scan_base.json`；
- 各目录 policy 就近贡献 legacy rules 和 out-of-scope notes；
- `docctl render-legacy` 合并、去重、排序并生成 `doc_classes.json`；
- `docctl doctor` 验证输出新鲜度，并使用旧 scanner 的结构和覆盖逻辑复核投影。

旧三类只服务 legacy scanner，不授予新系统的编辑权限。

## 结果

优点：

- 旧 scanner 无需改变固定入口；
- 文档类别的维护知识与目录共置；
- `doc_classes.json` 不再是第二个手写真源；
- 迁移可以渐进进行。

代价：

- 修改 local policy 后必须重建兼容投影；
- 新 class 需要显式选择 legacy 映射；
- 在补丁尚未加入 Git index 时，旧 scanner 的 tracked-only 验证可能看不到新增文件，因此补丁应用推荐使用 `git apply --index`。

## 未采用方案

- 同时手工维护 local policy 和 `doc_classes.json`：漂移必然回归。
- 立即重写或删除旧 scanner：扩大本阶段风险面，并混入与文档自描述无关的迁移。
